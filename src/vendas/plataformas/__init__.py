"""Registro das plataformas suportadas. Nova plataforma = novo adaptador + uma linha aqui."""

from vendas.config import Settings
from vendas.plataformas.base import Adaptador, ErroPayload, EventoIgnorado
from vendas.plataformas.hotmart import AdaptadorHotmart
from vendas.plataformas.kiwify import AdaptadorKiwify


def criar_adaptador(nome: str, settings: Settings) -> Adaptador | None:
    adaptadores: dict[str, Adaptador] = {
        "hotmart": AdaptadorHotmart(settings.hotmart_hottok),
        "kiwify": AdaptadorKiwify(settings.kiwify_token),
    }
    return adaptadores.get(nome)


__all__ = ["Adaptador", "ErroPayload", "EventoIgnorado", "criar_adaptador"]
