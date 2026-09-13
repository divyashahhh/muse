"""Seed the demo stores. Idempotent: re-running updates existing rows by slug.

Usage: python -m scripts.seed_stores
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, engine
from app.models import Store

# Fictional retailers. Each gets its own slice of the catalog and its own pricing
# so that store selection and Price Radar are meaningfully different per store.
DEMO_STORES = [
    {
        "slug": "atelier-noir",
        "name": "Atelier Noir",
        "tagline": "Considered wardrobe staples, cut clean.",
        "accent_color": "#1F1B18",
    },
    {
        "slug": "loom-and-lark",
        "name": "Loom & Lark",
        "tagline": "Soft textures, vintage-leaning and romantic.",
        "accent_color": "#9C6B4E",
    },
    {
        "slug": "concrete-club",
        "name": "Concrete Club",
        "tagline": "Streetwear, sportswear and everything oversized.",
        "accent_color": "#3D5A80",
    },
]


async def seed_stores(session: AsyncSession) -> None:
    stmt = insert(Store).values(DEMO_STORES)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Store.slug],
        set_={col: stmt.excluded[col] for col in ("name", "tagline", "accent_color")},
    )
    await session.execute(stmt)
    await session.commit()


async def main() -> None:
    async with SessionLocal() as session:
        await seed_stores(session)
    await engine.dispose()
    print(f"Seeded {len(DEMO_STORES)} demo stores.")


if __name__ == "__main__":
    asyncio.run(main())
