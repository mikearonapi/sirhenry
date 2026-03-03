"""Retirement — HENRY retirement planning profiles CRUD."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import RetirementProfile
from pipeline.planning.retirement import RetirementCalculator

# Import sub-router and shared Pydantic models (defined in retirement_scenarios
# to avoid circular imports)
from api.routes.retirement_scenarios import (
    router as scenarios_router,
    DebtPayoffIn,
    RetirementProfileIn,
    RetirementResultsOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/retirement", tags=["retirement"])

# Include sub-routers
router.include_router(scenarios_router)


# ---------------------------------------------------------------------------
# Pydantic Models (local to this module)
# ---------------------------------------------------------------------------
class RetirementProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    current_age: int
    retirement_age: int
    life_expectancy: int
    current_annual_income: float
    expected_income_growth_pct: float
    expected_social_security_monthly: float
    social_security_start_age: int
    pension_monthly: float
    other_retirement_income_monthly: float
    current_retirement_savings: float
    current_other_investments: float
    monthly_retirement_contribution: float
    employer_match_pct: float
    employer_match_limit_pct: float
    desired_annual_retirement_income: float | None
    income_replacement_pct: float
    healthcare_annual_estimate: float
    additional_annual_expenses: float
    inflation_rate_pct: float
    pre_retirement_return_pct: float
    post_retirement_return_pct: float
    tax_rate_in_retirement_pct: float
    current_annual_expenses: float | None
    debt_payoffs: list[DebtPayoffIn] = []
    # Computed results
    target_nest_egg: float | None
    projected_nest_egg_at_retirement: float | None
    monthly_savings_needed: float | None
    retirement_readiness_pct: float | None
    years_money_will_last: float | None
    projected_monthly_retirement_income: float | None
    savings_gap: float | None
    fire_number: float | None
    coast_fire_number: float | None
    earliest_retirement_age: int | None
    is_primary: bool
    last_computed_at: str | None
    notes: str | None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/profiles", response_model=list[RetirementProfileOut])
async def list_profiles(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(RetirementProfile).order_by(RetirementProfile.is_primary.desc(), RetirementProfile.created_at.desc())
    )
    profiles = list(result.scalars().all())
    return [_profile_out(p) for p in profiles]


@router.post("/profiles", response_model=RetirementProfileOut)
async def create_profile(body: RetirementProfileIn, session: AsyncSession = Depends(get_session)):
    data = body.model_dump()
    if data.get("is_primary"):
        from sqlalchemy import update as sa_update
        await session.execute(
            sa_update(RetirementProfile).values(is_primary=False)
        )

    debt_payoffs = data.pop("debt_payoffs", [])
    data["debt_payoffs_json"] = json.dumps([d if isinstance(d, dict) else d.model_dump() for d in debt_payoffs]) if debt_payoffs else None

    profile = RetirementProfile(**data)
    session.add(profile)
    await session.flush()

    results = RetirementCalculator.from_db_row(profile)
    _apply_results(profile, results)
    await session.flush()

    return _profile_out(profile)


@router.patch("/profiles/{profile_id}", response_model=RetirementProfileOut)
async def update_profile(
    profile_id: int,
    body: RetirementProfileIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(RetirementProfile).where(RetirementProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")

    updates = body.model_dump()
    debt_payoffs = updates.pop("debt_payoffs", [])
    updates["debt_payoffs_json"] = json.dumps(debt_payoffs) if debt_payoffs else None
    for k, v in updates.items():
        setattr(profile, k, v)
    profile.updated_at = datetime.now(timezone.utc)

    # Recompute
    results = RetirementCalculator.from_db_row(profile)
    _apply_results(profile, results)
    await session.flush()

    return _profile_out(profile)


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(RetirementProfile).where(RetirementProfile.id == profile_id))
    return {"deleted": profile_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _apply_results(profile: RetirementProfile, results):
    profile.target_nest_egg = round(results.target_nest_egg, 0)
    profile.projected_nest_egg_at_retirement = round(results.projected_nest_egg, 0)
    profile.monthly_savings_needed = round(results.monthly_savings_needed, 0)
    profile.retirement_readiness_pct = round(results.retirement_readiness_pct, 1)
    profile.years_money_will_last = round(results.years_money_will_last, 1)
    profile.projected_monthly_retirement_income = round(results.projected_monthly_income, 0)
    profile.savings_gap = round(results.savings_gap, 0)
    profile.fire_number = round(results.fire_number, 0)
    profile.coast_fire_number = round(results.coast_fire_number, 0)
    profile.earliest_retirement_age = results.earliest_retirement_age
    profile.last_computed_at = datetime.now(timezone.utc)


def _profile_out(p: RetirementProfile) -> RetirementProfileOut:
    debt_payoffs = []
    if hasattr(p, "debt_payoffs_json") and p.debt_payoffs_json:
        try:
            debt_payoffs = [DebtPayoffIn(**d) for d in json.loads(p.debt_payoffs_json)]
        except (json.JSONDecodeError, TypeError):
            pass

    return RetirementProfileOut(
        id=p.id,
        name=p.name,
        current_age=p.current_age,
        retirement_age=p.retirement_age,
        life_expectancy=p.life_expectancy,
        current_annual_income=p.current_annual_income,
        expected_income_growth_pct=p.expected_income_growth_pct,
        expected_social_security_monthly=p.expected_social_security_monthly,
        social_security_start_age=p.social_security_start_age,
        pension_monthly=p.pension_monthly,
        other_retirement_income_monthly=p.other_retirement_income_monthly,
        current_retirement_savings=p.current_retirement_savings,
        current_other_investments=p.current_other_investments,
        monthly_retirement_contribution=p.monthly_retirement_contribution,
        employer_match_pct=p.employer_match_pct,
        employer_match_limit_pct=p.employer_match_limit_pct,
        desired_annual_retirement_income=p.desired_annual_retirement_income,
        income_replacement_pct=p.income_replacement_pct,
        healthcare_annual_estimate=p.healthcare_annual_estimate,
        additional_annual_expenses=p.additional_annual_expenses,
        inflation_rate_pct=p.inflation_rate_pct,
        pre_retirement_return_pct=p.pre_retirement_return_pct,
        post_retirement_return_pct=p.post_retirement_return_pct,
        tax_rate_in_retirement_pct=p.tax_rate_in_retirement_pct,
        current_annual_expenses=getattr(p, "current_annual_expenses", None),
        debt_payoffs=debt_payoffs,
        target_nest_egg=p.target_nest_egg,
        projected_nest_egg_at_retirement=p.projected_nest_egg_at_retirement,
        monthly_savings_needed=p.monthly_savings_needed,
        retirement_readiness_pct=p.retirement_readiness_pct,
        years_money_will_last=p.years_money_will_last,
        projected_monthly_retirement_income=p.projected_monthly_retirement_income,
        savings_gap=p.savings_gap,
        fire_number=p.fire_number,
        coast_fire_number=p.coast_fire_number,
        earliest_retirement_age=getattr(p, "earliest_retirement_age", None),
        is_primary=p.is_primary,
        last_computed_at=p.last_computed_at.isoformat() if p.last_computed_at else None,
        notes=p.notes,
    )
