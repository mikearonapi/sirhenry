"""Insurance policy tracker — employer-provided and personally owned coverage."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import GapAnalysisIn, InsurancePolicyIn, InsurancePolicyOut
from pipeline.db import InsurancePolicy
from pipeline.db.schema import BenefitPackage
from pipeline.planning.insurance_analysis import analyze_insurance_gaps

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insurance", tags=["insurance"])


POLICY_TYPES = [
    "health", "life", "disability", "auto", "home",
    "umbrella", "pet", "vision", "dental", "ltc", "other",
]


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
    # Fetch active policies
    q = select(InsurancePolicy).where(InsurancePolicy.is_active.is_(True))
    if body.household_id:
        q = q.where(InsurancePolicy.household_id == body.household_id)
    result = await session.execute(q)
    policies = list(result.scalars().all())

    # Fetch employer benefit packages for cross-reference
    if body.household_id:
        bp_result = await session.execute(
            select(BenefitPackage).where(BenefitPackage.household_id == body.household_id)
        )
        benefit_packages = list(bp_result.scalars().all())
    else:
        benefit_packages = []

    return analyze_insurance_gaps(
        spouse_a_income=body.spouse_a_income,
        spouse_b_income=body.spouse_b_income,
        total_debt=body.total_debt,
        dependents=body.dependents,
        net_worth=body.net_worth,
        policies=policies,
        benefit_packages=benefit_packages,
    )
