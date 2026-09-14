"""Feature 2: find the exact same product at other retailers and compare prices.

Every free source is searched for the precise product (and its barcode, when the original
page published one). Listings with a matching GTIN are accepted outright; the rest are
checked by the AI so look-alikes and other colourways never enter the comparison.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.models import Item
from app.services.ai import ItemAnalysis, OfferCandidate, ProductAI
from app.services.sources import FoundListing, ProductSearch

MAX_CANDIDATES = 40


@dataclass
class VerifiedOffer:
    listing: FoundListing
    reason: str


async def compare_prices(item: Item, search: ProductSearch, ai: ProductAI) -> list[VerifiedOffer]:
    analysis = ItemAnalysis.model_validate(item.analysis)
    gtin = item_gtin(item)

    listings = await search.search(analysis.exact_match_query, gtin=gtin)
    candidates = _unique_priced(listings, exclude_url=item.source_url)[:MAX_CANDIDATES]

    offers: list[VerifiedOffer] = []
    to_verify: list[FoundListing] = []
    for listing in candidates:
        if gtin and listing.gtin and _same_gtin(gtin, listing.gtin):
            offers.append(VerifiedOffer(listing, "Same barcode (GTIN) as the original product."))
        else:
            to_verify.append(listing)

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
            for c in to_verify
        ],
    )
    offers += [
        VerifiedOffer(to_verify[v.index], v.reason) for v in verdicts if v.verdict == "same_product"
    ]
    return _cheapest_per_retailer(offers)


def item_gtin(item: Item) -> str | None:
    identifiers = item.identifiers or {}
    return next((v for k, v in identifiers.items() if k.startswith("gtin") and v), None)


def total(listing: FoundListing) -> Decimal:
    return (listing.price or Decimal(0)) + (listing.shipping or Decimal(0))


def _unique_priced(listings: list[FoundListing], exclude_url: str | None) -> list[FoundListing]:
    seen: set[str] = set()
    unique = []
    for listing in listings:
        if listing.price is None or listing.url == exclude_url or listing.url in seen:
            continue
        seen.add(listing.url)
        unique.append(listing)
    return unique


def _cheapest_per_retailer(offers: list[VerifiedOffer]) -> list[VerifiedOffer]:
    """One row per retailer and condition, keeping the lowest total."""
    best: dict[tuple[str, str], VerifiedOffer] = {}
    for offer in offers:
        listing = offer.listing
        # All eBay sellers count as one marketplace row per condition.
        retailer = "ebay" if listing.provider == "ebay" else (listing.retailer or listing.url)
        key = (retailer.strip().lower(), (listing.condition or "").lower())
        if key not in best or total(listing) < total(best[key].listing):
            best[key] = offer
    return sorted(best.values(), key=lambda o: total(o.listing))


def _same_gtin(a: str, b: str) -> bool:
    # UPC-A (12 digits) and EAN-13 differ only by a leading zero.
    return a.lstrip("0") == b.lstrip("0")
