"""Live product search via SerpApi (Google Lens, Google Shopping, Google product offers).

SerpApi returns Google's results for real retailers and resellers; we normalise its
several response shapes into `FoundListing`.
"""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

import httpx

from app.services.errors import UpstreamError

log = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"


@dataclass
class FoundListing:
    title: str
    url: str
    provider: str
    retailer: str | None = None
    retailer_icon: str | None = None
    image_url: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    shipping: Decimal | None = None
    in_stock: bool | None = None
    condition: str | None = None
    rating: float | None = None
    reviews: int | None = None
    # Google Shopping token for fetching every store selling this product.
    offers_token: str | None = None


class SerpApiClient:
    def __init__(
        self, api_key: str, *, country: str, language: str, http: httpx.AsyncClient | None = None
    ) -> None:
        self.api_key = api_key
        self.country = country
        self.language = language
        self.http = http or httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))

    async def lens(
        self, image_url: str, kind: Literal["products", "exact_matches"]
    ) -> list[FoundListing]:
        data = await self._search(
            engine="google_lens",
            url=image_url,
            type=kind,
            country=self.country,
            hl=self.language,
        )
        key = "exact_matches" if kind == "exact_matches" else "visual_matches"
        return [x for x in map(parse_lens_result, data.get(key, [])) if x]

    async def shopping(self, query: str) -> list[FoundListing]:
        data = await self._search(
            engine="google_shopping", q=query, gl=self.country, hl=self.language
        )
        return [x for x in map(parse_shopping_result, data.get("shopping_results", [])) if x]

    async def product_offers(self, offers_token: str) -> list[FoundListing]:
        data = await self._search(
            engine="google_immersive_product", page_token=offers_token, more_stores="true"
        )
        product = data.get("product_results") or {}
        image = next(iter(product.get("thumbnails") or []), None)
        return [
            x
            for x in (
                parse_store_offer(store, product.get("title"), image)
                for store in product.get("stores", [])
            )
            if x
        ]

    async def _search(self, **params: str) -> dict[str, Any]:
        try:
            response = await self.http.get(SERPAPI_URL, params={**params, "api_key": self.api_key})
        except httpx.HTTPError as exc:
            raise UpstreamError("Couldn't reach the product search service.") from exc
        data = response.json() if response.content else {}
        error = data.get("error")
        # SerpApi reports "no results" as an error string; that's an empty result, not a failure.
        if error and "hasn't returned any results" in error:
            return {}
        if response.is_error or error:
            log.warning(
                "SerpApi %s failed (%s): %s", params.get("engine"), response.status_code, error
            )
            raise UpstreamError("The product search service returned an error.")
        return data


def parse_lens_result(raw: dict[str, Any]) -> FoundListing | None:
    if not raw.get("link") or not raw.get("title"):
        return None
    # Lens uses {"price": {"value", "extracted_value", "currency"}} for product matches and
    # {"price": "$10", "extracted_price": 10.0} for exact matches.
    price_field = raw.get("price")
    if isinstance(price_field, dict):
        price = _decimal(price_field.get("extracted_value"))
        currency = price_field.get("currency") or _currency_symbol(price_field.get("value"))
    else:
        price = _decimal(raw.get("extracted_price"))
        currency = _currency_symbol(price_field)
    in_stock = raw.get("in_stock")
    if raw.get("out_of_stock"):
        in_stock = False
    return FoundListing(
        title=raw["title"],
        url=raw["link"],
        provider="google_lens",
        retailer=raw.get("source"),
        retailer_icon=raw.get("source_icon"),
        image_url=raw.get("image") or raw.get("thumbnail"),
        price=price,
        currency=currency if price is not None else None,
        in_stock=in_stock,
        condition=raw.get("condition"),
        rating=raw.get("rating"),
        reviews=raw.get("reviews"),
    )


def parse_shopping_result(raw: dict[str, Any]) -> FoundListing | None:
    url = raw.get("link") or raw.get("product_link")
    if not url or not raw.get("title"):
        return None
    price = _decimal(raw.get("extracted_price"))
    return FoundListing(
        title=raw["title"],
        url=url,
        provider="google_shopping",
        retailer=raw.get("source"),
        retailer_icon=raw.get("source_icon"),
        image_url=raw.get("thumbnail"),
        price=price,
        currency=_currency_symbol(raw.get("price")) if price is not None else None,
        condition=raw.get("second_hand_condition"),
        rating=raw.get("rating"),
        reviews=raw.get("reviews"),
        offers_token=_offers_token(raw),
    )


def parse_store_offer(
    raw: dict[str, Any], product_title: str | None, image_url: str | None
) -> FoundListing | None:
    if not raw.get("link"):
        return None
    price = _decimal(raw.get("extracted_price"))
    total = _decimal(raw.get("extracted_total"))
    shipping = _decimal(raw.get("shipping_extracted"))
    if shipping is None and price is not None and total is not None and total >= price:
        shipping = total - price
    return FoundListing(
        title=raw.get("title") or product_title or raw.get("name") or "Product",
        url=raw["link"],
        provider="google_immersive_product",
        retailer=raw.get("name"),
        retailer_icon=raw.get("logo"),
        image_url=image_url,
        price=price,
        currency=_currency_symbol(raw.get("price")) if price is not None else None,
        shipping=shipping,
        condition=raw.get("tag")
        if raw.get("tag") in ("Used", "Refurbished", "Pre-owned")
        else None,
        rating=raw.get("rating"),
        reviews=raw.get("reviews"),
    )


def _offers_token(raw: dict[str, Any]) -> str | None:
    if token := raw.get("immersive_product_page_token"):
        return token
    api_url = raw.get("serpapi_immersive_product_api")
    if api_url:
        return next(iter(parse_qs(urlsplit(api_url).query).get("page_token", [])), None)
    return None


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, (int, float)) and value >= 0:
        return Decimal(str(round(float(value), 2)))
    return None


_SYMBOL = re.compile(r"^\s*([^\d\s.,]+)")


def _currency_symbol(price_text: Any) -> str | None:
    if not isinstance(price_text, str):
        return None
    match = _SYMBOL.match(price_text)
    return match.group(1) if match else None
