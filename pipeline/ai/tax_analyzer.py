"""
Claude-powered tax strategy analyzer.
Reads the full DB summary for a given tax year and generates ranked optimization strategies.
Each strategy includes: title, description, type, priority, estimated savings range, action items.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import anthropic
from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import (
    get_all_business_entities,
    get_tax_summary,
    replace_tax_strategies,
)
from pipeline.db.schema import BusinessEntity, HouseholdProfile, Transaction
from pipeline.utils import CLAUDE_MODEL, strip_json_fences, get_claude_client, call_claude_with_retry

load_dotenv()
logger = logging.getLogger(__name__)

# 2025 MFJ tax brackets (for reference in prompt)
TAX_CONTEXT_2025 = """
2025 Federal Tax Brackets (Married Filing Jointly):
- 10%: $0 – $23,850
- 12%: $23,851 – $96,950
- 22%: $96,951 – $206,700
- 24%: $206,701 – $394,600
- 32%: $394,601 – $501,050
- 35%: $501,051 – $751,600
- 37%: over $751,600

Key thresholds:
- NIIT (3.8% on net investment income): $250,000 MFJ MAGI
- Additional Medicare Tax (0.9%): $250,000 MFJ
- SALT deduction cap: $10,000 (or $40,000 in CA if applicable)
- 401(k) employee contribution limit: $23,500 (2025), $31,000 if age 50+
- IRA contribution limit: $7,000, $8,000 if age 50+
- HSA family contribution limit: $8,550 (2025)
- SEP-IRA limit: 25% of net self-employment income, max $70,000
- QBI deduction (Section 199A): up to 20% of qualified business income
- Standard deduction MFJ: $30,000 (2025)
- Annual gift exclusion: $19,000/person
"""


async def _build_financial_snapshot(session: AsyncSession, tax_year: int) -> dict[str, Any]:
    """Aggregate all financial data for the tax year into a summary for Claude."""
    tax_summary = await get_tax_summary(session, tax_year)

    entities = await get_all_business_entities(session, include_inactive=True)
    entity_map = {e.id: e for e in entities}

    # Aggregate transaction totals by segment, category, and entity
    result = await session.execute(
        select(
            Transaction.effective_segment,
            Transaction.effective_category,
            Transaction.effective_business_entity_id,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            Transaction.period_year == tax_year,
            Transaction.is_excluded == False,
        )
        .group_by(
            Transaction.effective_segment,
            Transaction.effective_category,
            Transaction.effective_business_entity_id,
        )
    )
    rows = result.all()

    income_by_segment: dict[str, float] = {}
    expenses_by_category: dict[str, float] = {}
    business_expenses_by_entity: dict[str, dict[str, float]] = {}
    reimbursable_total = 0.0

    for row in rows:
        segment = row.effective_segment or "personal"
        category = row.effective_category or "Unknown"
        entity_id = row.effective_business_entity_id
        total = float(row.total or 0)

        if segment == "reimbursable":
            reimbursable_total += abs(total)
            continue

        if total > 0:
            income_by_segment[segment] = income_by_segment.get(segment, 0) + total
        else:
            if segment == "business" and entity_id:
                entity = entity_map.get(entity_id)
                entity_name = entity.name if entity else f"entity_{entity_id}"
                if entity_name not in business_expenses_by_entity:
                    business_expenses_by_entity[entity_name] = {}
                business_expenses_by_entity[entity_name][category] = (
                    business_expenses_by_entity[entity_name].get(category, 0) + abs(total)
                )
            elif segment == "business":
                if "Unassigned" not in business_expenses_by_entity:
                    business_expenses_by_entity["Unassigned"] = {}
                business_expenses_by_entity["Unassigned"][category] = (
                    business_expenses_by_entity["Unassigned"].get(category, 0) + abs(total)
                )
            else:
                expenses_by_category[category] = expenses_by_category.get(category, 0) + abs(total)

    all_business_expenses = sum(
        sum(cats.values()) for cats in business_expenses_by_entity.values()
    )

    entity_summaries = []
    for e in entities:
        entity_expenses = business_expenses_by_entity.get(e.name, {})
        entity_summaries.append({
            "name": e.name,
            "entity_type": e.entity_type,
            "tax_treatment": e.tax_treatment,
            "is_active": e.is_active,
            "is_provisional": e.is_provisional,
            "total_expenses": sum(entity_expenses.values()),
            "expense_categories": entity_expenses,
        })

    total_w2 = tax_summary["w2_total_wages"]
    total_nec = tax_summary["nec_total"]
    total_div = tax_summary["div_ordinary"]
    total_cg_long = tax_summary["capital_gains_long"]
    total_cg_short = tax_summary["capital_gains_short"]
    total_interest = tax_summary["interest_income"]
    total_investment_income = total_div + total_cg_long + total_cg_short + total_interest
    total_income = total_w2 + total_nec + total_investment_income

    return {
        "tax_year": tax_year,
        "w2_wages": total_w2,
        "w2_state_allocations": tax_summary.get("w2_state_allocations", []),
        "w2_federal_withheld": tax_summary["w2_federal_withheld"],
        "board_income_nec": total_nec,
        "dividend_income_ordinary": total_div,
        "dividend_income_qualified": tax_summary["div_qualified"],
        "capital_gains_long": total_cg_long,
        "capital_gains_short": total_cg_short,
        "interest_income": total_interest,
        "total_investment_income": total_investment_income,
        "estimated_total_income": total_income,
        "total_business_expenses": all_business_expenses,
        "business_expenses_by_entity": business_expenses_by_entity,
        "entity_summaries": entity_summaries,
        "reimbursable_expenses_excluded": reimbursable_total,
        "top_personal_expense_categories": dict(
            sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)[:10]
        ),
    }


def _build_strategy_prompt(snapshot: dict[str, Any], household_context: str = "") -> str:
    household_section = household_context if household_context else "- No household profile configured"
    return f"""You are a senior CPA and tax strategist specializing in high-income households.

{TAX_CONTEXT_2025}

Household Profile:
{household_section}

Financial Summary for Tax Year {snapshot["tax_year"]}:
{json.dumps(snapshot, indent=2, default=str)}

Based on this data, generate a comprehensive list of tax optimization strategies.
For each strategy, provide a specific, actionable recommendation tailored to their numbers.

Return a JSON array of strategy objects. Each object must have:
{{
  "priority": integer 1-5 (1=highest impact/urgency),
  "title": "concise strategy title",
  "description": "detailed explanation including WHY it applies to this household and HOW to implement",
  "strategy_type": one of: bracket | deduction | credit | structure | timing | retirement | investment | state,
  "estimated_savings_low": float (conservative estimate in dollars),
  "estimated_savings_high": float (optimistic estimate in dollars),
  "action_required": "specific next steps to take",
  "deadline": "when action must be taken (e.g., April 15, December 31, No deadline)"
}}

Focus on (as applicable to their income profile):
1. Multi-state income allocation — which states have income, state tax credit strategies
2. Partnership/K-1 income — partnership tax implications
3. Retirement contributions — 401(k), backdoor Roth, SEP-IRA for side business income
4. NIIT and AMT exposure given total income
5. Capital gains optimization — long vs short term, tax-loss harvesting, RSU/ESPP treatment
6. QBI deduction eligibility for any Schedule C or pass-through income
7. Section 195 startup costs — expenses that can be elected to deduct or amortize
8. Business expenses and deductions for active Schedule C entities
9. SALT workaround strategies (if applicable)
10. Charitable giving optimization (DAF, QCD if applicable)
11. Year-end timing strategies (defer income, accelerate deductions)
12. Reimbursable expense tracking — ensure reimbursed expenses are properly excluded
13. Entity structure optimization — when to formalize or restructure business entities

Return ONLY the JSON array, no other text. Generate 8-15 strategies."""


async def _build_tax_household_context(session: AsyncSession) -> str:
    """Build dynamic household context for tax analysis prompt from DB."""
    lines: list[str] = []

    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    if household:
        filing = (household.filing_status or "mfj").upper()
        lines.append(f"- Filing status: {filing}")
        if household.spouse_a_name and household.spouse_a_employer:
            state = f", multi-state" if household.spouse_a_work_state else ""
            lines.append(f"- {household.spouse_a_name}: W-2 employee at {household.spouse_a_employer}{state}")
        elif household.spouse_a_name:
            lines.append(f"- Primary earner: {household.spouse_a_name}")
        if household.spouse_b_name and household.spouse_b_employer:
            lines.append(f"- {household.spouse_b_name}: income from {household.spouse_b_employer}")
        elif household.spouse_b_name:
            lines.append(f"- Spouse/partner: {household.spouse_b_name}")

    entity_result = await session.execute(
        select(BusinessEntity)
    )
    entities = entity_result.scalars().all()
    active = [e for e in entities if e.is_active and not e.is_provisional]
    provisional = [e for e in entities if e.is_provisional]
    inactive = [e for e in entities if not e.is_active and not e.is_provisional]

    if active:
        for e in active:
            owner_part = f" (owner: {e.owner})" if e.owner else ""
            lines.append(f"- Active business: {e.name} ({e.entity_type}, {e.tax_treatment}){owner_part}")
    if provisional:
        for e in provisional:
            owner_part = f" (owner: {e.owner})" if e.owner else ""
            lines.append(f"- Provisional entity: {e.name} ({e.entity_type}, {e.tax_treatment}){owner_part}")
    if inactive:
        for e in inactive:
            lines.append(f"- Inactive/defunct entity: {e.name} ({e.entity_type})")

    return "\n".join(lines) if lines else "- No household profile configured"


async def run_tax_analysis(
    session: AsyncSession,
    tax_year: int | None = None,
) -> list[dict[str, Any]]:
    """
    Run full tax analysis for the given year.
    Generates strategies and stores them in the DB.
    Returns the list of strategy dicts.
    """
    year = tax_year or datetime.now(timezone.utc).year
    client = get_claude_client()

    logger.info(f"Building financial snapshot for {year}...")
    snapshot = await _build_financial_snapshot(session, year)
    household_context = await _build_tax_household_context(session)

    logger.info(f"Requesting tax strategy analysis from Claude ({CLAUDE_MODEL})...")
    prompt = _build_strategy_prompt(snapshot, household_context=household_context)

    response = call_claude_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = strip_json_fences(response.content[0].text)

    strategies: list[dict] = json.loads(raw)
    logger.info(f"Received {len(strategies)} strategies from Claude.")

    # Store in DB (replace existing non-dismissed)
    await replace_tax_strategies(session, year, strategies)

    return strategies
