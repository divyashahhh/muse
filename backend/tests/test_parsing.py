"""Unit tests for page parsing, SerpApi response normalisation, image handling and URL safety."""

from decimal import Decimal

import pytest
from PIL import Image

from app.services.errors import FetchError, InvalidImageError
from app.services.fetch import ensure_public_url
from app.services.imaging import MAX_EDGE, normalize_image
from app.services.product_page import parse_product_page
from app.services.search import parse_lens_result, parse_shopping_result, parse_store_offer
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


def test_lens_product_match_with_price_object() -> None:
    listing = parse_lens_result(
        {
            "title": "Hershey's Cookies n Creme",
            "link": "https://www.walmart.com/ip/6706455482",
            "source": "Walmart",
            "price": {"value": "$34*", "extracted_value": 34.0, "currency": "$"},
            "in_stock": True,
            "rating": 4.7,
            "reviews": 20714,
            "thumbnail": "https://encrypted-tbn2.gstatic.com/t",
            "image": "https://i5.walmartimages.com/full.jpg",
        }
    )
    assert listing is not None
    assert (listing.retailer, listing.price, listing.currency) == ("Walmart", Decimal("34.0"), "$")
    assert listing.image_url == "https://i5.walmartimages.com/full.jpg"
    assert (listing.in_stock, listing.reviews) == (True, 20714)


def test_lens_exact_match_with_flat_price() -> None:
    listing = parse_lens_result(
        {
            "title": "Samba OG",
            "link": "https://shop.example/samba",
            "source": "Shop",
            "thumbnail": "https://t.example/1.jpg",
            "price": "£85.00",
            "extracted_price": 85.0,
            "out_of_stock": True,
        }
    )
    assert listing is not None
    assert (listing.price, listing.currency, listing.in_stock) == (Decimal("85.0"), "£", False)


def test_lens_result_without_link_is_skipped() -> None:
    assert parse_lens_result({"title": "No link"}) is None


def test_shopping_result_extracts_offers_token() -> None:
    listing = parse_shopping_result(
        {
            "title": "Apple iPhone 17",
            "product_link": "https://www.google.com/search?ibp=oshop&prds=abc",
            "source": "Apple",
            "price": "$829.00",
            "extracted_price": 829.0,
            "thumbnail": "https://encrypted-tbn2.gstatic.com/shopping?q=1",
            "serpapi_immersive_product_api": (
                "https://serpapi.com/search.json?engine=google_immersive_product&page_token=eyJ"
            ),
        }
    )
    assert listing is not None
    assert listing.url == "https://www.google.com/search?ibp=oshop&prds=abc"
    assert (listing.price, listing.currency, listing.offers_token) == (Decimal("829.0"), "$", "eyJ")


def test_store_offer_derives_shipping_from_total() -> None:
    offer = parse_store_offer(
        {
            "name": "Best Buy",
            "link": "https://www.bestbuy.com/site/iphone",
            "price": "$829.99",
            "extracted_price": 829.99,
            "extracted_total": 839.99,
            "tag": "Refurbished",
        },
        product_title="Apple iPhone 17",
        image_url=None,
    )
    assert offer is not None
    assert offer.title == "Apple iPhone 17"
    assert (offer.price, offer.shipping, offer.condition) == (
        Decimal("829.99"),
        Decimal("10.00"),
        "Refurbished",
    )


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
