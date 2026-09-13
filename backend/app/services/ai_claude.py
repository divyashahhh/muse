import base64

import anthropic
from pydantic import BaseModel

from app.services.ai import ProductAI
from app.services.errors import UpstreamError


class ClaudeProductAI(ProductAI):
    """Anthropic Claude (paid API)."""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        self.client = client
        self.model = model

    async def _generate[T: BaseModel](
        self, system: str, text: str, schema: type[T], image_jpeg: bytes | None = None
    ) -> T:
        content: list[dict] = []
        if image_jpeg is not None:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.standard_b64encode(image_jpeg).decode(),
                    },
                }
            )
        content.append({"type": "text", "text": text})

        try:
            response = await self.client.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_format=schema,
                # User-facing request: medium effort keeps latency reasonable.
                output_config={"effort": "medium"},
            )
        except anthropic.AuthenticationError as exc:
            raise UpstreamError("The AI service rejected our credentials.") from exc
        except anthropic.RateLimitError as exc:
            raise UpstreamError("The AI service is busy. Please try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise UpstreamError("The AI service returned an error. Please try again.") from exc
        except anthropic.APIConnectionError as exc:
            raise UpstreamError("Couldn't reach the AI service.") from exc

        if response.stop_reason == "refusal":
            raise UpstreamError("The AI service declined to analyse this image.")
        if response.parsed_output is None:
            raise UpstreamError("The AI service returned an unexpected response.")
        return response.parsed_output
