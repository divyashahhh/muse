import enum
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# CLIP ViT-L/14 image embeddings. Changing this requires a migration and a re-embed.
EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


class Category(enum.StrEnum):
    """Garment slots a curated outfit is assembled from."""

    TOP = "top"
    BOTTOM = "bottom"
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    FOOTWEAR = "footwear"
    BAG = "bag"
    ACCESSORY = "accessory"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Store(TimestampMixin, Base):
    """A demo retailer. Store names are illustrative, not real businesses."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(200))
    # Hex colour used to give each store a distinct identity in the UI.
    accent_color: Mapped[str] = mapped_column(String(7))

    products: Mapped[list["Product"]] = relationship(back_populates="store")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("store_id", "source_id"),
        CheckConstraint("price_cents >= 0", name="price_non_negative"),
        Index("ix_products_store_category", "store_id", "category"),
        Index(
            "ix_products_image_embedding_hnsw",
            "image_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"image_embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    # ID of the item in the licensed source dataset. The same source item may be listed by
    # several demo stores at different prices; this is ground truth for evaluating Price Radar
    # matching and must never be used by the matcher itself.
    source_id: Mapped[str] = mapped_column(String(64), index=True)

    title: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[Category] = mapped_column(
        Enum(
            Category,
            name="category",
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    subcategory: Mapped[str | None] = mapped_column(String(64))
    base_color: Mapped[str | None] = mapped_column(String(32))
    gender: Mapped[str | None] = mapped_column(String(16))
    price_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    image_url: Mapped[str] = mapped_column(Text)
    product_url: Mapped[str | None] = mapped_column(Text)
    # Free-form dataset attributes (pattern, material, season, usage, ...).
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    image_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    store: Mapped[Store] = relationship(back_populates="products")


class Inspiration(TimestampMixin, Base):
    """The item a user shows Muse, from an upload or a product URL."""

    __tablename__ = "inspirations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Object-storage key of the uploaded or fetched image.
    image_key: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(300))
    price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    aesthetic_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    image_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class Board(TimestampMixin, Base):
    """A curated collection: one inspiration, one store, a set of explained picks."""

    __tablename__ = "boards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    inspiration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspirations.id", ondelete="CASCADE")
    )
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    # Snapshot of the profile used, so a board stays reproducible if extraction changes.
    aesthetic_profile: Mapped[dict[str, Any]] = mapped_column(JSONB)

    inspiration: Mapped[Inspiration] = relationship()
    store: Mapped[Store] = relationship()
    items: Mapped[list["BoardItem"]] = relationship(
        back_populates="board", order_by="BoardItem.position", cascade="all, delete-orphan"
    )


class BoardItem(Base):
    __tablename__ = "board_items"
    __table_args__ = (UniqueConstraint("board_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    rationale: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)

    board: Mapped[Board] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
