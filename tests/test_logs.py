import json
import logging

from vendas.logs import FormatadorJson


def _registro(**extra: object) -> logging.LogRecord:
    registro = logging.makeLogRecord(
        {"name": "teste", "levelname": "INFO", "msg": "venda %s", "args": ("ok",)}
    )
    for chave, valor in extra.items():
        setattr(registro, chave, valor)
    return registro


def test_formata_como_json_com_mensagem_interpolada():
    saida = json.loads(FormatadorJson().format(_registro()))
    assert saida["msg"] == "venda ok"
    assert saida["nivel"] == "INFO"
    assert "ts" in saida


def test_inclui_campos_extras():
    saida = json.loads(FormatadorJson().format(_registro(request_id="abc", plataforma="hotmart")))
    assert saida["request_id"] == "abc"
    assert saida["plataforma"] == "hotmart"
