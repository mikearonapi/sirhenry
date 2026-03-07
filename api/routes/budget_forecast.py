"""Budget forecasting, velocity, and unbudgeted category endpoints."""
import calendar
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    BudgetForecastOut, SpendVelocityOut, UnbudgetedCategoryOut,
)
from pipeline.db.schema import Transaction
from pipeline.db import Budget
from pipeline.planning.budget_forecast import BudgetForecastEngine
from pipeline.planning.budget_actuals import fetch_actuals as _fetch_actuals, INTERNAL_TRANSFER_CATEGORIES

router = APIRouter(tags=["budget"])


@router.get("/unbudgeted", response_model=list[UnbudgetedCategoryOut])
async def unbudgeted_categories(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Return categories that have actual spending but no budget set."""
    budgeted_result = await session.execute(
        select(Budget.category).where(Budget.year == year, Budget.month == month)
    )
    budgeted_cats = {row[0] for row in budgeted_result.all()}

    actuals = await _fetch_actuals(session, year, month)

    unbudgeted = [
        {"category": cat, "actual_amount": round(amount, 2)}
        for cat, amount in actuals.items()
        if cat not in budgeted_cats
    ]
    return sorted(unbudgeted, key=lambda x: x["actual_amount"], reverse=True)


@router.get("/forecast", response_model=BudgetForecastOut)
async def budget_forecast(
    year: int = Query(None),
    month: int = Query(None, ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Predicted spending by category for next month based on historical patterns."""
    now = datetime.now(timezone.utc)
    y = year or now.year
    m = month or now.month
    result = await session.execute(
        select(
            Transaction.effective_category,
            Transaction.period_year,
            Transaction.period_month,
            func.sum(Transaction.amount).label("total"),
        )
        .where(
            Transaction.is_excluded.is_(False),
            Transaction.amount < 0,
            Transaction.effective_category.notin_(INTERNAL_TRANSFER_CATEGORIES),
        )
        .group_by(Transaction.effective_category, Transaction.period_year, Transaction.period_month)
    )
    rows = result.all()
    # Build flat transaction list in the format the engine expects
    flat_transactions: list[dict] = []
    for row in rows:
        cat = row.effective_category
        if not cat:
            continue
        flat_transactions.append({
            "effective_category": cat,
            "period_month": row.period_month,
            "amount": -abs(float(row.total or 0)),  # Engine expects negative amounts for expenses
        })

    recurring_result = await session.execute(
        select(Budget.category, Budget.budget_amount)
        .where(Budget.year == y, Budget.month == m)
    )
    recurring_total = sum(r.budget_amount for r in recurring_result.all())

    forecast = BudgetForecastEngine.forecast_next_month(flat_transactions, recurring_total, m, y)
    seasonal = BudgetForecastEngine.detect_seasonal_patterns(flat_transactions)
    return {"forecast": forecast, "seasonal": seasonal, "target_month": m, "target_year": y}


@router.get("/velocity", response_model=list[SpendVelocityOut])
async def spend_velocity(
    year: int = Query(None),
    month: int = Query(None, ge=1, le=12),
    session: AsyncSession = Depends(get_session),
):
    """Current month spend velocity and projected month-end by category."""
    now = datetime.now(timezone.utc)
    y = year or now.year
    m = month or now.month
    days_in_month = calendar.monthrange(y, m)[1]
    days_elapsed = min(now.day, days_in_month) if y == now.year and m == now.month else days_in_month

    actuals = await _fetch_actuals(session, y, m)
    budgets_result = await session.execute(
        select(Budget).where(Budget.year == y, Budget.month == m)
    )
    budgets_list = list(budgets_result.scalars().all())

    budget_items = [
        {"category": b.category, "budget_amount": b.budget_amount}
        for b in budgets_list
    ]
    velocity = BudgetForecastEngine.spending_velocity(
        budget_items, actuals, days_elapsed, days_in_month
    )
    return velocity
