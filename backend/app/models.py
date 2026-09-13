import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def str_enum(cls: type[enum.StrEnum], name: str) -> Enum:
    """Store a StrEnum as a checked VARCHAR (no native Postgres enum to migrate)."""
    return Enum(
        cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=24,
        values_callable=lambda e: [m.value for m in e],
    )


class ItemSource(enum.StrEnum):
    UPLOAD = "upload"
    URL = "url"


class ListingKind(enum.StrEnum):
    VISUAL_MATCH = "visual_match"  # looks like the item (Google Lens)
    AESTHETIC = "aesthetic"  # different item, same style (AI-generated queries)
    SIMILAR_BRAND = "similar_brand"  # comparable brands selling this kind of item
    OFFER = "offer"  # the exact same product at another retailer (price comparison)


class SavedList(enum.StrEnum):
    BAG = "bag"
    WISHLIST = "wishlist"


class Item(Base):
    """A product the user showed Muse, plus Claude's analysis of it."""

    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[ItemSource] = mapped_column(str_enum(ItemSource, "item_source"))
    source_url: Mapped[str | None] = mapped_column(Text)
    # Our stored copy of the image (normalised JPEG), for display.
    image_key: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text)
    # An internet-reachable image URL for Google Lens; null when none is available
    # (e.g. an upload stored on local disk in development).
    search_image_url: Mapped[str | None] = mapped_column(Text)

    # Facts read from the product page, when the item came from a URL.
    title: Mapped[str | None] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(200))
    retailer: Mapped[str | None] = mapped_column(String(200))
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(8))

    # ItemAnalysis (see app/services/analysis.py), stored as JSON.
    analysis: Mapped[dict[str, Any]] = mapped_column(JSONB)

    # Set when each search last ran, so results are served from cache afterwards.
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prices_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listings: Mapped[list["Listing"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="Listing.position"
    )


class Listing(Base):
    """A real product listing found on a retailer's site for an item."""

    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("item_id", "kind", "url"),
        Index("ix_listings_item_kind", "item_id", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    kind: Mapped[ListingKind] = mapped_column(str_enum(ListingKind, "listing_kind"))
    # Sub-group within a kind, e.g. the aesthetic query or brand it was found under.
    group_label: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)

    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    retailer: Mapped[str | None] = mapped_column(String(200))
    retailer_icon: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    shipping: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    in_stock: Mapped[bool | None]
    condition: Mapped[str | None] = mapped_column(String(64))
    rating: Mapped[float | None] = mapped_column(Float)
    reviews: Mapped[int | None] = mapped_column(Integer)
    # Why Claude judged an offer to be the same product.
    match_reason: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[Item] = relationship(back_populates="listings")


class SavedItem(Base):
    """A listing the user put in their bag or wishlist.

    Listing details are snapshotted so saved items survive result refreshes. Users are
    anonymous for now, identified by a client-generated id sent in the X-Muse-Client header.
    """

    __tablename__ = "saved_items"
    __table_args__ = (UniqueConstraint("client_id", "list", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    list: Mapped[SavedList] = mapped_column(str_enum(SavedList, "saved_list"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    retailer: Mapped[str | None] = mapped_column(String(200))
    image_url: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
