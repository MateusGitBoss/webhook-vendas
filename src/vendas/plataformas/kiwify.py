"""Kiwify (formato simplificado da documentação pública).

Autenticação: a Kiwify manda ?signature=<HMAC-SHA1 do corpo usando o token da conta>.
Diferente da Hotmart, o segredo nunca trafega: só a assinatura.
"""

from collections.abc import Mapping
from typing import Any

from vendas.esquemas import StatusVenda, VendaNormalizada
from vendas.plataformas.base import ErroPayload, EventoIgnorado, pegar
from vendas.seguranca import assinatura_hmac, mesmo_segredo

STATUS: dict[str, StatusVenda] = {
    "waiting_payment": "pendente",
    "refused": "recusada",
    "paid": "aprovada",
    "approved": "aprovada",
    "refunded": "reembolsada",
    "canceled": "cancelada",
    "chargedback": "chargeback",
}


class AdaptadorKiwify:
    nome = "kiwify"

    def __init__(self, token: str) -> None:
        self._token = token

    def autenticar(
        self, corpo: bytes, cabecalhos: Mapping[str, str], parametros: Mapping[str, str]
    ) -> bool:
        if not self._token:
            return False
        return mesmo_segredo(parametros.get("signature"), assinatura_hmac(corpo, self._token))

    def normalizar(self, payload: dict[str, Any]) -> VendaNormalizada:
        status = pegar(payload, "order_status")
        if status not in STATUS:
            raise EventoIgnorado(f"status {status} não é de compra")
        valor = pegar(payload, "Commissions", "charge_amount")
        try:
            centavos = int(valor)  # Kiwify já manda em centavos
        except (TypeError, ValueError) as exc:
            raise ErroPayload(f"valor inválido: {valor!r}") from exc
        return VendaNormalizada(
            id_transacao=pegar(payload, "order_id"),
            status=STATUS[status],
            produto=pegar(payload, "Product", "product_name"),
            valor_centavos=centavos,
            comprador_email=pegar(payload, "Customer", "email"),
        )
