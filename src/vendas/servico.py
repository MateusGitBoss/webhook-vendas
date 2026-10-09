"""Regras de negócio: gravar a venda uma única vez e decidir quando o status muda."""

from datetime import date
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from vendas.esquemas import ResumoDia, VendaNormalizada, VendaPorHora, VendaPorProduto
from vendas.modelos import Venda
from vendas.seguranca import hash_email

Mudanca = Literal["nova", "status_atualizado", "sem_mudanca"]

# Quanto maior, mais "final" é o status. Aviso atrasado não desfaz um status final:
# se o reembolso chegar antes da aprovação (a internet não garante ordem), fica reembolsada.
PESO_STATUS = {
    "pendente": 0,
    "recusada": 1,
    "aprovada": 1,
    "reembolsada": 2,
    "cancelada": 2,
    "chargeback": 2,
}

CAMPOS_PESSOAIS = {"name", "full_name", "first_name", "last_name", "document", "cpf", "phone"}


def pode_mudar(atual: str, novo: str) -> bool:
    if atual == novo:
        return False
    if atual == "recusada" and novo == "aprovada":  # cartão recusado e depois aprovado
        return True
    return PESO_STATUS[novo] > PESO_STATUS[atual]


def registrar_venda(
    sessao: Session, plataforma: str, venda: VendaNormalizada, segredo_hash: str
) -> tuple[Venda, Mudanca]:
    """Insere ou atualiza. Seguro mesmo com dois avisos iguais chegando ao mesmo tempo."""
    # 1) Tenta inserir; se a (plataforma, id_transacao) já existe, o banco não insere nada.
    #    Checar "existe?" antes de inserir não basta: dois avisos simultâneos passariam
    #    pelo SELECT juntos e os dois inseririam. A UNIQUE no banco é que garante.
    novo_id = sessao.execute(
        insert(Venda)
        .values(
            plataforma=plataforma,
            id_transacao=venda.id_transacao,
            status=venda.status,
            produto=venda.produto,
            valor_centavos=venda.valor_centavos,
            comprador_email_hash=hash_email(venda.comprador_email, segredo_hash),
        )
        .on_conflict_do_nothing(constraint="uq_vendas_plataforma_transacao")
        .returning(Venda.id)
    ).scalar_one_or_none()

    if novo_id is not None:
        sessao.commit()
        return sessao.get_one(Venda, novo_id), "nova"

    # 2) Já existia: trava a linha (FOR UPDATE) para decidir a mudança de status sem corrida.
    existente = sessao.execute(
        select(Venda)
        .where(Venda.plataforma == plataforma, Venda.id_transacao == venda.id_transacao)
        .with_for_update()
    ).scalar_one()
    if pode_mudar(existente.status, venda.status):
        existente.status = venda.status
        sessao.commit()
        return existente, "status_atualizado"
    sessao.commit()
    return existente, "sem_mudanca"


def mascarar_dados_pessoais(payload: Any, segredo_hash: str) -> Any:
    """Remove nome/documento/telefone e troca e-mail por hash antes de guardar o aviso bruto."""
    if isinstance(payload, dict):
        limpo: dict[str, Any] = {}
        for chave, valor in payload.items():
            if chave.lower() in CAMPOS_PESSOAIS:
                limpo[chave] = "***"
            elif chave.lower() == "email" and isinstance(valor, str):
                limpo[chave] = f"hash:{hash_email(valor, segredo_hash)[:16]}"
            else:
                limpo[chave] = mascarar_dados_pessoais(valor, segredo_hash)
        return limpo
    if isinstance(payload, list):
        return [mascarar_dados_pessoais(v, segredo_hash) for v in payload]
    return payload


def resumo_do_dia(sessao: Session, dia: date, fuso: str) -> ResumoDia:
    """Agrega as vendas criadas no dia, no fuso de Brasília (não em UTC)."""
    filtro = "(criado_em AT TIME ZONE :fuso)::date = :dia"
    params = {"fuso": fuso, "dia": dia}
    totais = sessao.execute(
        text(
            f"""
            SELECT count(*) FILTER (WHERE status = 'aprovada') AS aprovadas,
                   coalesce(sum(valor_centavos) FILTER (WHERE status = 'aprovada'), 0)
                       AS faturamento,
                   count(*) FILTER (WHERE status = 'reembolsada') AS reembolsos,
                   count(*) FILTER (WHERE status = 'chargeback') AS chargebacks
              FROM vendas WHERE {filtro}
            """
        ),
        params,
    ).one()
    por_hora = sessao.execute(
        text(
            f"""
            SELECT extract(hour FROM criado_em AT TIME ZONE :fuso)::int AS hora,
                   count(*) AS quantidade, sum(valor_centavos) AS valor_centavos
              FROM vendas WHERE {filtro} AND status = 'aprovada'
             GROUP BY 1 ORDER BY 1
            """
        ),
        params,
    ).all()
    por_produto = sessao.execute(
        text(
            f"""
            SELECT produto, count(*) AS quantidade, sum(valor_centavos) AS valor_centavos
              FROM vendas WHERE {filtro} AND status = 'aprovada'
             GROUP BY produto ORDER BY 3 DESC
            """
        ),
        params,
    ).all()
    aprovadas = int(totais.aprovadas)
    faturamento = int(totais.faturamento)
    return ResumoDia(
        dia=dia.isoformat(),
        vendas_aprovadas=aprovadas,
        faturamento_centavos=faturamento,
        reembolsos=int(totais.reembolsos),
        chargebacks=int(totais.chargebacks),
        ticket_medio_centavos=faturamento // aprovadas if aprovadas else 0,
        por_hora=[VendaPorHora.model_validate(r._mapping) for r in por_hora],
        por_produto=[VendaPorProduto.model_validate(r._mapping) for r in por_produto],
    )


def compras_do_cliente(sessao: Session, email: str, segredo_hash: str) -> list[Venda]:
    return list(
        sessao.scalars(
            select(Venda)
            .where(Venda.comprador_email_hash == hash_email(email, segredo_hash))
            .order_by(Venda.atualizado_em.desc())
        )
    )
