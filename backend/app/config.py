from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost:5432/muse"
    # NoDecode: read as a plain comma-separated string rather than JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Which AI provider analyses items and verifies price matches.
    ai_provider: Literal["gemini", "claude"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # Tried in order when the primary model is overloaded or rate-limited.
    gemini_fallback_models: Annotated[list[str], NoDecode] = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"

    # Free search sources; each is enabled when its credentials are set.
    tavily_api_key: str = ""
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_marketplace: str = "EBAY_US"

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "uploads"

    public_api_url: str = "http://localhost:8000"
    # Where the web app lives; the API root redirects there (or to /docs when unset).
    frontend_url: str = ""
    media_dir: Path = Path("media")
    max_upload_bytes: int = 10 * 1024 * 1024

    @field_validator("database_url")
    @classmethod
    def use_async_driver(cls, url: str) -> str:
        # Hosted Postgres providers hand out postgres:// URLs; SQLAlchemy needs asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url.removeprefix(prefix)
        return url

    @field_validator("cors_origins", "gemini_fallback_models", mode="before")
    @classmethod
    def split_comma_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [entry.strip() for entry in value.split(",") if entry.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
