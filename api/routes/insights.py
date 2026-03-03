import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    InsightsOut,
    OutlierFeedbackIn,
    OutlierFeedbackOut,
)
from pipeline.analytics.insights import compute_annual_insights
from pipeline.db.schema import OutlierFeedback, Transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


def _extract_pattern(description: str) -> str:
    """Extract a stable matching pattern from a transaction description."""
    cleaned = re.sub(r"\d{2,}", "", description)
    cleaned = re.sub(r"[#*\-/]+", " ", cleaned)
    tokens = [t.strip() for t in cleaned.split() if len(t.strip()) >= 3]
    return " ".join(tokens[:4]).upper() if tokens else description.upper()[:50]


@router.get("/annual", response_model=InsightsOut)
async def get_annual_insights(
    year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """
    Compute comprehensive annual insights including outlier detection,
    budget normalization, seasonal patterns, category trends, and
    year-over-year comparison.
    """
    year = year or datetime.now(timezone.utc).year
    data = await compute_annual_insights(session, year)
    return InsightsOut(**data)


@router.post("/outlier-feedback", response_model=OutlierFeedbackOut)
async def submit_outlier_feedback(
    body: OutlierFeedbackIn,
    session: AsyncSession = Depends(get_session),
):
    """
    Submit or update user classification for an outlier transaction.
    Classifications: recurring, one_time, not_outlier.
    """
    tx_result = await session.execute(
        select(Transaction).where(Transaction.id == body.transaction_id)
    )
    tx = tx_result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    pattern = _extract_pattern(tx.description)

    existing = await session.execute(
        select(OutlierFeedback).where(
            OutlierFeedback.transaction_id == body.transaction_id
        )
    )
    feedback = existing.scalar_one_or_none()

    if feedback:
        await session.execute(
            update(OutlierFeedback)
            .where(OutlierFeedback.id == feedback.id)
            .values(
                classification=body.classification,
                user_note=body.user_note,
                apply_to_future=body.apply_to_future,
                description_pattern=pattern,
                category=tx.effective_category,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()
        refreshed = await session.execute(
            select(OutlierFeedback).where(OutlierFeedback.id == feedback.id)
        )
        feedback = refreshed.scalar_one()
    else:
        feedback = OutlierFeedback(
            transaction_id=body.transaction_id,
            classification=body.classification,
            user_note=body.user_note,
            description_pattern=pattern,
            category=tx.effective_category,
            apply_to_future=body.apply_to_future,
            year=body.year,
        )
        session.add(feedback)
        await session.flush()
        await session.refresh(feedback)

    logger.info(
        "Outlier feedback: txn=%d classified=%s pattern=%s",
        body.transaction_id,
        body.classification,
        pattern,
    )
    return OutlierFeedbackOut.model_validate(feedback)


@router.get("/outlier-feedback", response_model=list[OutlierFeedbackOut])
async def list_outlier_feedback(
    year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List all outlier feedback for a year (or all years)."""
    stmt = select(OutlierFeedback).order_by(OutlierFeedback.created_at.desc())
    if year is not None:
        stmt = stmt.where(OutlierFeedback.year == year)
    result = await session.execute(stmt)
    return [OutlierFeedbackOut.model_validate(f) for f in result.scalars().all()]


@router.delete("/outlier-feedback/{feedback_id}")
async def delete_outlier_feedback(
    feedback_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove outlier feedback (un-review a transaction)."""
    result = await session.execute(
        select(OutlierFeedback).where(OutlierFeedback.id == feedback_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Feedback not found")

    await session.execute(
        delete(OutlierFeedback).where(OutlierFeedback.id == feedback_id)
    )
    return {"ok": True}
