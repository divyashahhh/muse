import os

# Must be set before the app (and its engine) is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://localhost:5432/muse_test"
)

import io  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.deps import (  # noqa: E402
    get_product_ai,
    get_search,
    get_storage,
    get_visual_similarity,
)
from app.main import app  # noqa: E402
from app.services.ai import AestheticQuery, ItemAnalysis, OfferVerdict  # noqa: E402
from app.services.embeddings import VisualSimilarity  # noqa: E402
from app.services.sources import FoundListing, ProductSearch  # noqa: E402
from app.services.storage import StoredImage  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Build the test schema through the real migrations, from scratch."""
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield
    async with SessionLocal() as session:
        await session.execute(text("TRUNCATE saved_items, listings, items RESTART IDENTITY"))
        await session.commit()


ANALYSIS = ItemAnalysis(
    category="sneakers",
    product_name="Adidas Samba OG White Black",
    brand="Adidas",
    brand_confidence="likely",
    colors=["white", "black"],
    materials=["leather", "suede"],
    style_tags=["terrace", "retro"],
    gender="unisex",
    price_tier="mid",
    summary="Low-profile leather trainers with a gum sole.",
    exact_match_query="adidas samba og white black",
    visual_query="white leather gum sole trainers",
    aesthetic_queries=[
        AestheticQuery(label="Retro track jackets", query="retro track jacket"),
        AestheticQuery(label="Straight-leg jeans", query="straight leg jeans"),
    ],
    similar_brands=["Onitsuka Tiger", "Puma"],
)


def listing(title: str, url: str, retailer: str, price: str | None, **extra) -> FoundListing:
    return FoundListing(
        title=title,
        url=url,
        provider=extra.pop("provider", "fake"),
        retailer=retailer,
        price=Decimal(price) if price else None,
        currency="$" if price else None,
        **extra,
    )


class FakeAI:
    def __init__(self) -> None:
        self.analyzed_pages: list = []
        self.filtered: list = []

    async def analyze(self, image_jpeg: bytes, page) -> ItemAnalysis:
        assert image_jpeg[:2] == b"\xff\xd8", "analysis should receive a normalised JPEG"
        self.analyzed_pages.append(page)
        return ANALYSIS

    async def grade_relevance(self, analysis, listings) -> dict[int, int]:
        self.filtered.append(listings)
        return {i: 0 if "gift card" in item.title else 2 for i, item in enumerate(listings)}

    async def verify_offers(self, analysis, page_title, candidates) -> list[OfferVerdict]:
        self.verified = candidates
        return [
            OfferVerdict(
                index=i,
                brand="match",
                model="match" if "Samba OG" in c.title else "mismatch",
                color="match",
                verdict="same_product" if "Samba OG" in c.title else "different_product",
                confidence=0.9,
                reason="Same model and colourway." if "Samba OG" in c.title else "Other model.",
            )
            for i, c in enumerate(candidates)
        ]


class FakeSource:
    """A search source returning canned listings, recording queries."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def search(self, query: str, *, gtin: str | None = None) -> list[FoundListing]:
        self.calls.append((query, gtin))
        if query == ANALYSIS.exact_match_query:
            return [
                listing("Adidas Samba OG", "https://big.example/p1", "Big Store", "110.00"),
                listing("Adidas Gazelle", "https://big.example/p2", "Big Store", "80.00"),
                listing(
                    "Adidas Samba OG",
                    "https://cheap.example/s",
                    "Cheap Shoes",
                    "89.00",
                    shipping=Decimal("5"),
                ),
                listing("Adidas Samba OG", "https://pricey.example/s", "Pricey", "120.00"),
                listing("Adidas Samba OG", "https://nopr.example/s", "No Price", None),
                listing("adidas Samba OG Shoes", "https://shop.example/samba", "Shop", "95.00"),
                listing(
                    "Retro trainers", "https://code.example/x", "Coded", "70.00", gtin="04066748"
                ),
            ]
        slug = query.replace(" ", "-")
        return [
            listing(f"{query} item", f"https://s.example/{slug}", "Store", "40.00"),
            listing(f"{query} gift card", f"https://s.example/{slug}-gift", "Store", "25.00"),
            listing(f"{query} item", f"https://s.example/{slug}?color=2", "Store", "40.00"),
        ]


class FakeStorage:
    async def save_jpeg(self, data: bytes) -> StoredImage:
        return StoredImage(key="k.jpg", url="https://cdn.example/k.jpg")

    async def read_jpeg(self, key: str) -> bytes | None:
        return None


class FakeEmbedder:
    """Deterministic embeddings: one axis per keyword, so similarity is predictable.

    Images are identified by their bytes (FakeVision serves the URL as the "image").
    """

    AXES = ("shoe", "jacket", "jeans", "gift")

    def _vector(self, text: str) -> list[float]:
        vector = [1.0 if axis in text.lower() else 0.0 for axis in self.AXES]
        return [*vector, 0.1]  # never all-zero

    async def embed_images(self, images_jpeg) -> list[list[float]]:
        return [self._vector(image.decode(errors="ignore")) for image in images_jpeg]

    async def embed_texts(self, texts) -> list[list[float]]:
        return [self._vector(text) for text in texts]


def fake_vision() -> VisualSimilarity:
    async def fetch_image(url: str) -> bytes | None:
        return url.encode()

    return VisualSimilarity(FakeEmbedder(), fetch_image=fetch_image)


@pytest.fixture
def fake_ai() -> FakeAI:
    return FakeAI()


@pytest.fixture
def fake_source() -> FakeSource:
    return FakeSource()


@pytest.fixture
async def client(fake_ai: FakeAI, fake_source: FakeSource) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_product_ai] = lambda: fake_ai
    app.dependency_overrides[get_search] = lambda: ProductSearch([fake_source])
    app.dependency_overrides[get_storage] = lambda: FakeStorage()
    # No visual signal in API tests unless a test opts in; never call a real embedding API.
    app.dependency_overrides[get_visual_similarity] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def png_bytes(size: tuple[int, int] = (64, 48), mode: str = "RGBA") -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, (200, 30, 30, 255) if mode == "RGBA" else (200, 30, 30)).save(out, "PNG")
    return out.getvalue()
