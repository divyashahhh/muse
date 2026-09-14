"""Tavily web search -> retailer product pages -> schema.org product data.

Tavily finds candidate pages across the open web; Muse then fetches each page and keeps it
only if the retailer's own structured data describes a product with a price and image.
Articles, reviews and pages that block automated access simply drop out, so every price
shown comes from the retailer's page rather than a search snippet.
Docs: https://docs.tavily.com/documentation/api-reference/endpoint/search
"""

import asyncio
import logging
from urllib.parse import urlsplit

import httpx

from app.services.errors import FetchError, UpstreamError
from app.services.fetch import BROWSER_HEADERS, TIMEOUT, fetch
from app.services.product_page import PageProduct, parse_product_page
from app.services.retrieval import canonical_url
from app.services.sources.base import FoundListing

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.tavily.com/search"
# Basic-depth searches cost one credit whatever the result count, so take the maximum.
RESULTS_PER_SEARCH = 20
PAGE_FETCH_CONCURRENCY = 10
# One slow site (often a review blog, never a product page) shouldn't hold up every search.
PAGE_READ_TIMEOUT_SECONDS = 6.0
MAX_PAGE_BYTES = 4 * 1024 * 1024

# Never product pages.
EXCLUDED_DOMAINS = [
    "reddit.com", "youtube.com", "pinterest.com", "instagram.com", "tiktok.com", "facebook.com",
    "x.com", "twitter.com", "wikipedia.org", "quora.com", "medium.com", "vogue.com", "gq.com",
    "whowhatwear.com", "refinery29.com", "buzzfeed.com", "nytimes.com", "forbes.com",
    # Editorial shopping guides embed product data but aren't stores.
    "nymag.com", "wirecutter.com", "businessinsider.com", "cnn.com", "usatoday.com",
    "harpersbazaar.com", "elle.com", "cosmopolitan.com", "instyle.com", "glamour.com",
    "allure.com", "byrdie.com", "thezoereport.com", "popsugar.com", "today.com",
    # Aggregators and marketplaces that block automated reads (eBay is covered by its API),
    # and shortlinks that never resolve to a readable page. Excluding them frees result slots.
    "lyst.com", "etsy.com", "dhgate.com", "ebay.com", "amzn.to", "amazon.com", "temu.com",
    "shein.com", "aliexpress.com", "walmart.com", "target.com", "shopstyle.com", "modesens.com",
]  # fmt: skip


class TavilySource:
    name = "web"

    def __init__(self, api_key: str, *, http: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.http = http or httpx.AsyncClient(timeout=TIMEOUT, headers=BROWSER_HEADERS)

    async def search(self, query: str, *, gtin: str | None = None) -> list[FoundListing]:
        found = await self._search_urls(f"{gtin} {query}" if gtin else f"{query} buy")
        # Search results often list one page under http/https/www variants; read each once.
        urls: dict[str, str] = {}
        for url in found:
            urls.setdefault(canonical_url(url), url)
        semaphore = asyncio.Semaphore(PAGE_FETCH_CONCURRENCY)
        pages = await asyncio.gather(*(self._read_product(url, semaphore) for url in urls.values()))
        return [page for page in pages if page]

    async def _search_urls(self, query: str) -> list[str]:
        try:
            response = await self.http.post(
                SEARCH_URL,
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": RESULTS_PER_SEARCH,
                    "exclude_domains": EXCLUDED_DOMAINS,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("Couldn't reach the web search service.") from exc
        if response.status_code in (401, 403):
            raise UpstreamError("The web search service rejected our API key.")
        if response.status_code in (429, 432, 433):
            raise UpstreamError("The free web search quota is used up for now.")
        if response.is_error:
            raise UpstreamError(f"Web search failed ({response.status_code}).")
        return [r["url"] for r in response.json().get("results", []) if r.get("url")]

    async def _read_product(self, url: str, semaphore: asyncio.Semaphore) -> FoundListing | None:
        async with semaphore:
            try:
                resource = await asyncio.wait_for(
                    fetch(url, max_bytes=MAX_PAGE_BYTES, accept="text/html", client=self.http),
                    PAGE_READ_TIMEOUT_SECONDS,
                )
            except (FetchError, TimeoutError):
                return None
        if "html" not in resource.content_type:
            return None
        return listing_from_page(parse_product_page(resource.body, resource.url))


def listing_from_page(page: PageProduct) -> FoundListing | None:
    """Only real product pages qualify: structured price, image and title are required."""
    if page.price is None or not page.image_url or not page.title or not page.has_product_data:
        return None
    gtin = next((v for k, v in page.identifiers.items() if k.startswith("gtin")), None)
    return FoundListing(
        title=page.title,
        url=page.url,
        provider="web",
        retailer=page.retailer or urlsplit(page.url).hostname,
        image_url=page.image_url,
        price=page.price,
        currency=page.currency,
        in_stock=page.in_stock,
        brand=page.brand,
        gtin=gtin,
    )
