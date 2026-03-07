"""
Income sync — cascade payroll data into HouseholdProfile, BenefitPackage, TaxItem.
One payroll connection populates 7 pages of data.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    BenefitPackage,
    HouseholdProfile,
    PayStubRecord,
    PayrollConnection,
    TaxItem,
)

logger = logging.getLogger(__name__)

# Map Plaid deduction descriptions to BenefitPackage fields
DEDUCTION_MAP: dict[str, str] = {
    "401K": "annual_401k_contribution",
    "401(K)": "annual_401k_contribution",
    "ROTH 401K": "annual_401k_contribution",
    "ROTH 401(K)": "annual_401k_contribution",
    "HSA": "hsa_employer_contribution",
    "FSA": "has_fsa",
    "HEALTH": "health_premium_monthly",
    "MEDICAL": "health_premium_monthly",
    "DENTAL": "dental_vision_monthly",
    "VISION": "dental_vision_monthly",
    "LIFE INSURANCE": "life_insurance_cost_monthly",
    "LIFE INS": "life_insurance_cost_monthly",
}

# Multipliers for annualizing from pay frequency
FREQUENCY_MULTIPLIERS = {
    "WEEKLY": 52,
    "BIWEEKLY": 26,
    "SEMI_MONTHLY": 24,
    "MONTHLY": 12,
}


async def sync_payroll_to_household(
    session: AsyncSession,
    connection: PayrollConnection,
    payroll_data: dict[str, Any],
) -> dict[str, int]:
    """Cascade payroll data into all relevant tables. Returns counts of updates."""
    counts = {"household": 0, "benefits": 0, "tax_items": 0, "pay_stubs": 0}

    # 1. Store pay stubs
    for stub in payroll_data.get("pay_stubs", []):
        record = PayStubRecord(
            connection_id=connection.id,
            pay_date=stub["pay_date"],
            pay_period_start=stub.get("pay_period_start"),
            pay_period_end=stub.get("pay_period_end"),
            pay_frequency=stub.get("pay_frequency"),
            gross_pay=stub.get("gross_pay"),
            gross_pay_ytd=stub.get("gross_pay_ytd"),
            net_pay=stub.get("net_pay"),
            net_pay_ytd=stub.get("net_pay_ytd"),
            deductions_json=json.dumps(stub.get("deductions", [])),
            employer_name=stub.get("employer_name"),
            employer_ein=stub.get("employer_ein"),
            employer_address_json=(
                json.dumps(stub.get("employer_address"))
                if stub.get("employer_address")
                else None
            ),
            work_state=_extract_work_state(stub.get("employer_address")),
        )
        session.add(record)
        counts["pay_stubs"] += 1

    # Update employer on connection from most recent stub
    stubs = payroll_data.get("pay_stubs", [])
    if stubs:
        latest = sorted(stubs, key=lambda s: s.get("pay_date", ""), reverse=True)[0]
        if latest.get("employer_name"):
            connection.employer_name = latest["employer_name"]

    # 2. Update HouseholdProfile
    counts["household"] = await _update_household(session, payroll_data)

    # 3. Update BenefitPackage from deductions
    counts["benefits"] = await _update_benefits(session, payroll_data)

    # 4. Create TaxItem from W-2 data
    counts["tax_items"] = await _create_tax_items(session, payroll_data)

    connection.last_synced_at = datetime.now(timezone.utc)
    connection.status = "active"

    return counts


async def _update_household(session: AsyncSession, data: dict[str, Any]) -> int:
    """Update HouseholdProfile with income/employer from payroll."""
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return 0

    stubs = data.get("pay_stubs", [])
    if not stubs:
        return 0

    latest = sorted(stubs, key=lambda s: s.get("pay_date", ""), reverse=True)[0]
    employer_name = latest.get("employer_name", "")
    work_state = _extract_work_state(latest.get("employer_address"))
    annual_income = _estimate_annual_income(latest)

    updated = 0
    if annual_income and annual_income > 0:
        matched = _match_to_spouse(profile, employer_name)
        if matched == "a":
            if abs((profile.spouse_a_income or 0) - annual_income) > 500:
                profile.spouse_a_income = annual_income
                updated += 1
            if employer_name and profile.spouse_a_employer != employer_name:
                profile.spouse_a_employer = employer_name
                updated += 1
            if work_state and profile.spouse_a_work_state != work_state:
                profile.spouse_a_work_state = work_state
                updated += 1
        elif matched == "b":
            if abs((profile.spouse_b_income or 0) - annual_income) > 500:
                profile.spouse_b_income = annual_income
                updated += 1
            if employer_name and profile.spouse_b_employer != employer_name:
                profile.spouse_b_employer = employer_name
                updated += 1
            if work_state and profile.spouse_b_work_state != work_state:
                profile.spouse_b_work_state = work_state
                updated += 1

        if updated:
            profile.combined_income = (profile.spouse_a_income or 0) + (profile.spouse_b_income or 0)
            profile.updated_at = datetime.now(timezone.utc)

    return updated


async def _update_benefits(session: AsyncSession, data: dict[str, Any]) -> int:
    """Extract benefit deductions from pay stubs and update BenefitPackage."""
    stubs = data.get("pay_stubs", [])
    if not stubs:
        return 0

    latest = sorted(stubs, key=lambda s: s.get("pay_date", ""), reverse=True)[0]
    deductions = latest.get("deductions", [])
    if not deductions:
        return 0

    employer_name = latest.get("employer_name", "")
    pay_frequency = (latest.get("pay_frequency") or "SEMI_MONTHLY").upper()
    multiplier = FREQUENCY_MULTIPLIERS.get(pay_frequency, 24)

    # Find or create BenefitPackage
    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return 0

    spouse = _match_to_spouse(profile, employer_name)
    spouse_letter = spouse.upper()

    bp_result = await session.execute(
        select(BenefitPackage).where(
            BenefitPackage.household_id == profile.id,
            BenefitPackage.spouse == spouse_letter,
        ).limit(1)
    )
    bp = bp_result.scalar_one_or_none()
    if not bp:
        bp = BenefitPackage(household_id=profile.id, spouse=spouse_letter)
        session.add(bp)

    if employer_name:
        bp.employer_name = employer_name

    updated = 0
    for ded in deductions:
        desc = (ded.get("description") or "").upper().strip()
        amount = ded.get("current_amount", 0) or 0

        for pattern, field in DEDUCTION_MAP.items():
            if pattern in desc:
                if field == "has_fsa":
                    bp.has_fsa = True
                    updated += 1
                elif field == "annual_401k_contribution":
                    annual = amount * multiplier
                    bp.annual_401k_contribution = annual
                    bp.has_401k = True
                    if "ROTH" in desc:
                        bp.has_roth_401k = True
                    updated += 1
                elif field in ("health_premium_monthly", "dental_vision_monthly", "life_insurance_cost_monthly"):
                    setattr(bp, field, amount)
                    updated += 1
                elif field == "hsa_employer_contribution":
                    bp.has_hsa = True
                    bp.hsa_employer_contribution = amount * multiplier
                    updated += 1
                break

    return updated


async def _create_tax_items(session: AsyncSession, data: dict[str, Any]) -> int:
    """Create TaxItem records from Plaid W-2 data."""
    count = 0
    for w2 in data.get("w2s", []):
        tax_year = w2.get("tax_year")
        employer_name = w2.get("employer_name")
        if not tax_year:
            continue

        # Check for existing TaxItem with same employer + year
        existing = await session.execute(
            select(TaxItem).where(
                TaxItem.form_type == "w2",
                TaxItem.tax_year == tax_year,
                TaxItem.payer_name == employer_name,
            )
        )
        if existing.scalar_one_or_none():
            continue

        tax_item = TaxItem(
            source_document_id=None,  # No physical document — sourced from Plaid payroll
            tax_year=tax_year,
            form_type="w2",
            payer_name=employer_name,
            payer_ein=w2.get("employer_ein"),
            w2_wages=w2.get("wages_tips"),
            w2_federal_tax_withheld=w2.get("federal_tax_withheld"),
            w2_ss_wages=w2.get("ss_wages"),
            w2_ss_tax_withheld=w2.get("ss_tax_withheld"),
            w2_medicare_wages=w2.get("medicare_wages"),
            w2_medicare_tax_withheld=w2.get("medicare_tax_withheld"),
            raw_fields=json.dumps({
                "source": "plaid_payroll",
                "box_12": w2.get("box_12", []),
                "retirement_plan": w2.get("retirement_plan"),
            }),
        )
        session.add(tax_item)
        count += 1

    return count


def _estimate_annual_income(stub: dict[str, Any]) -> float:
    """Estimate annual income from a pay stub's YTD or frequency data."""
    ytd = stub.get("gross_pay_ytd")
    pay_date = stub.get("pay_date", "")

    if ytd and pay_date:
        try:
            month = int(str(pay_date).split("-")[1])
            if month > 0:
                return round(ytd * 12 / month, 2)
        except (ValueError, IndexError):
            pass

    gross = stub.get("gross_pay", 0) or 0
    freq = (stub.get("pay_frequency") or "").upper()
    multiplier = FREQUENCY_MULTIPLIERS.get(freq, 24)
    return round(gross * multiplier, 2)


import re

_CORP_SUFFIXES = re.compile(r"\b(llc|inc|corp|co|ltd|lp|plc|group|holdings)\b\.?", re.IGNORECASE)


def _normalize_employer(name: str) -> str:
    """Normalize employer name for comparison: lowercase, strip suffixes."""
    n = (name or "").lower().strip()
    n = _CORP_SUFFIXES.sub("", n).strip().rstrip(",").strip()
    return n


def _employer_matches(name_a: str, name_b: str) -> bool:
    """Bidirectional substring match on normalized employer names."""
    a = _normalize_employer(name_a)
    b = _normalize_employer(name_b)
    if not a or not b:
        return False
    return a in b or b in a


def _match_to_spouse(profile: HouseholdProfile, employer: str) -> str:
    """Match an employer to spouse A or B. Returns 'a' or 'b'.

    Uses normalized bidirectional matching and prefers the spouse slot
    that doesn't already have an employer set.
    """
    match_a = bool(profile.spouse_a_employer) and _employer_matches(employer, profile.spouse_a_employer)
    match_b = bool(profile.spouse_b_employer) and _employer_matches(employer, profile.spouse_b_employer)

    if match_a and not match_b:
        return "a"
    if match_b and not match_a:
        return "b"
    if match_a and match_b:
        return "a"  # both match — default to primary

    # No match — assign to empty slot
    if not profile.spouse_a_employer or (profile.spouse_a_income or 0) == 0:
        return "a"
    if not profile.spouse_b_employer or (profile.spouse_b_income or 0) == 0:
        return "b"
    return "b"


def _extract_work_state(address: Any) -> str | None:
    """Extract 2-letter state code from Plaid address object."""
    if not address:
        return None
    if isinstance(address, dict):
        return address.get("region") or address.get("state")
    return None
