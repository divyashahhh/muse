"""Feature 2: find the exact same product at other retailers and compare prices.

Candidates come from three places: Google Lens exact image matches, a Google Shopping
search for the precise product name, and the store list Google has grouped under the best
Shopping result. Claude then verifies each candidate really is the same product, so
look-alikes never pollute the comparison.
"""

import asyncio
import logging
from dataclasses import dataclass

from app.models import Item
from app.services.ai import ItemAnalysis, OfferCandidate, ProductAI
from app.services.errors import UpstreamError
from app.services.search import FoundListing, SerpApiClient

log = logging.getLogger(__name__)

SHOPPING_RESULTS_TO_CHECK = 6
PRODUCTS_TO_EXPAND = 2  # top Shopping results whose full store lists we fetch
MAX_CANDIDATES = 40


@dataclass
class VerifiedOffer:
    listing: FoundListing
    reason: str


async def compare_prices(item: Item, search: SerpApiClient, ai: ProductAI) -> list[VerifiedOffer]:
    analysis = ItemAnalysis.model_validate(item.analysis)

    lens_call = (
        search.lens(item.search_image_url, "exact_matches") if item.search_image_url else _empty()
    )
    lens_results, shopping_results = await asyncio.gather(
        lens_call, search.shopping(analysis.exact_match_query), return_exceptions=True
    )
    if isinstance(lens_results, BaseException) and isinstance(shopping_results, BaseException):
        raise UpstreamError("Price search is unavailable right now. Please try again.")
    lens_results = _or_empty(lens_results, "lens exact matches")
    shopping_results = _or_empty(shopping_results, "shopping")[:SHOPPING_RESULTS_TO_CHECK]

    tokens = [r.offers_token for r in shopping_results if r.offers_token][:PRODUCTS_TO_EXPAND]
    store_lists = await asyncio.gather(
        *(_tolerant(search.product_offers(token), "product offers") for token in tokens)
    )

    candidates = _dedupe(
        [*(offer for stores in store_lists for offer in stores), *lens_results, *shopping_results],
        exclude_url=item.source_url,
    )[:MAX_CANDIDATES]
    if not candidates:
        return []

    verdicts = await ai.verify_offers(
        analysis,
        page_title=item.title,
        candidates=[
            OfferCandidate(
                title=c.title,
                retailer=c.retailer,
                price=float(c.price) if c.price is not None else None,
                currency=c.currency,
                condition=c.condition,
            )
            for c in candidates
        ],
    )
    return [
        VerifiedOffer(listing=candidates[v.index], reason=v.reason)
        for v in verdicts
        if v.verdict == "same_product"
    ]


def _dedupe(listings: list[FoundListing], exclude_url: str | None) -> list[FoundListing]:
    """Keep priced listings, one per retailer (the cheapest), skipping the user's own link."""
    best: dict[str, FoundListing] = {}
    for listing in listings:
        if listing.price is None or listing.url == exclude_url:
            continue
        key = (listing.retailer or listing.url).strip().lower()
        current = best.get(key)
        if current is None or _total(listing) < _total(current):
            best[key] = listing
    return sorted(best.values(), key=_total)


def _total(listing: FoundListing):
    return (listing.price or 0) + (listing.shipping or 0)


def _or_empty(result: list[FoundListing] | BaseException, label: str) -> list[FoundListing]:
    if isinstance(result, UpstreamError):
        log.warning("Price search (%s) failed: %s", label, result)
        return []
    if isinstance(result, BaseException):
        raise result
    return result


async def _tolerant(call, label: str) -> list[FoundListing]:
    try:
        return await call
    except UpstreamError as exc:
        log.warning("Price search (%s) failed: %s", label, exc)
        return []


async def _empty() -> list[FoundListing]:
    return []
