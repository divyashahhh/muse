from httpx import AsyncClient

from tests.conftest import png_bytes

ALICE = {"X-Muse-Client": "alice-0001"}
BOB = {"X-Muse-Client": "bob-00001"}

SHOE = {
    "title": "Samba OG",
    "url": "https://shop.example/samba",
    "retailer": "Shop",
    "image_url": "https://cdn.example/samba.jpg",
    "price": 95.0,
    "currency": "USD",
}


async def test_requires_client_id(client: AsyncClient) -> None:
    assert (await client.get("/api/wishlist")).status_code == 400
    assert (await client.get("/api/wishlist", headers={"X-Muse-Client": "x"})).status_code == 400


async def test_add_is_idempotent_and_scoped_per_client(client: AsyncClient) -> None:
    first = await client.post("/api/wishlist", json=SHOE, headers=ALICE)
    again = await client.post("/api/wishlist", json=SHOE, headers=ALICE)
    assert first.status_code == again.status_code == 201
    assert first.json()["id"] == again.json()["id"]

    assert len((await client.get("/api/wishlist", headers=ALICE)).json()) == 1
    assert (await client.get("/api/wishlist", headers=BOB)).json() == []
    assert (
        await client.delete(f"/api/wishlist/{first.json()['id']}", headers=BOB)
    ).status_code == 404


async def test_remove(client: AsyncClient) -> None:
    saved = (await client.post("/api/wishlist", json=SHOE, headers=ALICE)).json()
    other = {**SHOE, "url": "https://shop.example/jacket", "title": "Jacket"}
    await client.post("/api/wishlist", json=other, headers=ALICE)

    assert (await client.delete(f"/api/wishlist/{saved['id']}", headers=ALICE)).status_code == 204
    remaining = (await client.get("/api/wishlist", headers=ALICE)).json()
    assert [s["title"] for s in remaining] == ["Jacket"]


async def test_add_tidies_scraped_fields_instead_of_rejecting(client: AsyncClient) -> None:
    messy = {
        **SHOE,
        "title": "  " + "x" * 1200,
        "retailer": "r" * 300,
        "image_url": "//cdn.example/samba.jpg",
        "currency": "not-a-currency",
        "price": -1,
    }
    response = await client.post("/api/wishlist", json=messy, headers=ALICE)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert len(saved["title"]) == 1000
    assert len(saved["retailer"]) == 200
    assert saved["image_url"] == "https://cdn.example/samba.jpg"
    assert saved["currency"] is None
    assert saved["price"] is None

    unusable_image = {
        **SHOE,
        "url": "https://shop.example/b",
        "image_url": "data:image/png;base64,AA",
    }
    response = await client.post("/api/wishlist", json=unusable_image, headers=ALICE)
    assert response.status_code == 201
    assert response.json()["image_url"] is None


async def test_can_save_a_searched_item(client: AsyncClient) -> None:
    item = (
        await client.post(
            "/api/items/upload",
            files={"file": ("x.png", png_bytes(), "image/png")},
            headers=ALICE,
        )
    ).json()
    body = {
        "item_id": item["id"],
        "title": item["title"] or item["analysis"]["product_name"],
        "url": f"http://localhost:5173/items/{item['id']}",
        "image_url": item["image_url"],
    }
    response = await client.post("/api/wishlist", json=body, headers=ALICE)
    assert response.status_code == 201, response.text
    assert response.json()["item_id"] == item["id"]


async def test_recents_are_per_browser_newest_first(client: AsyncClient) -> None:
    async def upload(headers: dict | None = None) -> dict:
        response = await client.post(
            "/api/items/upload",
            files={"file": ("x.png", png_bytes(), "image/png")},
            headers=headers,
        )
        assert response.status_code == 201
        return response.json()

    first = await upload(ALICE)
    second = await upload(ALICE)
    await upload(BOB)
    await upload()  # no browser id: not in anyone's recents

    recents = (await client.get("/api/items/recent", headers=ALICE)).json()
    assert [r["id"] for r in recents] == [second["id"], first["id"]]
    assert recents[0]["product_name"] == "Adidas Samba OG White Black"
    assert recents[0]["discovered_at"] is None
    assert recents[0]["source_url"] is None

    assert (await client.delete(f"/api/items/{first['id']}", headers=BOB)).status_code == 404
    assert (await client.delete(f"/api/items/{first['id']}", headers=ALICE)).status_code == 204
    recents = (await client.get("/api/items/recent", headers=ALICE)).json()
    assert [r["id"] for r in recents] == [second["id"]]
