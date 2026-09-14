"""Search sources against mock HTTP transports (no network, no keys)."""

import json
from decimal import Decimal

import httpx
import pytest

from app.services.errors import UpstreamError
from app.services.fetch import FetchedResource
from app.services.sources import FoundListing, ProductSearch
from app.services.sources import tavily as tavily_module
from app.services.sources.ebay import EbaySource, parse_item_summary
from app.services.sources.tavily import TavilySource

EBAY_ITEM = {
    "itemId": "v1|1234|0",
    "title": "Everlane The Day Glove Black Leather Flats Size 7",
    "image": {"imageUrl": "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"},
    "price": {"value": "58.00", "currency": "USD"},
    "itemWebUrl": "https://www.ebay.com/itm/1234",
    "condition": "Pre-owned",
    "seller": {"username": "closetcleanout", "feedbackPercentage": "99.8"},
    "shippingOptions": [
        {"shippingCostType": "FIXED", "shippingCost": {"value": "7.50", "currency": "USD"}}
    ],
    "buyingOptions": ["FIXED_PRICE"],
}


def test_parse_ebay_item_summary() -> None:
    listing = parse_item_summary(EBAY_ITEM)
    assert listing is not None
    assert (listing.price, listing.currency, listing.shipping) == (
        Decimal("58.00"),
        "USD",
        Decimal("7.50"),
    )
    assert listing.retailer == "eBay · closetcleanout"
    assert (listing.condition, listing.provider) == ("Pre-owned", "ebay")


def test_ebay_item_without_price_is_skipped() -> None:
    assert parse_item_summary({**EBAY_ITEM, "price": None}) is None


async def test_ebay_fetches_token_once_and_searches() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/identity/v1/oauth2/token":
            assert request.headers["Authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "app-token", "expires_in": 7200})
        assert request.headers["Authorization"] == "Bearer app-token"
        assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"
        return httpx.Response(200, json={"itemSummaries": [EBAY_ITEM]})

    source = EbaySource(
        "id",
        "secret",
        marketplace="EBAY_GB",
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await source.search("everlane day glove")
    results = await source.search("everlane day glove", gtin="0123456789012")

    assert len(results) == 1
    token_calls = [r for r in requests if r.url.path.endswith("/token")]
    assert len(token_calls) == 1
    last = requests[-1]
    assert last.url.params["gtin"] == "0123456789012"
    assert last.url.params["filter"] == "buyingOptions:{FIXED_PRICE}"


async def test_tavily_keeps_only_real_product_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["query"] == "everlane day glove buy"
        assert "reddit.com" in body["exclude_domains"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://shop.example/day-glove",
                        "title": "Day Glove",
                        "content": "...",
                    },
                    {"url": "https://blog.example/review", "title": "Review", "content": "..."},
                    {"url": "https://blocked.example/p", "title": "Blocked", "content": "..."},
                ]
            },
        )

    pages = {
        "https://shop.example/day-glove": """<meta property="og:site_name" content="Shop">
          <script type="application/ld+json">{"@type": "Product", "name": "The Day Glove",
          "brand": "Everlane", "image": "https://shop.example/g.jpg", "gtin13": "0123456789012",
          "offers": {"price": "145.00", "priceCurrency": "USD"}}</script>""",
        "https://blog.example/review": """<meta property="og:title" content="Is the Day Glove worth it?">
          <meta property="og:image" content="https://blog.example/hero.jpg">""",
    }

    async def fake_fetch(url: str, **_) -> FetchedResource:
        if url not in pages:
            from app.services.errors import FetchError

            raise FetchError("blocked")
        return FetchedResource(url=url, content_type="text/html", body=pages[url].encode())

    monkeypatch.setattr(tavily_module, "fetch", fake_fetch)
    source = TavilySource("key", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    results = await source.search("everlane day glove")

    assert [(r.retailer, r.price, r.currency, r.gtin) for r in results] == [
        ("Shop", Decimal("145.00"), "USD", "0123456789012")
    ]


async def test_tavily_quota_error() -> None:
    source = TavilySource(
        "key",
        http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(432))),
    )
    with pytest.raises(UpstreamError, match="quota"):
        await source.search("anything")


class _Source:
    def __init__(self, name: str, result: list[FoundListing] | Exception) -> None:
        self.name = name
        self.result = result

    async def search(self, query: str, *, gtin: str | None = None) -> list[FoundListing]:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


async def test_product_search_tolerates_one_failing_source() -> None:
    listing = FoundListing(title="x", url="https://a.example/x", provider="a")
    search = ProductSearch([_Source("a", [listing]), _Source("b", UpstreamError("down"))])
    assert await search.search("q") == [listing]


async def test_product_search_fails_when_every_source_fails() -> None:
    search = ProductSearch(
        [_Source("a", UpstreamError("down")), _Source("b", UpstreamError("down"))]
    )
    with pytest.raises(UpstreamError):
        await search.search("q")
