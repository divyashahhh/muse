"""Candidate retrieval: multi-query search, URL canonicalisation and rank fusion.

Muse issues several queries per intent (query expansion) across several sources (eBay,
the open web). Each (query, source) pair returns its own ranked list; Reciprocal Rank
Fusion (Cormack et al., SIGIR 2009) merges them without needing comparable scores:

    rrf(d) = sum over lists L containing d of 1 / (k + rank_L(d))

Listings that several queries and sources agree on rise; a single source's long tail
can't crowd everything else out. k=60 is the standard default.
"""

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.errors import UpstreamError
from app.services.sources import FoundListing, ProductSearch

RRF_K = 60

# Query parameters that track clicks or campaigns rather than identify a product.
TRACKING_PARAMS = re.compile(
    r"^(utm_.*|gclid|gbraid|wbraid|fbclid|msclkid|mc_[a-z]+|ref|ref_|referrer|source|"
    r"campaign|affiliate|aff_?id|clickid|irclickid|srsltid|_ga|_gl|hash|trk|trkid|mkevt|"
    r"mkcid|mkrid|campid|toolid|customid|siteid|epid|_trkparms|_trksid|amdata|var|hsh)$",
    re.IGNORECASE,
)


def canonical_url(url: str) -> str:
    """A stable identity for a listing URL: lower-cased host, no www, fragment or tracking."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not TRACKING_PARAMS.match(k)
    ]
    path = parts.path.rstrip("/") or "/"
    # eBay item URLs carry the item id in the path; everything else is presentation.
    if host.endswith("ebay.com") and (match := re.search(r"/itm/(?:[^/]+/)?(\d+)", path)):
        return f"ebay.com/itm/{match.group(1)}"
    return urlunsplit(("", host, path, urlencode(sorted(query)), "")).lstrip("/")


def title_key(listing: FoundListing) -> tuple[str, str]:
    """Same retailer + same normalised title: one product under several URLs (e.g. colour links)."""
    title = re.sub(r"[^a-z0-9]+", " ", listing.title.lower()).strip()
    return (listing.retailer or "").strip().lower(), title


@dataclass
class Candidate:
    """A unique listing with its fused retrieval evidence."""

    listing: FoundListing
    rrf: float = 0.0
    # Which (query, provider) lists found it and at what 1-based rank.
    hits: list[tuple[str, str, int]] = field(default_factory=list)


def reciprocal_rank_fusion(
    ranked_lists: Sequence[tuple[str, Sequence[FoundListing]]],
    *,
    exclude_urls: set[str] | None = None,
    k: int = RRF_K,
) -> list[Candidate]:
    """Fuse ranked lists keyed by query into unique candidates, best fused score first.

    Each query's results are split by provider first, because sources are ranked
    independently (eBay's rank 1 and the web's rank 1 are both "best").
    """
    excluded = {canonical_url(u) for u in exclude_urls or ()}
    by_url: dict[str, Candidate] = {}
    by_title: dict[tuple[str, str], Candidate] = {}
    for query, listings in ranked_lists:
        per_provider: dict[str, list[FoundListing]] = {}
        for listing in listings:
            per_provider.setdefault(listing.provider, []).append(listing)
        for provider, provider_listings in per_provider.items():
            for rank, listing in enumerate(provider_listings, start=1):
                url_key = canonical_url(listing.url)
                if url_key in excluded:
                    continue
                candidate = by_url.get(url_key) or by_title.get(title_key(listing))
                if candidate is None:
                    candidate = Candidate(listing)
                    by_title[title_key(listing)] = candidate
                by_url[url_key] = candidate
                # A list contributes once per candidate, at its best rank.
                if any(q == query and p == provider for q, p, _ in candidate.hits):
                    continue
                candidate.rrf += 1 / (k + rank)
                candidate.hits.append((query, provider, rank))
    unique = {id(c): c for c in by_url.values()}.values()
    return sorted(unique, key=lambda c: c.rrf, reverse=True)


async def search_all(
    search: ProductSearch, queries: Sequence[str], *, gtin: str | None = None
) -> list[tuple[str, list[FoundListing]]]:
    """Run queries concurrently. Individual failures are skipped; all failing is an error."""
    unique_queries = list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))
    results = await asyncio.gather(
        *(search.search(q, gtin=gtin) for q in unique_queries), return_exceptions=True
    )
    ranked: list[tuple[str, list[FoundListing]]] = []
    for query, result in zip(unique_queries, results, strict=True):
        if isinstance(result, UpstreamError):
            continue
        if isinstance(result, BaseException):
            raise result
        ranked.append((query, result))
    if unique_queries and not ranked:
        raise UpstreamError("Product search is unavailable right now. Please try again.")
    return ranked
