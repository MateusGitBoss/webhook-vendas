"""Autenticidade dos webhooks e proteção de dados pessoais."""

import hashlib
import hmac


def mesmo_segredo(recebido: str | None, esperado: str) -> bool:
    """Compara em tempo constante.

    `==` para no primeiro caractere diferente: medindo o tempo da resposta, um atacante
    descobre o token caractere por caractere. `compare_digest` sempre leva o mesmo tempo.
    """
    if not recebido or not esperado:
        return False
    return hmac.compare_digest(recebido.encode(), esperado.encode())


def assinatura_hmac(corpo: bytes, segredo: str, algoritmo: str = "sha1") -> str:
    """Assinatura HMAC do corpo: só quem conhece o segredo consegue gerar o mesmo valor."""
    return hmac.new(segredo.encode(), corpo, algoritmo).hexdigest()


def hash_email(email: str, segredo: str) -> str:
    """Guarda o e-mail embaralhado (LGPD): dá para buscar compras de alguém sem guardar o e-mail.

    HMAC com segredo (e não SHA-256 puro) impede descobrir o e-mail testando uma lista
    de e-mails conhecidos.
    """
    normalizado = email.strip().lower()
    return hmac.new(segredo.encode(), normalizado.encode(), hashlib.sha256).hexdigest()
