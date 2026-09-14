import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx

from app.services.errors import UpstreamError


@dataclass(frozen=True)
class StoredImage:
    key: str
    url: str


class ImageStorage(Protocol):
    async def save_jpeg(self, data: bytes) -> StoredImage: ...

    async def read_jpeg(self, key: str) -> bytes | None: ...


def new_key() -> str:
    return f"{datetime.now(UTC):%Y/%m/%d}/{uuid.uuid4().hex}.jpg"


class LocalImageStorage:
    """Development storage: files on disk, served by the API under /media."""

    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/")

    async def save_jpeg(self, data: bytes) -> StoredImage:
        key = new_key()
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredImage(key=key, url=f"{self.public_base_url}/media/{key}")

    async def read_jpeg(self, key: str) -> bytes | None:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            return None
        return path.read_bytes()


class SupabaseImageStorage:
    """Supabase Storage, for deployments without a persistent disk. The bucket must be public."""

    def __init__(self, project_url: str, service_key: str, bucket: str) -> None:
        self.project_url = project_url.rstrip("/")
        self.service_key = service_key
        self.bucket = bucket

    async def save_jpeg(self, data: bytes) -> StoredImage:
        key = new_key()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.project_url}/storage/v1/object/{self.bucket}/{key}",
                content=data,
                headers={
                    "Authorization": f"Bearer {self.service_key}",
                    "apikey": self.service_key,
                    "Content-Type": "image/jpeg",
                },
            )
        if response.is_error:
            raise UpstreamError("Couldn't store the image. Please try again.")
        return StoredImage(key=key, url=self._public_url(key))

    async def read_jpeg(self, key: str) -> bytes | None:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(self._public_url(key))
            except httpx.HTTPError:
                return None
        return response.content if response.is_success else None

    def _public_url(self, key: str) -> str:
        return f"{self.project_url}/storage/v1/object/public/{self.bucket}/{key}"
