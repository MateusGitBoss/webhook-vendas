"""Dispara avisos de venda assinados contra a API, como as plataformas fariam.

Uso:
    uv run python scripts/simular_vendas.py --url http://localhost:8000 --quantidade 30

Envia vendas aprovadas da Hotmart e da Kiwify, alguns avisos repetidos (para provar a
idempotência) e alguns reembolsos. Lê HOTMART_HOTTOK e KIWIFY_TOKEN do ambiente/.env.
"""

import argparse
import json
import random
import uuid
from collections import Counter
from typing import Any

import httpx

from vendas.config import get_settings
from vendas.seguranca import assinatura_hmac

PRODUTOS = [
    ("Curso Lives que Vendem", 19790),
    ("Mentoria Afiliados Pro", 49700),
    ("E-book Roteiros para Reels", 4790),
    ("Comunidade Criadores VIP", 9700),
]


def evento_hotmart(
    transacao: str, evento: str, produto: str, centavos: int, cliente: int = 1, evento_id: str = ""
) -> dict[str, Any]:
    return {
        "id": evento_id or str(uuid.uuid4()),
        "event": evento,
        "version": "2.0.0",
        "data": {
            "product": {"id": 1, "name": produto},
            "buyer": {"email": f"cliente{cliente}@example.com", "name": "Cliente"},
            "purchase": {
                "transaction": transacao,
                "price": {"value": centavos / 100, "currency_value": "BRL"},
            },
        },
    }


def evento_kiwify(
    pedido: str, status: str, produto: str, centavos: int, cliente: int = 1
) -> dict[str, Any]:
    return {
        "order_id": pedido,
        "order_status": status,
        "Product": {"product_id": "p1", "product_name": produto},
        "Customer": {"email": f"cliente{cliente}@example.com", "full_name": "C"},
        "Commissions": {"charge_amount": centavos, "currency": "BRL"},
    }


def gerar_envios(quantidade: int, semente: int | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Lista de (plataforma, payload) com vendas, repetições e reembolsos misturados."""
    aleatorio = random.Random(semente)
    envios: list[tuple[str, dict[str, Any]]] = []
    for i in range(quantidade):
        produto, centavos = aleatorio.choice(PRODUTOS)
        cliente = aleatorio.randint(1, 500)
        if aleatorio.random() < 0.5:
            transacao = f"HP{1000000 + i}"
            evento_id = str(uuid.UUID(int=aleatorio.getrandbits(128)))
            aprovado = evento_hotmart(
                transacao, "PURCHASE_APPROVED", produto, centavos, cliente, evento_id
            )
            envios.append(("hotmart", aprovado))
            if aleatorio.random() < 0.2:  # plataforma reenviou o mesmo aviso
                envios.append(("hotmart", aprovado))
            if aleatorio.random() < 0.1:
                envios.append(("hotmart", {**aprovado, "event": "PURCHASE_REFUNDED"}))
        else:
            pedido = f"KW-{uuid.UUID(int=aleatorio.getrandbits(128))}"
            pago = evento_kiwify(pedido, "paid", produto, centavos, cliente)
            envios.append(("kiwify", pago))
            if aleatorio.random() < 0.2:
                envios.append(("kiwify", pago))
            if aleatorio.random() < 0.1:
                envios.append(("kiwify", {**pago, "order_status": "refunded"}))
    return envios


def enviar(cliente: httpx.Client, url: str, plataforma: str, payload: dict[str, Any]) -> str:
    settings = get_settings()
    corpo = json.dumps(payload).encode()
    if plataforma == "hotmart":
        resposta = cliente.post(
            f"{url}/webhooks/hotmart",
            content=corpo,
            headers={"X-Hotmart-Hottok": settings.hotmart_hottok},
        )
    else:
        resposta = cliente.post(
            f"{url}/webhooks/kiwify",
            content=corpo,
            params={"signature": assinatura_hmac(corpo, settings.kiwify_token)},
        )
    resposta.raise_for_status()
    return str(resposta.json()["mudanca"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--quantidade", type=int, default=20)
    parser.add_argument("--semente", type=int, default=None)
    args = parser.parse_args()

    resultados: Counter[str] = Counter()
    with httpx.Client(timeout=15) as cliente:
        for plataforma, payload in gerar_envios(args.quantidade, args.semente):
            resultados[enviar(cliente, args.url.rstrip("/"), plataforma, payload)] += 1
    print(dict(resultados))


if __name__ == "__main__":
    main()
