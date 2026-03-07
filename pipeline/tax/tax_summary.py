"""
Tax summary with data-source fallback logic.

Extracted from api/routes/tax_analysis.py to keep routes thin.
Priority chain: tax documents → household profile → none.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import get_tax_summary
from pipeline.db.schema import HouseholdProfile


async def get_tax_summary_with_fallback(session: AsyncSession, tax_year: int) -> dict[str, Any]:
    """Build a tax summary dict, falling back from document data to household profile.

    Returns the summary dict with a ``data_source`` key set to one of:
    - "documents" — data sourced from parsed tax forms (W-2, 1099, K-1, etc.)
    - "setup_profile" — income from HouseholdProfile (onboarding data)
    - "none" — no income data available
    """
    summary = await get_tax_summary(session, tax_year)

    # Check if document-sourced data exists
    has_doc_income = any(summary.get(k, 0) != 0 for k in (
        "w2_total_wages", "nec_total", "div_ordinary", "capital_gains_long",
        "capital_gains_short", "interest_income",
        "k1_ordinary_income", "k1_guaranteed_payments", "k1_rental_income",
    ))

    if has_doc_income:
        summary["data_source"] = "documents"
        return summary

    # Fallback to household profile income
    household_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = household_result.scalar_one_or_none()
    total_hh = (household.spouse_a_income or 0) + (household.spouse_b_income or 0) if household else 0

    if household and total_hh + (household.other_income_annual or 0) > 0:
        summary["data_source"] = "setup_profile"
        summary["w2_total_wages"] = total_hh
        if household.other_income_sources_json:
            try:
                other_sources = json.loads(household.other_income_sources_json)
                for src in other_sources:
                    amt = float(src.get("amount", 0) or 0)
                    src_type = src.get("type", "")
                    if src_type in ("business_1099", "partnership_k1", "scorp_k1", "trust_k1"):
                        summary["nec_total"] = summary.get("nec_total", 0) + amt
                    elif src_type == "dividends_1099":
                        summary["div_ordinary"] = summary.get("div_ordinary", 0) + amt
                    elif src_type in ("rental", "other"):
                        summary["interest_income"] = summary.get("interest_income", 0) + amt
            except (ValueError, TypeError):
                summary["interest_income"] = summary.get("interest_income", 0) + (household.other_income_annual or 0)
        elif household.other_income_annual:
            summary["interest_income"] = summary.get("interest_income", 0) + household.other_income_annual
    else:
        summary["data_source"] = "none"

    return summary
