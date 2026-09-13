"""Feature 1: from one item, discover similar items, same-aesthetic pieces and similar brands."""

import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import dataclass

from app.models import Item, ListingKind
from app.services.ai import ItemAnalysis
from app.services.errors import UpstreamError
from app.services.search import FoundListing, SerpApiClient

log = logging.getLogger(__name__)

MAX_PER_GROUP = 12
MAX_AESTHETIC_QUERIES = 3
MAX_SIMILAR_BRANDS = 3


@dataclass
class DiscoveredGroup:
    kind: ListingKind
    label: str
    listings: list[FoundListing]


async def discover(item: Item, search: SerpApiClient) -> list[DiscoveredGroup]:
    analysis = ItemAnalysis.model_validate(item.analysis)

    planned: list[tuple[ListingKind, str, Awaitable[list[FoundListing]]]] = []
    if item.search_image_url:
        planned.append(
            (
                ListingKind.VISUAL_MATCH,
                "Looks like this",
                search.lens(item.search_image_url, "products"),
            )
        )
    for aesthetic in analysis.aesthetic_queries[:MAX_AESTHETIC_QUERIES]:
        planned.append((ListingKind.AESTHETIC, aesthetic.label, search.shopping(aesthetic.query)))
    for brand in analysis.similar_brands[:MAX_SIMILAR_BRANDS]:
        planned.append(
            (ListingKind.SIMILAR_BRAND, brand, search.shopping(f"{brand} {analysis.category}"))
        )

    results = await asyncio.gather(*(call for _, _, call in planned), return_exceptions=True)

    groups: list[DiscoveredGroup] = []
    seen_urls = {item.source_url} if item.source_url else set()
    failures = 0
    for (kind, label, _), result in zip(planned, results, strict=True):
        if isinstance(result, BaseException):
            if not isinstance(result, UpstreamError):
                raise result
            log.warning("Discovery search %r failed: %s", label, result)
            failures += 1
            continue
        listings = []
        for listing in result:
            if listing.url in seen_urls:
                continue
            seen_urls.add(listing.url)
            listings.append(listing)
            if len(listings) == MAX_PER_GROUP:
                break
        if listings:
            groups.append(DiscoveredGroup(kind=kind, label=label, listings=listings))

    if planned and failures == len(planned):
        raise UpstreamError("Product search is unavailable right now. Please try again.")
    return groups
