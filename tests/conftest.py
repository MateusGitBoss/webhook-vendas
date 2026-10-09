import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from vendas.api import app, get_notificador
from vendas.config import Settings, get_settings
from vendas.db import get_session

RAIZ = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"

SETTINGS_TESTE = Settings(
    hotmart_hottok="hottok-teste",
    kiwify_token="token-kiwify-teste",
    hash_segredo="segredo-de-teste",
    api_token="api-token-teste",
    discord_webhook_url="",
)


@pytest.fixture
def payload():
    def _ler(nome: str) -> dict[str, Any]:
        return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))

    return _ler


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("DATABASE_URL_TESTE")
    if not url:
        pytest.skip("DATABASE_URL_TESTE não definido")
    motor = create_engine(url)
    try:
        motor.connect().close()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL indisponível: {exc}")
    yield motor
    motor.dispose()


@pytest.fixture
def sessao(engine: Engine) -> Iterator[Session]:
    """Schema recriado pelas migrações do Alembic a cada teste: testa as migrações também."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    config.attributes["url"] = engine.url.render_as_string(hide_password=False)
    command.upgrade(config, "head")
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s


class NotificadorFalso:
    def __init__(self) -> None:
        self.enviados: list[tuple[str, str, int, str]] = []

    def enviar_venda(self, status: str, produto: str, valor_centavos: int, plataforma: str) -> bool:
        self.enviados.append((status, produto, valor_centavos, plataforma))
        return True


@pytest.fixture
def notificador() -> NotificadorFalso:
    return NotificadorFalso()


@pytest.fixture
def cliente(sessao: Session, notificador: NotificadorFalso) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: sessao
    app.dependency_overrides[get_settings] = lambda: SETTINGS_TESTE
    app.dependency_overrides[get_notificador] = lambda: notificador
    yield TestClient(app)
    app.dependency_overrides.clear()
