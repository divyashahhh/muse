import uuid
from datetime import UTC, datetime
from itertools import count

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Session
from app.deps import ProductAIDep, SearchDep, StorageDep
from app.models import Item, Listing, ListingKind
from app.schemas import (
    DiscoverOut,
    DiscoverSection,
    ItemFromUrlIn,
    ItemOut,
    ListingOut,
    PriceComparisonOut,
    ReferencePrice,
)
from app.services import discover as discover_service
from app.services import ingest
from app.services import prices as prices_service
from app.services.errors import InvalidImageError
from app.services.search import FoundListing

router = APIRouter(prefix="/items", tags=["items"])

DISCOVER_KINDS = (ListingKind.VISUAL_MATCH, ListingKind.AESTHETIC, ListingKind.SIMILAR_BRAND)


@router.post("/upload", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_from_upload(
    file: UploadFile, session: Session, storage: StorageDep, ai: ProductAIDep
) -> ItemOut:
    data = await file.read(get_settings().max_upload_bytes + 1)
    if len(data) > get_settings().max_upload_bytes:
        raise InvalidImageError("Images must be 10 MB or smaller.")
    item = await ingest.item_from_upload(data, storage, ai)
    session.add(item)
    await session.commit()
    return item_out(item)


@router.post("/from-url", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_from_url(
    body: ItemFromUrlIn, session: Session, storage: StorageDep, ai: ProductAIDep
) -> ItemOut:
    item = await ingest.item_from_url(str(body.url), storage, ai)
    session.add(item)
    await session.commit()
    return item_out(item)


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: uuid.UUID, session: Session) -> ItemOut:
    return item_out(await _get_item(session, item_id))


@router.post("/{item_id}/discover", response_model=DiscoverOut)
async def discover(
    item_id: uuid.UUID, session: Session, search: SearchDep, refresh: bool = False
) -> DiscoverOut:
    """Run discovery searches, or return the cached results from a previous run."""
    item = await _get_item(session, item_id, lock=True)
    if item.discovered_at is None or refresh:
        groups = await discover_service.discover(item, search)
        await session.execute(
            delete(Listing).where(Listing.item_id == item.id, Listing.kind.in_(DISCOVER_KINDS))
        )
        position = count()
        for group in groups:
            for found in group.listings:
                session.add(_listing(item, group.kind, group.label, next(position), found))
        item.discovered_at = datetime.now(UTC)
        await session.commit()

    listings = await _listings(session, item.id, DISCOVER_KINDS)
    sections: dict[tuple[ListingKind, str], DiscoverSection] = {}
    for listing in listings:
        key = (listing.kind, listing.group_label or "")
        if key not in sections:
            sections[key] = DiscoverSection(kind=listing.kind, label=key[1], listings=[])
        sections[key].listings.append(ListingOut.model_validate(listing))
    return DiscoverOut(
        item_id=item.id, searched_at=item.discovered_at, sections=list(sections.values())
    )


@router.post("/{item_id}/prices", response_model=PriceComparisonOut)
async def compare_prices(
    item_id: uuid.UUID, session: Session, search: SearchDep, ai: ProductAIDep, refresh: bool = False
) -> PriceComparisonOut:
    """Find the same product at other retailers, or return the cached comparison."""
    item = await _get_item(session, item_id, lock=True)
    if item.prices_checked_at is None or refresh:
        offers = await prices_service.compare_prices(item, search, ai)
        await session.execute(
            delete(Listing).where(Listing.item_id == item.id, Listing.kind == ListingKind.OFFER)
        )
        for position, offer in enumerate(offers):
            listing = _listing(item, ListingKind.OFFER, None, position, offer.listing)
            listing.match_reason = offer.reason
            session.add(listing)
        item.prices_checked_at = datetime.now(UTC)
        await session.commit()

    offers = sorted(
        await _listings(session, item.id, (ListingKind.OFFER,)),
        key=lambda o: (o.price or 0) + (o.shipping or 0),
    )
    reference = (
        ReferencePrice(
            retailer=item.retailer,
            url=item.source_url,
            price=float(item.price),
            currency=item.currency,
        )
        if item.source_url and item.price is not None
        else None
    )
    return PriceComparisonOut(
        item_id=item.id,
        checked_at=item.prices_checked_at,
        reference=reference,
        offers=[ListingOut.model_validate(o) for o in offers],
    )


def item_out(item: Item) -> ItemOut:
    return ItemOut.model_validate(
        {
            **{c: getattr(item, c) for c in ItemOut.model_fields if hasattr(item, c)},
            "visual_search_available": item.search_image_url is not None,
        }
    )


async def _get_item(session: AsyncSession, item_id: uuid.UUID, lock: bool = False) -> Item:
    query = select(Item).where(Item.id == item_id)
    if lock:
        # Serialise concurrent searches for one item so a double-click doesn't pay twice.
        query = query.with_for_update()
    item = await session.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return item


async def _listings(
    session: AsyncSession, item_id: uuid.UUID, kinds: tuple[ListingKind, ...]
) -> list[Listing]:
    result = await session.scalars(
        select(Listing)
        .where(Listing.item_id == item_id, Listing.kind.in_(kinds))
        .order_by(Listing.position)
    )
    return list(result)


def _listing(
    item: Item, kind: ListingKind, label: str | None, position: int, found: FoundListing
) -> Listing:
    return Listing(
        item_id=item.id,
        kind=kind,
        group_label=label,
        position=position,
        title=found.title[:2000],
        url=found.url,
        retailer=found.retailer and found.retailer[:200],
        retailer_icon=found.retailer_icon,
        image_url=found.image_url,
        price=found.price,
        currency=found.currency,
        shipping=found.shipping,
        in_stock=found.in_stock,
        condition=found.condition,
        rating=found.rating,
        reviews=found.reviews,
        provider=found.provider,
    )
