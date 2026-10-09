#!/bin/sh
# Aplica migrações pendentes e sobe a API. Falha cedo se o banco não estiver acessível.
set -e
alembic upgrade head
exec uvicorn vendas.api:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
