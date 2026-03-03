"""Recurring transactions — detection and management."""
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import RecurringOut, RecurringSummaryOut, RecurringUpdateIn
from pipeline.db.schema import Transaction
from pipeline.db import RecurringTransaction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recurring", tags=["recurring"])


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
    items = list(result.scalars().all())

    out = []
    for r in items:
        freq_mult = {"monthly": 12, "annual": 1, "quarterly": 4, "weekly": 52, "bi-weekly": 26}.get(r.frequency, 12)
        out.append(RecurringOut(
            id=r.id, name=r.name, amount=r.amount, frequency=r.frequency,
            category=r.category, segment=r.segment, status=r.status,
            last_seen_date=str(r.last_seen_date) if r.last_seen_date else None,
            next_expected_date=str(r.next_expected_date) if r.next_expected_date else None,
            is_auto_detected=r.is_auto_detected, notes=r.notes,
            annual_cost=round(abs(r.amount) * freq_mult, 2),
        ))
    return out


@router.patch("/{recurring_id}", response_model=RecurringOut)
async def update_recurring(
    recurring_id: int,
    body: RecurringUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
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
    r = result.scalar_one()
    freq_mult = {"monthly": 12, "annual": 1, "quarterly": 4, "weekly": 52, "bi-weekly": 26}.get(r.frequency, 12)
    return RecurringOut(
        id=r.id, name=r.name, amount=r.amount, frequency=r.frequency,
        category=r.category, segment=r.segment, status=r.status,
        last_seen_date=str(r.last_seen_date) if r.last_seen_date else None,
        next_expected_date=str(r.next_expected_date) if r.next_expected_date else None,
        is_auto_detected=r.is_auto_detected, notes=r.notes,
        annual_cost=round(abs(r.amount) * freq_mult, 2),
    )


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

    # Group by normalized description
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        key = re.sub(r"\d+", "#", tx.description.lower().strip())[:40]
        groups[key].append(tx)

    detected = 0
    for key, txs in groups.items():
        if len(txs) < 2:
            continue
        amounts = [abs(t.amount) for t in txs]
        avg_amount = sum(amounts) / len(amounts)
        # Check variance is small (< 10%)
        if max(amounts) - min(amounts) > avg_amount * 0.10 + 2:
            continue

        # Check frequency
        dates = sorted(t.date for t in txs)
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0

        if 25 <= avg_gap <= 35:
            frequency = "monthly"
        elif 85 <= avg_gap <= 95:
            frequency = "quarterly"
        elif 350 <= avg_gap <= 380:
            frequency = "annual"
        elif 6 <= avg_gap <= 9:
            frequency = "weekly"
        else:
            continue

        # Upsert recurring record
        existing = await session.execute(
            select(RecurringTransaction).where(
                RecurringTransaction.description_pattern == key
            )
        )
        rec = existing.scalar_one_or_none()
        if not rec:
            last_tx = max(txs, key=lambda t: t.date)
            next_date = last_tx.date + timedelta(days={"monthly": 30, "quarterly": 90, "annual": 365, "weekly": 7}.get(frequency, 30))
            rec = RecurringTransaction(
                name=txs[0].description[:100],
                description_pattern=key,
                amount=-avg_amount,
                frequency=frequency,
                category=txs[-1].effective_category,
                segment=txs[-1].effective_segment or "personal",
                last_seen_date=max(t.date for t in txs),
                next_expected_date=next_date,
                first_seen_date=min(t.date for t in txs),
                is_auto_detected=True,
            )
            session.add(rec)
            detected += 1

    await session.flush()
    return {"detected": detected, "total_checked": len(groups)}


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
