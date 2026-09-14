"""Feature 1: from one item, discover look-alikes, same-aesthetic pieces and similar brands.

A retrieve-then-rank pipeline (see docs/AI_LAYER.md):

1. Plan:     each section gets one or more AI-planned queries (query expansion).
2. Retrieve: every query runs on every source concurrently; per section, the ranked lists are
             merged with Reciprocal Rank Fusion and de-duplicated by canonical URL and title.
3. Signals:  in parallel, the AI grades each candidate's relevance (0-3) and candidate photos
             are embedded and compared with the shopper's cropped item.
4. Rank:     a weighted, calibrated score per section, relevance gates, near-duplicate
             suppression and MMR diversity pick what's shown.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from app.models import Item, ListingKind
from app.services.ai import ItemAnalysis, ListingSummary, ProductAI
from app.services.embeddings import Similarity, Vector, VisualSimilarity
from app.services.errors import UpstreamError
from app.services.matching import normalize_code
from app.services.ranking import score_section, select_diverse
from app.services.retrieval import (
    Candidate,
    canonical_url,
    reciprocal_rank_fusion,
    search_all,
    title_key,
)
from app.services.sources import FoundListing, ProductSearch

log = logging.getLogger(__name__)

MAX_PER_GROUP = 12
CANDIDATES_PER_GROUP = 20  # ranked by the full model
MAX_AESTHETIC_QUERIES = 3
MAX_SIMILAR_BRANDS = 3


@dataclass
class RankedListing:
    listing: FoundListing
    score: float
    signals: dict


@dataclass
class DiscoveredGroup:
    kind: ListingKind
    label: str
    listings: list[RankedListing]


@dataclass
class _Plan:
    kind: ListingKind
    label: str
    queries: list[str]
    section: str  # how the relevance grader sees this group


def plan_searches(analysis: ItemAnalysis) -> list[_Plan]:
    category = analysis.category
    visual = analysis.visual_query or " ".join(
        [*analysis.colors[:1], *analysis.materials[:1], category]
    )
    # A second, attribute-built phrasing of the look widens recall for the most important section.
    attribute_query = " ".join(
        [*analysis.colors[:1], *analysis.materials[:1], *analysis.key_features[:1], category]
    )
    plans = [
        _Plan(
            ListingKind.VISUAL_MATCH,
            "Looks like this",
            _unique([visual, attribute_query]),
            "Looks like this",
        )
    ]
    plans += [
        _Plan(ListingKind.AESTHETIC, a.label, [a.query], f"Same aesthetic: {a.label}")
        for a in analysis.aesthetic_queries[:MAX_AESTHETIC_QUERIES]
    ]
    plans += [
        _Plan(
            ListingKind.SIMILAR_BRAND,
            brand,
            [f"{brand} {category}"],
            f"Similar brand: {brand}",
        )
        for brand in _other_brands(analysis)[:MAX_SIMILAR_BRANDS]
    ]
    return plans


def _other_brands(analysis: ItemAnalysis) -> list[str]:
    """Similar brands, minus the item's own (models sometimes include it despite the prompt)."""
    own = normalize_code(analysis.brand or "")
    seen: set[str] = set()
    brands = []
    for brand in analysis.similar_brands:
        key = normalize_code(brand)
        if key and key not in seen and not (own and (own in key or key in own)):
            seen.add(key)
            brands.append(brand)
    return brands


async def discover(
    item: Item,
    search: ProductSearch,
    ai: ProductAI,
    vision: VisualSimilarity | None = None,
    reference: Vector | None = None,
) -> list[DiscoveredGroup]:
    started = time.monotonic()
    analysis = ItemAnalysis.model_validate(item.analysis)
    plans = plan_searches(analysis)

    results = dict(await search_all(search, [q for plan in plans for q in plan.queries]))
    retrieved = sum(len(r) for r in results.values())

    # Fuse per section; each unique product lands in the first section that found it.
    taken_urls = {canonical_url(item.source_url)} if item.source_url else set()
    taken_titles: set[tuple[str, str]] = set()
    pools: list[list[Candidate]] = []
    for plan in plans:
        fused = reciprocal_rank_fusion(
            [(q, results[q]) for q in plan.queries if q in results],
            exclude_urls={item.source_url} if item.source_url else None,
        )
        pool: list[Candidate] = []
        for candidate in fused:
            url, title = canonical_url(candidate.listing.url), title_key(candidate.listing)
            if url in taken_urls or title in taken_titles:
                continue
            taken_urls.add(url)
            taken_titles.add(title)
            pool.append(candidate)
            if len(pool) == CANDIDATES_PER_GROUP:
                break
        pools.append(pool)

    flat = [(plan_index, c) for plan_index, pool in enumerate(pools) for c in pool]
    grades, similarities = await _signals(ai, analysis, plans, flat, vision, reference)

    groups: list[DiscoveredGroup] = []
    offset = 0
    for plan, pool in zip(plans, pools, strict=True):
        span = slice(offset, offset + len(pool))
        offset += len(pool)
        scored = score_section(plan.kind, pool, grades[span], similarities[span])
        chosen = select_diverse(scored, MAX_PER_GROUP)
        if chosen:
            groups.append(
                DiscoveredGroup(
                    plan.kind,
                    plan.label,
                    [RankedListing(s.candidate.listing, s.score, s.signals) for s in chosen],
                )
            )

    log.info(
        "discover item=%s queries=%d retrieved=%d candidates=%d shown=%d visual=%s %.1fs",
        item.id,
        len(results),
        retrieved,
        len(flat),
        sum(len(g.listings) for g in groups),
        "on" if any(similarities) else "off",
        time.monotonic() - started,
    )
    return groups


async def _signals(
    ai: ProductAI,
    analysis: ItemAnalysis,
    plans: list[_Plan],
    flat: list[tuple[int, Candidate]],
    vision: VisualSimilarity | None,
    reference: Vector | None,
) -> tuple[list[int | None], list[Similarity | None]]:
    """AI relevance grades and visual similarities, computed concurrently."""

    async def visual() -> list[Similarity | None]:
        if vision is None or reference is None:
            return [None] * len(flat)
        return await vision.score(
            reference, [(c.listing.image_url, c.listing.title) for _, c in flat]
        )

    summaries = [
        ListingSummary(
            section=plans[plan_index].section,
            title=c.listing.title,
            retailer=c.listing.retailer,
            price=float(c.listing.price) if c.listing.price is not None else None,
            currency=c.listing.currency,
        )
        for plan_index, c in flat
    ]
    graded, similarities = await asyncio.gather(
        ai.grade_relevance(analysis, summaries), visual(), return_exceptions=True
    )
    if isinstance(similarities, BaseException):
        raise similarities
    if isinstance(graded, UpstreamError) and any(similarities):
        # Visual similarity alone still ranks sensibly; better than failing the whole search.
        log.warning("Relevance grading failed, ranking on visual signal: %s", graded)
        graded = {}
    elif isinstance(graded, BaseException):
        raise graded
    grades: list[int | None] = [graded.get(i) for i in range(len(flat))]
    return grades, similarities


def _unique(queries: list[str]) -> list[str]:
    return list(dict.fromkeys(" ".join(q.split()) for q in queries if q.strip()))
