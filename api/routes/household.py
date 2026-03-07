"""Household profile CRUD and benefits endpoints."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    TaxStrategyProfileIn,
    HouseholdProfileIn,
    HouseholdProfileOut,
    BenefitPackageIn,
    BenefitPackageOut,
)
from pipeline.db import HouseholdProfile, BenefitPackage, InsurancePolicy, LifeEvent

from api.routes.household_optimization import router as optimization_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/household", tags=["household"])

# Include sub-routers
router.include_router(optimization_router)


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
    profile.combined_income = (profile.spouse_a_income or 0) + (profile.spouse_b_income or 0)

    # Auto-set first household as primary; enforce single primary
    existing_count = await session.scalar(select(func.count()).select_from(HouseholdProfile))
    if (existing_count or 0) == 0:
        profile.is_primary = True
    elif profile.is_primary:
        # Clear any existing primary before setting the new one
        await session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary == True)
        )
        for existing in (await session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary == True)
        )).scalars():
            existing.is_primary = False

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

    updates = body.model_dump(exclude_unset=True)

    # Enforce single primary: clear others when setting this one as primary
    if updates.get("is_primary"):
        for existing in (await session.execute(
            select(HouseholdProfile).where(
                HouseholdProfile.is_primary == True,
                HouseholdProfile.id != profile_id,
            )
        )).scalars():
            existing.is_primary = False

    for k, v in updates.items():
        setattr(profile, k, v)
    profile.combined_income = (profile.spouse_a_income or 0) + (profile.spouse_b_income or 0)
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

    # Explicitly cascade to tables that may have SET NULL FKs in existing DBs
    for model in (InsurancePolicy, LifeEvent):
        related = await session.execute(
            select(model).where(model.household_id == profile_id)
        )
        for record in related.scalars():
            await session.delete(record)

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
    data = None
    if profile.tax_strategy_profile_json:
        try:
            data = json.loads(profile.tax_strategy_profile_json)
        except Exception:
            pass
    return {"profile": data}


@router.put("/tax-strategy-profile")
async def save_tax_strategy_profile(body: TaxStrategyProfileIn, session: AsyncSession = Depends(get_session)):
    """Save tax strategy interview answers to the primary household profile."""
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No primary household profile found. Complete setup first.")
    profile.tax_strategy_profile_json = json.dumps(body.model_dump())
    await session.flush()
    return {"status": "saved"}
