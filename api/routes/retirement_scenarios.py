"""Retirement scenario calculations, trajectory projections, and budget snapshot.

Also defines shared Pydantic models used by both this sub-router and the
main retirement.py router (to avoid circular imports).
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import RetirementProfile
from pipeline.planning.retirement import RetirementCalculator, RetirementInputs

logger = logging.getLogger(__name__)
router = APIRouter(tags=["retirement"])


# ---------------------------------------------------------------------------
# Shared Pydantic Models (imported by retirement.py)
# ---------------------------------------------------------------------------

class DebtPayoffIn(BaseModel):
    name: str = ""
    monthly_payment: float = 0.0
    payoff_age: int = 0


class RetirementProfileIn(BaseModel):
    name: str = "My Retirement Plan"
    current_age: int
    retirement_age: int = 65
    life_expectancy: int = 90
    current_annual_income: float
    expected_income_growth_pct: float = 3.0
    expected_social_security_monthly: float = 0.0
    social_security_start_age: int = 67
    pension_monthly: float = 0.0
    other_retirement_income_monthly: float = 0.0
    current_retirement_savings: float = 0.0
    current_other_investments: float = 0.0
    monthly_retirement_contribution: float = 0.0
    employer_match_pct: float = 0.0
    employer_match_limit_pct: float = 6.0
    desired_annual_retirement_income: Optional[float] = None
    income_replacement_pct: float = 80.0
    healthcare_annual_estimate: float = 12000.0
    additional_annual_expenses: float = 0.0
    inflation_rate_pct: float = 3.0
    pre_retirement_return_pct: float = 7.0
    post_retirement_return_pct: float = 5.0
    tax_rate_in_retirement_pct: float = 22.0
    current_annual_expenses: Optional[float] = None
    debt_payoffs: list[DebtPayoffIn] = []
    is_primary: bool = False
    notes: Optional[str] = None


class RetirementResultsOut(BaseModel):
    years_to_retirement: int
    years_in_retirement: int
    annual_income_needed_today: float
    annual_income_needed_at_retirement: float
    monthly_income_needed_at_retirement: float
    target_nest_egg: float
    fire_number: float
    coast_fire_number: float
    lean_fire_number: float
    projected_nest_egg: float
    projected_monthly_income: float
    savings_gap: float
    monthly_savings_needed: float
    retirement_readiness_pct: float
    years_money_will_last: float
    on_track: bool
    current_savings_rate_pct: float
    recommended_savings_rate_pct: float
    total_monthly_contribution: float
    employer_match_monthly: float
    social_security_annual: float
    pension_annual: float
    other_income_annual: float
    total_guaranteed_income_annual: float
    portfolio_income_needed_annual: float
    debt_payoff_savings_annual: float
    earliest_retirement_age: int
    yearly_projection: list[dict]


class BudgetSnapshotOut(BaseModel):
    annual_expenses: float
    monthly_expenses: float
    categories: list[dict]
    liabilities: list[dict]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/calculate", response_model=RetirementResultsOut)
async def calculate_retirement(body: RetirementProfileIn):
    """
    Stateless calculation -- doesn't save a profile.
    Useful for real-time "what-if" slider adjustments.
    """
    data = body.model_dump()
    # Convert debt_payoffs from dicts to the format the calculator expects
    debt_payoffs_raw = data.pop("debt_payoffs", [])
    calc_data = {k: v for k, v in data.items() if k in RetirementInputs.__dataclass_fields__}
    calc_data["debt_payoffs"] = debt_payoffs_raw
    inputs = RetirementInputs(**calc_data)
    results = RetirementCalculator.calculate(inputs)
    return RetirementResultsOut(
        years_to_retirement=results.years_to_retirement,
        years_in_retirement=results.years_in_retirement,
        annual_income_needed_today=round(results.annual_income_needed_today, 0),
        annual_income_needed_at_retirement=round(results.annual_income_needed_at_retirement, 0),
        monthly_income_needed_at_retirement=round(results.monthly_income_needed_at_retirement, 0),
        target_nest_egg=round(results.target_nest_egg, 0),
        fire_number=round(results.fire_number, 0),
        coast_fire_number=round(results.coast_fire_number, 0),
        lean_fire_number=round(results.lean_fire_number, 0),
        projected_nest_egg=round(results.projected_nest_egg, 0),
        projected_monthly_income=round(results.projected_monthly_income, 0),
        savings_gap=round(results.savings_gap, 0),
        monthly_savings_needed=round(results.monthly_savings_needed, 0),
        retirement_readiness_pct=round(results.retirement_readiness_pct, 1),
        years_money_will_last=round(results.years_money_will_last, 1),
        on_track=results.on_track,
        current_savings_rate_pct=round(results.current_savings_rate_pct, 1),
        recommended_savings_rate_pct=round(results.recommended_savings_rate_pct, 1),
        total_monthly_contribution=round(results.total_monthly_contribution, 0),
        employer_match_monthly=round(results.employer_match_monthly, 0),
        social_security_annual=round(results.social_security_annual, 0),
        pension_annual=round(results.pension_annual, 0),
        other_income_annual=round(results.other_income_annual, 0),
        total_guaranteed_income_annual=round(results.total_guaranteed_income_annual, 0),
        portfolio_income_needed_annual=round(results.portfolio_income_needed_annual, 0),
        debt_payoff_savings_annual=round(results.debt_payoff_savings_annual, 0),
        earliest_retirement_age=results.earliest_retirement_age,
        yearly_projection=results.yearly_projection,
    )


@router.get("/trajectory/{profile_id}")
async def get_trajectory(profile_id: int, session: AsyncSession = Depends(get_session)):
    """
    Returns 3-scenario fan chart data (pessimistic / base / optimistic) for a given
    retirement profile.  Each scenario tweaks pre- and post-retirement returns by +/-2 pp
    relative to the profile's configured values.
    """
    result = await session.execute(
        select(RetirementProfile).where(RetirementProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Retirement profile not found")

    base_pre = profile.pre_retirement_return_pct
    base_post = profile.post_retirement_return_pct

    scenarios = [
        ("Pessimistic", base_pre - 2, base_post - 2),
        ("Base", base_pre, base_post),
        ("Optimistic", base_pre + 2, base_post + 2),
    ]

    out_scenarios = []
    base_results = None

    for name, pre_ret, post_ret in scenarios:
        inputs = RetirementInputs(
            current_age=profile.current_age,
            retirement_age=profile.retirement_age,
            life_expectancy=profile.life_expectancy,
            current_annual_income=profile.current_annual_income,
            expected_income_growth_pct=profile.expected_income_growth_pct,
            expected_social_security_monthly=profile.expected_social_security_monthly,
            social_security_start_age=profile.social_security_start_age,
            pension_monthly=profile.pension_monthly,
            other_retirement_income_monthly=profile.other_retirement_income_monthly,
            current_retirement_savings=profile.current_retirement_savings,
            current_other_investments=profile.current_other_investments,
            monthly_retirement_contribution=profile.monthly_retirement_contribution,
            employer_match_pct=profile.employer_match_pct,
            employer_match_limit_pct=profile.employer_match_limit_pct,
            desired_annual_retirement_income=profile.desired_annual_retirement_income,
            income_replacement_pct=profile.income_replacement_pct,
            healthcare_annual_estimate=profile.healthcare_annual_estimate,
            additional_annual_expenses=profile.additional_annual_expenses,
            inflation_rate_pct=profile.inflation_rate_pct,
            pre_retirement_return_pct=max(0.0, pre_ret),
            post_retirement_return_pct=max(0.0, post_ret),
            tax_rate_in_retirement_pct=profile.tax_rate_in_retirement_pct,
            current_annual_expenses=profile.current_annual_expenses,
        )
        results = RetirementCalculator.calculate(inputs)
        if name == "Base":
            base_results = results
        out_scenarios.append({
            "name": name,
            "data": [{"age": row["age"], "balance": round(row["balance"], 0)} for row in results.yearly_projection],
        })

    return {
        "scenarios": out_scenarios,
        "target_nest_egg": round(base_results.target_nest_egg, 0) if base_results else 0,
        "retirement_age": profile.retirement_age,
        "readiness_pct": round(base_results.retirement_readiness_pct, 1) if base_results else 0,
        "projected_nest_egg": round(base_results.projected_nest_egg, 0) if base_results else 0,
        "on_track": base_results.on_track if base_results else False,
    }


@router.get("/budget-snapshot", response_model=BudgetSnapshotOut)
async def budget_snapshot(session: AsyncSession = Depends(get_session)):
    """
    Pull current budget + liability data to auto-populate retirement expenses.
    Returns total annual expenses from budget and active liabilities.
    """
    from pipeline.db.schema_extended import Budget, ManualAsset, RecurringTransaction
    now = datetime.now(timezone.utc)

    # Get most recent full month of budget data
    budget_result = await session.execute(
        select(Budget.category, func.sum(Budget.budget_amount).label("total"))
        .where(Budget.year == now.year, Budget.month == now.month)
        .group_by(Budget.category)
    )
    budget_rows = budget_result.all()

    # If no current month data, try previous month
    if not budget_rows:
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1
        budget_result = await session.execute(
            select(Budget.category, func.sum(Budget.budget_amount).label("total"))
            .where(Budget.year == prev_year, Budget.month == prev_month)
            .group_by(Budget.category)
        )
        budget_rows = budget_result.all()

    categories = [{"category": row.category, "monthly": row.total, "annual": row.total * 12} for row in budget_rows]
    monthly_total = sum(row.total for row in budget_rows)

    # Also check recurring expenses not captured in budget
    recurring_result = await session.execute(
        select(RecurringTransaction)
        .where(RecurringTransaction.status == "active")
    )
    recurring_items = recurring_result.scalars().all()
    for r in recurring_items:
        if r.frequency == "monthly":
            monthly_amount = abs(r.amount)
        elif r.frequency == "annual":
            monthly_amount = abs(r.amount) / 12
        elif r.frequency == "quarterly":
            monthly_amount = abs(r.amount) / 3
        elif r.frequency == "weekly":
            monthly_amount = abs(r.amount) * 52 / 12
        elif r.frequency == "bi-weekly":
            monthly_amount = abs(r.amount) * 26 / 12
        else:
            monthly_amount = abs(r.amount)

        existing = next((c for c in categories if c["category"] == r.category), None)
        if not existing:
            categories.append({"category": r.category or r.name, "monthly": monthly_amount, "annual": monthly_amount * 12})
            monthly_total += monthly_amount

    # Get active liabilities
    liab_result = await session.execute(
        select(ManualAsset).where(ManualAsset.is_liability == True, ManualAsset.is_active == True)
    )
    liabilities = liab_result.scalars().all()
    liab_out = [{
        "name": l.name,
        "type": l.asset_type,
        "balance": l.current_value,
        "institution": l.institution,
    } for l in liabilities]

    return BudgetSnapshotOut(
        annual_expenses=round(monthly_total * 12, 0),
        monthly_expenses=round(monthly_total, 0),
        categories=categories,
        liabilities=liab_out,
    )
