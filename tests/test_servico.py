import pytest

from vendas.esquemas import VendaNormalizada
from vendas.servico import mascarar_dados_pessoais, pode_mudar, registrar_venda


def _venda(status="aprovada", transacao="T1") -> VendaNormalizada:
    return VendaNormalizada(
        id_transacao=transacao,
        status=status,
        produto="Curso",
        valor_centavos=10000,
        comprador_email="ana@example.com",
    )


@pytest.mark.parametrize(
    ("atual", "novo", "esperado"),
    [
        ("pendente", "aprovada", True),
        ("aprovada", "reembolsada", True),
        ("reembolsada", "aprovada", False),  # aviso atrasado não desfaz reembolso
        ("aprovada", "aprovada", False),
        ("recusada", "aprovada", True),
        ("aprovada", "pendente", False),
    ],
)
def test_regra_de_mudanca_de_status(atual, novo, esperado):
    assert pode_mudar(atual, novo) is esperado


def test_mascarar_dados_pessoais():
    dados = {
        "buyer": {"email": "Ana@x.com", "name": "Ana", "document": "123"},
        "itens": [{"full_name": "B"}],
        "valor": 10,
    }
    limpo = mascarar_dados_pessoais(dados, "s")
    assert limpo["buyer"]["name"] == "***"
    assert limpo["buyer"]["document"] == "***"
    assert limpo["buyer"]["email"].startswith("hash:")
    assert "Ana@x.com" not in str(limpo)
    assert limpo["itens"][0]["full_name"] == "***"
    assert limpo["valor"] == 10


def test_registrar_e_idempotente(sessao):
    venda1, m1 = registrar_venda(sessao, "hotmart", _venda(), "s")
    venda2, m2 = registrar_venda(sessao, "hotmart", _venda(), "s")
    assert (m1, m2) == ("nova", "sem_mudanca")
    assert venda1.id == venda2.id


def test_mesma_transacao_em_plataformas_diferentes_sao_vendas_diferentes(sessao):
    a, _ = registrar_venda(sessao, "hotmart", _venda(), "s")
    b, _ = registrar_venda(sessao, "kiwify", _venda(), "s")
    assert a.id != b.id


def test_reembolso_atualiza_e_aprovacao_atrasada_nao_desfaz(sessao):
    registrar_venda(sessao, "hotmart", _venda("aprovada"), "s")
    venda, mudanca = registrar_venda(sessao, "hotmart", _venda("reembolsada"), "s")
    assert (venda.status, mudanca) == ("reembolsada", "status_atualizado")

    venda, mudanca = registrar_venda(sessao, "hotmart", _venda("aprovada"), "s")
    assert (venda.status, mudanca) == ("reembolsada", "sem_mudanca")


def test_email_nao_e_gravado_em_texto(sessao):
    venda, _ = registrar_venda(sessao, "hotmart", _venda(), "s")
    assert "@" not in venda.comprador_email_hash
    assert len(venda.comprador_email_hash) == 64
