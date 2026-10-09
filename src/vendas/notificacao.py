"""Avisos de venda para a equipe num canal do Discord."""

import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

TITULOS = {
    "aprovada": "Nova venda aprovada",
    "reembolsada": "Venda reembolsada",
    "chargeback": "Chargeback recebido",
    "cancelada": "Venda cancelada",
    "recusada": "Pagamento recusado",
    "pendente": "Venda aguardando pagamento",
}
CORES = {"aprovada": 0x2E7D32, "reembolsada": 0xF9A825, "chargeback": 0xC62828}


def formatar_reais(centavos: int) -> str:
    """19790 -> 'R$ 197,90' (padrão brasileiro: ponto no milhar, vírgula nos centavos)."""
    texto = f"{centavos / 100:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


class Notificador(Protocol):
    def enviar_venda(
        self, status: str, produto: str, valor_centavos: int, plataforma: str
    ) -> bool: ...


class NotificadorDiscord:
    # Só incomoda a equipe com o que importa
    STATUS_AVISADOS = frozenset({"aprovada", "reembolsada", "chargeback", "cancelada"})

    def __init__(self, webhook_url: str, cliente: httpx.Client | None = None) -> None:
        self._url = webhook_url
        self._cliente = cliente or httpx.Client(timeout=10)

    def enviar_venda(self, status: str, produto: str, valor_centavos: int, plataforma: str) -> bool:
        if status not in self.STATUS_AVISADOS:
            return False
        if not self._url:
            logger.info("Discord não configurado; aviso só no log", extra={"status": status})
            return False
        mensagem = {
            "username": "webhook-vendas",
            "embeds": [
                {
                    "title": TITULOS[status],
                    "description": f"**{produto}**\n{formatar_reais(valor_centavos)}",
                    "color": CORES.get(status, 0x546E7A),
                    "footer": {"text": plataforma},
                }
            ],
        }
        try:
            self._cliente.post(self._url, json=mensagem).raise_for_status()
            return True
        except httpx.HTTPError:
            logger.exception("falha ao avisar no Discord")
            return False
