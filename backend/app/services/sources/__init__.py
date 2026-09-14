"""Free product search sources, combined.

- eBay Browse API: official marketplace API (free developer account, 5,000 calls/day).
- Tavily: AI web search (free 1,000 credits/month); Muse then reads each product page's
  schema.org data itself for the real price and image.
"""

import asyncio
import logging

from app.services.errors import UpstreamError
from app.services.sources.base import FoundListing, ProductSource

log = logging.getLogger(__name__)

__all__ = ["FoundListing", "ProductSearch", "ProductSource"]


class ProductSearch:
    def __init__(self, sources: list[ProductSource]) -> None:
        self.sources = sources

    @property
    def source_names(self) -> list[str]:
        return [source.name for source in self.sources]

    async def search(
        self, query: str, *, gtin: str | None = None, only: set[str] | None = None
    ) -> list[FoundListing]:
        """Query every (or the named) source concurrently; one failing source doesn't fail all."""
        sources = [s for s in self.sources if only is None or s.name in only]
        if not sources:
            return []
        results = await asyncio.gather(
            *(source.search(query, gtin=gtin) for source in sources), return_exceptions=True
        )
        listings: list[FoundListing] = []
        failures = 0
        for source, result in zip(sources, results, strict=True):
            if isinstance(result, UpstreamError):
                log.warning("%s search %r failed: %s", source.name, query, result)
                failures += 1
            elif isinstance(result, BaseException):
                raise result
            else:
                listings.extend(result)
        if failures == len(sources):
            raise UpstreamError("Product search is unavailable right now. Please try again.")
        return listings
