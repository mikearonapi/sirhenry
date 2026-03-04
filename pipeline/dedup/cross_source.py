"""Cross-source transaction deduplication.

Detects duplicate transactions that exist from different data sources
(e.g., CSV import + Plaid sync) within the same account. Uses fuzzy
matching on date, amount, and description since hash schemes differ
across sources.
"""
import logging
from datetime import timedelta
from difflib import SequenceMatcher

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import Transaction

logger = logging.getLogger(__name__)


async def find_cross_source_duplicates(
    session: AsyncSession,
    account_id: int,
    date_tolerance_days: int = 2,
    amount_tolerance: float = 0.01,
) -> list[dict]:
    """Find potential duplicate transactions across data sources in the same account.

    Returns a list of candidate pairs with confidence scores.
    Each pair: {plaid_tx_id, csv_tx_id, plaid_date, csv_date, amount, confidence, description_similarity}
    """
    result = await session.execute(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.is_excluded.is_(False),
        ).order_by(Transaction.date)
    )
    all_txns = list(result.scalars().all())

    plaid_txns = [t for t in all_txns if t.data_source == "plaid"]
    csv_txns = [t for t in all_txns if t.data_source in ("csv", "monarch")]

    if not plaid_txns or not csv_txns:
        return []

    candidates: list[dict] = []
    matched_csv_ids: set[int] = set()

    for ptx in plaid_txns:
        best_match = None
        best_score = 0.0

        for ctx in csv_txns:
            if ctx.id in matched_csv_ids:
                continue

            # Date check
            date_diff = abs((ptx.date - ctx.date).days)
            if date_diff > date_tolerance_days:
                continue

            # Amount check
            if abs(ptx.amount - ctx.amount) > amount_tolerance:
                continue

            # Description similarity
            p_desc = (ptx.merchant_name or ptx.description or "").lower()
            c_desc = (ctx.description or "").lower()
            desc_sim = SequenceMatcher(None, p_desc, c_desc).ratio()

            # Confidence score: exact amount + close date = high confidence
            confidence = 0.5  # base for amount match
            if date_diff == 0:
                confidence += 0.3
            elif date_diff == 1:
                confidence += 0.15
            if desc_sim > 0.6:
                confidence += 0.2

            if confidence > best_score:
                best_score = confidence
                best_match = (ctx, desc_sim)

        if best_match and best_score >= 0.5:
            ctx, desc_sim = best_match
            matched_csv_ids.add(ctx.id)
            candidates.append({
                "plaid_tx_id": ptx.id,
                "csv_tx_id": ctx.id,
                "plaid_date": ptx.date.isoformat(),
                "csv_date": ctx.date.isoformat(),
                "amount": ptx.amount,
                "confidence": round(best_score, 2),
                "description_similarity": round(desc_sim, 2),
                "plaid_description": ptx.merchant_name or ptx.description,
                "csv_description": ctx.description,
            })

    return candidates


async def auto_resolve_duplicates(
    session: AsyncSession,
    account_id: int,
    min_confidence: float = 0.8,
) -> dict:
    """Auto-resolve obvious duplicate pairs (high confidence).

    Keeps the Plaid version (richer metadata), excludes the CSV version.
    Returns summary: {resolved: int, skipped: int}
    """
    candidates = await find_cross_source_duplicates(session, account_id)

    resolved = 0
    skipped = 0

    for pair in candidates:
        if pair["confidence"] >= min_confidence:
            await session.execute(
                update(Transaction)
                .where(Transaction.id == pair["csv_tx_id"])
                .values(
                    is_excluded=True,
                    notes=f"[auto-dedup] Duplicate of Plaid tx #{pair['plaid_tx_id']}",
                )
            )
            resolved += 1
        else:
            skipped += 1

    if resolved > 0:
        await session.flush()
        logger.info(f"Auto-resolved {resolved} duplicates for account {account_id}")

    return {"resolved": resolved, "skipped": skipped, "total_candidates": len(candidates)}
