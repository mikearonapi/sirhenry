"""Household sync — keep HouseholdProfile denormalized fields in step with FamilyMember rows.

Called after any create/update/delete of family members to re-derive
spouse_a/b fields, combined_income, and dependents_json.
"""
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import FamilyMember, HouseholdProfile


def _age_on(dob: date, ref: date) -> int:
    """Full years between *dob* and *ref* date."""
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


async def sync_household_from_members(
    session: AsyncSession,
    household_id: int,
) -> dict | None:
    """Re-derive spouse_a/b fields and dependents_json from current family members.

    Returns a summary dict of the updated fields, or ``None`` if the
    household was not found.

    The caller is responsible for committing — this function only mutates
    the ``HouseholdProfile`` instance within the session.
    """
    hp = await session.get(HouseholdProfile, household_id)
    if not hp:
        return None

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
    today = date.today()
    hp.dependents_json = json.dumps([
        {
            "id": d.id,
            "name": d.name,
            "age": _age_on(d.date_of_birth, today) if d.date_of_birth else None,
            "dob": d.date_of_birth.isoformat() if d.date_of_birth else None,
            "care_cost_annual": d.care_cost_annual,
            "college_start_year": d.college_start_year,
        }
        for d in dependents
    ])

    return {
        "household_id": household_id,
        "spouse_a_name": hp.spouse_a_name,
        "spouse_b_name": hp.spouse_b_name,
        "combined_income": hp.combined_income,
        "dependents_count": len(dependents),
    }
