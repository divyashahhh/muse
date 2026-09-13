"""Extract product facts from a retailer's product page.

Prefers schema.org Product JSON-LD (what retailers publish for Google Shopping), then
falls back to Open Graph / product meta tags.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


@dataclass
class PageProduct:
    url: str
    title: str | None = None
    brand: str | None = None
    retailer: str | None = None
    description: str | None = None
    image_url: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    # gtin / mpn / sku — the strongest signals for finding the exact same product elsewhere.
    identifiers: dict[str, str] = field(default_factory=dict)


def parse_product_page(html: str | bytes, url: str) -> PageProduct:
    soup = BeautifulSoup(html, "html.parser")
    product = PageProduct(url=url)

    for node in _json_ld_products(soup):
        _apply_json_ld(product, node)
        break

    meta = _meta_tags(soup)
    product.title = product.title or meta.get("og:title") or _text(soup.title)
    product.image_url = product.image_url or meta.get("og:image") or meta.get("twitter:image")
    product.description = product.description or meta.get("og:description")
    product.brand = product.brand or meta.get("product:brand") or meta.get("og:brand")
    if product.price is None:
        product.price = _decimal(meta.get("product:price:amount") or meta.get("og:price:amount"))
        product.currency = (
            product.currency or meta.get("product:price:currency") or meta.get("og:price:currency")
        )
    product.retailer = meta.get("og:site_name") or _domain_name(url)

    if product.image_url:
        product.image_url = urljoin(url, product.image_url)
    if product.title:
        product.title = " ".join(product.title.split())[:500]
    if product.description:
        product.description = " ".join(product.description.split())[:1000]
    return product


def _json_ld_products(soup: BeautifulSoup) -> Iterator[dict[str, Any]]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "", strict=False)
        except json.JSONDecodeError:
            continue
        yield from _find_products(data)


def _find_products(data: Any) -> Iterator[dict[str, Any]]:
    if isinstance(data, list):
        for entry in data:
            yield from _find_products(entry)
    elif isinstance(data, dict):
        types = data.get("@type")
        types = types if isinstance(types, list) else [types]
        if "Product" in types:
            yield data
        elif "ProductGroup" in types:
            variants = data.get("hasVariant") or []
            merged = {**data, **(variants[0] if variants and isinstance(variants[0], dict) else {})}
            yield merged
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data:
                yield from _find_products(data[key])


def _apply_json_ld(product: PageProduct, node: dict[str, Any]) -> None:
    product.title = _as_text(node.get("name"))
    product.description = _as_text(node.get("description"))
    brand = node.get("brand")
    product.brand = _as_text(brand.get("name") if isinstance(brand, dict) else brand)
    product.image_url = _first_image(node.get("image"))

    offers = node.get("offers")
    offer = offers[0] if isinstance(offers, list) and offers else offers
    if isinstance(offer, dict):
        product.price = _decimal(offer.get("price") or offer.get("lowPrice"))
        product.currency = _as_text(offer.get("priceCurrency"))
        spec = offer.get("priceSpecification")
        if product.price is None and isinstance(spec, dict):
            product.price = _decimal(spec.get("price"))
            product.currency = product.currency or _as_text(spec.get("priceCurrency"))

    for key in ("gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn", "sku"):
        value = _as_text(node.get(key))
        if value:
            product.identifiers[key] = value


def _meta_tags(soup: BeautifulSoup) -> dict[str, str]:
    tags: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name") or tag.get("itemprop")
        content = tag.get("content")
        if isinstance(key, str) and isinstance(content, str) and content.strip():
            tags.setdefault(key.lower(), content.strip())
    return tags


def _first_image(value: Any) -> str | None:
    if isinstance(value, list):
        return _first_image(value[0]) if value else None
    if isinstance(value, dict):
        return _as_text(value.get("url") or value.get("contentUrl"))
    return _as_text(value)


def _as_text(value: Any) -> str | None:
    if isinstance(value, (str, int, float)) and str(value).strip():
        return str(value).strip()
    return None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def _text(tag: Any) -> str | None:
    return (tag.get_text(strip=True) or None) if tag else None


def _domain_name(url: str) -> str | None:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.") or None
