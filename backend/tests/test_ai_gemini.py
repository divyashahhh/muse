"""Exercise the real google-genai SDK request path against a fake HTTP transport."""

import json

import httpx
import pytest
from google import genai
from google.genai import types

from app.services.ai import OfferCandidate
from app.services.ai_gemini import GeminiProductAI
from app.services.errors import UpstreamError
from tests.conftest import ANALYSIS


def gemini_client(handler) -> genai.Client:
    return genai.Client(
        api_key="test-key",
        http_options=types.HttpOptions(
            httpx_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def model_reply(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": json.dumps(payload)}]},
                    "finishReason": "STOP",
                }
            ]
        },
    )


async def test_analyze_sends_image_system_prompt_and_schema() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return model_reply(ANALYSIS.model_dump(mode="json"))

    ai = GeminiProductAI(gemini_client(handler), "gemini-test")
    result = await ai.analyze(b"\xff\xd8fake-jpeg", page=None)

    assert result == ANALYSIS
    body = requests[0]
    parts = body["contents"][0]["parts"]
    assert parts[0]["inlineData"]["mimeType"] == "image/jpeg"
    assert "uploaded this photo" in parts[1]["text"]
    assert "You are Muse" in body["systemInstruction"]["parts"][0]["text"]
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    schema = json.dumps(config.get("responseSchema") or config.get("responseJsonSchema"))
    assert "exact_match_query" in schema and "aesthetic_queries" in schema


async def test_verify_offers_parses_verdicts_and_drops_bad_indexes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return model_reply(
            {
                "verdicts": [
                    {"index": 0, "verdict": "same_product", "reason": "Same model."},
                    {"index": 7, "verdict": "same_product", "reason": "Out of range."},
                ]
            }
        )

    ai = GeminiProductAI(gemini_client(handler), "gemini-test")
    candidate = OfferCandidate(
        title="Samba OG", retailer="Shop", price=90, currency="$", condition=None
    )
    verdicts = await ai.verify_offers(ANALYSIS, None, [candidate])
    assert [(v.index, v.verdict) for v in verdicts] == [(0, "same_product")]


async def test_quota_exhaustion_becomes_friendly_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}
            },
        )

    ai = GeminiProductAI(gemini_client(handler), "gemini-test")
    with pytest.raises(UpstreamError, match="free AI quota"):
        await ai.analyze(b"\xff\xd8", page=None)


async def test_malformed_output_becomes_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return model_reply({"not": "an analysis"})

    ai = GeminiProductAI(gemini_client(handler), "gemini-test")
    with pytest.raises(UpstreamError, match="unexpected response"):
        await ai.analyze(b"\xff\xd8", page=None)
