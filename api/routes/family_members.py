"""Family member profile routes — one record per person in the household."""
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import FamilyMember, HouseholdProfile
from pipeline.db.household_sync import sync_household_from_members
from pipeline.planning.milestones import compute_milestones

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/family-members", tags=["family-members"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class FamilyMemberIn(BaseModel):
    household_id: int
    name: str
    relationship: str  # self | spouse | child | other_dependent | parent | other
    date_of_birth: Optional[date] = None
    ssn_last4: Optional[str] = None
    is_earner: bool = False
    income: Optional[float] = 0.0
    employer: Optional[str] = None
    work_state: Optional[str] = None
    employer_start_date: Optional[date] = None
    grade_level: Optional[str] = None
    school_name: Optional[str] = None
    care_cost_annual: Optional[float] = None
    college_start_year: Optional[int] = None
    notes: Optional[str] = None


class FamilyMemberPatch(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    date_of_birth: Optional[date] = None
    ssn_last4: Optional[str] = None
    is_earner: Optional[bool] = None
    income: Optional[float] = None
    employer: Optional[str] = None
    work_state: Optional[str] = None
    employer_start_date: Optional[date] = None
    grade_level: Optional[str] = None
    school_name: Optional[str] = None
    care_cost_annual: Optional[float] = None
    college_start_year: Optional[int] = None
    notes: Optional[str] = None


class FamilyMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    name: str
    relationship: str
    date_of_birth: Optional[date] = None
    ssn_last4: Optional[str] = None
    is_earner: bool
    income: Optional[float] = None
    employer: Optional[str] = None
    work_state: Optional[str] = None
    employer_start_date: Optional[date] = None
    grade_level: Optional[str] = None
    school_name: Optional[str] = None
    care_cost_annual: Optional[float] = None
    college_start_year: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[FamilyMemberOut])
async def list_family_members(
    household_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(FamilyMember)
    if household_id is not None:
        q = q.where(FamilyMember.household_id == household_id)
    result = await session.execute(q.order_by(FamilyMember.id))
    return list(result.scalars())


@router.post("/", response_model=FamilyMemberOut, status_code=201)
async def create_family_member(
    body: FamilyMemberIn,
    session: AsyncSession = Depends(get_session),
):
    hp = await session.get(HouseholdProfile, body.household_id)
    if not hp:
        raise HTTPException(404, "Household profile not found")

    # Enforce single self/spouse per household
    if body.relationship in ("self", "spouse"):
        existing = await session.execute(
            select(FamilyMember).where(
                FamilyMember.household_id == body.household_id,
                FamilyMember.relationship == body.relationship,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, f"A family member with relationship='{body.relationship}' already exists for this household. Use PATCH to update.")

    member = FamilyMember(**body.model_dump())
    session.add(member)
    await session.flush()
    await sync_household_from_members(session, body.household_id)
    await session.refresh(member)
    logger.info(f"Created family member {member.id} ({member.name}) for household {member.household_id}")
    return member


@router.get("/{member_id}", response_model=FamilyMemberOut)
async def get_family_member(
    member_id: int,
    session: AsyncSession = Depends(get_session),
):
    member = await session.get(FamilyMember, member_id)
    if not member:
        raise HTTPException(404, "Family member not found")
    return member


@router.patch("/{member_id}", response_model=FamilyMemberOut)
async def update_family_member(
    member_id: int,
    body: FamilyMemberPatch,
    session: AsyncSession = Depends(get_session),
):
    member = await session.get(FamilyMember, member_id)
    if not member:
        raise HTTPException(404, "Family member not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    member.updated_at = datetime.now(timezone.utc)

    await sync_household_from_members(session, member.household_id)
    await session.flush()
    await session.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204)
async def delete_family_member(
    member_id: int,
    session: AsyncSession = Depends(get_session),
):
    member = await session.get(FamilyMember, member_id)
    if not member:
        raise HTTPException(404, "Family member not found")
    household_id = member.household_id
    await session.delete(member)
    await session.flush()
    await sync_household_from_members(session, household_id)


@router.get("/milestones/by-household", response_model=list[dict])
async def get_milestones(
    household_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(FamilyMember).where(FamilyMember.household_id == household_id)
    )
    members = list(result.scalars())
    return compute_milestones(members)
