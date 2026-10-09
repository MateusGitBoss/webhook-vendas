import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

caminho = Path(__file__).parent.parent / "scripts" / "simular_vendas.py"
spec = importlib.util.spec_from_file_location("simular_vendas", caminho)
assert spec and spec.loader
simulador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulador)


def test_gera_mistura_reprodutivel():
    a = simulador.gerar_envios(40, semente=7)
    b = simulador.gerar_envios(40, semente=7)
    assert a == b
    assert {p for p, _ in a} == {"hotmart", "kiwify"}
    assert len(a) >= 40


def test_simulacao_ponta_a_ponta(cliente: TestClient, monkeypatch):
    from tests.conftest import SETTINGS_TESTE

    monkeypatch.setattr(simulador, "get_settings", lambda: SETTINGS_TESTE)
    mudancas = [
        simulador.enviar(cliente, "", plataforma, payload)
        for plataforma, payload in simulador.gerar_envios(30, semente=1)
    ]
    assert mudancas.count("nova") == 30
    assert set(mudancas) <= {"nova", "sem_mudanca", "status_atualizado"}
