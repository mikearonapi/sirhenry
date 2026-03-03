"""Admin reminders — bill due dates, tax deadlines, financial calendar.

CRUD endpoints for reminders. Seeding and bulk operations are in reminders_seed.py.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import ReminderIn, ReminderOut, ReminderUpdateIn
from pipeline.db import Reminder

from api.routes.reminders_seed import (
    router as seed_router,
    seed_all_reminders,
    _advance_recurring,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reminders", tags=["reminders"])

# Include sub-routers
router.include_router(seed_router)


def _reminder_out(r: Reminder) -> ReminderOut:
    due = r.due_date if isinstance(r.due_date, datetime) else datetime.fromisoformat(str(r.due_date))
    now = datetime.now(timezone.utc)
    days_until = (due - now).days
    return ReminderOut(
        id=r.id,
        title=r.title,
        description=r.description,
        reminder_type=r.reminder_type,
        due_date=str(r.due_date),
        amount=r.amount,
        advance_notice=r.advance_notice,
        status=r.status,
        is_recurring=r.is_recurring,
        recurrence_rule=r.recurrence_rule,
        days_until_due=days_until,
        is_overdue=days_until < 0 and r.status == "pending",
    )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ReminderOut])
async def list_reminders(
    reminder_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    q = select(Reminder).where(Reminder.status != "dismissed")
    if reminder_type:
        q = q.where(Reminder.reminder_type == reminder_type)
    if status:
        q = q.where(Reminder.status == status)
    q = q.order_by(Reminder.due_date.asc())
    result = await session.execute(q)
    reminders = list(result.scalars().all())
    return [_reminder_out(r) for r in reminders]


@router.post("", response_model=ReminderOut)
async def create_reminder(body: ReminderIn, session: AsyncSession = Depends(get_session)):
    data = body.model_dump()
    data["due_date"] = datetime.fromisoformat(data["due_date"])
    r = Reminder(**data)
    session.add(r)
    await session.flush()
    return _reminder_out(r)


@router.patch("/{reminder_id}", response_model=ReminderOut)
async def update_reminder(
    reminder_id: int,
    body: ReminderUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "status" in updates and updates["status"] == "completed":
        updates["completed_at"] = datetime.now(timezone.utc)
    if "due_date" in updates:
        updates["due_date"] = datetime.fromisoformat(updates["due_date"])
    for k, v in updates.items():
        setattr(r, k, v)
    r.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Advance recurring reminders on completion
    if r.status == "completed" and r.is_recurring:
        next_r = _advance_recurring(r)
        if next_r:
            existing_next = await session.execute(
                select(Reminder).where(
                    Reminder.title == next_r.title,
                    Reminder.status.in_(["pending", "snoozed"]),
                )
            )
            if not existing_next.scalar_one_or_none():
                session.add(next_r)
                await session.flush()
                logger.info(f"Advanced recurring reminder: '{next_r.title}' due {next_r.due_date}")

    return _reminder_out(r)
