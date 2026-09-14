"""Exact-product matching for price comparison: rules, evidence and the decision policy.

Entity-matching systems (e.g. the WDC Products benchmark, Peeters & Bizer's LLM matchers) split
the problem into cheap *blocking* rules that settle obvious pairs and an expensive *matcher* for
the rest. Muse follows that shape:

1. Rules settle certain cases without AI: an identical GTIN is accepted; a clearly different
   brand, or a photo that looks nothing like the item, is rejected.
2. Everything else gets evidence (image similarity, barcode relation, model number, price
   plausibility) and goes to the AI matcher, which answers attribute by attribute with a
   calibrated confidence.
3. `accept_verdict` turns that answer into a decision with a precision-first policy: a wrong
   "same product" puts a look-alike in a price comparison, which is worse than a missed offer.
"""

import re
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.ai import ItemAnalysis, OfferVerdict, VisualEvidence
from app.services.embeddings import Similarity
from app.services.sources import FoundListing

# Calibrated on gemini-embedding-2 (768-d) with real listings: two photos of the same product
# scored 0.95-0.99, look-alikes in the same category 0.70-0.87, other categories 0.56-0.60.
IMAGE_SAME_PRODUCT = 0.92
IMAGE_HIGH = 0.85
IMAGE_MODERATE = 0.75
IMAGE_REJECT_BELOW = 0.70
# Image-vs-title similarity sits on a much lower scale (0.27-0.48 in the same study).
TEXT_HIGH = 0.45
TEXT_LOW = 0.33

MIN_ACCEPT_CONFIDENCE = 0.7
# Prices this far below the reference/median are a common replica signal.
SUSPICIOUS_PRICE_RATIO = Decimal("0.4")

type RuleOutcome = Literal["accept", "reject", "ai"]


@dataclass(frozen=True)
class RuleDecision:
    outcome: RuleOutcome
    reason: str | None = None


def normalize_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def same_gtin(a: str, b: str) -> bool:
    # UPC-A (12 digits) and EAN-13 differ only by a leading zero.
    return normalize_code(a).lstrip("0") == normalize_code(b).lstrip("0")


def brand_conflict(analysis: ItemAnalysis, listing: FoundListing) -> bool:
    """True only when both brands are known and clearly different."""
    if not analysis.brand or analysis.brand_confidence == "unknown" or not listing.brand:
        return False
    ours, theirs = normalize_code(analysis.brand), normalize_code(listing.brand)
    if not ours or not theirs or ours in theirs or theirs in ours:
        return False
    # Marketplace sellers often put the real brand in the title while the brand field is wrong.
    return ours not in normalize_code(listing.title)


def model_number_in_title(analysis: ItemAnalysis, listing: FoundListing) -> bool | None:
    code = normalize_code(analysis.model_number or "")
    if len(code) < 4 or not re.search(r"\d", code):
        return None
    return code in normalize_code(listing.title)


def visual_evidence(similarity: Similarity | None) -> VisualEvidence:
    if similarity is None:
        return "unknown"
    if similarity.modality == "text":
        if similarity.cosine >= TEXT_HIGH:
            return "high"
        return "low" if similarity.cosine < TEXT_LOW else "moderate"
    if similarity.cosine >= IMAGE_SAME_PRODUCT:
        return "very_high"
    if similarity.cosine >= IMAGE_HIGH:
        return "high"
    return "moderate" if similarity.cosine >= IMAGE_MODERATE else "low"


def apply_rules(
    analysis: ItemAnalysis,
    listing: FoundListing,
    *,
    reference_gtin: str | None,
    similarity: Similarity | None,
) -> RuleDecision:
    if reference_gtin and listing.gtin and same_gtin(reference_gtin, listing.gtin):
        return RuleDecision("accept", "Same barcode (GTIN) as the original product.")
    if brand_conflict(analysis, listing):
        return RuleDecision("reject", f"Different brand ({listing.brand}).")
    if (
        similarity is not None
        and similarity.modality == "image"
        and similarity.cosine < IMAGE_REJECT_BELOW
        and not model_number_in_title(analysis, listing)
    ):
        return RuleDecision("reject", "Photo looks like a different item.")
    return RuleDecision("ai")


def price_notes(
    listings: list[FoundListing], reference_price: Decimal | None, reference_currency: str | None
) -> list[str | None]:
    """Flag implausibly cheap listings relative to the reference price (or the pool median)."""
    notes: list[str | None] = []
    for listing in listings:
        baseline = _baseline(listings, listing.currency, reference_price, reference_currency)
        if listing.price is None or baseline is None or baseline == 0:
            notes.append(None)
            continue
        ratio = listing.price / baseline
        notes.append(
            f"{round((1 - ratio) * 100)}% below the typical price; possible replica"
            if ratio < SUSPICIOUS_PRICE_RATIO
            else None
        )
    return notes


def _baseline(
    listings: list[FoundListing],
    currency: str | None,
    reference_price: Decimal | None,
    reference_currency: str | None,
) -> Decimal | None:
    if reference_price is not None and reference_currency == currency:
        return reference_price
    same_currency = [x.price for x in listings if x.price is not None and x.currency == currency]
    # A median needs a few prices to mean anything.
    return statistics.median(same_currency) if len(same_currency) >= 3 else None


def accept_verdict(verdict: OfferVerdict) -> bool:
    """Precision-first decision policy over the matcher's attribute-level answer."""
    if verdict.verdict != "same_product" or verdict.confidence < MIN_ACCEPT_CONFIDENCE:
        return False
    return "mismatch" not in (verdict.brand, verdict.model, verdict.color)
