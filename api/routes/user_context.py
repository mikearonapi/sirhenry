"""User Context — persistent learned facts for AI personalization."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db.models import (
    get_active_user_context,
    upsert_user_context,
    delete_user_context,
)

router = APIRouter(prefix="/user-context", tags=["user-context"])


class UserContextOut(BaseModel):
    id: int
    category: str
    key: str
    value: str
    source: str
    confidence: float
    is_active: bool
    created_at: str
    updated_at: str


class UserContextIn(BaseModel):
    category: str
    key: str
    value: str
    source: str = "manual"


@router.get("")
async def list_user_context(
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    facts = await get_active_user_context(session, category=category)
    return {
        "count": len(facts),
        "facts": [
            UserContextOut(
                id=f.id,
                category=f.category,
                key=f.key,
                value=f.value,
                source=f.source,
                confidence=f.confidence,
                is_active=f.is_active,
                created_at=str(f.created_at),
                updated_at=str(f.updated_at),
            )
            for f in facts
        ],
    }


@router.post("")
async def create_or_update_user_context(
    body: UserContextIn,
    session: AsyncSession = Depends(get_session),
):
    ctx = await upsert_user_context(session, body.model_dump())
    return UserContextOut(
        id=ctx.id,
        category=ctx.category,
        key=ctx.key,
        value=ctx.value,
        source=ctx.source,
        confidence=ctx.confidence,
        is_active=ctx.is_active,
        created_at=str(ctx.created_at),
        updated_at=str(ctx.updated_at),
    )


@router.delete("/{context_id}")
async def remove_user_context(
    context_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_user_context(session, context_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Context entry not found")
    return {"success": True, "deleted_id": context_id}
