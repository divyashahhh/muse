import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.models import ItemSource, ListingKind
from app.services.ai import ItemAnalysis


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthOut(BaseModel):
    status: str
    database: str


class ItemFromUrlIn(BaseModel):
    url: AnyHttpUrl


class ItemOut(ORMModel):
    id: uuid.UUID
    source: ItemSource
    source_url: str | None
    image_url: str
    title: str | None
    brand: str | None
    retailer: str | None
    price: float | None
    currency: str | None
    analysis: ItemAnalysis
    created_at: datetime


class RecentItemOut(ORMModel):
    id: uuid.UUID
    source: ItemSource
    image_url: str
    title: str | None
    brand: str | None
    retailer: str | None
    price: float | None
    currency: str | None
    product_name: str
    category: str
    created_at: datetime
    discovered_at: datetime | None
    prices_checked_at: datetime | None


class ListingOut(ORMModel):
    id: int
    kind: ListingKind
    group_label: str | None
    title: str
    url: str
    retailer: str | None
    retailer_icon: str | None
    image_url: str | None
    price: float | None
    currency: str | None
    shipping: float | None
    in_stock: bool | None
    condition: str | None
    rating: float | None
    reviews: int | None
    match_reason: str | None


class DiscoverSection(BaseModel):
    kind: ListingKind
    label: str
    listings: list[ListingOut]


class DiscoverOut(BaseModel):
    item_id: uuid.UUID
    searched_at: datetime
    sections: list[DiscoverSection]


class ReferencePrice(BaseModel):
    retailer: str | None
    url: str
    price: float
    currency: str | None


class PriceComparisonOut(BaseModel):
    item_id: uuid.UUID
    checked_at: datetime
    # The price on the link the user pasted, if any.
    reference: ReferencePrice | None
    # Verified same-product offers, cheapest (price + shipping) first.
    offers: list[ListingOut]


class SavedItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    url: AnyHttpUrl
    retailer: str | None = Field(default=None, max_length=200)
    image_url: AnyHttpUrl | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    item_id: uuid.UUID | None = None


class SavedItemOut(ORMModel):
    id: int
    item_id: uuid.UUID | None
    title: str
    url: str
    retailer: str | None
    image_url: str | None
    price: float | None
    currency: str | None
    created_at: datetime
