import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from vendas.modelos import EventoWebhook
from vendas.seguranca import assinatura_hmac

HOTTOK = {"X-Hotmart-Hottok": "hottok-teste"}
TOKEN_API = {"Authorization": "Bearer api-token-teste"}


def _hotmart(cliente, dados, cabecalhos=HOTTOK):
    return cliente.post("/webhooks/hotmart", content=json.dumps(dados), headers=cabecalhos)


def _kiwify(cliente, dados, token="token-kiwify-teste"):
    corpo = json.dumps(dados).encode()
    return cliente.post(
        "/webhooks/kiwify",
        content=corpo,
        params={"signature": assinatura_hmac(corpo, token)},
    )


def test_saude(cliente):
    assert cliente.get("/saude").json() == {"status": "ok"}


def test_venda_nova_e_registrada_e_avisada(cliente, payload, notificador):
    resposta = _hotmart(cliente, payload("hotmart_compra_aprovada.json"))

    assert resposta.status_code == 200
    assert resposta.json()["mudanca"] == "nova"
    assert "x-request-id" in resposta.headers
    assert notificador.enviados == [("aprovada", "Curso Lives que Vendem", 19790, "hotmart")]


def test_mesmo_aviso_tres_vezes_gera_uma_venda_e_um_aviso(cliente, payload, notificador):
    respostas = [_hotmart(cliente, payload("hotmart_compra_aprovada.json")) for _ in range(3)]

    assert [r.json()["mudanca"] for r in respostas] == ["nova", "sem_mudanca", "sem_mudanca"]
    assert len({r.json()["venda_id"] for r in respostas}) == 1
    assert len(notificador.enviados) == 1


def test_reembolso_atualiza_e_avisa(cliente, payload, notificador):
    _hotmart(cliente, payload("hotmart_compra_aprovada.json"))
    reembolso = payload("hotmart_compra_aprovada.json") | {"event": "PURCHASE_REFUNDED"}
    resposta = _hotmart(cliente, reembolso)

    assert resposta.json()["mudanca"] == "status_atualizado"
    assert [e[0] for e in notificador.enviados] == ["aprovada", "reembolsada"]


def test_token_errado_e_recusado_mas_fica_registrado(cliente, payload, sessao, notificador):
    resposta = _hotmart(
        cliente, payload("hotmart_compra_aprovada.json"), {"X-Hotmart-Hottok": "falso"}
    )

    assert resposta.status_code == 401
    evento = sessao.scalars(select(EventoWebhook)).one()
    assert evento.assinatura_valida is False
    assert evento.erro == "assinatura inválida"
    assert notificador.enviados == []


def test_aviso_bruto_e_guardado_sem_dados_pessoais(cliente, payload, sessao):
    _hotmart(cliente, payload("hotmart_compra_aprovada.json"))
    evento = sessao.scalars(select(EventoWebhook)).one()

    guardado = json.dumps(evento.payload)
    assert "Ana Souza" not in guardado
    assert "Ana.Souza@Example.com" not in guardado
    assert "12345678900" not in guardado
    assert evento.processado is True


def test_kiwify_com_assinatura_valida(cliente, payload):
    resposta = _kiwify(cliente, payload("kiwify_pedido_pago.json"))
    assert resposta.status_code == 200
    assert resposta.json()["mudanca"] == "nova"


def test_kiwify_com_assinatura_de_outro_token(cliente, payload):
    resposta = _kiwify(cliente, payload("kiwify_pedido_pago.json"), token="outro")
    assert resposta.status_code == 401


def test_evento_que_nao_e_compra_responde_200_e_ignora(cliente, payload, notificador):
    dados = payload("hotmart_compra_aprovada.json") | {"event": "CLUB_FIRST_ACCESS"}
    resposta = _hotmart(cliente, dados)
    assert resposta.status_code == 200
    assert resposta.json() == {"recebido": True, "venda_id": None, "mudanca": "sem_mudanca"}
    assert notificador.enviados == []


def test_payload_quebrado_da_422(cliente, payload):
    dados = payload("hotmart_compra_aprovada.json")
    del dados["data"]["product"]
    resposta = _hotmart(cliente, dados)
    assert resposta.status_code == 422
    assert "data.product.name" in resposta.json()["detail"]


def test_corpo_que_nao_e_json_da_400(cliente):
    resposta = cliente.post("/webhooks/hotmart", content=b"<xml/>", headers=HOTTOK)
    assert resposta.status_code == 400


def test_plataforma_desconhecida_da_404(cliente):
    assert cliente.post("/webhooks/eduzz", content=b"{}").status_code == 404


def test_resumo_do_dia(cliente, payload):
    _hotmart(cliente, payload("hotmart_compra_aprovada.json"))
    _kiwify(cliente, payload("kiwify_pedido_pago.json"))
    reembolsada = payload("kiwify_pedido_pago.json") | {
        "order_id": "outro",
        "order_status": "refunded",
    }
    _kiwify(cliente, reembolsada)

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    resumo = cliente.get("/vendas/resumo", params={"dia": hoje}).json()

    assert resumo["vendas_aprovadas"] == 2
    assert resumo["faturamento_centavos"] == 19790 + 49700
    assert resumo["reembolsos"] == 1
    assert resumo["ticket_medio_centavos"] == (19790 + 49700) // 2
    assert sum(h["quantidade"] for h in resumo["por_hora"]) == 2
    assert resumo["por_produto"][0]["produto"] == "Mentoria Afiliados Pro"


def test_resumo_de_dia_sem_vendas(cliente):
    resumo = cliente.get("/vendas/resumo", params={"dia": "2020-01-01"}).json()
    assert resumo["vendas_aprovadas"] == 0 and resumo["ticket_medio_centavos"] == 0


def test_listar_vendas_exige_token(cliente, payload):
    _hotmart(cliente, payload("hotmart_compra_aprovada.json"))
    assert cliente.get("/vendas").status_code == 401
    vendas = cliente.get("/vendas", headers=TOKEN_API).json()
    assert vendas[0]["id_transacao"] == "HP16015479281022"
    assert "comprador_email_hash" not in vendas[0]


def test_consulta_status_por_email(cliente, payload):
    _hotmart(cliente, payload("hotmart_compra_aprovada.json"))
    resposta = cliente.post(
        "/vendas/consulta-status", json={"email": "ana.souza@example.com"}, headers=TOKEN_API
    )
    assert [c["status"] for c in resposta.json()] == ["aprovada"]

    vazio = cliente.post(
        "/vendas/consulta-status", json={"email": "outra@example.com"}, headers=TOKEN_API
    )
    assert vazio.json() == []
