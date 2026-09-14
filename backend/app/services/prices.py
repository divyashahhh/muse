"""Feature 2: find the exact same product at other retailers and compare prices.

An entity-matching pipeline (see docs/AI_LAYER.md and app/services/matching.py):

1. Retrieve: the exact-match query plus AI-planned alternates (and the barcode, when the
             original page published one) on every source, fused with Reciprocal Rank Fusion.
2. Evidence: candidate photos are compared with the shopper's cropped item; barcodes, model
             numbers and price plausibility are checked.
3. Rules:    certain cases are settled without AI (same GTIN accepted; different brand or a
             clearly different photo rejected).
4. Match:    the AI compares the rest attribute by attribute with a calibrated confidence;
             a precision-first policy decides what enters the comparison.
5. Present:  the cheapest verified offer per retailer and condition, by price + shipping.
"""

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal

from app.models import Item
from app.services.ai import ItemAnalysis, OfferCandidate, ProductAI
from app.services.embeddings import Similarity, Vector, VisualSimilarity
from app.services.matching import (
    accept_verdict,
    apply_rules,
    model_number_in_title,
    price_notes,
    same_gtin,
    visual_evidence,
)
from app.services.retrieval import reciprocal_rank_fusion, search_all
from app.services.sources import FoundListing, ProductSearch

log = logging.getLogger(__name__)

MAX_CANDIDATES = 40
MAX_ALTERNATE_QUERIES = 1


@dataclass
class VerifiedOffer:
    listing: FoundListing
    reason: str
    confidence: float = 1.0
    signals: dict = field(default_factory=dict)


async def compare_prices(
    item: Item,
    search: ProductSearch,
    ai: ProductAI,
    vision: VisualSimilarity | None = None,
    reference: Vector | None = None,
) -> list[VerifiedOffer]:
    started = time.monotonic()
    analysis = ItemAnalysis.model_validate(item.analysis)
    gtin = item_gtin(item)

    queries = [analysis.exact_match_query, *analysis.alternate_queries[:MAX_ALTERNATE_QUERIES]]
    ranked_lists = await search_all(search, queries, gtin=gtin)
    fused = reciprocal_rank_fusion(
        ranked_lists, exclude_urls={item.source_url} if item.source_url else None
    )
    candidates = [c for c in fused if c.listing.price is not None][:MAX_CANDIDATES]
    listings = [c.listing for c in candidates]

    similarities: list[Similarity | None] = [None] * len(listings)
    if vision is not None and reference is not None and listings:
        similarities = await vision.score(reference, [(x.image_url, x.title) for x in listings])

    offers: list[VerifiedOffer] = []
    to_verify: list[tuple[FoundListing, OfferCandidate, dict]] = []
    rejected = 0
    notes = price_notes(listings, item.price, item.currency)
    for listing, similarity, note, candidate in zip(
        listings, similarities, notes, candidates, strict=True
    ):
        signals = {
            "visual_cosine": round(similarity.cosine, 4) if similarity else None,
            "visual_modality": similarity.modality if similarity else None,
            "rrf": round(candidate.rrf, 5),
        }
        rule = apply_rules(analysis, listing, reference_gtin=gtin, similarity=similarity)
        if rule.outcome == "accept":
            offers.append(
                VerifiedOffer(listing, rule.reason or "", 1.0, {**signals, "rule": "gtin"})
            )
            continue
        if rule.outcome == "reject":
            rejected += 1
            continue
        evidence = OfferCandidate(
            title=listing.title,
            retailer=listing.retailer,
            price=float(listing.price) if listing.price is not None else None,
            currency=listing.currency,
            condition=listing.condition,
            brand=listing.brand,
            image_similarity=visual_evidence(similarity),
            barcode=_barcode_relation(gtin, listing.gtin),
            model_number_in_title=model_number_in_title(analysis, listing),
            price_note=note,
        )
        to_verify.append((listing, evidence, signals))

    verdicts = await ai.verify_offers(
        analysis, page_title=item.title, candidates=[evidence for _, evidence, _ in to_verify]
    )
    for verdict in verdicts:
        listing, _, signals = to_verify[verdict.index]
        if accept_verdict(verdict):
            offers.append(
                VerifiedOffer(
                    listing,
                    verdict.reason,
                    verdict.confidence,
                    {
                        **signals,
                        "confidence": verdict.confidence,
                        "attributes": {
                            "brand": verdict.brand,
                            "model": verdict.model,
                            "color": verdict.color,
                        },
                    },
                )
            )

    result = _cheapest_per_retailer(offers)
    log.info(
        "prices item=%s queries=%d candidates=%d rule_rejected=%d ai_checked=%d accepted=%d "
        "shown=%d %.1fs",
        item.id,
        len(ranked_lists),
        len(listings),
        rejected,
        len(to_verify),
        len(offers),
        len(result),
        time.monotonic() - started,
    )
    return result


def item_gtin(item: Item) -> str | None:
    identifiers = item.identifiers or {}
    return next((v for k, v in identifiers.items() if k.startswith("gtin") and v), None)


def total(listing: FoundListing) -> Decimal:
    return (listing.price or Decimal(0)) + (listing.shipping or Decimal(0))


def _barcode_relation(reference: str | None, candidate: str | None):
    if not reference or not candidate:
        return "unknown"
    return "same" if same_gtin(reference, candidate) else "different"


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
