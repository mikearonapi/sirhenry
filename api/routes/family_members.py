"""Family member profile routes — one record per person in the household."""
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import FamilyMember, HouseholdProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/family-members", tags=["family-members"])


# ---------------------------------------------------------------------------
# Milestone calculation helpers
# ---------------------------------------------------------------------------

def _age_on(dob: date, ref: date) -> int:
    """Full years between dob and ref date."""
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def _years_until(target_age: int, dob: date, ref: date) -> int:
    return max(0, target_age - _age_on(dob, ref))


def _compute_milestones(members: list[FamilyMember]) -> list[dict]:
    today = date.today()
    milestones = []

    for m in members:
        if not m.date_of_birth:
            continue
        dob = m.date_of_birth
        age = _age_on(dob, today)

        if m.relationship in ("self", "spouse"):
            # Social Security (FRA 67 for born 1960+)
            fra = 67
            yrs_fra = _years_until(fra, dob, today)
            if yrs_fra > 0:
                milestones.append({
                    "member_id": m.id,
                    "member_name": m.name,
                    "relationship": m.relationship,
                    "type": "social_security_fra",
                    "label": f"{m.name} reaches Social Security full retirement age ({fra})",
                    "years_away": yrs_fra,
                    "target_year": today.year + yrs_fra,
                    "age_at_event": fra,
                    "action": "Review SS benefit estimate at ssa.gov/myaccount. Consider delay to 70 for 8%/yr increase.",
                    "category": "retirement",
                })
            # Medicare (65)
            yrs_medicare = _years_until(65, dob, today)
            if 0 < yrs_medicare <= 20:
                milestones.append({
                    "member_id": m.id,
                    "member_name": m.name,
                    "relationship": m.relationship,
                    "type": "medicare_eligible",
                    "label": f"{m.name} becomes Medicare-eligible (65)",
                    "years_away": yrs_medicare,
                    "target_year": today.year + yrs_medicare,
                    "age_at_event": 65,
                    "action": "Enroll in Medicare Parts A & B within 8 months of leaving employer coverage to avoid late penalties.",
                    "category": "healthcare",
                })
            # RMD (73)
            yrs_rmd = _years_until(73, dob, today)
            if 0 < yrs_rmd <= 20:
                milestones.append({
                    "member_id": m.id,
                    "member_name": m.name,
                    "relationship": m.relationship,
                    "type": "rmd_start",
                    "label": f"{m.name} must begin Required Minimum Distributions (73)",
                    "years_away": yrs_rmd,
                    "target_year": today.year + yrs_rmd,
                    "age_at_event": 73,
                    "action": "Consider Roth conversions before RMDs begin to reduce future taxable distributions.",
                    "category": "retirement",
                })

        elif m.relationship in ("child", "other_dependent"):
            # Driving age (16)
            yrs_drive = _years_until(16, dob, today)
            if 0 < yrs_drive <= 8:
                milestones.append({
                    "member_id": m.id,
                    "member_name": m.name,
                    "relationship": m.relationship,
                    "type": "driving_age",
                    "label": f"{m.name} reaches driving age (16)",
                    "years_away": yrs_drive,
                    "target_year": today.year + yrs_drive,
                    "age_at_event": 16,
                    "action": "Review auto insurance — adding a teen driver typically increases premiums 50–100%. Shop early.",
                    "category": "insurance",
                })
            # College / FAFSA (18)
            college_yr = m.college_start_year or (dob.year + 18)
            yrs_college = max(0, college_yr - today.year)
            if 0 < yrs_college <= 18:
                milestones.append({
                    "member_id": m.id,
                    "member_name": m.name,
                    "relationship": m.relationship,
                    "type": "college_start",
                    "label": f"{m.name} starts college (~{college_yr})",
                    "years_away": yrs_college,
                    "target_year": college_yr,
                    "age_at_event": age + yrs_college,
                    "action": (
                        f"529 balance target: {yrs_college} yrs of contributions remaining. "
                        "FAFSA filing opens Oct 1 of senior year. Consider asset repositioning before FAFSA."
                    ),
                    "category": "education",
                })
            # Aging off dependent status (24 for tax, 26 for health insurance)
            yrs_tax_dep = _years_until(19, dob, today)
            if 0 < yrs_tax_dep <= 5:
                milestones.append({
                    "member_id": m.id,
                    "member_name": m.name,
                    "relationship": m.relationship,
                    "type": "tax_dependent_age_limit",
                    "label": f"{m.name} ages off as qualifying child for CTC (19)",
                    "years_away": yrs_tax_dep,
                    "target_year": today.year + yrs_tax_dep,
                    "age_at_event": 19,
                    "action": "Child Tax Credit ($2,000) ends. Review Other Dependent Credit ($500) eligibility if full-time student.",
                    "category": "tax",
                })
            yrs_health = _years_until(26, dob, today)
            if 0 < yrs_health <= 8:
                milestones.append({
                    "member_id": m.id,
                    "member_name": m.name,
                    "relationship": m.relationship,
                    "type": "health_insurance_rolloff",
                    "label": f"{m.name} ages off parental health plan (26)",
                    "years_away": yrs_health,
                    "target_year": today.year + yrs_health,
                    "age_at_event": 26,
                    "action": "Arrange independent health coverage before 26th birthday — qualifying event allows marketplace enrollment.",
                    "category": "healthcare",
                })

    milestones.sort(key=lambda x: x["years_away"])
    return milestones


# ---------------------------------------------------------------------------
# Sync helper — keeps HouseholdProfile denormalized fields in step
# ---------------------------------------------------------------------------

async def _sync_household(household_id: int, session: AsyncSession) -> None:
    """Re-derive spouse_a/b fields and dependents_json from current family members."""
    hp = await session.get(HouseholdProfile, household_id)
    if not hp:
        return

    members_result = await session.execute(
        select(FamilyMember).where(FamilyMember.household_id == household_id)
    )
    members = list(members_result.scalars())

    earner_self = next((m for m in members if m.relationship == "self"), None)
    earner_spouse = next((m for m in members if m.relationship == "spouse"), None)
    dependents = [m for m in members if m.relationship in ("child", "other_dependent")]

    # Always set spouse_a fields — clear if self member was deleted
    if earner_self:
        hp.spouse_a_name = earner_self.name
        hp.spouse_a_income = earner_self.income or 0.0
        hp.spouse_a_employer = earner_self.employer
        hp.spouse_a_work_state = earner_self.work_state
        hp.spouse_a_start_date = earner_self.employer_start_date
    else:
        hp.spouse_a_name = None
        hp.spouse_a_income = 0.0
        hp.spouse_a_employer = None
        hp.spouse_a_work_state = None
        hp.spouse_a_start_date = None

    # Always set spouse_b fields — clear if spouse member was deleted
    if earner_spouse:
        hp.spouse_b_name = earner_spouse.name
        hp.spouse_b_income = earner_spouse.income or 0.0
        hp.spouse_b_employer = earner_spouse.employer
        hp.spouse_b_work_state = earner_spouse.work_state
        hp.spouse_b_start_date = earner_spouse.employer_start_date
    else:
        hp.spouse_b_name = None
        hp.spouse_b_income = 0.0
        hp.spouse_b_employer = None
        hp.spouse_b_work_state = None
        hp.spouse_b_start_date = None

    hp.combined_income = (hp.spouse_a_income or 0.0) + (hp.spouse_b_income or 0.0)

    # Always update dependents — clear to empty array if none remain
    hp.dependents_json = json.dumps([
        {
            "id": d.id,
            "name": d.name,
            "age": _age_on(d.date_of_birth, date.today()) if d.date_of_birth else None,
            "dob": d.date_of_birth.isoformat() if d.date_of_birth else None,
            "care_cost_annual": d.care_cost_annual,
            "college_start_year": d.college_start_year,
        }
        for d in dependents
    ])


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
    await _sync_household(body.household_id, session)
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

    await _sync_household(member.household_id, session)
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
    await _sync_household(household_id, session)


@router.get("/milestones/by-household", response_model=list[dict])
async def get_milestones(
    household_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(FamilyMember).where(FamilyMember.household_id == household_id)
    )
    members = list(result.scalars())
    return _compute_milestones(members)
