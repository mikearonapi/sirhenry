"""Household profile CRUD and benefits endpoints."""
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import HouseholdProfile, BenefitPackage

from api.routes.household_optimization import router as optimization_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/household", tags=["household"])

# Include sub-routers
router.include_router(optimization_router)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HouseholdProfileIn(BaseModel):
    name: str = "Our Household"
    filing_status: str = "mfj"
    state: Optional[str] = None
    dependents_json: Optional[str] = None
    spouse_a_name: Optional[str] = None
    spouse_a_income: float = 0
    spouse_a_employer: Optional[str] = None
    spouse_a_work_state: Optional[str] = None
    spouse_a_start_date: Optional[str] = None
    spouse_b_name: Optional[str] = None
    spouse_b_income: float = 0
    spouse_b_employer: Optional[str] = None
    spouse_b_work_state: Optional[str] = None
    spouse_b_start_date: Optional[str] = None
    estate_will_status: Optional[str] = None
    estate_poa_status: Optional[str] = None
    estate_hcd_status: Optional[str] = None
    estate_trust_status: Optional[str] = None
    beneficiaries_reviewed: Optional[bool] = None
    beneficiaries_reviewed_date: Optional[str] = None
    other_income_annual: Optional[float] = None
    other_income_sources_json: Optional[str] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None


class HouseholdProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    filing_status: str
    state: Optional[str]
    dependents_json: Optional[str]
    spouse_a_name: Optional[str]
    spouse_a_income: float
    spouse_a_employer: Optional[str]
    spouse_a_work_state: Optional[str] = None
    spouse_a_start_date: Optional[date] = None
    spouse_b_name: Optional[str]
    spouse_b_income: float
    spouse_b_employer: Optional[str]
    spouse_b_work_state: Optional[str] = None
    spouse_b_start_date: Optional[date] = None
    combined_income: float
    estate_will_status: Optional[str] = None
    estate_poa_status: Optional[str] = None
    estate_hcd_status: Optional[str] = None
    estate_trust_status: Optional[str] = None
    beneficiaries_reviewed: Optional[bool] = None
    beneficiaries_reviewed_date: Optional[date] = None
    other_income_annual: Optional[float] = None
    other_income_sources_json: Optional[str] = None
    is_primary: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class BenefitPackageIn(BaseModel):
    spouse: str
    employer_name: Optional[str] = None
    has_401k: bool = False
    employer_match_pct: float = 0
    employer_match_limit_pct: float = 6
    has_roth_401k: bool = False
    has_mega_backdoor: bool = False
    annual_401k_contribution: float = 0
    has_hsa: bool = False
    hsa_employer_contribution: float = 0
    has_fsa: bool = False
    has_dep_care_fsa: bool = False
    health_premium_monthly: float = 0
    dental_vision_monthly: float = 0
    health_plan_options_json: Optional[str] = None
    life_insurance_coverage: float = 0
    life_insurance_cost_monthly: float = 0
    std_coverage_pct: Optional[float] = None
    std_waiting_days: Optional[int] = None
    ltd_coverage_pct: Optional[float] = None
    ltd_waiting_days: Optional[int] = None
    commuter_monthly_limit: float = 0
    tuition_reimbursement_annual: float = 0
    has_espp: bool = False
    espp_discount_pct: float = 15
    open_enrollment_start: Optional[str] = None
    open_enrollment_end: Optional[str] = None
    notes: Optional[str] = None


class BenefitPackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: int
    spouse: str
    employer_name: Optional[str]
    has_401k: bool
    employer_match_pct: Optional[float]
    employer_match_limit_pct: Optional[float]
    has_roth_401k: bool
    has_mega_backdoor: bool
    annual_401k_limit: Optional[float]
    mega_backdoor_limit: Optional[float]
    annual_401k_contribution: Optional[float]
    has_hsa: bool
    hsa_employer_contribution: Optional[float]
    has_fsa: bool
    has_dep_care_fsa: bool
    health_premium_monthly: Optional[float]
    dental_vision_monthly: Optional[float]
    health_plan_options_json: Optional[str]
    life_insurance_coverage: Optional[float]
    life_insurance_cost_monthly: Optional[float]
    std_coverage_pct: Optional[float]
    std_waiting_days: Optional[int]
    ltd_coverage_pct: Optional[float]
    ltd_waiting_days: Optional[int]
    commuter_monthly_limit: Optional[float]
    tuition_reimbursement_annual: Optional[float]
    has_espp: bool
    espp_discount_pct: Optional[float]
    open_enrollment_start: Optional[date] = None
    open_enrollment_end: Optional[date] = None
    other_benefits_json: Optional[str]
    notes: Optional[str]


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

@router.get("/profiles", response_model=list[HouseholdProfileOut])
async def list_profiles(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(HouseholdProfile).order_by(HouseholdProfile.created_at.desc()))
    return result.scalars().all()


@router.post("/profiles", response_model=HouseholdProfileOut, status_code=201)
async def create_profile(body: HouseholdProfileIn, session: AsyncSession = Depends(get_session)):
    data = body.model_dump()
    profile = HouseholdProfile(**data)
    profile.combined_income = profile.spouse_a_income + profile.spouse_b_income
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    return profile


@router.patch("/profiles/{profile_id}", response_model=HouseholdProfileOut)
async def update_profile(profile_id: int, body: HouseholdProfileIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(HouseholdProfile).where(HouseholdProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    profile.combined_income = profile.spouse_a_income + profile.spouse_b_income
    profile.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(profile)
    return profile


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(HouseholdProfile).where(HouseholdProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")
    await session.delete(profile)
    await session.flush()


# ---------------------------------------------------------------------------
# Benefits
# ---------------------------------------------------------------------------

@router.get("/profiles/{profile_id}/benefits", response_model=list[BenefitPackageOut])
async def get_benefits(profile_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(BenefitPackage).where(BenefitPackage.household_id == profile_id)
    )
    return result.scalars().all()


@router.post("/profiles/{profile_id}/benefits")
async def upsert_benefits(profile_id: int, body: BenefitPackageIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(BenefitPackage)
        .where(BenefitPackage.household_id == profile_id)
        .where(BenefitPackage.spouse == body.spouse)
    )
    existing = result.scalar_one_or_none()
    if existing:
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(existing, k, v)
        await session.flush()
        return {"status": "updated"}
    else:
        pkg = BenefitPackage(household_id=profile_id, **body.model_dump())
        session.add(pkg)
        await session.flush()
        return {"status": "created"}


# ---------------------------------------------------------------------------
# Tax Strategy Interview Profile
# ---------------------------------------------------------------------------

@router.get("/tax-strategy-profile")
async def get_tax_strategy_profile(session: AsyncSession = Depends(get_session)):
    """Get the tax strategy interview profile from the primary household."""
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {"profile": None}
    import json
    data = None
    if profile.tax_strategy_profile_json:
        try:
            data = json.loads(profile.tax_strategy_profile_json)
        except Exception:
            pass
    return {"profile": data}


@router.put("/tax-strategy-profile")
async def save_tax_strategy_profile(body: dict, session: AsyncSession = Depends(get_session)):
    """Save tax strategy interview answers to the primary household profile."""
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No primary household profile found. Complete setup first.")
    import json
    profile.tax_strategy_profile_json = json.dumps(body)
    await session.flush()
    return {"status": "saved"}
