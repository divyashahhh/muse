import pytest
from httpx import AsyncClient

from app.services import ingest
from app.services.errors import FetchError
from app.services.fetch import FetchedResource
from tests.conftest import FakeAI, FakeSource, png_bytes

PRODUCT_PAGE = b"""
<html><head>
<meta property="og:site_name" content="Sneaker Shop">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product", "name": "Samba OG Shoes",
 "brand": {"@type": "Brand", "name": "adidas"}, "image": ["/img/samba.png"], "gtin13": "4066748",
 "offers": {"@type": "Offer", "price": "100.00", "priceCurrency": "USD"}}
</script></head><body></body></html>
"""


async def upload(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/items/upload", files={"file": ("shoe.png", png_bytes(), "image/png")}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_upload_creates_analysed_item(client: AsyncClient, fake_ai: FakeAI) -> None:
    item = await upload(client)
    assert item["source"] == "upload"
    assert item["analysis"]["product_name"] == "Adidas Samba OG White Black"
    assert fake_ai.analyzed_pages == [None]

    fetched = await client.get(f"/api/items/{item['id']}")
    assert fetched.json()["analysis"] == item["analysis"]


async def test_upload_rejects_non_images(client: AsyncClient) -> None:
    response = await client.post(
        "/api/items/upload", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 422
    assert "image" in response.json()["detail"]


async def test_item_from_product_url(
    client: AsyncClient, fake_ai: FakeAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_fetch(url: str, **_) -> FetchedResource:
        if url == "https://shop.example/samba":
            return FetchedResource(url=url, content_type="text/html", body=PRODUCT_PAGE)
        assert url == "https://shop.example/img/samba.png"
        return FetchedResource(url=url, content_type="image/png", body=png_bytes())

    monkeypatch.setattr(ingest, "fetch", fake_fetch)
    response = await client.post("/api/items/from-url", json={"url": "https://shop.example/samba"})
    assert response.status_code == 201, response.text
    item = response.json()
    assert (item["title"], item["brand"], item["retailer"]) == (
        "Samba OG Shoes",
        "adidas",
        "Sneaker Shop",
    )
    assert (item["price"], item["currency"]) == (100.0, "USD")
    assert fake_ai.analyzed_pages[0].identifiers == {"gtin13": "4066748"}


async def test_item_from_url_surfaces_fetch_errors(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def blocked(url: str, **_) -> FetchedResource:
        raise FetchError("That site blocked automated access.")

    monkeypatch.setattr(ingest, "fetch", blocked)
    response = await client.post("/api/items/from-url", json={"url": "https://shop.example/x"})
    assert response.status_code == 422
    assert response.json()["detail"] == "That site blocked automated access."


async def test_discover_groups_filtered_results_and_caches(
    client: AsyncClient, fake_source: FakeSource, fake_ai: FakeAI
) -> None:
    item = await upload(client)

    first = await client.post(f"/api/items/{item['id']}/discover")
    assert first.status_code == 200, first.text
    sections = first.json()["sections"]
    assert [(s["kind"], s["label"]) for s in sections] == [
        ("visual_match", "Looks like this"),
        ("aesthetic", "Retro track jackets"),
        ("aesthetic", "Straight-leg jeans"),
        ("similar_brand", "Onitsuka Tiger"),
        ("similar_brand", "Puma"),
    ]
    queries = [query for query, _ in fake_source.calls]
    assert queries[0] == "white leather gum sole trainers"
    assert "Puma sneakers" in queries
    # The relevance filter saw section context and removed the gift cards.
    assert fake_ai.filtered[0][0].section == "Looks like this"
    assert all("gift card" not in x["title"] for s in sections for x in s["listings"])
    # Same retailer + title under another URL is shown once.
    titles = [(x["retailer"], x["title"]) for s in sections for x in s["listings"]]
    assert len(titles) == len(set(titles))

    calls_after_first = len(fake_source.calls)
    second = await client.post(f"/api/items/{item['id']}/discover")
    assert second.json()["sections"] == sections
    assert len(fake_source.calls) == calls_after_first, "cached results should not search again"

    await client.post(f"/api/items/{item['id']}/discover", params={"refresh": True})
    assert len(fake_source.calls) > calls_after_first


async def test_price_comparison_keeps_verified_offers_cheapest_first(client: AsyncClient) -> None:
    item = await upload(client)

    response = await client.post(f"/api/items/{item['id']}/prices")
    assert response.status_code == 200, response.text
    offers = response.json()["offers"]
    # Gazelle rejected by verification; unpriced listing dropped; the "Retro trainers" title
    # would fail verification but there's no GTIN on an upload; sorted by price + shipping.
    assert [(o["retailer"], o["price"], o["shipping"]) for o in offers] == [
        ("Cheap Shoes", 89.0, 5.0),
        ("Shop", 95.0, None),
        ("Big Store", 110.0, None),
        ("Pricey", 120.0, None),
    ]
    assert all(o["match_reason"] for o in offers)
    assert response.json()["reference"] is None


async def test_price_comparison_accepts_matching_gtin_without_ai(
    client: AsyncClient, fake_source: FakeSource, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_fetch(url: str, **_) -> FetchedResource:
        if url == "https://shop.example/samba":
            return FetchedResource(url=url, content_type="text/html", body=PRODUCT_PAGE)
        return FetchedResource(url=url, content_type="image/png", body=png_bytes())

    monkeypatch.setattr(ingest, "fetch", fake_fetch)
    item = (
        await client.post("/api/items/from-url", json={"url": "https://shop.example/samba"})
    ).json()

    response = await client.post(f"/api/items/{item['id']}/prices")
    offers = response.json()["offers"]
    assert fake_source.calls[-1] == ("adidas samba og white black", "4066748")
    coded = next(o for o in offers if o["retailer"] == "Coded")
    assert "barcode" in coded["match_reason"]
    # The user's own link is the reference, not an offer.
    assert "https://shop.example/samba" not in [o["url"] for o in offers]
    assert response.json()["reference"]["price"] == 100.0


async def test_unknown_item_is_404(client: AsyncClient) -> None:
    response = await client.post("/api/items/00000000-0000-0000-0000-000000000000/discover")
    assert response.status_code == 404
