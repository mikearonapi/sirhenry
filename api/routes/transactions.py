import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import TransactionCreateIn, TransactionListOut, TransactionOut, TransactionUpdateIn
from pipeline.db import (
    count_transactions,
    get_account,
    get_transactions,
    apply_entity_rules,
    update_transaction_category,
    update_transaction_entity,
)
from pipeline.db.schema import Transaction
from pipeline.ai.category_rules import learn_from_override

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListOut)
async def list_transactions(
    segment: Optional[str] = Query(None, description="personal | business | investment | reimbursable"),
    business_entity_id: Optional[int] = Query(None, description="Filter by business entity"),
    category: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    is_excluded: bool = Query(False),
    search: Optional[str] = Query(None, description="Search description or category"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    items = await get_transactions(
        session,
        segment=segment,
        category=category,
        business_entity_id=business_entity_id,
        year=year,
        month=month,
        account_id=account_id,
        is_excluded=is_excluded,
        search=search,
        limit=limit,
        offset=offset,
    )
    total = await count_transactions(
        session, year=year, month=month, segment=segment,
        category=category, business_entity_id=business_entity_id,
        account_id=account_id, is_excluded=is_excluded,
        search=search,
    )
    return TransactionListOut(total=total, items=[TransactionOut.model_validate(t) for t in items])


@router.get("/audit")
async def transaction_audit(
    year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Categorization quality audit: counts, top categories, uncategorized transactions."""
    filters = [Transaction.is_excluded.is_(False)]
    if year:
        filters.append(Transaction.period_year == year)

    total = (await session.execute(
        select(func.count(Transaction.id)).where(*filters)
    )).scalar() or 0

    categorized = (await session.execute(
        select(func.count(Transaction.id)).where(
            *filters,
            Transaction.effective_category.isnot(None),
            Transaction.effective_category != "",
            Transaction.effective_category != "Uncategorized",
        )
    )).scalar() or 0

    manually_reviewed = (await session.execute(
        select(func.count(Transaction.id)).where(
            *filters, Transaction.is_manually_reviewed.is_(True),
        )
    )).scalar() or 0

    uncategorized_count = total - categorized

    top_cats = (await session.execute(
        select(Transaction.effective_category, func.count(Transaction.id).label("cnt"))
        .where(
            *filters,
            Transaction.effective_category.isnot(None),
            Transaction.effective_category != "",
        )
        .group_by(Transaction.effective_category)
        .order_by(func.count(Transaction.id).desc())
        .limit(15)
    )).all()

    uncategorized_sample = []
    if uncategorized_count > 0:
        sample_result = await session.execute(
            select(Transaction.id, Transaction.date, Transaction.description, Transaction.amount)
            .where(
                *filters,
                (Transaction.effective_category.is_(None))
                | (Transaction.effective_category == "")
                | (Transaction.effective_category == "Uncategorized"),
            )
            .order_by(Transaction.date.desc())
            .limit(10)
        )
        uncategorized_sample = [
            {"id": r.id, "date": str(r.date), "description": r.description, "amount": r.amount}
            for r in sample_result.all()
        ]

    categorization_rate = round(categorized / total * 100, 1) if total > 0 else 0

    return {
        "total_transactions": total,
        "categorized": categorized,
        "uncategorized": uncategorized_count,
        "manually_reviewed": manually_reviewed,
        "categorization_rate": categorization_rate,
        "quality": "good" if categorization_rate >= 90 else "needs_attention" if categorization_rate >= 70 else "poor",
        "top_categories": [{"category": cat, "count": cnt} for cat, cnt in top_cats],
        "uncategorized_sample": uncategorized_sample,
    }


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    out = TransactionOut.model_validate(tx)

    # Attach children if this is a split parent
    children_result = await session.execute(
        select(Transaction).where(
            Transaction.parent_transaction_id == tx.id
        ).order_by(Transaction.amount.asc())
    )
    children = children_result.scalars().all()
    if children:
        out.children = [TransactionOut.model_validate(c) for c in children]

    return out


@router.patch("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: int,
    body: TransactionUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if body.category_override is not None or body.tax_category_override is not None or body.segment_override is not None:
        await update_transaction_category(
            session,
            transaction_id=transaction_id,
            category_override=body.category_override,
            tax_category_override=body.tax_category_override,
            segment_override=body.segment_override,
        )

    if body.business_entity_override is not None:
        await update_transaction_entity(session, transaction_id, body.business_entity_override)

    if body.notes is not None or body.is_excluded is not None:
        values = {}
        if body.notes is not None:
            values["notes"] = body.notes
        if body.is_excluded is not None:
            values["is_excluded"] = body.is_excluded
        await session.execute(
            update(Transaction).where(Transaction.id == transaction_id).values(**values)
        )

    await session.flush()
    result2 = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    tx_updated = result2.scalar_one()
    return TransactionOut.model_validate(tx_updated)


@router.post("", response_model=TransactionOut, status_code=201)
async def create_manual_transaction(
    body: TransactionCreateIn,
    session: AsyncSession = Depends(get_session),
):
    """Create a single manual transaction."""
    account = await get_account(session, body.account_id)
    if not account:
        raise HTTPException(404, f"Account {body.account_id} not found")

    tx = Transaction(
        account_id=body.account_id,
        date=body.date,
        description=body.description,
        amount=body.amount,
        currency=body.currency,
        segment=body.segment,
        effective_segment=body.segment,
        category=body.category,
        effective_category=body.category,
        tax_category=body.tax_category,
        effective_tax_category=body.tax_category,
        period_month=body.date.month,
        period_year=body.date.year,
        notes=body.notes,
        data_source="manual",
    )
    session.add(tx)
    await session.flush()

    # Generate hash using the auto-incremented ID
    tx.transaction_hash = hashlib.sha256(f"manual|{tx.id}".encode()).hexdigest()

    # Apply entity rules
    await apply_entity_rules(session, transaction_id=tx.id)
    await session.flush()

    # Re-fetch to get updated fields
    result = await session.execute(
        select(Transaction).where(Transaction.id == tx.id)
    )
    return TransactionOut.model_validate(result.scalar_one())
