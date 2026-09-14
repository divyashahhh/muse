"""Unit tests for page parsing, image handling and URL safety."""

from decimal import Decimal

import pytest
from PIL import Image

from app.services.errors import FetchError, InvalidImageError
from app.services.fetch import ensure_public_url
from app.services.imaging import MAX_EDGE, normalize_image
from app.services.product_page import parse_product_page
from tests.conftest import png_bytes


def test_json_ld_product_group_in_graph() -> None:
    html = """<html><head><title>ignored</title>
    <script type="application/ld+json">{"@graph": [{"@type": "WebPage"},
      {"@type": "ProductGroup", "name": "Linen Dress", "brand": "Rouje",
       "hasVariant": [{"@type": "Product", "sku": "RJ-1", "image": {"url": "https://c.example/d.jpg"},
         "offers": [{"@type": "Offer", "price": "1,250.00", "priceCurrency": "EUR"}]}]}]}
    </script></head></html>"""
    page = parse_product_page(html, "https://www.rouje.example/dress")
    assert page.title == "Linen Dress"
    assert page.brand == "Rouje"
    assert page.image_url == "https://c.example/d.jpg"
    assert (page.price, page.currency) == (Decimal("1250.00"), "EUR")
    assert page.identifiers == {"sku": "RJ-1"}
    assert page.retailer == "rouje.example"
    assert page.has_product_data


def test_category_page_item_list_is_not_a_product() -> None:
    html = """<script type="application/ld+json">{"@type": "ItemList", "itemListElement": [
      {"@type": "ListItem", "item": {"@type": "Product", "name": "Flat", "offers": {"price": "10"}}}]}
    </script><meta property="og:title" content="All flats"><meta property="og:image" content="/c.jpg">"""
    page = parse_product_page(html, "https://shop.example/flats")
    assert not page.has_product_data
    assert page.price is None


def test_json_ld_html_entities_are_decoded() -> None:
    html = """<script type="application/ld+json">{"@type": "Product", "name": "Rollneck&trade; Sweater &amp; Scarf"}</script>"""
    assert parse_product_page(html, "https://shop.example/p").title == "Rollneck™ Sweater & Scarf"


def test_offer_availability() -> None:
    html = """<script type="application/ld+json">{"@type": "Product", "name": "Flat",
      "offers": {"price": "10", "priceCurrency": "USD", "availability": "https://schema.org/OutOfStock"}}
    </script>"""
    assert parse_product_page(html, "https://shop.example/p").in_stock is False


def test_open_graph_fallback_and_relative_image() -> None:
    html = """<html><head><title> Cool   Jacket | Shop </title>
    <meta property="og:image" content="/media/jacket.jpg">
    <meta property="product:price:amount" content="89.5">
    <meta property="product:price:currency" content="GBP">
    <script type="application/ld+json">{ not json </script>
    </head></html>"""
    page = parse_product_page(html, "https://shop.example/p/jacket")
    assert page.title == "Cool Jacket | Shop"
    assert page.image_url == "https://shop.example/media/jacket.jpg"
    assert (page.price, page.currency) == (Decimal("89.5"), "GBP")


def test_normalize_image_flattens_and_bounds_size() -> None:
    jpeg = normalize_image(png_bytes(size=(4000, 1000)))
    with Image.open(__import__("io").BytesIO(jpeg)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert max(image.size) == MAX_EDGE


def test_normalize_image_rejects_garbage() -> None:
    with pytest.raises(InvalidImageError):
        normalize_image(b"definitely not an image")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]:8000/",
        "file:///etc/passwd",
        "ftp://example.com/file",
    ],
)
async def test_private_and_non_http_urls_are_refused(url: str) -> None:
    with pytest.raises(FetchError):
        await ensure_public_url(url)


async def test_public_ip_is_allowed() -> None:
    await ensure_public_url("https://8.8.8.8/")
