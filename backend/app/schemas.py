from pydantic import BaseModel, ConfigDict

from app.models import Category


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthOut(BaseModel):
    status: str
    database: str


class StoreOut(ORMModel):
    id: int
    slug: str
    name: str
    tagline: str
    accent_color: str
    product_count: int


class ProductOut(ORMModel):
    id: int
    store_id: int
    title: str
    brand: str | None
    category: Category
    subcategory: str | None
    base_color: str | None
    price_cents: int
    currency: str
    image_url: str
    product_url: str | None


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int
