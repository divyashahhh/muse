from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session
from app.models import Category, Product, Store
from app.schemas import ProductPage, StoreOut

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("", response_model=list[StoreOut])
async def list_stores(session: Session) -> list[StoreOut]:
    product_count = (
        select(func.count(Product.id))
        .where(Product.store_id == Store.id)
        .correlate(Store)
        .scalar_subquery()
    )
    rows = await session.execute(select(Store, product_count).order_by(Store.name))
    return [
        StoreOut(
            id=store.id,
            slug=store.slug,
            name=store.name,
            tagline=store.tagline,
            accent_color=store.accent_color,
            product_count=count,
        )
        for store, count in rows.all()
    ]


async def _get_store(session: AsyncSession, slug: str) -> Store:
    store = await session.scalar(select(Store).where(Store.slug == slug))
    if store is None:
        raise HTTPException(status_code=404, detail=f"Store '{slug}' not found")
    return store


@router.get("/{slug}/products", response_model=ProductPage)
async def list_store_products(
    slug: str,
    session: Session,
    category: Category | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductPage:
    store = await _get_store(session, slug)

    query = select(Product).where(Product.store_id == store.id)
    if category is not None:
        query = query.where(Product.category == category)

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    products = await session.scalars(query.order_by(Product.id).limit(limit).offset(offset))
    return ProductPage(items=list(products), total=total or 0, limit=limit, offset=offset)
