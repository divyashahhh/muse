import logging

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.services.ai import ProductAI
from app.services.errors import UpstreamError

log = logging.getLogger(__name__)


class GeminiProductAI(ProductAI):
    """Google Gemini (free tier available via Google AI Studio)."""

    def __init__(self, client: genai.Client, model: str) -> None:
        self.client = client
        self.model = model

    async def _generate[T: BaseModel](
        self, system: str, text: str, schema: type[T], image_jpeg: bytes | None = None
    ) -> T:
        contents: list[types.Part | str] = []
        if image_jpeg is not None:
            contents.append(types.Part.from_bytes(data=image_jpeg, mime_type="image/jpeg"))
        contents.append(text)

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except errors.APIError as exc:
            log.warning("Gemini request failed: %s %s", exc.code, exc.message)
            if exc.code == 429:
                raise UpstreamError(
                    "The free AI quota is used up for now. Please try again in a minute."
                ) from exc
            if exc.code in (400, 401, 403) and "API key" in (exc.message or ""):
                raise UpstreamError("The AI service rejected our API key.") from exc
            raise UpstreamError("The AI service returned an error. Please try again.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("Couldn't reach the AI service.") from exc

        if isinstance(response.parsed, schema):
            return response.parsed
        try:
            return schema.model_validate_json(response.text or "")
        except ValidationError as exc:
            log.warning("Gemini returned unparseable output: %r", (response.text or "")[:500])
            raise UpstreamError("The AI service returned an unexpected response.") from exc
