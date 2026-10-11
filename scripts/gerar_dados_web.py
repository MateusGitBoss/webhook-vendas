"""Gera os casos de conferência da demonstração web (web/dados/demo.json).

A página em web/ roda no navegador, sem servidor nem banco: ela refaz em JavaScript as
regras puras deste projeto (tradução de cada plataforma, ordem dos status, máscara de dados
pessoais e assinaturas HMAC). Para garantir que a cópia não se afasta do original, este
script roda o código Python de verdade e grava as respostas; a página confere caso a caso
ao abrir e mostra o resultado.

    uv run python scripts/gerar_dados_web.py
"""

import json
from pathlib import Path

from vendas.plataformas.hotmart import AdaptadorHotmart
from vendas.plataformas.kiwify import AdaptadorKiwify
from vendas.seguranca import assinatura_hmac, hash_email
from vendas.servico import PESO_STATUS, mascarar_dados_pessoais, pode_mudar

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = RAIZ / "tests" / "fixtures"
SAIDA = RAIZ / "web" / "dados" / "demo.json"

# Segredos de mentira, só para a demonstração (a página usa os mesmos)
SEGREDO_HASH = "segredo-da-demonstracao"
TOKEN_KIWIFY = "token-kiwify-demonstracao"


def main() -> None:
    hotmart = json.loads((FIXTURES / "hotmart_compra_aprovada.json").read_text("utf-8"))
    kiwify_bytes = (FIXTURES / "kiwify_pedido_pago.json").read_bytes()
    kiwify = json.loads(kiwify_bytes)

    status = list(PESO_STATUS)
    dados = {
        "segredo_hash": SEGREDO_HASH,
        "token_kiwify": TOKEN_KIWIFY,
        "exemplos": {"hotmart": hotmart, "kiwify": kiwify},
        "conferencia": {
            "pode_mudar": [
                {"atual": a, "novo": n, "resultado": pode_mudar(a, n)}
                for a in status
                for n in status
            ],
            "normalizar": {
                "hotmart": AdaptadorHotmart("x").normalizar(hotmart).model_dump(),
                "kiwify": AdaptadorKiwify("x").normalizar(kiwify).model_dump(),
            },
            "mascarar": {
                "hotmart": mascarar_dados_pessoais(hotmart, SEGREDO_HASH),
                "kiwify": mascarar_dados_pessoais(kiwify, SEGREDO_HASH),
            },
            "hash_email": {
                "entrada": " Ana.Souza@Example.com ",
                "saida": hash_email(" Ana.Souza@Example.com ", SEGREDO_HASH),
            },
            "assinatura_kiwify": {
                "corpo": kiwify_bytes.decode("utf-8"),
                "saida": assinatura_hmac(kiwify_bytes, TOKEN_KIWIFY),
            },
        },
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"casos de conferência -> {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
