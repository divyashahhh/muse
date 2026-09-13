import logging
from collections.abc import Sequence

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.services.ai import ProductAI
from app.services.errors import UpstreamError

log = logging.getLogger(__name__)

# Worth trying the next model: overloaded, rate-limited/quota, or transient server errors.
FALLBACK_STATUS_CODES = {429, 500, 503, 504}
REQUEST_TIMEOUT_MS = 60_000


def gemini_client(api_key: str) -> genai.Client:
    # Fail fast and fall back to another model instead of the SDK's long retry loop.
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )


class GeminiProductAI(ProductAI):
    """Google Gemini (free tier available via Google AI Studio).

    Free-tier models are often briefly overloaded, so requests fall through `models` in order.
    """

    def __init__(self, client: genai.Client, models: Sequence[str]) -> None:
        if not models:
            raise ValueError("At least one Gemini model is required.")
        self.client = client
        self.models = list(models)

    async def _generate[T: BaseModel](
        self, system: str, text: str, schema: type[T], image_jpeg: bytes | None = None
    ) -> T:
        contents: list[types.Part | str] = []
        if image_jpeg is not None:
            contents.append(types.Part.from_bytes(data=image_jpeg, mime_type="image/jpeg"))
        contents.append(text)
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        last_error: Exception | None = None
        for model in self.models:
            try:
                response = await self.client.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
            except errors.APIError as exc:
                log.warning("Gemini %s failed: %s %s", model, exc.code, exc.message)
                if exc.code in FALLBACK_STATUS_CODES:
                    last_error = exc
                    continue
                if exc.code in (400, 401, 403) and "API key" in (exc.message or ""):
                    raise UpstreamError("The AI service rejected our API key.") from exc
                raise UpstreamError("The AI service returned an error. Please try again.") from exc
            except httpx.TimeoutException as exc:
                log.warning("Gemini %s timed out", model)
                last_error = exc
                continue
            except httpx.HTTPError as exc:
                raise UpstreamError("Couldn't reach the AI service.") from exc
            return _parse(response, schema, model)

        if isinstance(last_error, errors.APIError) and last_error.code == 429:
            raise UpstreamError(
                "The free AI quota is used up for now. Please try again in a minute."
            ) from last_error
        raise UpstreamError(
            "The AI service is overloaded right now. Please try again shortly."
        ) from last_error


def _parse[T: BaseModel](response: types.GenerateContentResponse, schema: type[T], model: str) -> T:
    if isinstance(response.parsed, schema):
        return response.parsed
    try:
        return schema.model_validate_json(response.text or "")
    except ValidationError as exc:
        log.warning("Gemini %s returned unparseable output: %r", model, (response.text or "")[:500])
        raise UpstreamError("The AI service returned an unexpected response.") from exc
