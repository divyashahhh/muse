from httpx import AsyncClient

ALICE = {"X-Muse-Client": "alice-0001"}
BOB = {"X-Muse-Client": "bob-00001"}

SHOE = {
    "list": "bag",
    "title": "Samba OG",
    "url": "https://shop.example/samba",
    "retailer": "Shop",
    "image_url": "https://cdn.example/samba.jpg",
    "price": 95.0,
    "currency": "$",
}


async def test_requires_client_id(client: AsyncClient) -> None:
    assert (await client.get("/api/saved")).status_code == 400
    bad = await client.get("/api/saved", headers={"X-Muse-Client": "x"})
    assert bad.status_code == 400


async def test_save_is_idempotent_and_scoped_per_client(client: AsyncClient) -> None:
    first = await client.post("/api/saved", json=SHOE, headers=ALICE)
    again = await client.post("/api/saved", json=SHOE, headers=ALICE)
    assert first.status_code == again.status_code == 201
    assert first.json()["id"] == again.json()["id"]

    assert len((await client.get("/api/saved", headers=ALICE)).json()) == 1
    assert (await client.get("/api/saved", headers=BOB)).json() == []
    assert (await client.delete(f"/api/saved/{first.json()['id']}", headers=BOB)).status_code == 404


async def test_filter_move_and_remove(client: AsyncClient) -> None:
    bag_item = (await client.post("/api/saved", json=SHOE, headers=ALICE)).json()
    wish = {**SHOE, "list": "wishlist", "url": "https://shop.example/jacket", "title": "Jacket"}
    await client.post("/api/saved", json=wish, headers=ALICE)

    bag = await client.get("/api/saved", params={"list": "bag"}, headers=ALICE)
    assert [s["title"] for s in bag.json()] == ["Samba OG"]

    moved = await client.patch(
        f"/api/saved/{bag_item['id']}", json={"list": "wishlist"}, headers=ALICE
    )
    assert moved.json()["list"] == "wishlist"
    wishlist = await client.get("/api/saved", params={"list": "wishlist"}, headers=ALICE)
    assert {s["title"] for s in wishlist.json()} == {"Samba OG", "Jacket"}

    removed = await client.delete(f"/api/saved/{bag_item['id']}", headers=ALICE)
    assert removed.status_code == 204
    assert len((await client.get("/api/saved", headers=ALICE)).json()) == 1


async def test_moving_onto_a_duplicate_merges(client: AsyncClient) -> None:
    in_bag = (await client.post("/api/saved", json=SHOE, headers=ALICE)).json()
    in_wishlist = (
        await client.post("/api/saved", json={**SHOE, "list": "wishlist"}, headers=ALICE)
    ).json()

    moved = await client.patch(
        f"/api/saved/{in_bag['id']}", json={"list": "wishlist"}, headers=ALICE
    )
    assert moved.json()["id"] == in_wishlist["id"]
    assert len((await client.get("/api/saved", headers=ALICE)).json()) == 1
