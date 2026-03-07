"""
Budget actuals computation — expense and income category totals for a given month.

Extracted from api/routes/budget.py to break the circular import between
budget.py ↔ budget_forecast.py.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import HouseholdProfile, Transaction

# Internal transfer categories excluded from spending analysis
INTERNAL_TRANSFER_CATEGORIES = {"Transfer", "Credit Card Payment", "Savings"}

# Generic income category names applicable to any household.
# Employer-specific names are added dynamically from HouseholdProfile.
_BASE_INCOME_CATEGORIES: frozenset[str] = frozenset({
    "Other Income", "Dividend Income", "Interest Income", "Capital Gain",
    "Board / Director Income", "W-2 Wages", "1099-NEC / Consulting Income",
    "K-1 / Partnership Income", "Rental Income", "Trust Income",
})


async def get_income_categories(session: AsyncSession) -> set[str]:
    """Return the full income category set: base generic + employer-specific names from DB."""
    categories = set(_BASE_INCOME_CATEGORIES)
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    household = result.scalar_one_or_none()
    if household:
        for employer in [household.spouse_a_employer, household.spouse_b_employer]:
            if employer:
                categories.add(f"{employer} Paycheck")
                categories.add(f"{employer} Bonus")
                categories.add(f"{employer} Expenses")
    return categories


def build_expense_actuals_query(year: int, month: int):
    """Expense actuals: sum of negative amounts grouped by effective_category."""
    return (
        select(Transaction.effective_category, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.period_year == year,
            Transaction.period_month == month,
            Transaction.is_excluded.is_(False),
            Transaction.amount < 0,
            Transaction.effective_category.notin_(INTERNAL_TRANSFER_CATEGORIES),
        )
        .group_by(Transaction.effective_category)
    )


def build_income_actuals_query(year: int, month: int):
    """Income actuals: sum of positive amounts for income categories."""
    return (
        select(Transaction.effective_category, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.period_year == year,
            Transaction.period_month == month,
            Transaction.is_excluded.is_(False),
            Transaction.amount > 0,
            Transaction.effective_category.notin_(INTERNAL_TRANSFER_CATEGORIES),
        )
        .group_by(Transaction.effective_category)
    )


async def fetch_actuals(session: AsyncSession, year: int, month: int) -> dict[str, float]:
    """Fetch both expense and income actuals, merged into one dict."""
    income_categories = await get_income_categories(session)

    expense_result = await session.execute(build_expense_actuals_query(year, month))
    actuals: dict[str, float] = {
        row.effective_category: abs(float(row.total or 0))
        for row in expense_result.all()
        if row.effective_category
    }

    income_result = await session.execute(build_income_actuals_query(year, month))
    for row in income_result.all():
        if row.effective_category and row.effective_category in income_categories:
            actuals[row.effective_category] = float(row.total or 0)

    return actuals
