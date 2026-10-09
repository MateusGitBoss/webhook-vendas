"""Contrato dos adaptadores: cada plataforma tem seu formato, o resto do sistema só vê um."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Protocol

from vendas.esquemas import VendaNormalizada


class ErroPayload(ValueError):
    """O aviso chegou num formato que não entendemos."""


class EventoIgnorado(Exception):  # sinal de fluxo, não um erro
    """Evento válido que não nos interessa (ex.: carrinho abandonado). Responde 200 e ignora."""


class Adaptador(Protocol):
    nome: str

    def autenticar(
        self, corpo: bytes, cabecalhos: Mapping[str, str], parametros: Mapping[str, str]
    ) -> bool: ...

    def normalizar(self, payload: dict[str, Any]) -> VendaNormalizada: ...


def pegar(dados: Any, *caminho: str) -> Any:
    """Lê dados["a"]["b"]["c"] sem estourar KeyError no meio do caminho."""
    atual = dados
    for chave in caminho:
        if not isinstance(atual, dict) or chave not in atual:
            raise ErroPayload(f"campo obrigatório ausente: {'.'.join(caminho)}")
        atual = atual[chave]
    return atual


def reais_para_centavos(valor: Any) -> int:
    """197.9 -> 19790. Passa por Decimal(str()) para não herdar erro de float."""
    try:
        return int((Decimal(str(valor)) * 100).quantize(Decimal("1")))
    except Exception as exc:
        raise ErroPayload(f"valor inválido: {valor!r}") from exc
