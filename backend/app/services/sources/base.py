from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass
class FoundListing:
    """A real listing from a retailer or marketplace, normalised across sources.

    Prices always come from structured data (a marketplace API or the retailer's own
    schema.org markup), never from AI-generated text.
    """

    title: str
    url: str
    provider: str
    retailer: str | None = None
    retailer_icon: str | None = None
    image_url: str | None = None
    price: Decimal | None = None
    currency: str | None = None  # ISO 4217 code
    shipping: Decimal | None = None
    in_stock: bool | None = None
    condition: str | None = None
    rating: float | None = None
    reviews: int | None = None
    brand: str | None = None
    # Barcode-style identifier (GTIN/UPC/EAN) when the source exposes one.
    gtin: str | None = None


class ProductSource(Protocol):
    name: str

    async def search(self, query: str, *, gtin: str | None = None) -> list[FoundListing]: ...
