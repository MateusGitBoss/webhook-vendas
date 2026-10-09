"""Rotas HTTP: recebimento dos webhooks e consultas."""

import json
import logging
import uuid
from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from vendas import servico
from vendas.config import Settings, get_settings
from vendas.db import get_session
from vendas.esquemas import (
    ConsultaStatus,
    RespostaWebhook,
    ResumoDia,
    StatusCompra,
    VendaPublica,
)
from vendas.logs import configurar_logs
from vendas.modelos import EventoWebhook, Venda
from vendas.notificacao import Notificador, NotificadorDiscord
from vendas.plataformas import ErroPayload, EventoIgnorado, criar_adaptador
from vendas.seguranca import mesmo_segredo

logger = logging.getLogger(__name__)
configurar_logs(get_settings().nivel_log)

app = FastAPI(
    title="webhook-vendas",
    description="Recebe avisos de venda das plataformas e expõe consultas para a equipe.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().lista_cors_origens,
    allow_methods=["GET"],
    allow_headers=["*"],
)

SessaoDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_notificador(settings: SettingsDep) -> Notificador:
    return NotificadorDiscord(settings.discord_webhook_url)


async def ler_corpo(request: Request) -> bytes:
    """O corpo cru (bytes) é necessário para conferir a assinatura HMAC byte a byte."""
    return await request.body()


def exigir_token(
    settings: SettingsDep, authorization: Annotated[str | None, Header()] = None
) -> None:
    recebido = (authorization or "").removeprefix("Bearer ").strip()
    if not mesmo_segredo(recebido, settings.api_token):
        raise HTTPException(status_code=401, detail="token inválido")


@app.middleware("http")
async def id_da_requisicao(request: Request, call_next: Any) -> Any:
    """Cada requisição ganha um id que aparece no log e na resposta: facilita rastrear."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    resposta = await call_next(request)
    resposta.headers["x-request-id"] = request_id
    logger.info(
        "requisição",
        extra={
            "request_id": request_id,
            "metodo": request.method,
            "rota": request.url.path,
            "status": resposta.status_code,
        },
    )
    return resposta


@app.get("/saude")
def saude(sessao: SessaoDep) -> dict[str, str]:
    sessao.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/webhooks/{plataforma}", response_model=RespostaWebhook)
def receber_webhook(
    plataforma: str,
    request: Request,
    tarefas: BackgroundTasks,
    sessao: SessaoDep,
    settings: SettingsDep,
    notificador: Annotated[Notificador, Depends(get_notificador)],
    corpo: Annotated[bytes, Depends(ler_corpo)],
) -> RespostaWebhook:
    adaptador = criar_adaptador(plataforma, settings)
    if adaptador is None:
        raise HTTPException(status_code=404, detail="plataforma não suportada")

    try:
        payload = json.loads(corpo)
    except ValueError:
        payload = None
    valida = adaptador.autenticar(corpo, request.headers, request.query_params)

    # 1) Guarda o aviso SEMPRE, antes de qualquer decisão: é a trilha de auditoria
    evento = EventoWebhook(
        plataforma=plataforma,
        assinatura_valida=valida,
        payload=servico.mascarar_dados_pessoais(payload, settings.hash_segredo)
        if isinstance(payload, dict)
        else {"_corpo_invalido": corpo.decode(errors="replace")[:2000]},
    )
    sessao.add(evento)
    sessao.commit()

    def falhar(codigo: int, motivo: str) -> HTTPException:
        evento.erro = motivo
        sessao.commit()
        logger.warning("webhook rejeitado", extra={"plataforma": plataforma, "motivo": motivo})
        return HTTPException(status_code=codigo, detail=motivo)

    if not valida:
        raise falhar(401, "assinatura inválida")
    if not isinstance(payload, dict):
        raise falhar(400, "corpo não é um JSON válido")

    try:
        venda_normalizada = adaptador.normalizar(payload)
    except EventoIgnorado as exc:
        # 200: se respondêssemos erro, a plataforma ficaria reenviando para sempre
        evento.processado = True
        evento.erro = f"ignorado: {exc}"
        sessao.commit()
        return RespostaWebhook(mudanca="sem_mudanca")
    except (ErroPayload, ValidationError) as exc:
        raise falhar(422, f"payload inválido: {exc}") from exc

    venda, mudanca = servico.registrar_venda(
        sessao, plataforma, venda_normalizada, settings.hash_segredo
    )
    evento.processado = True
    sessao.commit()
    logger.info(
        "venda registrada",
        extra={"plataforma": plataforma, "venda_id": venda.id, "mudanca": mudanca},
    )

    # 2) Responde rápido; o aviso no Discord roda depois da resposta (background)
    if mudanca != "sem_mudanca":
        tarefas.add_task(
            notificador.enviar_venda, venda.status, venda.produto, venda.valor_centavos, plataforma
        )
    return RespostaWebhook(venda_id=venda.id, mudanca=mudanca)


@app.get("/vendas/resumo", response_model=ResumoDia)
def resumo(sessao: SessaoDep, settings: SettingsDep, dia: date | None = None) -> ResumoDia:
    """Público: só números agregados, sem dado de cliente (o painel React usa esta rota)."""
    hoje = datetime.now(ZoneInfo(settings.fuso_horario)).date()
    return servico.resumo_do_dia(sessao, dia or hoje, settings.fuso_horario)


@app.get("/vendas", response_model=list[VendaPublica], dependencies=[Depends(exigir_token)])
def listar_vendas(
    sessao: SessaoDep, limite: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[Venda]:
    return list(sessao.scalars(select(Venda).order_by(Venda.criado_em.desc()).limit(limite)))


@app.post(
    "/vendas/consulta-status",
    response_model=list[StatusCompra],
    dependencies=[Depends(exigir_token)],
)
def consultar_status(
    consulta: ConsultaStatus, sessao: SessaoDep, settings: SettingsDep
) -> list[Venda]:
    """Usado pelo bot do Discord. E-mail vai no corpo (POST), nunca na URL, que acaba em log."""
    return servico.compras_do_cliente(sessao, consulta.email, settings.hash_segredo)
