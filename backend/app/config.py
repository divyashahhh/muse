from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost:5432/muse"
    # NoDecode: read as a plain comma-separated string rather than JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    anthropic_api_key: str = ""
    replicate_api_token: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""

    @field_validator("database_url")
    @classmethod
    def use_async_driver(cls, url: str) -> str:
        # Hosted Postgres providers hand out postgres:// URLs; SQLAlchemy needs asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url.removeprefix(prefix)
        return url

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
