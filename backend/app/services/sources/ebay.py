"""eBay Browse API: new and pre-owned listings with real prices, images and shipping.

Uses an application token (client-credentials grant), so no eBay user login is involved.
Docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
"""

import base64
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.services.errors import UpstreamError
from app.services.sources.base import FoundListing

API_ROOT = "https://api.ebay.com"
SCOPE = "https://api.ebay.com/oauth/api_scope"
RESULTS_PER_SEARCH = 20


class EbaySource:
    name = "ebay"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        marketplace: str = "EBAY_US",
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.marketplace = marketplace
        self.http = http or httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0))
        self._token: str | None = None
        self._token_expires_at = 0.0

    async def search(self, query: str, *, gtin: str | None = None) -> list[FoundListing]:
        params = {
            "q": query,
            "limit": str(RESULTS_PER_SEARCH),
            # Auctions don't have a firm price to compare.
            "filter": "buyingOptions:{FIXED_PRICE}",
        }
        if gtin:
            params["gtin"] = gtin
        response = await self._get("/buy/browse/v1/item_summary/search", params)
        return [x for x in map(parse_item_summary, response.get("itemSummaries", [])) if x]

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {await self._access_token()}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
        }
        try:
            response = await self.http.get(f"{API_ROOT}{path}", params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamError("Couldn't reach eBay.") from exc
        if response.status_code == 401:
            self._token = None
        if response.is_error:
            raise UpstreamError(f"eBay search failed ({response.status_code}).")
        return response.json()

    async def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        try:
            response = await self.http.post(
                f"{API_ROOT}/identity/v1/oauth2/token",
                data={"grant_type": "client_credentials", "scope": SCOPE},
                headers={"Authorization": f"Basic {credentials}"},
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("Couldn't reach eBay.") from exc
        if response.is_error:
            raise UpstreamError("eBay rejected the app credentials.")
        body = response.json()
        self._token = body["access_token"]
        # Refresh a minute early.
        self._token_expires_at = time.monotonic() + int(body.get("expires_in", 7200)) - 60
        return self._token


def parse_item_summary(raw: dict[str, Any]) -> FoundListing | None:
    url = raw.get("itemWebUrl")
    price = raw.get("price") or {}
    amount = _decimal(price.get("value"))
    if not url or not raw.get("title") or amount is None:
        return None
    image = (raw.get("image") or {}).get("imageUrl") or next(
        (i.get("imageUrl") for i in raw.get("thumbnailImages") or []), None
    )
    shipping = None
    for option in raw.get("shippingOptions") or []:
        cost = option.get("shippingCost") or {}
        if cost.get("currency") in (None, price.get("currency")):
            shipping = _decimal(cost.get("value"))
            break
    seller = (raw.get("seller") or {}).get("username")
    return FoundListing(
        title=raw["title"],
        url=url,
        provider="ebay",
        retailer=f"eBay · {seller}" if seller else "eBay",
        image_url=image,
        price=amount,
        currency=price.get("currency"),
        shipping=shipping,
        condition=raw.get("condition"),
    )


def _decimal(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None
