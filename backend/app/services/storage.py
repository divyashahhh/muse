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
        return StoredImage(
            key=key,
            url=f"{self.project_url}/storage/v1/object/public/{self.bucket}/{key}",
        )
