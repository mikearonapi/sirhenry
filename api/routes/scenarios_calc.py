"""Scenario calculation, comparison, composition, and projection endpoints."""
import json
import logging
import os
import random
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import LifeScenario
from pipeline.db.schema import HouseholdProfile, LifeEvent, EquityGrant, Goal
from pipeline.planning.life_scenarios import LifeScenarioEngine, SCENARIO_TEMPLATES
from pipeline.utils import CLAUDE_MODEL

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scenarios"])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ScenarioCalcIn(BaseModel):
    """Stateless calculation request (no save)."""
    scenario_type: str
    parameters: dict
    annual_income: float
    monthly_take_home: float
    current_monthly_expenses: float
    current_monthly_debt_payments: float = 0
    current_savings: float = 0
    current_investments: float = 0


class ComposeIn(BaseModel):
    scenario_ids: list[int]

class MultiYearIn(BaseModel):
    years: int = 10

class MonteCarloIn(BaseModel):
    runs: int = Field(default=1000, ge=100, le=10000)

class CompareIn(BaseModel):
    scenario_a_id: int
    scenario_b_id: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/templates")
async def get_templates():
    """Get all available scenario templates with parameter definitions."""
    return {"templates": SCENARIO_TEMPLATES}


@router.post("/calculate")
async def calculate_scenario(body: ScenarioCalcIn):
    """Stateless affordability calculation -- doesn't save."""
    result = LifeScenarioEngine.calculate(
        scenario_type=body.scenario_type,
        params=body.parameters,
        annual_income=body.annual_income,
        monthly_take_home=body.monthly_take_home,
        current_monthly_expenses=body.current_monthly_expenses,
        current_monthly_debt=body.current_monthly_debt_payments,
        current_savings=body.current_savings,
        current_investments=body.current_investments,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/compose")
async def compose_scenarios(body: ComposeIn, session: AsyncSession = Depends(get_session)):
    """Combine multiple saved scenarios into an aggregate impact view."""
    result = await session.execute(
        select(LifeScenario).where(LifeScenario.id.in_(body.scenario_ids))
    )
    scenarios = result.scalars().all()
    if len(scenarios) < 2:
        raise HTTPException(400, "Need at least 2 scenarios to compose")

    combined_payment = sum(s.new_monthly_payment or 0 for s in scenarios)
    base = scenarios[0]
    take_home = base.monthly_take_home or 0
    expenses = base.current_monthly_expenses or 0
    income = base.annual_income or 0

    new_surplus = take_home - expenses - combined_payment
    sr_before = ((take_home - expenses) / take_home * 100) if take_home > 0 else 0
    sr_after = (new_surplus / take_home * 100) if take_home > 0 else 0
    dti_after = ((expenses + combined_payment) / (income / 12) * 100) if income > 0 else 0

    score = max(0, min(100, 50 + (new_surplus / take_home * 100) if take_home > 0 else 0))
    if score >= 70:
        verdict = "comfortable"
    elif score >= 55:
        verdict = "feasible"
    elif score >= 40:
        verdict = "stretch"
    elif score >= 25:
        verdict = "risky"
    else:
        verdict = "not_recommended"

    return {
        "combined_monthly_impact": round(combined_payment, 2),
        "combined_savings_rate_after": round(sr_after, 2),
        "combined_dti_after": round(dti_after, 2),
        "combined_affordability_score": round(score, 2),
        "combined_verdict": verdict,
        "scenarios": [
            {"id": s.id, "name": s.name, "monthly_impact": s.new_monthly_payment or 0}
            for s in scenarios
        ],
    }


@router.post("/{scenario_id}/multi-year")
async def multi_year_projection(scenario_id: int, body: MultiYearIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scenario not found")

    take_home = (s.monthly_take_home or 0) * 12
    expenses = (s.current_monthly_expenses or 0) * 12
    payment = (s.new_monthly_payment or 0) * 12
    savings_rate = ((take_home - expenses - payment) / take_home) if take_home > 0 else 0
    savings = (s.current_savings or 0) + (s.current_investments or 0)

    years = []
    net_worth = savings
    for y in range(1, body.years + 1):
        income = take_home * (1.03 ** y)
        annual_expenses = (expenses + payment) * (1.02 ** y)
        annual_savings = income - annual_expenses
        net_worth = net_worth * 1.07 + annual_savings
        years.append({
            "year": y,
            "net_worth": round(net_worth, 2),
            "savings": round(annual_savings, 2),
            "expenses": round(annual_expenses, 2),
            "cash_flow": round(income - annual_expenses, 2),
        })

    return {"years": years}


@router.post("/{scenario_id}/retirement-impact")
async def retirement_impact(scenario_id: int, session: AsyncSession = Depends(get_session)):
    s_result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    s = s_result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scenario not found")

    from pipeline.db import RetirementProfile
    r_result = await session.execute(
        select(RetirementProfile).where(RetirementProfile.is_primary.is_(True)).limit(1)
    )
    r = r_result.scalar_one_or_none()
    if not r:
        return {
            "current_retirement_age": 65, "new_retirement_age": 65,
            "years_delayed": 0, "current_fire_number": 0, "new_fire_number": 0,
        }

    monthly_impact = s.new_monthly_payment or 0
    annual_impact = monthly_impact * 12
    current_fire = r.fire_number or 0
    new_fire = current_fire + annual_impact * 25

    current_age = r.retirement_age or 65
    savings_monthly = r.monthly_retirement_contribution or 0
    reduced_savings = max(0, savings_monthly - monthly_impact)
    if reduced_savings > 0 and savings_monthly > 0:
        ratio = savings_monthly / reduced_savings
        delay = max(0, (ratio - 1) * (current_age - (r.current_age or 35)))
    else:
        delay = 5
    new_age = min(75, current_age + round(delay))

    return {
        "current_retirement_age": current_age,
        "new_retirement_age": new_age,
        "years_delayed": round(delay, 1),
        "current_fire_number": round(current_fire, 2),
        "new_fire_number": round(new_fire, 2),
    }


@router.post("/{scenario_id}/monte-carlo")
async def monte_carlo(scenario_id: int, body: MonteCarloIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scenario not found")

    savings = (s.current_savings or 0) + (s.current_investments or 0)
    annual_contribution = ((s.monthly_take_home or 0) - (s.current_monthly_expenses or 0) - (s.new_monthly_payment or 0)) * 12

    outcomes = []
    for _ in range(body.runs):
        balance = savings
        for _ in range(20):
            r = random.gauss(0.07, 0.15)
            balance = balance * (1 + r) + annual_contribution
        outcomes.append(balance)

    outcomes.sort()
    n = len(outcomes)
    return {
        "p10": round(outcomes[int(n * 0.10)], 2),
        "p25": round(outcomes[int(n * 0.25)], 2),
        "p50": round(outcomes[int(n * 0.50)], 2),
        "p75": round(outcomes[int(n * 0.75)], 2),
        "p90": round(outcomes[int(n * 0.90)], 2),
        "runs": body.runs,
    }


@router.post("/compare")
async def compare_scenarios(body: CompareIn, session: AsyncSession = Depends(get_session)):
    a_result = await session.execute(select(LifeScenario).where(LifeScenario.id == body.scenario_a_id))
    b_result = await session.execute(select(LifeScenario).where(LifeScenario.id == body.scenario_b_id))
    a = a_result.scalar_one_or_none()
    b = b_result.scalar_one_or_none()
    if not a or not b:
        raise HTTPException(404, "One or both scenarios not found")

    def _metrics(s):
        return {
            "monthly_payment": s.new_monthly_payment or 0,
            "total_cost": s.total_cost or 0,
            "savings_rate_after": s.savings_rate_after_pct or 0,
            "dti_after": s.dti_after_pct or 0,
            "affordability_score": s.affordability_score or 0,
        }

    ma = _metrics(a)
    mb = _metrics(b)
    diffs = {k: round(ma[k] - mb[k], 2) for k in ma}

    return {
        "scenario_a": {"id": a.id, "name": a.name, "metrics": ma},
        "scenario_b": {"id": b.id, "name": b.name, "metrics": mb},
        "differences": diffs,
    }


@router.post("/{scenario_id}/ai-analysis")
async def ai_scenario_analysis(scenario_id: int, session: AsyncSession = Depends(get_session)):
    """Generate AI analysis for a life scenario using Claude."""
    result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    # Get household context
    hp_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = hp_result.scalar_one_or_none()

    household_context = ""
    if household:
        income = (household.spouse_a_income or 0) + (household.spouse_b_income or 0)
        household_context = f"Household income: ${income:,.0f}, Filing: {household.filing_status}, State: {household.state}"

    params = {}
    if scenario.parameters:
        try:
            params = json.loads(scenario.parameters) if isinstance(scenario.parameters, str) else scenario.parameters
        except (json.JSONDecodeError, TypeError):
            pass

    prompt = f"""Analyze this life scenario for a HENRY (High Earner, Not Rich Yet) and provide actionable advice in 3-4 concise paragraphs.

Scenario: {scenario.name} ({scenario.scenario_type})
{household_context}

Financial Impact:
- Total cost: ${(scenario.total_cost or 0):,.0f}
- New monthly payment: ${(scenario.new_monthly_payment or 0):,.0f}
- Monthly surplus after: ${(scenario.monthly_surplus_after or 0):,.0f}
- Savings rate: {(scenario.savings_rate_before_pct or 0):.1f}% → {(scenario.savings_rate_after_pct or 0):.1f}%
- DTI ratio: {(scenario.dti_before_pct or 0):.1f}% → {(scenario.dti_after_pct or 0):.1f}%
- Affordability score: {(scenario.affordability_score or 0):.0f}/100
- Verdict: {scenario.verdict}

Parameters: {json.dumps(params)}

Provide:
1. Whether this is a good financial decision and why
2. Key risks to watch out for
3. Specific steps to prepare (tax optimization, timing, savings targets)
4. How this affects their long-term wealth building as a HENRY"""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "AI features not configured")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    analysis = response.content[0].text if response.content else ""

    # Save to scenario
    scenario.ai_analysis = analysis
    await session.flush()

    return {"analysis": analysis, "scenario_id": scenario_id}


# ---------------------------------------------------------------------------
# Life Event → Scenario Suggestions
# ---------------------------------------------------------------------------
EVENT_TO_SCENARIO_MAP: dict[str, list[dict]] = {
    "real_estate_purchase": [
        {"scenario_type": "second_home", "label": "Model Home Purchase", "reason": "You recorded a real estate purchase — run the numbers"},
    ],
    "real_estate_sale": [
        {"scenario_type": "lifestyle_upgrade", "label": "Lifestyle Upgrade with Proceeds", "reason": "Home sale proceeds could fund an upgrade"},
        {"scenario_type": "early_retirement", "label": "Accelerate Retirement", "reason": "Could sale proceeds accelerate your FIRE timeline?"},
    ],
    "family_birth": [
        {"scenario_type": "college_fund", "label": "Start a College Fund", "reason": "New child — start a 529 plan early for max compound growth"},
    ],
    "family_adoption": [
        {"scenario_type": "college_fund", "label": "Start a College Fund", "reason": "Plan for education expenses with a 529"},
    ],
    "family_marriage": [
        {"scenario_type": "second_home", "label": "Buy a Home Together", "reason": "Combined income could support a home purchase"},
        {"scenario_type": "lifestyle_upgrade", "label": "Combined Lifestyle Adjustment", "reason": "Marriage changes your financial picture"},
    ],
    "employment_job_change": [
        {"scenario_type": "lifestyle_upgrade", "label": "Lifestyle Adjustment", "reason": "New job may change your income and expenses"},
    ],
    "employment_layoff": [
        {"scenario_type": "sabbatical", "label": "Plan Career Break", "reason": "Model how long your savings can sustain you"},
        {"scenario_type": "starting_business", "label": "Start a Business", "reason": "Layoff could be the push to go entrepreneurial"},
    ],
    "employment_start_business": [
        {"scenario_type": "starting_business", "label": "Business Viability Analysis", "reason": "Run the numbers on your new venture"},
    ],
    "education_college": [
        {"scenario_type": "college_fund", "label": "College Fund Calculator", "reason": "Model tuition costs and savings needed"},
    ],
}


@router.get("/suggestions")
async def scenario_suggestions(session: AsyncSession = Depends(get_session)):
    """Return scenario suggestions based on life events and financial data."""
    suggestions: list[dict] = []
    seen_types: set[str] = set()

    # 1. Life event-based suggestions
    events = await session.execute(
        select(LifeEvent).order_by(LifeEvent.created_at.desc()).limit(20)
    )
    for event in events.scalars().all():
        key = f"{event.event_type}_{event.event_subtype}" if event.event_subtype else event.event_type
        mapped = EVENT_TO_SCENARIO_MAP.get(key, EVENT_TO_SCENARIO_MAP.get(event.event_type, []))
        for suggestion in mapped:
            if suggestion["scenario_type"] not in seen_types:
                suggestions.append({
                    **suggestion,
                    "source": "life_event",
                    "source_detail": event.title,
                })
                seen_types.add(suggestion["scenario_type"])

    # 2. Equity-based suggestions — if they have equity grants, suggest tax reserve goal
    grants = await session.execute(
        select(EquityGrant).where(EquityGrant.is_active == True).limit(5)
    )
    grant_list = grants.scalars().all()
    if grant_list and "lifestyle_upgrade" not in seen_types:
        total_vest_value = sum(
            (g.unvested_shares or 0) * (g.current_fmv or 0) for g in grant_list
        )
        if total_vest_value > 0:
            suggestions.append({
                "scenario_type": "lifestyle_upgrade",
                "label": "RSU Tax Reserve Strategy",
                "reason": f"~${total_vest_value:,.0f} in unvested equity — plan for tax withholding gaps",
                "source": "equity_grants",
            })

    # 3. Default HENRY suggestions if no events
    if not suggestions:
        suggestions = [
            {"scenario_type": "second_home", "label": "Buy a Home", "reason": "Most HENRYs' biggest financial decision", "source": "default"},
            {"scenario_type": "college_fund", "label": "Start a College Fund", "reason": "Early 529 contributions have max compound growth", "source": "default"},
            {"scenario_type": "early_retirement", "label": "Early Retirement / FIRE", "reason": "See if your savings rate supports early retirement", "source": "default"},
            {"scenario_type": "starting_business", "label": "Side Business", "reason": "Many HENRYs build wealth through entrepreneurship", "source": "default"},
        ]

    return {"suggestions": suggestions}
