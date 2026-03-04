"""Goals — financial goals with progress tracking."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import GoalIn, GoalOut, GoalUpdateIn
from pipeline.db import Goal

router = APIRouter(prefix="/goals", tags=["goals"])


def _compute_goal_out(g: Goal) -> GoalOut:
    progress = (g.current_amount / g.target_amount * 100) if g.target_amount > 0 else 0.0
    months_remaining = None
    on_track = None

    if g.target_date:
        now = datetime.now(timezone.utc)
        target = g.target_date if isinstance(g.target_date, datetime) else datetime.fromisoformat(str(g.target_date))
        months_left = max(0, (target.year - now.year) * 12 + (target.month - now.month))
        months_remaining = months_left
        remaining_amount = g.target_amount - g.current_amount
        if months_left > 0 and g.monthly_contribution:
            projected = g.current_amount + g.monthly_contribution * months_left
            on_track = projected >= g.target_amount

    return GoalOut(
        id=g.id,
        name=g.name,
        description=g.description,
        goal_type=g.goal_type,
        target_amount=g.target_amount,
        current_amount=g.current_amount,
        target_date=str(g.target_date) if g.target_date else None,
        status=g.status,
        color=g.color or "#6366f1",
        icon=g.icon,
        monthly_contribution=g.monthly_contribution,
        notes=g.notes,
        progress_pct=round(progress, 1),
        months_remaining=months_remaining,
        on_track=on_track,
    )


@router.get("", response_model=list[GoalOut])
async def list_goals(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Goal).where(Goal.status != "cancelled").order_by(Goal.created_at.desc())
    )
    goals = list(result.scalars().all())
    return [_compute_goal_out(g) for g in goals]


@router.post("", response_model=GoalOut)
async def create_goal(body: GoalIn, session: AsyncSession = Depends(get_session)):
    data = body.model_dump()
    if data.get("target_date"):
        data["target_date"] = datetime.fromisoformat(data["target_date"])
    g = Goal(**data)
    session.add(g)
    await session.flush()
    return _compute_goal_out(g)


@router.patch("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: int,
    body: GoalUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Goal).where(Goal.id == goal_id))
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Goal not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates.get("status") == "completed":
        updates["completed_at"] = datetime.now(timezone.utc)
    if updates.get("target_date"):
        updates["target_date"] = datetime.fromisoformat(updates["target_date"])
    for k, v in updates.items():
        setattr(g, k, v)
    g.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return _compute_goal_out(g)


@router.delete("/{goal_id}")
async def delete_goal(goal_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(Goal).where(Goal.id == goal_id))
    return {"deleted": goal_id}
