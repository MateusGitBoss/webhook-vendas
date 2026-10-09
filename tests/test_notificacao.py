import json

import httpx
import pytest

from vendas.notificacao import NotificadorDiscord, formatar_reais


@pytest.mark.parametrize(
    ("centavos", "texto"), [(19790, "R$ 197,90"), (123456789, "R$ 1.234.567,89"), (5, "R$ 0,05")]
)
def test_formatar_reais(centavos, texto):
    assert formatar_reais(centavos) == texto


def test_envia_venda_aprovada():
    recebidos = []

    def responder(req: httpx.Request) -> httpx.Response:
        recebidos.append(json.loads(req.content))
        return httpx.Response(204)

    notificador = NotificadorDiscord(
        "https://discord.test/x", httpx.Client(transport=httpx.MockTransport(responder))
    )
    assert notificador.enviar_venda("aprovada", "Curso", 19790, "hotmart")
    assert "R$ 197,90" in recebidos[0]["embeds"][0]["description"]


def test_nao_avisa_venda_pendente():
    assert not NotificadorDiscord("https://discord.test/x").enviar_venda("pendente", "C", 1, "h")


def test_discord_fora_do_ar_nao_quebra():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert not NotificadorDiscord("https://discord.test/x", cliente).enviar_venda(
        "aprovada", "C", 1, "h"
    )
