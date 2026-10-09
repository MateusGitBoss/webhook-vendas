import pytest
from pydantic import ValidationError

from vendas.plataformas.base import ErroPayload, EventoIgnorado, reais_para_centavos
from vendas.plataformas.hotmart import AdaptadorHotmart
from vendas.plataformas.kiwify import AdaptadorKiwify
from vendas.seguranca import assinatura_hmac


@pytest.mark.parametrize(
    ("valor", "centavos"), [(197.9, 19790), ("49.99", 4999), (0.1 + 0.2, 30), (1000, 100000)]
)
def test_reais_para_centavos(valor, centavos):
    assert reais_para_centavos(valor) == centavos


def test_hotmart_normaliza(payload):
    venda = AdaptadorHotmart("t").normalizar(payload("hotmart_compra_aprovada.json"))
    assert venda.id_transacao == "HP16015479281022"
    assert venda.status == "aprovada"
    assert venda.valor_centavos == 19790
    assert venda.produto == "Curso Lives que Vendem"


@pytest.mark.parametrize(
    ("evento", "status"),
    [
        ("PURCHASE_REFUNDED", "reembolsada"),
        ("PURCHASE_CHARGEBACK", "chargeback"),
        ("PURCHASE_BILLET_PRINTED", "pendente"),
    ],
)
def test_hotmart_eventos(payload, evento, status):
    dados = payload("hotmart_compra_aprovada.json") | {"event": evento}
    assert AdaptadorHotmart("t").normalizar(dados).status == status


def test_hotmart_evento_desconhecido_e_ignorado(payload):
    dados = payload("hotmart_compra_aprovada.json") | {"event": "CLUB_FIRST_ACCESS"}
    with pytest.raises(EventoIgnorado):
        AdaptadorHotmart("t").normalizar(dados)


def test_hotmart_campo_faltando(payload):
    dados = payload("hotmart_compra_aprovada.json")
    del dados["data"]["purchase"]["transaction"]
    with pytest.raises(ErroPayload, match=r"data\.purchase\.transaction"):
        AdaptadorHotmart("t").normalizar(dados)


def test_hotmart_email_invalido(payload):
    dados = payload("hotmart_compra_aprovada.json")
    dados["data"]["buyer"]["email"] = "nao-e-email"
    with pytest.raises(ValidationError):
        AdaptadorHotmart("t").normalizar(dados)


def test_hotmart_autentica_pelo_hottok():
    adaptador = AdaptadorHotmart("segredo")
    assert adaptador.autenticar(b"{}", {"x-hotmart-hottok": "segredo"}, {})
    assert not adaptador.autenticar(b"{}", {"x-hotmart-hottok": "errado"}, {})
    assert not adaptador.autenticar(b"{}", {}, {})


def test_kiwify_normaliza(payload):
    venda = AdaptadorKiwify("t").normalizar(payload("kiwify_pedido_pago.json"))
    assert venda.status == "aprovada"
    assert venda.valor_centavos == 49700
    assert venda.comprador_email == "joao@example.com"


def test_kiwify_autentica_pela_assinatura_do_corpo():
    adaptador = AdaptadorKiwify("token")
    corpo = b'{"order_id": "1"}'
    assinatura = assinatura_hmac(corpo, "token")
    assert adaptador.autenticar(corpo, {}, {"signature": assinatura})
    # Corpo alterado no caminho: a assinatura não bate mais
    assert not adaptador.autenticar(b'{"order_id": "2"}', {}, {"signature": assinatura})


def test_kiwify_sem_token_configurado_recusa_tudo():
    assert not AdaptadorKiwify("").autenticar(b"{}", {}, {"signature": "x"})
