"""
Compute a full federal + SE tax estimate based on known income data.

Pulls income from tax documents (TaxItem), falls back to HouseholdProfile
setup data, and folds in LifeEvent capital gains / bonuses.  Imports the
pure-math helpers from pipeline.tax.calculator and constants from
pipeline.tax.constants — this module adds the DB-aware orchestration layer.
"""
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import get_tax_summary
from pipeline.db.schema import HouseholdProfile, LifeEvent
from pipeline.tax.calculator import (
    federal_tax as calc_fed_tax,
    fica_tax as calc_fica,
    marginal_rate as calc_marginal,
    niit_tax as calc_niit,
    se_tax as calc_se_tax,
    standard_deduction as std_deduction,
)


async def compute_tax_estimate(session: AsyncSession, tax_year: int) -> dict:
    """
    Compute a rough federal + SE tax estimate based on known income data.
    This is an estimate only — not professional tax advice.

    Returns a dict with all estimate fields (AGI, taxable income, tax
    components, effective/marginal rates, balance due, etc.).
    """
    summary = await get_tax_summary(session, tax_year)

    # Resolve filing_status from HouseholdProfile instead of hardcoding "mfj"
    household_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = household_result.scalar_one_or_none()
    filing_status = household.filing_status if household else "mfj"

    # Determine data source and fall back to HouseholdProfile income if no documents
    has_document_income = (
        summary["w2_total_wages"] > 0
        or summary["nec_total"] > 0
        or summary["div_ordinary"] > 0
        or summary["capital_gains_long"] > 0
        or summary["capital_gains_short"] > 0
        or summary["interest_income"] > 0
        or summary.get("k1_ordinary_income", 0) != 0
        or summary.get("k1_guaranteed_payments", 0) != 0
    )
    if has_document_income:
        data_source = "documents"
    elif household and ((household.spouse_a_income or 0) + (household.spouse_b_income or 0) + (household.other_income_annual or 0)) > 0:
        data_source = "setup_profile"
        # Use Setup income as fallback
        summary["w2_total_wages"] = (household.spouse_a_income or 0) + (household.spouse_b_income or 0)
        # Parse other_income_sources_json for income type breakdown
        if household.other_income_sources_json:
            try:
                other_sources = json.loads(household.other_income_sources_json)
                for src in other_sources:
                    amt = float(src.get("amount", 0) or 0)
                    src_type = src.get("type", "")
                    if src_type in ("business_1099", "partnership_k1", "scorp_k1", "trust_k1"):
                        summary["nec_total"] += amt
                    elif src_type == "dividends_1099":
                        summary["div_ordinary"] += amt
                    elif src_type in ("rental", "other"):
                        summary["interest_income"] += amt
            except (ValueError, TypeError):
                # Fallback: put all other income into interest as catch-all
                summary["interest_income"] += household.other_income_annual or 0
        elif household.other_income_annual:
            summary["interest_income"] += household.other_income_annual
    else:
        data_source = "none"

    # Fold in life event amounts for the tax year (capital gains, bonuses, etc.)
    life_event_cap_gains_long: float = 0.0
    life_event_cap_gains_short: float = 0.0
    life_event_bonus_income: float = 0.0
    le_result = await session.execute(
        select(LifeEvent).where(LifeEvent.tax_year == tax_year)
    )
    life_events = le_result.scalars().all()
    for le in life_events:
        if not le.amounts_json:
            continue
        try:
            amounts = json.loads(le.amounts_json)
        except (ValueError, TypeError):
            continue
        # real_estate:sale — capital_gain field
        if le.event_type == "real_estate" and le.event_subtype in ("sale", "sold"):
            cap_gain = float(amounts.get("capital_gain", 0) or 0)
            # Assume long-term unless explicitly marked short
            if amounts.get("holding_period") == "short":
                life_event_cap_gains_short += cap_gain
            else:
                life_event_cap_gains_long += cap_gain
        # employment:job_change — signing_bonus, bonus fields
        if le.event_type == "employment":
            life_event_bonus_income += float(amounts.get("signing_bonus", 0) or 0)
            life_event_bonus_income += float(amounts.get("bonus", 0) or 0)
        # Any event with a generic "capital_gain" or "bonus" key
        if le.event_type not in ("real_estate", "employment"):
            life_event_cap_gains_long += float(amounts.get("capital_gain", 0) or 0)
            life_event_bonus_income += float(amounts.get("bonus", 0) or 0)

    w2_wages = summary["w2_total_wages"] + life_event_bonus_income
    nec_income = summary["nec_total"]
    ord_div = summary["div_ordinary"]
    qual_div = summary["div_qualified"]
    cg_long = summary["capital_gains_long"] + life_event_cap_gains_long
    cg_short = summary["capital_gains_short"] + life_event_cap_gains_short
    interest = summary["interest_income"]

    # K-1 income components
    k1_ordinary = summary.get("k1_ordinary_income", 0)
    k1_guaranteed = summary.get("k1_guaranteed_payments", 0)
    k1_rental = summary.get("k1_rental_income", 0)
    k1_interest = summary.get("k1_interest_income", 0)
    k1_dividends = summary.get("k1_dividends", 0)
    k1_cap_gains = summary.get("k1_capital_gains", 0)

    # 1099-R retirement distributions (taxable portion is ordinary income)
    retirement_taxable = summary.get("retirement_taxable", 0)

    # 1099-G (unemployment = ordinary income; state tax refund = ordinary if itemized prior year)
    unemployment = summary.get("unemployment_income", 0)
    state_refund = summary.get("state_tax_refund", 0)

    # 1099-K (payment platform income — treated as self-employment unless W-2 employer)
    platform_income = summary.get("payment_platform_income", 0)

    # 1098 deductions (mortgage interest + property tax)
    mortgage_deduction = summary.get("mortgage_interest_deduction", 0)
    property_tax_ded = summary.get("property_tax_deduction", 0)

    # K-1 interest/dividends/cap gains add to their respective buckets
    interest += k1_interest
    ord_div += k1_dividends
    cg_long += k1_cap_gains

    unqualified_div = ord_div - qual_div
    ordinary_income = (
        w2_wages + nec_income + cg_short + unqualified_div + interest
        + k1_ordinary + k1_guaranteed + k1_rental
        + retirement_taxable + unemployment + state_refund + platform_income
    )

    # SE tax applies to NEC + K-1 guaranteed payments + 1099-K platform income
    se_eligible = nec_income + k1_guaranteed + platform_income
    se_tax_amt = calc_se_tax(se_eligible, filing_status) if se_eligible > 0 else 0
    se_deduction = se_tax_amt * 0.5

    agi = ordinary_income + qual_div + cg_long - se_deduction

    # Use itemized deduction if mortgage + property tax + state tax exceeds standard
    std_ded = std_deduction(filing_status)
    itemized = mortgage_deduction + min(property_tax_ded, 10000)  # SALT cap $10K
    deduction = max(std_ded, itemized)

    taxable_income = max(0, agi - deduction)

    fed_tax = calc_fed_tax(taxable_income, filing_status)
    mrate = calc_marginal(taxable_income, filing_status)

    investment_income = ord_div + cg_long + cg_short + interest
    niit = calc_niit(agi, investment_income, filing_status)

    additional_medicare = calc_fica(w2_wages, filing_status) - (w2_wages * 0.0765) if w2_wages > 0 else 0
    additional_medicare = max(0, additional_medicare)

    total_tax = fed_tax + se_tax_amt + niit + additional_medicare

    return {
        "tax_year": tax_year,
        "filing_status": filing_status,
        "estimated_agi": round(agi, 2),
        "estimated_taxable_income": round(taxable_income, 2),
        "ordinary_income": round(ordinary_income, 2),
        "qualified_dividends_and_ltcg": round(qual_div + cg_long, 2),
        "self_employment_income": round(nec_income, 2),
        "life_event_capital_gains": round(life_event_cap_gains_long + life_event_cap_gains_short, 2),
        "life_event_bonus_income": round(life_event_bonus_income, 2),
        "federal_income_tax": round(fed_tax, 2),
        "self_employment_tax": round(se_tax_amt, 2),
        "niit": round(niit, 2),
        "additional_medicare_tax": round(additional_medicare, 2),
        "total_estimated_tax": round(total_tax, 2),
        "effective_rate": round(total_tax / max(1, agi) * 100, 1),
        "marginal_rate": round(mrate * 100, 1),
        "w2_federal_already_withheld": round(summary["w2_federal_withheld"], 2),
        "estimated_balance_due": round(total_tax - summary["w2_federal_withheld"], 2),
        "data_source": data_source,
        "disclaimer": "This is a rough estimate only. Consult a CPA for official tax advice.",
    }
