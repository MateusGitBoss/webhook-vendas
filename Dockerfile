FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
# Dependências primeiro: a camada fica em cache enquanto só o código muda
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY README.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY scripts/iniciar.sh ./scripts/iniciar.sh
RUN uv sync --locked --no-dev

RUN useradd --create-home app
USER app

EXPOSE 8000
# Railway e outras plataformas informam a porta pela variável PORT
CMD ["sh", "scripts/iniciar.sh"]
