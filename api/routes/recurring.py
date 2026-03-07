"""Recurring transactions — detection and management."""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import RecurringOut, RecurringSummaryOut, RecurringUpdateIn
from pipeline.db.schema import Transaction
from pipeline.db import RecurringTransaction
from pipeline.db.recurring_detection import detect_recurring_transactions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recurring", tags=["recurring"])

# Single source of truth for frequency → annual multiplier
FREQ_TO_ANNUAL: dict[str, float] = {
    "monthly": 12, "annual": 1, "quarterly": 4, "weekly": 52, "bi-weekly": 26,
}


def _to_recurring_out(r: RecurringTransaction) -> RecurringOut:
    """Convert a RecurringTransaction ORM row to the API response model."""
    freq_mult = FREQ_TO_ANNUAL.get(r.frequency, 12)
    return RecurringOut(
        id=r.id, name=r.name, amount=r.amount, frequency=r.frequency,
        category=r.category, segment=r.segment, status=r.status,
        last_seen_date=str(r.last_seen_date) if r.last_seen_date else None,
        next_expected_date=str(r.next_expected_date) if r.next_expected_date else None,
        is_auto_detected=r.is_auto_detected, notes=r.notes,
        annual_cost=round(abs(r.amount) * freq_mult, 2),
    )


@router.get("", response_model=list[RecurringOut])
async def list_recurring(
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    q = select(RecurringTransaction)
    if status:
        q = q.where(RecurringTransaction.status == status)
    q = q.order_by(RecurringTransaction.amount.desc())
    result = await session.execute(q)
    return [_to_recurring_out(r) for r in result.scalars().all()]


@router.patch("/{recurring_id}", response_model=RecurringOut)
async def update_recurring(
    recurring_id: int,
    body: RecurringUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    values = body.model_dump(exclude_unset=True)
    if values:
        values["updated_at"] = datetime.now(timezone.utc)
        await session.execute(
            update(RecurringTransaction)
            .where(RecurringTransaction.id == recurring_id)
            .values(**values)
        )
    result = await session.execute(
        select(RecurringTransaction).where(RecurringTransaction.id == recurring_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring item not found")
    return _to_recurring_out(r)


@router.post("/detect", response_model=dict)
async def detect_recurring(
    lookback_months: int = Query(6, ge=3, le=24),
    session: AsyncSession = Depends(get_session),
):
    """
    Auto-detect recurring transactions by finding descriptions that appear
    with similar amounts on regular intervals.
    """
    since = datetime.now(timezone.utc) - timedelta(days=lookback_months * 30)
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.date >= since,
            Transaction.amount < 0,
            Transaction.is_excluded == False,
        )
        .order_by(Transaction.description, Transaction.date)
    )
    transactions = list(result.scalars().all())
    return await detect_recurring_transactions(session, transactions)


@router.get("/summary", response_model=RecurringSummaryOut)
async def recurring_summary(session: AsyncSession = Depends(get_session)):
    """Return total monthly and annual recurring cost."""
    result = await session.execute(
        select(RecurringTransaction).where(RecurringTransaction.status == "active")
    )
    items = list(result.scalars().all())

    freq_to_monthly = {"monthly": 1, "quarterly": 1/3, "annual": 1/12, "weekly": 4.33, "bi-weekly": 2.17}
    total_monthly = sum(abs(r.amount) * freq_to_monthly.get(r.frequency, 1) for r in items)
    total_annual = total_monthly * 12

    by_category: dict[str, float] = defaultdict(float)
    for r in items:
        by_category[r.category or "Unknown"] += abs(r.amount) * freq_to_monthly.get(r.frequency, 1)

    return {
        "total_monthly_cost": round(total_monthly, 2),
        "total_annual_cost": round(total_annual, 2),
        "subscription_count": len(items),
        "by_category": dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True)),
    }
