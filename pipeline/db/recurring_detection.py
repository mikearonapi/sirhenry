"""Recurring transaction detection — pattern matching and frequency analysis.

Analyzes transaction history to identify charges that recur on a regular
interval (weekly, monthly, quarterly, annual).
"""
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import RecurringTransaction, Transaction


def _normalize_description(desc: str) -> str:
    """Collapse digits and trim to produce a grouping key."""
    return re.sub(r"\d+", "#", desc.lower().strip())[:40]


def _detect_frequency(gaps: list[int]) -> str | None:
    """Return frequency label if average gap matches a known interval, else None."""
    if not gaps:
        return None
    avg_gap = sum(gaps) / len(gaps)
    if 25 <= avg_gap <= 35:
        return "monthly"
    if 85 <= avg_gap <= 95:
        return "quarterly"
    if 350 <= avg_gap <= 380:
        return "annual"
    if 6 <= avg_gap <= 9:
        return "weekly"
    return None


FREQUENCY_DAYS = {"monthly": 30, "quarterly": 90, "annual": 365, "weekly": 7}


async def detect_recurring_transactions(
    session: AsyncSession,
    transactions: list[Transaction],
) -> list[dict]:
    """Analyse *transactions* for recurring patterns and persist new detections.

    Returns a list of summary dicts ``{"detected": int, "total_checked": int}``.
    New ``RecurringTransaction`` rows are added to the session (but NOT committed
    — the caller's ``get_session`` dependency handles that).

    Parameters
    ----------
    session:
        The active async DB session (needed to check for existing records and
        to add new ``RecurringTransaction`` rows).
    transactions:
        Pre-fetched outflow transactions to analyse.  The caller is responsible
        for the query filters (date range, amount < 0, etc.).
    """

    # Group by normalised description
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        key = _normalize_description(tx.description)
        groups[key].append(tx)

    detected = 0
    for key, txs in groups.items():
        if len(txs) < 2:
            continue

        amounts = [abs(t.amount) for t in txs]
        avg_amount = sum(amounts) / len(amounts)

        # Variance must be small (< 10% + $2 buffer)
        if max(amounts) - min(amounts) > avg_amount * 0.10 + 2:
            continue

        # Determine frequency from inter-transaction gaps
        dates = sorted(t.date for t in txs)
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        frequency = _detect_frequency(gaps)
        if frequency is None:
            continue

        # Upsert — only create if no existing record with same pattern
        existing = await session.execute(
            select(RecurringTransaction).where(
                RecurringTransaction.description_pattern == key
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        last_tx = max(txs, key=lambda t: t.date)
        next_date = last_tx.date + timedelta(
            days=FREQUENCY_DAYS.get(frequency, 30)
        )
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
    return {"detected": detected, "total_checked": len(transactions)}
