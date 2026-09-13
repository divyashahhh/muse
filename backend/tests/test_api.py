from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Product, Store
from scripts.seed_stores import DEMO_STORES, seed_stores


def make_product(store: Store, source_id: str, category: Category, price_cents: int) -> Product:
    return Product(
        store_id=store.id,
        source_id=source_id,
        title=f"Item {source_id}",
        category=category,
        price_cents=price_cents,
        image_url=f"https://example.com/{source_id}.jpg",
    )


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_seed_stores_is_idempotent(session: AsyncSession) -> None:
    await seed_stores(session)
    await seed_stores(session)
    stores = (await session.scalars(select(Store))).all()
    assert sorted(s.slug for s in stores) == sorted(s["slug"] for s in DEMO_STORES)


async def test_list_stores_includes_product_counts(
    client: AsyncClient, session: AsyncSession
) -> None:
    await seed_stores(session)
    noir = await session.scalar(select(Store).where(Store.slug == "atelier-noir"))
    session.add_all(
        [
            make_product(noir, "a", Category.TOP, 4500),
            make_product(noir, "b", Category.FOOTWEAR, 12000),
        ]
    )
    await session.commit()

    response = await client.get("/api/stores")
    assert response.status_code == 200
    counts = {s["slug"]: s["product_count"] for s in response.json()}
    assert counts == {"atelier-noir": 2, "concrete-club": 0, "loom-and-lark": 0}


async def test_store_products_filter_and_paginate(
    client: AsyncClient, session: AsyncSession
) -> None:
    await seed_stores(session)
    noir = await session.scalar(select(Store).where(Store.slug == "atelier-noir"))
    session.add_all(
        [make_product(noir, f"top-{i}", Category.TOP, 1000 + i) for i in range(5)]
        + [make_product(noir, "shoe", Category.FOOTWEAR, 9000)]
    )
    await session.commit()

    response = await client.get(
        "/api/stores/atelier-noir/products", params={"category": "top", "limit": 2, "offset": 2}
    )
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 5
    assert [p["title"] for p in page["items"]] == ["Item top-2", "Item top-3"]
    assert all(p["category"] == "top" for p in page["items"])


async def test_unknown_store_is_404(client: AsyncClient) -> None:
    response = await client.get("/api/stores/nope/products")
    assert response.status_code == 404


async def test_invalid_category_is_422(client: AsyncClient, session: AsyncSession) -> None:
    await seed_stores(session)
    response = await client.get("/api/stores/atelier-noir/products", params={"category": "hat"})
    assert response.status_code == 422
