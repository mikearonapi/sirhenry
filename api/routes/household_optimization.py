"""Household optimization, W-4, tax threshold, and filing comparison endpoints."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import FilingComparisonIn, OptimizeIn, W4OptimizeIn, TaxThresholdIn
from pipeline.db import HouseholdProfile, BenefitPackage, HouseholdOptimization
from pipeline.planning.household import HouseholdEngine
from pipeline.planning.thresholds import compute_tax_thresholds
from pipeline.planning.w4 import compute_w4_recommendations

logger = logging.getLogger(__name__)
router = APIRouter(tags=["household"])


# ---------------------------------------------------------------------------
# Optimization
# ---------------------------------------------------------------------------

@router.post("/optimize")
async def optimize(body: OptimizeIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(HouseholdProfile).where(HouseholdProfile.id == body.household_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")

    ben_result = await session.execute(
        select(BenefitPackage).where(BenefitPackage.household_id == body.household_id)
    )
    benefits = {b.spouse: b for b in ben_result.scalars().all()}
    benefits_a = {c.name: getattr(benefits.get("a"), c.name, None) for c in BenefitPackage.__table__.columns} if "a" in benefits else {}
    benefits_b = {c.name: getattr(benefits.get("b"), c.name, None) for c in BenefitPackage.__table__.columns} if "b" in benefits else {}

    opt = HouseholdEngine.full_optimization(
        spouse_a_income=profile.spouse_a_income,
        spouse_b_income=profile.spouse_b_income,
        benefits_a=benefits_a,
        benefits_b=benefits_b,
        dependents_json=profile.dependents_json or "[]",
        state=profile.state or "CA",
    )

    tax_year = body.tax_year or datetime.now(timezone.utc).year
    rec = HouseholdOptimization(
        household_id=body.household_id,
        tax_year=tax_year,
        optimal_filing_status=opt["filing"]["recommendation"],
        mfj_tax=opt["filing"]["mfj_tax"],
        mfs_tax=opt["filing"]["mfs_tax"],
        filing_savings=opt["filing"]["filing_savings"],
        optimal_retirement_strategy_json=json.dumps(opt["retirement"]),
        optimal_insurance_selection=json.dumps(opt["insurance"]),
        childcare_strategy_json=json.dumps(opt["childcare"]),
        total_annual_savings=opt["total_annual_savings"],
        recommendations_json=json.dumps(opt["recommendations"]),
    )
    session.add(rec)
    await session.flush()

    return {
        "household_id": body.household_id,
        "tax_year": tax_year,
        "optimal_filing_status": opt["filing"]["recommendation"],
        "mfj_tax": opt["filing"]["mfj_tax"],
        "mfs_tax": opt["filing"]["mfs_tax"],
        "filing_savings": opt["filing"]["filing_savings"],
        "retirement_strategy": opt["retirement"],
        "insurance_selection": opt["insurance"],
        "childcare_strategy": opt["childcare"],
        "total_annual_savings": opt["total_annual_savings"],
        "recommendations": opt["recommendations"],
    }


@router.get("/profiles/{profile_id}/optimization")
async def get_optimization(profile_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(HouseholdOptimization)
        .where(HouseholdOptimization.household_id == profile_id)
        .order_by(HouseholdOptimization.computed_at.desc())
        .limit(1)
    )
    opt = result.scalar_one_or_none()
    if not opt:
        raise HTTPException(404, "No optimization found. Run optimization first.")
    return {
        "household_id": opt.household_id,
        "tax_year": opt.tax_year,
        "optimal_filing_status": opt.optimal_filing_status,
        "mfj_tax": opt.mfj_tax,
        "mfs_tax": opt.mfs_tax,
        "filing_savings": opt.filing_savings,
        "retirement_strategy": json.loads(opt.optimal_retirement_strategy_json or "{}"),
        "insurance_selection": json.loads(opt.optimal_insurance_selection or "{}"),
        "childcare_strategy": json.loads(opt.childcare_strategy_json or "{}"),
        "total_annual_savings": opt.total_annual_savings,
        "recommendations": json.loads(opt.recommendations_json or "[]"),
    }


@router.post("/filing-comparison")
async def filing_comparison(body: FilingComparisonIn):
    result = HouseholdEngine.optimize_filing_status(
        body.spouse_a_income, body.spouse_b_income, body.dependents, body.state or "CA",
    )
    return result


# ---------------------------------------------------------------------------
# W-4 Optimization
# ---------------------------------------------------------------------------

@router.post("/w4-optimization")
async def w4_optimization(body: W4OptimizeIn):
    """Compute W-4 withholding recommendations for a dual-income household."""
    return compute_w4_recommendations(
        spouse_a_income=body.spouse_a_income,
        spouse_b_income=body.spouse_b_income,
        spouse_a_pay_periods=body.spouse_a_pay_periods,
        spouse_b_pay_periods=body.spouse_b_pay_periods,
        other_income=body.other_income,
        pre_tax_deductions_a=body.pre_tax_deductions_a,
        pre_tax_deductions_b=body.pre_tax_deductions_b,
        filing_status=body.filing_status,
    )


# ---------------------------------------------------------------------------
# Tax Threshold Monitor
# ---------------------------------------------------------------------------

@router.post("/tax-thresholds")
async def tax_thresholds(body: TaxThresholdIn):
    """Return proximity to key HENRY tax thresholds for a dual-income household."""
    return compute_tax_thresholds(
        spouse_a_income=body.spouse_a_income,
        spouse_b_income=body.spouse_b_income,
        capital_gains=body.capital_gains,
        qualified_dividends=body.qualified_dividends,
        pre_tax_deductions=body.pre_tax_deductions,
        filing_status=body.filing_status,
        dependents=body.dependents,
    )
