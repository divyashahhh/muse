"""FastAPI dependencies for external services. Tests override these with fakes."""

import re
from functools import lru_cache
from typing import Annotated

import anthropic
from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.services.ai import ProductAI
from app.services.ai_claude import ClaudeProductAI
from app.services.ai_gemini import GeminiProductAI, gemini_client
from app.services.embeddings import GeminiEmbedder, VisualSimilarity
from app.services.errors import NotConfiguredError
from app.services.sources import ProductSearch, ProductSource
from app.services.sources.ebay import EbaySource
from app.services.sources.tavily import TavilySource
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
    models = [settings.gemini_model, *settings.gemini_fallback_models]
    return GeminiProductAI(gemini_client(settings.gemini_api_key), list(dict.fromkeys(models)))


@lru_cache
def get_visual_similarity() -> VisualSimilarity | None:
    """Visual ranking signal; None (text-only ranking) when no Gemini key is configured."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    embedder = GeminiEmbedder(
        gemini_client(settings.gemini_api_key),
        settings.embedding_model,
        settings.embedding_dimensions,
    )
    return VisualSimilarity(embedder)


@lru_cache
def get_search() -> ProductSearch:
    settings = get_settings()
    sources: list[ProductSource] = []
    if settings.ebay_client_id and settings.ebay_client_secret:
        sources.append(
            EbaySource(
                settings.ebay_client_id,
                settings.ebay_client_secret,
                marketplace=settings.ebay_marketplace,
            )
        )
    if settings.tavily_api_key:
        sources.append(TavilySource(settings.tavily_api_key))
    if not sources:
        raise NotConfiguredError(
            "Product search isn't configured: set TAVILY_API_KEY and/or EBAY_CLIENT_ID and "
            "EBAY_CLIENT_SECRET (both have free tiers)."
        )
    return ProductSearch(sources)


@lru_cache
def get_storage() -> ImageStorage:
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_key:
        return SupabaseImageStorage(
            settings.supabase_url, settings.supabase_service_key, settings.supabase_bucket
        )
    return LocalImageStorage(settings.media_dir, settings.public_api_url)


_CLIENT_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def get_optional_client_id(x_muse_client: Annotated[str | None, Header()] = None) -> str | None:
    """Anonymous per-browser id until accounts exist."""
    if x_muse_client is None:
        return None
    if not _CLIENT_ID.fullmatch(x_muse_client):
        raise HTTPException(status_code=400, detail="Invalid X-Muse-Client header.")
    return x_muse_client


def get_client_id(client_id: Annotated[str | None, Depends(get_optional_client_id)]) -> str:
    if client_id is None:
        raise HTTPException(status_code=400, detail="Missing X-Muse-Client header.")
    return client_id


ProductAIDep = Annotated[ProductAI, Depends(get_product_ai)]
SearchDep = Annotated[ProductSearch, Depends(get_search)]
StorageDep = Annotated[ImageStorage, Depends(get_storage)]
VisionDep = Annotated[VisualSimilarity | None, Depends(get_visual_similarity)]
ClientId = Annotated[str, Depends(get_client_id)]
OptionalClientId = Annotated[str | None, Depends(get_optional_client_id)]
