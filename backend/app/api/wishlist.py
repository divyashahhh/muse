"""Wishlist: listings a shopper saved for later."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import Session
from app.deps import ClientId
from app.models import SavedItem
from app.schemas import SavedItemIn, SavedItemOut

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[SavedItemOut])
async def list_wishlist(session: Session, client_id: ClientId) -> list[SavedItem]:
    result = await session.scalars(
        select(SavedItem)
        .where(SavedItem.client_id == client_id)
        .order_by(SavedItem.created_at.desc(), SavedItem.id.desc())
    )
    return list(result)


@router.post("", response_model=SavedItemOut, status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(body: SavedItemIn, session: Session, client_id: ClientId) -> SavedItem:
    """Saving the same link again is a no-op."""
    values = body.model_dump(mode="json")
    await session.execute(
        insert(SavedItem)
        .values(client_id=client_id, **values)
        .on_conflict_do_nothing(index_elements=["client_id", "url"])
    )
    await session.commit()
    return await session.scalar(
        select(SavedItem).where(SavedItem.client_id == client_id, SavedItem.url == values["url"])
    )


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(saved_id: int, session: Session, client_id: ClientId) -> Response:
    saved = await session.scalar(
        select(SavedItem).where(SavedItem.id == saved_id, SavedItem.client_id == client_id)
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Wishlist item not found.")
    await session.delete(saved)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
