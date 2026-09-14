"""Feature 1: from one item, discover look-alikes, same-aesthetic pieces and similar brands.

Searches every free source with AI-planned queries, then has the AI drop keyword-search
noise so each section only shows listings that actually fit.
"""

import asyncio
from dataclasses import dataclass

from app.models import Item, ListingKind
from app.services.ai import ItemAnalysis, ListingSummary, ProductAI
from app.services.errors import UpstreamError
from app.services.sources import FoundListing, ProductSearch

MAX_PER_GROUP = 12
CANDIDATES_PER_GROUP = 20  # sent to the relevance filter
MAX_AESTHETIC_QUERIES = 3
MAX_SIMILAR_BRANDS = 3


@dataclass
class DiscoveredGroup:
    kind: ListingKind
    label: str
    listings: list[FoundListing]


@dataclass
class _Plan:
    kind: ListingKind
    label: str
    query: str
    section: str  # how the relevance filter sees this group


def plan_searches(analysis: ItemAnalysis) -> list[_Plan]:
    visual = analysis.visual_query or " ".join(
        [*analysis.colors[:1], *analysis.materials[:1], analysis.category]
    )
    plans = [_Plan(ListingKind.VISUAL_MATCH, "Looks like this", visual, "Looks like this")]
    plans += [
        _Plan(ListingKind.AESTHETIC, a.label, a.query, f"Same aesthetic: {a.label}")
        for a in analysis.aesthetic_queries[:MAX_AESTHETIC_QUERIES]
    ]
    plans += [
        _Plan(
            ListingKind.SIMILAR_BRAND,
            brand,
            f"{brand} {analysis.category}",
            f"Similar brand: {brand}",
        )
        for brand in analysis.similar_brands[:MAX_SIMILAR_BRANDS]
    ]
    return plans


async def discover(item: Item, search: ProductSearch, ai: ProductAI) -> list[DiscoveredGroup]:
    analysis = ItemAnalysis.model_validate(item.analysis)
    plans = plan_searches(analysis)

    results = await asyncio.gather(
        *(search.search(plan.query) for plan in plans), return_exceptions=True
    )
    if all(isinstance(r, UpstreamError) for r in results):
        raise UpstreamError("Product search is unavailable right now. Please try again.")

    seen_urls = {item.source_url} if item.source_url else set()
    # The same product often appears under several URLs (colour or tracking parameters).
    seen_products: set[tuple[str, str]] = set()
    candidates: list[tuple[int, FoundListing]] = []
    for plan_index, result in enumerate(results):
        if isinstance(result, UpstreamError):
            continue
        if isinstance(result, BaseException):
            raise result
        taken = 0
        for listing in _interleave_by_provider(result):
            product_key = (listing.retailer or "").lower(), " ".join(listing.title.lower().split())
            if listing.url in seen_urls or product_key in seen_products:
                continue
            seen_urls.add(listing.url)
            seen_products.add(product_key)
            candidates.append((plan_index, listing))
            taken += 1
            if taken == CANDIDATES_PER_GROUP:
                break

    keep = await ai.filter_relevant(
        analysis,
        [
            ListingSummary(
                section=plans[plan_index].section,
                title=listing.title,
                retailer=listing.retailer,
                price=float(listing.price) if listing.price is not None else None,
                currency=listing.currency,
            )
            for plan_index, listing in candidates
        ],
    )

    grouped: dict[int, list[FoundListing]] = {}
    for index, (plan_index, listing) in enumerate(candidates):
        group = grouped.setdefault(plan_index, [])
        if index in keep and len(group) < MAX_PER_GROUP:
            group.append(listing)
    return [
        DiscoveredGroup(kind=plans[i].kind, label=plans[i].label, listings=listings)
        for i, listings in sorted(grouped.items())
        if listings
    ]


def _interleave_by_provider(listings: list[FoundListing]) -> list[FoundListing]:
    """Alternate sources so one marketplace doesn't crowd out retailer pages."""
    by_provider: dict[str, list[FoundListing]] = {}
    for listing in listings:
        by_provider.setdefault(listing.provider, []).append(listing)
    queues = list(by_provider.values())
    mixed: list[FoundListing] = []
    while any(queues):
        for queue in queues:
            if queue:
                mixed.append(queue.pop(0))
    return mixed
