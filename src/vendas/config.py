"""Configuração lida de variáveis de ambiente (ou do arquivo .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/vendas"
    hotmart_hottok: str = ""
    kiwify_token: str = ""
    hash_segredo: str = "troque-esta-chave"
    api_token: str = ""
    discord_webhook_url: str = ""
    cors_origens: str = "http://localhost:5173"
    fuso_horario: str = "America/Sao_Paulo"
    nivel_log: str = "INFO"

    @property
    def lista_cors_origens(self) -> list[str]:
        return [o.strip() for o in self.cors_origens.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
