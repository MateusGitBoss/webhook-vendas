"""Conexão com o banco via SQLAlchemy 2.0."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from vendas.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: descarta conexões que o banco já fechou (comum em nuvem)
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por requisição, sempre fechada no final."""
    fabrica = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with fabrica() as sessao:
        yield sessao
