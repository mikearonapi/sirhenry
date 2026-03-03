"""Household optimization, W-4, tax threshold, and filing comparison endpoints."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import HouseholdProfile, BenefitPackage, HouseholdOptimization
from pipeline.planning.household import HouseholdEngine
from pipeline.tax.constants import (
    MFJ_BRACKETS as _MFJ_BRACKETS,
    SINGLE_BRACKETS as _SINGLE_BRACKETS,
    STANDARD_DEDUCTION,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["household"])

# Derived from the central STANDARD_DEDUCTION dict
_MFJ_STANDARD_DEDUCTION = STANDARD_DEDUCTION["mfj"]
_SINGLE_STANDARD_DEDUCTION = STANDARD_DEDUCTION["single"]


def _calc_tax(taxable_income: float, brackets: list) -> float:
    """Compute federal income tax from graduated brackets."""
    tax = 0.0
    prev = 0.0
    for ceiling, rate in brackets:
        if taxable_income <= prev:
            break
        taxable_in_bracket = min(taxable_income, ceiling) - prev
        tax += taxable_in_bracket * rate
        prev = ceiling
    return max(0.0, tax)


def _marginal_rate(taxable_income: float, brackets: list) -> float:
    prev = 0.0
    for ceiling, rate in brackets:
        if taxable_income <= ceiling:
            return rate
        prev = ceiling
    return brackets[-1][1]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class FilingComparisonIn(BaseModel):
    spouse_a_income: float
    spouse_b_income: float
    state: Optional[str] = "CA"
    dependents: int = 0


class OptimizeIn(BaseModel):
    household_id: int
    tax_year: Optional[int] = None


class W4OptimizeIn(BaseModel):
    spouse_a_income: float
    spouse_b_income: float
    spouse_a_pay_periods: int = 26   # bi-weekly
    spouse_b_pay_periods: int = 26
    other_income: float = 0          # 1099 / investment income not captured in W-2
    pre_tax_deductions_a: float = 0  # 401k, HSA, health premiums
    pre_tax_deductions_b: float = 0
    filing_status: str = "mfj"


class TaxThresholdIn(BaseModel):
    spouse_a_income: float
    spouse_b_income: float
    capital_gains: float = 0
    qualified_dividends: float = 0
    pre_tax_deductions: float = 0
    filing_status: str = "mfj"
    dependents: int = 0


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
    """
    Compute W-4 withholding recommendations for a dual-income household.
    Dual earners systematically under-withhold because each employer treats
    the other spouse's income as $0 when calculating withholding.
    """
    income_a = body.spouse_a_income
    income_b = body.spouse_b_income
    combined = income_a + income_b + body.other_income

    std_ded = _MFJ_STANDARD_DEDUCTION if body.filing_status == "mfj" else _SINGLE_STANDARD_DEDUCTION

    # Actual MFJ tax owed
    taxable_mfj = max(0, combined - std_ded - body.pre_tax_deductions_a - body.pre_tax_deductions_b)
    actual_tax = _calc_tax(taxable_mfj, _MFJ_BRACKETS)

    # What each spouse will withhold (employer calculates as if they're single at their salary)
    taxable_a_as_single = max(0, income_a - _SINGLE_STANDARD_DEDUCTION - body.pre_tax_deductions_a)
    taxable_b_as_single = max(0, income_b - _SINGLE_STANDARD_DEDUCTION - body.pre_tax_deductions_b)
    withheld_a = _calc_tax(taxable_a_as_single, _SINGLE_BRACKETS)
    withheld_b = _calc_tax(taxable_b_as_single, _SINGLE_BRACKETS)
    total_withheld = withheld_a + withheld_b

    shortfall = actual_tax - total_withheld

    # Per-paycheck extra withholding to cover the shortfall
    extra_per_paycheck_a = max(0, (shortfall / 2) / body.spouse_a_pay_periods) if body.spouse_a_pay_periods > 0 else 0
    extra_per_paycheck_b = max(0, (shortfall / 2) / body.spouse_b_pay_periods) if body.spouse_b_pay_periods > 0 else 0

    marginal = _marginal_rate(taxable_mfj, _MFJ_BRACKETS)

    recommendation_lines = []
    if shortfall > 500:
        recommendation_lines.append(
            f"Your combined withholding is estimated to be short by {shortfall:,.0f}. "
            f"To avoid an underpayment penalty, consider adding extra withholding."
        )
        recommendation_lines.append(
            f"Spouse A: Add ~${extra_per_paycheck_a:,.0f} per paycheck (W-4 Step 4c)."
        )
        recommendation_lines.append(
            f"Spouse B: Add ~${extra_per_paycheck_b:,.0f} per paycheck (W-4 Step 4c)."
        )
        recommendation_lines.append(
            "Alternatively, use the IRS Tax Withholding Estimator at irs.gov/W4app for a precise calculation."
        )
    elif shortfall > 0:
        recommendation_lines.append(
            f"Minor shortfall of ~${shortfall:,.0f} estimated — within safe harbor threshold."
        )
    else:
        recommendation_lines.append("Withholding appears sufficient. You may receive a refund.")

    return {
        "spouse_a_income": income_a,
        "spouse_b_income": income_b,
        "combined_income": combined,
        "estimated_mfj_tax": round(actual_tax, 0),
        "estimated_withheld_a": round(withheld_a, 0),
        "estimated_withheld_b": round(withheld_b, 0),
        "total_estimated_withheld": round(total_withheld, 0),
        "estimated_shortfall": round(shortfall, 0),
        "extra_per_paycheck_a": round(extra_per_paycheck_a, 0),
        "extra_per_paycheck_b": round(extra_per_paycheck_b, 0),
        "marginal_rate": marginal,
        "effective_rate": round(actual_tax / combined, 4) if combined > 0 else 0,
        "recommendation": " ".join(recommendation_lines),
        "recommendation_lines": recommendation_lines,
    }


# ---------------------------------------------------------------------------
# Tax Threshold Monitor
# ---------------------------------------------------------------------------

@router.post("/tax-thresholds")
async def tax_thresholds(body: TaxThresholdIn):
    """
    Return proximity to key HENRY tax thresholds for a dual-income household.
    Each threshold includes current exposure and recommended actions.
    """
    combined = body.spouse_a_income + body.spouse_b_income
    magi_estimate = combined + body.capital_gains + body.qualified_dividends - body.pre_tax_deductions

    thresholds = []

    # 1. Additional Medicare Tax (0.9%) — kicks in above $200k single / $250k MFJ
    amt_threshold = 250_000 if body.filing_status == "mfj" else 200_000
    amt_exposure = max(0, magi_estimate - amt_threshold)
    thresholds.append({
        "id": "additional_medicare",
        "label": "Additional Medicare Tax (0.9%)",
        "threshold": amt_threshold,
        "current_magi": magi_estimate,
        "exposure": round(amt_exposure),
        "tax_impact": round(amt_exposure * 0.009),
        "proximity_pct": min(100, round((magi_estimate / amt_threshold) * 100, 1)),
        "exceeded": magi_estimate > amt_threshold,
        "description": "An extra 0.9% Medicare tax applies to wages and self-employment income above this threshold. "
                       "Cannot be avoided through pre-tax deductions (applies to wages, not MAGI).",
        "actions": [
            "No direct avoidance — this is on wages/SE income",
            "Ensure proper withholding to avoid underpayment penalty",
            "Track via W-2 Box 6 and Form 8959 at filing",
        ],
    })

    # 2. Net Investment Income Tax (3.8%) — on investment income above $250k MFJ MAGI
    niit_threshold = 250_000 if body.filing_status == "mfj" else 200_000
    investment_income = body.capital_gains + body.qualified_dividends
    niit_exposure = min(investment_income, max(0, magi_estimate - niit_threshold))
    thresholds.append({
        "id": "niit",
        "label": "Net Investment Income Tax / NIIT (3.8%)",
        "threshold": niit_threshold,
        "current_magi": magi_estimate,
        "exposure": round(niit_exposure),
        "tax_impact": round(niit_exposure * 0.038),
        "proximity_pct": min(100, round((magi_estimate / niit_threshold) * 100, 1)),
        "exceeded": magi_estimate > niit_threshold,
        "description": "3.8% surtax on net investment income (dividends, interest, capital gains) "
                       "when MAGI exceeds threshold. Reducing MAGI below threshold eliminates it.",
        "actions": [
            "Maximize 401k, HSA, and pre-tax deductions to reduce MAGI",
            "Harvest capital losses to offset gains",
            "Consider tax-exempt municipal bonds for investment income",
            "Shift investments to deferred accounts where possible",
        ],
    })

    # 3. Roth IRA Phase-out ($236,000–$246,000 MFJ 2025)
    roth_start = 236_000 if body.filing_status == "mfj" else 150_000
    roth_end = 246_000 if body.filing_status == "mfj" else 165_000
    roth_reduced = magi_estimate > roth_start
    roth_eliminated = magi_estimate >= roth_end
    thresholds.append({
        "id": "roth_ira",
        "label": "Roth IRA Direct Contribution Limit",
        "threshold": roth_start,
        "threshold_end": roth_end,
        "current_magi": magi_estimate,
        "exposure": 0,
        "tax_impact": 0,
        "proximity_pct": min(100, round((magi_estimate / roth_start) * 100, 1)),
        "exceeded": roth_eliminated,
        "partially_exceeded": roth_reduced and not roth_eliminated,
        "description": f"Direct Roth IRA contributions phase out between ${roth_start:,} and ${roth_end:,} MAGI "
                       f"({'MFJ' if body.filing_status == 'mfj' else 'Single'}). "
                       "Above the upper limit, direct contributions are not allowed.",
        "actions": [
            "Use the Backdoor Roth IRA strategy (Traditional IRA → convert to Roth) if over the limit",
            "Mega Backdoor Roth via after-tax 401k contributions if your plan allows",
            "Pre-tax deductions (401k, HSA) reduce MAGI and may restore eligibility",
        ],
    })

    # 4. Child Tax Credit Phase-out ($400k MFJ)
    ctc_threshold = 400_000 if body.filing_status == "mfj" else 200_000
    if body.dependents > 0:
        ctc_excess = max(0, magi_estimate - ctc_threshold)
        ctc_reduction = min(body.dependents * 2000, (ctc_excess / 1000) * 50)
        thresholds.append({
            "id": "child_tax_credit",
            "label": "Child Tax Credit Phase-out",
            "threshold": ctc_threshold,
            "current_magi": magi_estimate,
            "exposure": round(ctc_excess),
            "tax_impact": round(ctc_reduction),
            "proximity_pct": min(100, round((magi_estimate / ctc_threshold) * 100, 1)),
            "exceeded": magi_estimate > ctc_threshold,
            "description": f"The ${body.dependents * 2000:,} Child Tax Credit reduces by $50 for every $1,000 of "
                           f"income above ${ctc_threshold:,} (MFJ). "
                           f"With {body.dependents} dependent(s), estimated credit reduction: ${ctc_reduction:,.0f}.",
            "actions": [
                "Maximize pre-tax deductions to reduce MAGI below the threshold",
                "401k, HSA, and FSA contributions all reduce MAGI",
            ],
        })

    # 5. SALT Cap ($10,000)
    salt_cap = 10_000
    estimated_salt = (magi_estimate * 0.05)  # rough 5% effective state+local rate estimate
    thresholds.append({
        "id": "salt_cap",
        "label": "SALT Deduction Cap ($10,000)",
        "threshold": salt_cap,
        "current_magi": magi_estimate,
        "exposure": 0,
        "tax_impact": 0,
        "proximity_pct": min(100, round((estimated_salt / salt_cap) * 100, 1)),
        "exceeded": estimated_salt > salt_cap,
        "description": "State and local tax (SALT) deductions are capped at $10,000 for itemizers. "
                       "High earners in high-tax states typically cannot deduct their full state tax bill. "
                       "Standard deduction is $30,000 MFJ (2025) — compare before itemizing.",
        "actions": [
            "Verify whether itemizing or standard deduction is more beneficial",
            "Bunch deductions in alternating years (mortgage interest + SALT + charitable)",
            "Consider Donor Advised Fund to front-load charitable deductions in high-income years",
        ],
    })

    # 6. AMT Exposure (simplified check — relevant for ISO holders and high-income)
    # AMT exemption for MFJ: ~$137,000 (2025 estimated), phases out at $1,237,450
    amt_exemption = 137_000 if body.filing_status == "mfj" else 88_100
    # Rough AMT income = MAGI - pre_tax_deductions + some add-backs (simplification)
    amt_income_est = magi_estimate + body.pre_tax_deductions  # rough
    amt_taxable_est = max(0, amt_income_est - amt_exemption)
    amt_tax_est = amt_taxable_est * 0.26  # 26% AMT rate below $232k, 28% above
    regular_tax = _calc_tax(max(0, magi_estimate - body.pre_tax_deductions - _MFJ_STANDARD_DEDUCTION), _MFJ_BRACKETS)
    amt_applies = amt_tax_est > regular_tax and amt_taxable_est > 0
    thresholds.append({
        "id": "amt",
        "label": "Alternative Minimum Tax (AMT)",
        "threshold": amt_exemption,
        "current_magi": magi_estimate,
        "exposure": round(max(0, amt_tax_est - regular_tax)) if amt_applies else 0,
        "tax_impact": round(max(0, amt_tax_est - regular_tax)) if amt_applies else 0,
        "proximity_pct": min(100, round((amt_income_est / (amt_exemption + 200_000)) * 100, 1)),
        "exceeded": amt_applies,
        "description": "The AMT is a parallel tax system that disallows many deductions. "
                       "Most relevant for ISO stock option holders — exercising ISOs triggers AMT preference items. "
                       "Also triggered by high miscellaneous itemized deductions.",
        "actions": [
            "ISO holders: run AMT crossover analysis before exercising options",
            "Spread ISO exercises across tax years to stay below AMT",
            "Check Form 6251 at filing to understand AMT exposure",
            "AMT credits from prior-year exercise can offset future regular tax",
        ],
    })

    # Summary metrics
    exceeded_count = sum(1 for t in thresholds if t.get("exceeded"))
    total_estimated_impact = sum(t.get("tax_impact", 0) for t in thresholds if t.get("exceeded"))

    return {
        "combined_income": combined,
        "magi_estimate": round(magi_estimate),
        "filing_status": body.filing_status,
        "thresholds": thresholds,
        "exceeded_count": exceeded_count,
        "total_estimated_additional_tax": total_estimated_impact,
        "note": "MAGI estimates are approximate. Consult a tax professional for precise calculations.",
    }
