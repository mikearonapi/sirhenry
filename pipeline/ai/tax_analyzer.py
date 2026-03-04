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
from pipeline.ai.privacy import PIISanitizer, log_ai_privacy_audit
from pipeline.db.schema import BenefitPackage, BusinessEntity, HouseholdProfile, Transaction
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
  "deadline": "when action must be taken (e.g., April 15, December 31, No deadline)",
  "confidence": float 0.0-1.0 (how confident you are this strategy applies and the savings estimate is accurate),
  "confidence_reasoning": "one sentence explaining what makes you confident or uncertain",
  "category": one of: "quick_win" (can do this week) | "this_year" (act before Dec 31) | "big_move" (structural change like starting a business or buying property) | "long_term" (multi-year play),
  "complexity": one of: "low" (simple action) | "medium" (may need CPA) | "high" (requires legal/structural changes),
  "prerequisites_json": "JSON string array of requirements, e.g. [\\"Must have self-employment income\\"]",
  "who_its_for": "brief description of who benefits most",
  "related_simulator": one of: "roth-conversion" | "scorp-analysis" | "estimated-payments" | "daf-bunching" | "student-loans" | "multi-year" | "tax-loss-harvest" | "mega-backdoor" | "defined-benefit" | "real-estate-str" | "section-179" | "equity-comp" | "hsa-max" | "filing-status" | "qbi-deduction" | "state-comparison" | null
}}

Focus on (as applicable to their income profile):
1. Multi-state income allocation — state tax credit strategies
2. Partnership/K-1 income — partnership tax implications
3. Retirement contributions — 401(k), backdoor Roth, SEP-IRA for side business income
4. NIIT and AMT exposure given total income
5. Capital gains optimization — tax-loss harvesting, RSU/ESPP treatment
6. QBI deduction eligibility for pass-through income
7. Section 195 startup costs
8. Business expenses and deductions for Schedule C entities
9. SALT workaround strategies
10. Charitable giving optimization (DAF, QCD, donating appreciated stock)
11. Year-end timing strategies (defer income, accelerate deductions)
12. Reimbursable expense tracking
13. Entity structure optimization
14. Real estate strategies — short-term rental (STR) loophole with cost segregation and bonus depreciation to offset W-2 income
15. Buy-borrow-die — leveraging appreciated assets with portfolio loans instead of selling
16. Mega backdoor Roth — after-tax 401(k) contributions with in-plan Roth conversion
17. Defined benefit plan — sheltering $100K-$300K/year for high-income self-employed
18. Augusta Rule (Section 280A) — renting home to business for 14 days tax-free
19. Hiring family members in a legitimate business
20. Asset location — placing tax-inefficient investments in tax-advantaged accounts
21. Section 179 heavy equipment — buying equipment (excavators, trucks, etc.) and deducting the full cost year-one, then renting it out for income
22. HSA triple tax advantage — maximize contributions, invest the balance in index funds, use for medical in retirement
23. 529 plan contributions — state income tax deductions, superfunding (5-year gift election), grandparent strategies
24. Filing status optimization — MFJ vs MFS analysis, especially for dual-income couples with student loans on IDR
25. Opportunity Zones — defer and reduce capital gains through Qualified Opportunity Fund investment (180-day window from realization)
26. 1031 Like-Kind Exchange — defer capital gains on investment property sales by reinvesting in replacement property
27. Estate and gift planning — annual gift exclusion ($19K/person), irrevocable trusts, generation-skipping strategies
28. NIIT avoidance strategies — material participation, real estate professional status, passive activity grouping election
29. Equity compensation planning — RSU withholding gap analysis, ISO AMT crossover, ESPP qualifying disposition timing

Return ONLY the JSON array, no other text. Generate 8-15 strategies."""


async def _build_tax_household_context(session: AsyncSession) -> tuple[str, PIISanitizer]:
    """Build sanitized household context for tax analysis — names/employers anonymized.

    Returns (context_string, sanitizer) so entity names in the snapshot can also be sanitized.
    """
    lines: list[str] = []

    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    entity_result = await session.execute(select(BusinessEntity))
    entities = entity_result.scalars().all()

    # Build sanitizer with all known PII
    sanitizer = PIISanitizer()
    sanitizer.register_household(household, entities)

    if household:
        filing = (household.filing_status or "mfj").upper()
        lines.append(f"- Filing status: {filing}")
        if household.spouse_a_income:
            state = f", multi-state" if getattr(household, "spouse_a_work_state", None) else ""
            lines.append(f"- Primary Earner: W-2 employee at Employer A{state}")
        if household.spouse_b_income:
            lines.append(f"- Secondary Earner: income from Employer B")

    active = [e for e in entities if e.is_active and not getattr(e, "is_provisional", False)]
    provisional = [e for e in entities if getattr(e, "is_provisional", False)]
    inactive = [e for e in entities if not e.is_active and not getattr(e, "is_provisional", False)]

    if active:
        for e in active:
            owner_part = f" (owner: {sanitizer.sanitize_text(e.owner)})" if e.owner else ""
            lines.append(f"- Active business: {sanitizer.sanitize_text(e.name)} ({e.entity_type}, {e.tax_treatment}){owner_part}")
    if provisional:
        for e in provisional:
            owner_part = f" (owner: {sanitizer.sanitize_text(e.owner)})" if e.owner else ""
            lines.append(f"- Provisional entity: {sanitizer.sanitize_text(e.name)} ({e.entity_type}, {e.tax_treatment}){owner_part}")
    if inactive:
        for e in inactive:
            lines.append(f"- Inactive/defunct entity: {sanitizer.sanitize_text(e.name)} ({e.entity_type})")

    # Include benefit package info (HSA eligibility, 401k)
    if household:
        try:
            benefit_result = await session.execute(
                select(BenefitPackage).where(BenefitPackage.household_profile_id == household.id)
            )
            benefits = benefit_result.scalars().all()
            for b in benefits:
                benefit_parts = []
                if getattr(b, "has_hsa", False):
                    hsa_contrib = getattr(b, "annual_hsa_contribution", 0) or 0
                    benefit_parts.append(f"HSA eligible (contributing ${hsa_contrib:,.0f})")
                k401_contrib = getattr(b, "annual_401k_contribution", 0) or 0
                if k401_contrib > 0:
                    benefit_parts.append(f"401(k) contributing ${k401_contrib:,.0f}")
                if getattr(b, "has_after_tax_401k", False):
                    benefit_parts.append("after-tax 401(k) available")
                if benefit_parts:
                    lines.append(f"- Benefits: {', '.join(benefit_parts)}")
        except Exception:
            pass

    # Include tax strategy interview answers if available
    if household and getattr(household, "tax_strategy_profile_json", None):
        try:
            import json as _json
            interview = _json.loads(household.tax_strategy_profile_json)
            lines.append("\nTax Strategy Interview Responses:")
            for key, val in interview.items():
                label = key.replace("_", " ").title()
                lines.append(f"- {label}: {val}")
        except Exception:
            pass

    context = "\n".join(lines) if lines else "- No household profile configured"
    return context, sanitizer


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
    household_context, sanitizer = await _build_tax_household_context(session)

    # Sanitize entity names in the snapshot before sending to Claude
    sanitized_snapshot = sanitizer.sanitize_dict(snapshot) if sanitizer.has_mappings else snapshot
    log_ai_privacy_audit("tax_analysis", ["income", "expenses", "entities", "tax_items"], sanitized=True)

    logger.info(f"Requesting tax strategy analysis from Claude ({CLAUDE_MODEL})...")
    prompt = _build_strategy_prompt(sanitized_snapshot, household_context=household_context)

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

    # Audit log
    try:
        from pipeline.security.audit import log_audit
        await log_audit(session, "ai_tax_analysis", "tax_strategies", f"year={year},strategies={len(strategies)}")
    except Exception:
        pass

    return strategies
