"""Insurance policy tracker — employer-provided and personally owned coverage."""
import json
import logging
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import GapAnalysisIn, InsurancePolicyIn, InsurancePolicyOut
from pipeline.db import InsurancePolicy
from pipeline.db.schema import BenefitPackage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insurance", tags=["insurance"])


POLICY_TYPES = [
    "health", "life", "disability", "auto", "home",
    "umbrella", "pet", "vision", "dental", "ltc", "other",
]


# ---------------------------------------------------------------------------
# Life insurance adequacy calculator
# ---------------------------------------------------------------------------

def _calc_life_insurance_need(
    income: float,
    years_to_replace: int = 10,
    debt: float = 0,
    dependents: int = 0,
) -> float:
    """
    DIME method approximation: Debt + Income replacement + Mortgage + Education.
    Simplified: income × years_to_replace + debt + (dependents × 50000 for education).
    """
    education_estimate = dependents * 50_000
    return income * years_to_replace + debt + education_estimate




# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[InsurancePolicyOut])
async def list_policies(
    household_id: Optional[int] = Query(None),
    policy_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    q = select(InsurancePolicy).order_by(InsurancePolicy.renewal_date.asc().nullslast())
    if household_id is not None:
        q = q.where(InsurancePolicy.household_id == household_id)
    if policy_type:
        q = q.where(InsurancePolicy.policy_type == policy_type)
    if is_active is not None:
        q = q.where(InsurancePolicy.is_active == is_active)
    result = await session.execute(q)
    return result.scalars().all()


@router.post("/", response_model=InsurancePolicyOut, status_code=201)
async def create_policy(body: InsurancePolicyIn, session: AsyncSession = Depends(get_session)):
    if body.policy_type not in POLICY_TYPES:
        raise HTTPException(400, f"Invalid policy_type. Must be one of: {', '.join(POLICY_TYPES)}")
    # Sync annual/monthly premium if only one is provided
    data = body.model_dump()
    if data.get("annual_premium") and not data.get("monthly_premium"):
        data["monthly_premium"] = data["annual_premium"] / 12
    elif data.get("monthly_premium") and not data.get("annual_premium"):
        data["annual_premium"] = data["monthly_premium"] * 12
    policy = InsurancePolicy(**data)
    session.add(policy)
    await session.flush()
    await session.refresh(policy)
    logger.info(f"Insurance policy created: {policy.policy_type} — {policy.provider}")
    return policy


@router.get("/{policy_id}", response_model=InsurancePolicyOut)
async def get_policy(policy_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(InsurancePolicy).where(InsurancePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy


@router.patch("/{policy_id}", response_model=InsurancePolicyOut)
async def update_policy(policy_id: int, body: InsurancePolicyIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(InsurancePolicy).where(InsurancePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(404, "Policy not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(policy, k, v)
    # Sync premium fields
    if body.annual_premium is not None and body.monthly_premium is None:
        policy.monthly_premium = body.annual_premium / 12
    elif body.monthly_premium is not None and body.annual_premium is None:
        policy.annual_premium = body.monthly_premium * 12
    policy.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(policy_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(InsurancePolicy).where(InsurancePolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(404, "Policy not found")
    await session.delete(policy)
    await session.flush()


@router.post("/gap-analysis")
async def gap_analysis(body: GapAnalysisIn, session: AsyncSession = Depends(get_session)):
    """
    Compute insurance coverage gaps for a household.
    Compares existing policies against recommended coverage levels.
    """
    q = select(InsurancePolicy).where(InsurancePolicy.is_active.is_(True))
    if body.household_id:
        q = q.where(InsurancePolicy.household_id == body.household_id)
    result = await session.execute(q)
    policies = result.scalars().all()

    # Query employer benefit packages for cross-reference
    employer_life_total = 0.0
    employer_std_monthly = 0.0
    employer_ltd_monthly = 0.0
    if body.household_id:
        bp_result = await session.execute(
            select(BenefitPackage).where(BenefitPackage.household_id == body.household_id)
        )
        benefit_packages = bp_result.scalars().all()
    else:
        benefit_packages = []

    combined_income = body.spouse_a_income + body.spouse_b_income
    for bp in benefit_packages:
        employer_life_total += bp.life_insurance_coverage or 0
        # STD/LTD coverage expressed as % of income → convert to monthly dollar amount
        spouse_income = body.spouse_a_income if bp.spouse == "A" else body.spouse_b_income
        if bp.std_coverage_pct:
            employer_std_monthly += spouse_income * (bp.std_coverage_pct / 100) / 12
        if bp.ltd_coverage_pct:
            employer_ltd_monthly += spouse_income * (bp.ltd_coverage_pct / 100) / 12

    by_type: dict[str, list] = {}
    for p in policies:
        by_type.setdefault(p.policy_type, []).append(p)

    gaps = []
    total_annual_premium = sum(
        (p.annual_premium or 0) for p in policies if p.is_active
    )

    # --- Life insurance gap ---
    life_policies = by_type.get("life", [])
    personal_life_coverage = sum(p.coverage_amount or 0 for p in life_policies)
    total_life_coverage = personal_life_coverage + employer_life_total
    recommended_life_a = _calc_life_insurance_need(body.spouse_a_income, 10, body.total_debt / 2, body.dependents)
    recommended_life_b = _calc_life_insurance_need(body.spouse_b_income, 10, body.total_debt / 2, body.dependents)
    recommended_life = recommended_life_a + recommended_life_b
    life_gap = max(0, recommended_life - total_life_coverage)
    life_note = (
        f"Recommended: 10× combined income + debt. "
        f"Current total: ${total_life_coverage:,.0f}"
    )
    if employer_life_total > 0:
        life_note += f" (includes ${employer_life_total:,.0f} employer-provided)"
    life_note += f". Recommended: ${recommended_life:,.0f}."
    gaps.append({
        "type": "life",
        "label": "Life Insurance",
        "current_coverage": total_life_coverage,
        "recommended_coverage": round(recommended_life),
        "gap": round(life_gap),
        "severity": "high" if life_gap > 500_000 else "medium" if life_gap > 100_000 else "low",
        "employer_provided": employer_life_total,
        "note": life_note,
    })

    # --- Disability insurance gap ---
    dis_policies = by_type.get("disability", [])
    has_ltd = any("ltd" in (p.notes or "").lower() or "long" in (p.notes or "").lower() for p in dis_policies) or len(dis_policies) > 0
    # Rough recommendation: 60-70% of gross income covered
    recommended_disability_monthly = combined_income * 0.65 / 12
    personal_disability_monthly = sum(
        (p.coverage_amount or 0) / 12 if (p.coverage_amount or 0) > 5000 else (p.coverage_amount or 0)
        for p in dis_policies
    )
    covered_disability_monthly = personal_disability_monthly + employer_std_monthly + employer_ltd_monthly
    dis_gap = max(0, recommended_disability_monthly - covered_disability_monthly)
    employer_dis_monthly = employer_std_monthly + employer_ltd_monthly
    has_any_disability = dis_policies or employer_dis_monthly > 0
    dis_note = f"Recommended: 65% of combined income = ${recommended_disability_monthly:,.0f}/mo. "
    if not has_any_disability:
        dis_note += "No disability coverage found."
    else:
        dis_note += f"Current: ${covered_disability_monthly:,.0f}/mo"
        if employer_dis_monthly > 0:
            dis_note += f" (includes ${employer_dis_monthly:,.0f}/mo employer STD/LTD)"
        dis_note += "."
    gaps.append({
        "type": "disability",
        "label": "Disability Insurance",
        "current_coverage": round(covered_disability_monthly),
        "recommended_coverage": round(recommended_disability_monthly),
        "gap": round(dis_gap),
        "severity": "high" if not has_any_disability else ("medium" if dis_gap > 3000 else "low"),
        "employer_provided": round(employer_dis_monthly),
        "note": dis_note,
    })

    # --- Umbrella policy ---
    umbrella_policies = by_type.get("umbrella", [])
    needs_umbrella = body.net_worth > 300_000
    umbrella_gap = not umbrella_policies and needs_umbrella
    gaps.append({
        "type": "umbrella",
        "label": "Umbrella / Excess Liability",
        "current_coverage": sum(p.coverage_amount or 0 for p in umbrella_policies),
        "recommended_coverage": max(1_000_000, int(body.net_worth / 1_000_000) * 1_000_000 + 1_000_000) if needs_umbrella else 0,
        "gap": 0 if not umbrella_gap else 1_000_000,
        "severity": "medium" if umbrella_gap else "low",
        "note": "Umbrella policy recommended when net worth exceeds $300k. "
                f"{'No umbrella policy found.' if not umbrella_policies else 'Umbrella coverage in place.'} "
                "Typically $1M–$5M coverage for ~$200–$500/year.",
    })

    # --- Renewing soon ---
    today = date.today()
    renewing_soon = []
    for p in policies:
        if p.renewal_date:
            try:
                rd = p.renewal_date if isinstance(p.renewal_date, date) else date.fromisoformat(str(p.renewal_date))
                days_until = (rd - today).days
                if 0 <= days_until <= 60:
                    renewing_soon.append({
                        "id": p.id,
                        "label": f"{p.policy_type.title()} — {p.provider or 'Unknown'}",
                        "renewal_date": str(rd),
                        "days_until": days_until,
                    })
            except Exception:
                pass

    high_severity_count = sum(1 for g in gaps if g["severity"] == "high")
    medium_severity_count = sum(1 for g in gaps if g["severity"] == "medium")

    return {
        "total_policies": len(policies),
        "total_annual_premium": round(total_annual_premium),
        "total_monthly_premium": round(total_annual_premium / 12),
        "gaps": gaps,
        "high_severity_gaps": high_severity_count,
        "medium_severity_gaps": medium_severity_count,
        "renewing_soon": renewing_soon,
        "recommendations": [
            g["note"] for g in gaps if g["severity"] in ("high", "medium")
        ],
    }
