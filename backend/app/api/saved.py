"""Feature 3: shopping bag and wishlist."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session
from app.deps import ClientId
from app.models import SavedItem, SavedList
from app.schemas import SavedItemIn, SavedItemMove, SavedItemOut

router = APIRouter(prefix="/saved", tags=["saved"])


@router.get("", response_model=list[SavedItemOut])
async def list_saved(
    session: Session,
    client_id: ClientId,
    list_name: Annotated[SavedList | None, Query(alias="list")] = None,
) -> list[SavedItem]:
    query = select(SavedItem).where(SavedItem.client_id == client_id)
    if list_name is not None:
        query = query.where(SavedItem.list == list_name)
    result = await session.scalars(query.order_by(SavedItem.created_at.desc(), SavedItem.id.desc()))
    return list(result)


@router.post("", response_model=SavedItemOut, status_code=status.HTTP_201_CREATED)
async def save_item(body: SavedItemIn, session: Session, client_id: ClientId) -> SavedItem:
    """Add to the bag or wishlist. Saving the same link to the same list again is a no-op."""
    values = body.model_dump(mode="json")
    stmt = (
        insert(SavedItem)
        .values(client_id=client_id, **values)
        .on_conflict_do_nothing(index_elements=["client_id", "list", "url"])
    )
    await session.execute(stmt)
    await session.commit()
    return await session.scalar(
        select(SavedItem).where(
            SavedItem.client_id == client_id,
            SavedItem.list == body.list,
            SavedItem.url == values["url"],
        )
    )


@router.patch("/{saved_id}", response_model=SavedItemOut)
async def move_item(
    saved_id: int, body: SavedItemMove, session: Session, client_id: ClientId
) -> SavedItem:
    """Move between bag and wishlist."""
    saved = await _get(session, client_id, saved_id)
    if saved.list == body.list:
        return saved
    existing = await session.scalar(
        select(SavedItem).where(
            SavedItem.client_id == client_id,
            SavedItem.list == body.list,
            SavedItem.url == saved.url,
        )
    )
    if existing:
        await session.delete(saved)
        await session.commit()
        return existing
    saved.list = body.list
    await session.commit()
    return saved


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(saved_id: int, session: Session, client_id: ClientId) -> Response:
    await session.delete(await _get(session, client_id, saved_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _get(session: AsyncSession, client_id: str, saved_id: int) -> SavedItem:
    saved = await session.scalar(
        select(SavedItem).where(SavedItem.id == saved_id, SavedItem.client_id == client_id)
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved item not found.")
    return saved
