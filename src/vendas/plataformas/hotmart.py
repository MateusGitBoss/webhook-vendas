"""Hotmart (webhook versão 2.0, formato simplificado da documentação pública).

Autenticação: a Hotmart envia o "hottok" da conta no cabeçalho X-HOTMART-HOTTOK.
"""

from collections.abc import Mapping
from typing import Any

from vendas.esquemas import StatusVenda, VendaNormalizada
from vendas.plataformas.base import ErroPayload, EventoIgnorado, pegar, reais_para_centavos
from vendas.seguranca import mesmo_segredo

EVENTOS: dict[str, StatusVenda] = {
    "PURCHASE_BILLET_PRINTED": "pendente",
    "PURCHASE_DELAYED": "pendente",
    "PURCHASE_APPROVED": "aprovada",
    "PURCHASE_COMPLETE": "aprovada",
    "PURCHASE_REFUNDED": "reembolsada",
    "PURCHASE_CANCELED": "cancelada",
    "PURCHASE_EXPIRED": "cancelada",
    "PURCHASE_CHARGEBACK": "chargeback",
}


class AdaptadorHotmart:
    nome = "hotmart"

    def __init__(self, hottok: str) -> None:
        self._hottok = hottok

    def autenticar(
        self, corpo: bytes, cabecalhos: Mapping[str, str], parametros: Mapping[str, str]
    ) -> bool:
        return mesmo_segredo(cabecalhos.get("x-hotmart-hottok"), self._hottok)

    def normalizar(self, payload: dict[str, Any]) -> VendaNormalizada:
        evento = pegar(payload, "event")
        if evento not in EVENTOS:
            raise EventoIgnorado(f"evento {evento} não é de compra")
        moeda = pegar(payload, "data", "purchase", "price").get("currency_value", "BRL")
        if moeda != "BRL":
            raise ErroPayload(f"moeda não suportada: {moeda}")
        return VendaNormalizada(
            id_transacao=pegar(payload, "data", "purchase", "transaction"),
            status=EVENTOS[evento],
            produto=pegar(payload, "data", "product", "name"),
            valor_centavos=reais_para_centavos(
                pegar(payload, "data", "purchase", "price", "value")
            ),
            comprador_email=pegar(payload, "data", "buyer", "email"),
        )
