"""Age-based financial milestone computation for family members.

Pure computation — no database access required.  Takes ORM objects (or
anything with the same attributes) and returns plain dicts.
"""
from datetime import date
from typing import Any


def _age_on(dob: date, ref: date) -> int:
    """Full years between *dob* and *ref* date."""
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def _years_until(target_age: int, dob: date, ref: date) -> int:
    return max(0, target_age - _age_on(dob, ref))


def compute_milestones(members: list[Any]) -> list[dict]:
    """Return a sorted list of upcoming financial milestones for *members*.

    Each member is expected to have at least:
    ``id``, ``name``, ``relationship``, ``date_of_birth``, and
    ``college_start_year`` attributes (matching the ``FamilyMember`` ORM
    model).

    Returns a list of milestone dicts sorted by ``years_away`` ascending.
    """
    today = date.today()
    milestones: list[dict] = []

    for m in members:
        if not m.date_of_birth:
            continue
        dob = m.date_of_birth
        age = _age_on(dob, today)

        if m.relationship in ("self", "spouse"):
            _add_adult_milestones(milestones, m, dob, age, today)
        elif m.relationship in ("child", "other_dependent"):
            _add_dependent_milestones(milestones, m, dob, age, today)

    milestones.sort(key=lambda x: x["years_away"])
    return milestones


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _add_adult_milestones(
    milestones: list[dict],
    m: Any,
    dob: date,
    age: int,
    today: date,
) -> None:
    # Social Security full retirement age (67 for born 1960+)
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

    # Required Minimum Distributions (73)
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


def _add_dependent_milestones(
    milestones: list[dict],
    m: Any,
    dob: date,
    age: int,
    today: date,
) -> None:
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

    # Aging off dependent status — tax (19)
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

    # Aging off parental health plan (26)
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
