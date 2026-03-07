"""Budget routes — CRUD for monthly budget targets + actuals vs budget."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    BudgetIn, BudgetOut, BudgetSummaryOut, BudgetUpdateIn,
)
from pipeline.db.schema import Transaction
from pipeline.db import Budget
from pipeline.planning.budget_actuals import (
    fetch_actuals as _fetch_actuals,
    get_income_categories as _get_income_categories,
    INTERNAL_TRANSFER_CATEGORIES,
)

from api.routes.budget_forecast import router as forecast_router

router = APIRouter(prefix="/budget", tags=["budget"])

# Include sub-routers
router.include_router(forecast_router)


# Generic goal/savings categories applicable to any household.
_BASE_GOAL_CATEGORIES: frozenset[str] = frozenset({
    "Emergency Fund", "Vacation Fund", "Retirement Contribution",
    "Investment Contribution", "Home Improvement", "Education Fund",
})


# ---- Fixed-path endpoints BEFORE path-parameter endpoints ----


@router.get("/categories")
async def budget_categories(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Return distinct effective_category values with inferred type (income/goal/expense)."""
    q = select(Transaction.effective_category).where(
        Transaction.effective_category.isnot(None),
        Transaction.is_excluded.is_(False),
    ).distinct()
    if year:
        q = q.where(Transaction.period_year == year)
    if month:
        q = q.where(Transaction.period_month == month)
    result = await session.execute(q)
    categories = sorted([row[0] for row in result.all() if row[0]])

    income_cats = await _get_income_categories(session)

    def _category_type(cat: str) -> str:
        if cat in income_cats:
            return "income"
        if cat in _BASE_GOAL_CATEGORIES:
            return "goal"
        return "expense"

    return [{"category": cat, "category_type": _category_type(cat)} for cat in categories]


@router.get("/summary", response_model=BudgetSummaryOut)
async def budget_summary(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Return over-budget categories and overall budget health."""
    budgets_result = await session.execute(
        select(Budget).where(Budget.year == year, Budget.month == month)
    )
    budgets = list(budgets_result.scalars().all())
    actuals = await _fetch_actuals(session, year, month)

    total_budgeted = sum(b.budget_amount for b in budgets)
    total_actual_budgeted = sum(actuals.get(b.category, 0) for b in budgets)
    over_budget = [
        {"category": b.category, "budgeted": b.budget_amount, "actual": actuals.get(b.category, 0)}
        for b in budgets
        if actuals.get(b.category, 0) > b.budget_amount
    ]

    yoy_data = []
    for prev_year in range(year - 2, year):
        prev_result = await session.execute(
            select(func.sum(Transaction.amount))
            .where(
                Transaction.period_year == prev_year,
                Transaction.period_month == month,
                Transaction.is_excluded.is_(False),
                Transaction.amount < 0,
            )
        )
        prev_total = abs(float(prev_result.scalar() or 0))
        yoy_data.append({"year": prev_year, "total_expenses": round(prev_total, 2)})
    yoy_data.append({"year": year, "total_expenses": round(total_actual_budgeted, 2)})

    return {
        "year": year,
        "month": month,
        "total_budgeted": round(total_budgeted, 2),
        "total_actual": round(total_actual_budgeted, 2),
        "variance": round(total_budgeted - total_actual_budgeted, 2),
        "utilization_pct": round(
            total_actual_budgeted / total_budgeted * 100 if total_budgeted > 0 else 0, 1
        ),
        "over_budget_categories": over_budget,
        "year_over_year": yoy_data,
    }


@router.post("/copy", response_model=dict)
async def copy_budget(
    from_year: int = Query(...),
    from_month: int = Query(..., ge=1, le=12),
    to_year: int = Query(...),
    to_month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Copy all budget lines from one month to another, skipping categories that already exist."""
    source_result = await session.execute(
        select(Budget).where(Budget.year == from_year, Budget.month == from_month)
    )
    source_budgets = list(source_result.scalars().all())
    if not source_budgets:
        raise HTTPException(status_code=404, detail="No budgets found for source month")

    existing_result = await session.execute(
        select(Budget.category, Budget.segment).where(
            Budget.year == to_year, Budget.month == to_month
        )
    )
    existing_keys = {(row[0], row[1]) for row in existing_result.all()}

    copied = 0
    for b in source_budgets:
        if (b.category, b.segment) in existing_keys:
            continue
        session.add(Budget(
            year=to_year,
            month=to_month,
            category=b.category,
            segment=b.segment,
            budget_amount=b.budget_amount,
            notes=b.notes,
        ))
        copied += 1

    await session.flush()
    return {
        "copied": copied,
        "from": f"{from_year}-{from_month:02d}",
        "to": f"{to_year}-{to_month:02d}",
    }


@router.post("/auto-generate", response_model=dict)
async def auto_generate_budget(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Generate a smart budget based on spending patterns. Returns preview (does NOT save)."""
    from pipeline.planning.smart_defaults import generate_smart_budget
    lines = await generate_smart_budget(session, year, month)
    total = sum(line["budget_amount"] for line in lines)
    return {"lines": lines, "total": round(total, 2), "year": year, "month": month}


@router.post("/auto-generate/apply", response_model=dict)
async def apply_auto_budget(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Generate and save a smart budget for the given month."""
    from pipeline.planning.smart_defaults import generate_smart_budget
    lines = await generate_smart_budget(session, year, month)

    # Check existing budgets
    existing_result = await session.execute(
        select(Budget.category, Budget.segment).where(
            Budget.year == year, Budget.month == month
        )
    )
    existing_keys = {(row[0], row[1]) for row in existing_result.all()}

    created = 0
    for line in lines:
        key = (line["category"], line["segment"])
        if key in existing_keys:
            continue
        session.add(Budget(
            year=year,
            month=month,
            category=line["category"],
            segment=line["segment"],
            budget_amount=line["budget_amount"],
            notes=f"Auto-generated from {line['source']}",
        ))
        created += 1

    await session.flush()
    return {"created": created, "year": year, "month": month}


# ---- CRUD endpoints ----


@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    segment: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    q = select(Budget).where(Budget.year == year, Budget.month == month)
    if segment:
        q = q.where(Budget.segment == segment)
    result = await session.execute(q)
    budgets = list(result.scalars().all())

    actuals = await _fetch_actuals(session, year, month)

    out = []
    for b in budgets:
        actual = actuals.get(b.category, 0.0)
        variance = b.budget_amount - actual
        util = (actual / b.budget_amount * 100) if b.budget_amount > 0 else 0.0
        out.append(BudgetOut(
            id=b.id,
            year=b.year,
            month=b.month,
            category=b.category,
            segment=b.segment,
            budget_amount=b.budget_amount,
            notes=b.notes,
            actual_amount=round(actual, 2),
            variance=round(variance, 2),
            utilization_pct=round(util, 1),
        ))
    return out


@router.post("", response_model=BudgetOut)
async def create_budget(
    body: BudgetIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Budget).where(
            Budget.year == body.year,
            Budget.month == body.month,
            Budget.category == body.category,
            Budget.segment == body.segment,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.budget_amount = body.budget_amount
        existing.notes = body.notes
        existing.updated_at = datetime.now(timezone.utc)
        b = existing
    else:
        b = Budget(**body.model_dump())
        session.add(b)
    await session.flush()
    return BudgetOut(
        id=b.id, year=b.year, month=b.month, category=b.category,
        segment=b.segment, budget_amount=b.budget_amount, notes=b.notes,
    )


@router.patch("/{budget_id}", response_model=BudgetOut)
async def update_budget(
    budget_id: int,
    body: BudgetUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Budget).where(Budget.id == budget_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Budget not found")

    if body.budget_amount is not None:
        b.budget_amount = body.budget_amount
    if body.notes is not None:
        b.notes = body.notes
    b.updated_at = datetime.now(timezone.utc)
    await session.flush()

    actuals = await _fetch_actuals(session, b.year, b.month)
    actual = actuals.get(b.category, 0.0)
    variance = b.budget_amount - actual
    util = (actual / b.budget_amount * 100) if b.budget_amount > 0 else 0.0

    return BudgetOut(
        id=b.id, year=b.year, month=b.month, category=b.category,
        segment=b.segment, budget_amount=b.budget_amount, notes=b.notes,
        actual_amount=round(actual, 2),
        variance=round(variance, 2),
        utilization_pct=round(util, 1),
    )


@router.delete("/{budget_id}")
async def delete_budget(budget_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(Budget).where(Budget.id == budget_id))
    return {"deleted": budget_id}
