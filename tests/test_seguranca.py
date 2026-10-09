from vendas.seguranca import assinatura_hmac, hash_email, mesmo_segredo


def test_mesmo_segredo():
    assert mesmo_segredo("abc", "abc")
    assert not mesmo_segredo("abd", "abc")
    assert not mesmo_segredo(None, "abc")
    assert not mesmo_segredo("", "")  # segredo não configurado nunca autentica


def test_assinatura_hmac_conhecida():
    # Valor de referência: HMAC-SHA1 de "corpo" com a chave "chave"
    assert assinatura_hmac(b"corpo", "chave") == "8ee5930c0f79d321adf9767941653e0b6c067043"


def test_assinatura_muda_se_o_corpo_mudar():
    assert assinatura_hmac(b'{"v": 100}', "k") != assinatura_hmac(b'{"v": 1000}', "k")


def test_hash_de_email_ignora_maiusculas_e_espacos():
    assert hash_email(" Ana@Example.com ", "s") == hash_email("ana@example.com", "s")


def test_hash_depende_do_segredo():
    assert hash_email("ana@example.com", "s1") != hash_email("ana@example.com", "s2")
