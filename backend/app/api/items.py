import uuid
from datetime import UTC, datetime
from itertools import count

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Session
from app.deps import (
    ClientId,
    OptionalClientId,
    ProductAIDep,
    SearchDep,
    StorageDep,
    VisionDep,
)
from app.models import Item, Listing, ListingKind
from app.schemas import (
    DiscoverOut,
    DiscoverSection,
    ItemFromUrlIn,
    ItemOut,
    ListingOut,
    PriceComparisonOut,
    RecentItemOut,
    ReferencePrice,
)
from app.services import discover as discover_service
from app.services import ingest
from app.services import prices as prices_service
from app.services.ai import ItemAnalysis
from app.services.embeddings import Vector, VisualSimilarity
from app.services.errors import InvalidImageError
from app.services.sources import FoundListing
from app.services.storage import ImageStorage

router = APIRouter(prefix="/items", tags=["items"])

DISCOVER_KINDS = (ListingKind.VISUAL_MATCH, ListingKind.AESTHETIC, ListingKind.SIMILAR_BRAND)


@router.post("/upload", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_from_upload(
    file: UploadFile,
    session: Session,
    storage: StorageDep,
    ai: ProductAIDep,
    vision: VisionDep,
    client_id: OptionalClientId,
) -> ItemOut:
    data = await file.read(get_settings().max_upload_bytes + 1)
    if len(data) > get_settings().max_upload_bytes:
        raise InvalidImageError("Images must be 10 MB or smaller.")
    item = await ingest.item_from_upload(data, storage, ai, vision)
    item.client_id = client_id
    session.add(item)
    await session.commit()
    return item_out(item)


@router.post("/from-url", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_from_url(
    body: ItemFromUrlIn,
    session: Session,
    storage: StorageDep,
    ai: ProductAIDep,
    vision: VisionDep,
    client_id: OptionalClientId,
) -> ItemOut:
    item = await ingest.item_from_url(str(body.url), storage, ai, vision)
    item.client_id = client_id
    session.add(item)
    await session.commit()
    return item_out(item)


@router.get("/recent", response_model=list[RecentItemOut])
async def recent_items(
    session: Session, client_id: ClientId, limit: int = 60
) -> list[RecentItemOut]:
    """Items this browser searched, newest first."""
    items = await session.scalars(
        select(Item)
        .where(Item.client_id == client_id)
        .order_by(Item.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    return [
        RecentItemOut.model_validate(
            {
                **{f: getattr(item, f) for f in RecentItemOut.model_fields if hasattr(item, f)},
                "product_name": item.analysis.get("product_name", ""),
                "category": item.analysis.get("category", ""),
            }
        )
        for item in items
    ]


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_recent(item_id: uuid.UUID, session: Session, client_id: ClientId) -> Response:
    """Remove an item from this browser's Recents (and its cached results)."""
    item = await _get_item(session, item_id)
    if item.client_id != client_id:
        raise HTTPException(status_code=404, detail="Item not found.")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: uuid.UUID, session: Session) -> ItemOut:
    return item_out(await _get_item(session, item_id))


@router.post("/{item_id}/discover", response_model=DiscoverOut)
async def discover(
    item_id: uuid.UUID,
    session: Session,
    search: SearchDep,
    ai: ProductAIDep,
    vision: VisionDep,
    storage: StorageDep,
    refresh: bool = False,
) -> DiscoverOut:
    """Run discovery searches, or return the cached results from a previous run."""
    item = await _get_item(session, item_id, lock=True)
    if item.discovered_at is None or refresh:
        reference = await _reference(item, vision, storage)
        groups = await discover_service.discover(item, search, ai, vision, reference)
        await session.execute(
            delete(Listing).where(Listing.item_id == item.id, Listing.kind.in_(DISCOVER_KINDS))
        )
        position = count()
        for group in groups:
            for ranked in group.listings:
                listing = _listing(item, group.kind, group.label, next(position), ranked.listing)
                listing.score = ranked.score
                listing.signals = ranked.signals
                session.add(listing)
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
    item_id: uuid.UUID,
    session: Session,
    search: SearchDep,
    ai: ProductAIDep,
    vision: VisionDep,
    storage: StorageDep,
    refresh: bool = False,
) -> PriceComparisonOut:
    """Find the same product at other retailers, or return the cached comparison."""
    item = await _get_item(session, item_id, lock=True)
    if item.prices_checked_at is None or refresh:
        reference = await _reference(item, vision, storage)
        offers = await prices_service.compare_prices(item, search, ai, vision, reference)
        await session.execute(
            delete(Listing).where(Listing.item_id == item.id, Listing.kind == ListingKind.OFFER)
        )
        for position, offer in enumerate(offers):
            listing = _listing(item, ListingKind.OFFER, None, position, offer.listing)
            listing.match_reason = offer.reason
            listing.score = offer.confidence
            listing.signals = offer.signals
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


async def _reference(
    item: Item, vision: VisualSimilarity | None, storage: ImageStorage
) -> Vector | None:
    """The item's reference embedding, computed now for items created before embeddings."""
    if vision is None or item.image_embedding is not None:
        return item.image_embedding
    image = await storage.read_jpeg(item.image_key)
    if image is None:
        return None
    analysis = ItemAnalysis.model_validate(item.analysis)
    item.image_embedding = await ingest.reference_embedding(image, analysis, vision)
    return item.image_embedding


def item_out(item: Item) -> ItemOut:
    return ItemOut.model_validate(item)


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
