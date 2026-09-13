"""FastAPI dependencies for external services. Tests override these with fakes."""

import re
from functools import lru_cache
from typing import Annotated

import anthropic
from fastapi import Depends, Header, HTTPException
from google import genai

from app.config import get_settings
from app.services.ai import ProductAI
from app.services.ai_claude import ClaudeProductAI
from app.services.ai_gemini import GeminiProductAI
from app.services.errors import NotConfiguredError
from app.services.search import SerpApiClient
from app.services.storage import ImageStorage, LocalImageStorage, SupabaseImageStorage


@lru_cache
def get_product_ai() -> ProductAI:
    settings = get_settings()
    if settings.ai_provider == "claude":
        if not settings.anthropic_api_key:
            raise NotConfiguredError("AI analysis isn't configured: set ANTHROPIC_API_KEY.")
        return ClaudeProductAI(
            anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key), settings.claude_model
        )
    if not settings.gemini_api_key:
        raise NotConfiguredError("AI analysis isn't configured: set GEMINI_API_KEY.")
    return GeminiProductAI(genai.Client(api_key=settings.gemini_api_key), settings.gemini_model)


@lru_cache
def get_search() -> SerpApiClient:
    settings = get_settings()
    if not settings.serpapi_api_key:
        raise NotConfiguredError("Product search isn't configured: set SERPAPI_API_KEY.")
    return SerpApiClient(
        settings.serpapi_api_key, country=settings.search_country, language=settings.search_language
    )


@lru_cache
def get_storage() -> ImageStorage:
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_key:
        return SupabaseImageStorage(
            settings.supabase_url, settings.supabase_service_key, settings.supabase_bucket
        )
    return LocalImageStorage(settings.media_dir, settings.public_api_url)


_CLIENT_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def get_client_id(x_muse_client: Annotated[str | None, Header()] = None) -> str:
    """Anonymous per-browser id until accounts exist."""
    if not x_muse_client or not _CLIENT_ID.fullmatch(x_muse_client):
        raise HTTPException(status_code=400, detail="Missing or invalid X-Muse-Client header.")
    return x_muse_client


ProductAIDep = Annotated[ProductAI, Depends(get_product_ai)]
SearchDep = Annotated[SerpApiClient, Depends(get_search)]
StorageDep = Annotated[ImageStorage, Depends(get_storage)]
ClientId = Annotated[str, Depends(get_client_id)]
