"""Configuração do Alembic: usa a mesma URL e os mesmos modelos da aplicação."""

from alembic import context
from sqlalchemy import create_engine

from vendas import modelos  # noqa: F401  (registra as tabelas no Base.metadata)
from vendas.config import get_settings
from vendas.db import Base

alvo = Base.metadata


def rodar_offline() -> None:
    context.configure(url=get_settings().database_url, target_metadata=alvo, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    url = context.config.attributes.get("url") or get_settings().database_url
    with create_engine(url).connect() as conexao:
        context.configure(connection=conexao, target_metadata=alvo)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()
