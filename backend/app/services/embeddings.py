"""Multimodal embeddings: the visual-similarity signal for ranking and verification.

Industry visual search (Pinterest Lens / Shop The Look, Amazon StyleSnap, Google Lens) compares
items in a learned embedding space rather than by keywords. Muse can't index a catalogue, so
it applies the same idea as a *re-ranker*: keyword search retrieves candidates, then each
candidate's image is embedded and compared with the shopper's (cropped) item.

gemini-embedding-2 maps images and text into one space, so a candidate without a usable image
can still be compared through its title (cross-modal), on a lower, separately calibrated scale.
"""

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from google import genai
from google.genai import errors, types

from app.services.errors import FetchError, InvalidImageError
from app.services.fetch import BROWSER_HEADERS, fetch
from app.services.imaging import EMBED_EDGE, normalize_image

log = logging.getLogger(__name__)

type Vector = list[float]

EMBED_BATCH_SIZE = 24
IMAGE_FETCH_CONCURRENCY = 8
MAX_CANDIDATE_IMAGE_BYTES = 4 * 1024 * 1024


class Embedder(Protocol):
    async def embed_images(self, images_jpeg: Sequence[bytes]) -> list[Vector]: ...

    async def embed_texts(self, texts: Sequence[str]) -> list[Vector]: ...


class GeminiEmbedder:
    """gemini-embedding-2 (free tier via Google AI Studio). Vectors come back normalised."""

    def __init__(self, client: genai.Client, model: str, dimensions: int) -> None:
        self.client = client
        self.model = model
        self.dimensions = dimensions

    async def embed_images(self, images_jpeg: Sequence[bytes]) -> list[Vector]:
        return await self._embed(
            [
                types.Content(parts=[types.Part.from_bytes(data=image, mime_type="image/jpeg")])
                for image in images_jpeg
            ]
        )

    async def embed_texts(self, texts: Sequence[str]) -> list[Vector]:
        return await self._embed([types.Content(parts=[types.Part(text=t)]) for t in texts])

    async def _embed(self, contents: list[types.Content]) -> list[Vector]:
        batches = [
            contents[i : i + EMBED_BATCH_SIZE] for i in range(0, len(contents), EMBED_BATCH_SIZE)
        ]
        results = await asyncio.gather(*(self._embed_batch(batch) for batch in batches))
        return [vector for batch in results for vector in batch]

    async def _embed_batch(self, contents: list[types.Content]) -> list[Vector]:
        response = await self.client.aio.models.embed_content(
            model=self.model,
            contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
        )
        vectors = [list(e.values or []) for e in response.embeddings or []]
        if len(vectors) != len(contents):
            raise EmbeddingError(f"Expected {len(contents)} embeddings, got {len(vectors)}.")
        return vectors


class EmbeddingError(Exception):
    pass


def cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return dot / norm if norm else 0.0


@dataclass(frozen=True)
class Similarity:
    """How alike a candidate is to the reference item.

    `modality` says what was compared: the candidate's image, or (fallback) its title.
    Image-image and image-text cosines live on different scales, so they're calibrated apart.
    """

    cosine: float
    modality: Literal["image", "text"]
    vector: Vector  # the candidate's embedding, reused for near-duplicate and diversity checks


type ImageFetcher = Callable[[str], Awaitable[bytes | None]]


class VisualSimilarity:
    """Scores candidate listings against a reference embedding."""

    def __init__(
        self,
        embedder: Embedder,
        *,
        fetch_image: ImageFetcher | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.embedder = embedder
        self._http = http
        self._fetch_image = fetch_image or self._download

    async def reference(self, image_jpeg: bytes) -> Vector | None:
        """Embed the shopper's item. Failures degrade ranking gracefully instead of erroring."""
        try:
            return (await self.embedder.embed_images([normalize_image(image_jpeg, EMBED_EDGE)]))[0]
        except (errors.APIError, httpx.HTTPError, EmbeddingError, InvalidImageError) as exc:
            log.warning("Reference embedding failed: %s", exc)
            return None

    async def score(
        self, reference: Vector, candidates: Sequence[tuple[str | None, str]]
    ) -> list[Similarity | None]:
        """Similarity for each (image_url, title) candidate, None where nothing could be compared.

        Candidate images are downloaded concurrently (SSRF-guarded) and embedded in batches;
        candidates whose image can't be read fall back to a title embedding.
        """
        semaphore = asyncio.Semaphore(IMAGE_FETCH_CONCURRENCY)

        async def load(url: str | None) -> bytes | None:
            if not url:
                return None
            async with semaphore:
                return await self._fetch_image(url)

        images = await asyncio.gather(*(load(url) for url, _ in candidates))
        with_image = [i for i, image in enumerate(images) if image]
        title_only = [i for i, image in enumerate(images) if not image]

        results: list[Similarity | None] = [None] * len(candidates)
        try:
            image_vectors, text_vectors = await asyncio.gather(
                self.embedder.embed_images([images[i] for i in with_image]),  # type: ignore[misc]
                self.embedder.embed_texts([candidates[i][1] for i in title_only]),
            )
        except (errors.APIError, httpx.HTTPError, EmbeddingError) as exc:
            log.warning("Candidate embedding failed; ranking without visual signal: %s", exc)
            return results
        for i, vector in zip(with_image, image_vectors, strict=True):
            results[i] = Similarity(cosine(reference, vector), "image", vector)
        for i, vector in zip(title_only, text_vectors, strict=True):
            results[i] = Similarity(cosine(reference, vector), "text", vector)
        return results

    async def _download(self, url: str) -> bytes | None:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(8.0, connect=4.0), headers=BROWSER_HEADERS
            )
        try:
            resource = await fetch(
                url, max_bytes=MAX_CANDIDATE_IMAGE_BYTES, accept="image/*", client=self._http
            )
            return normalize_image(resource.body, EMBED_EDGE, quality=85)
        except (FetchError, InvalidImageError):
            return None
