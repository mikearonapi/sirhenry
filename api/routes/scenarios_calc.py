"""Scenario calculation, comparison, composition, and projection endpoints."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    ScenarioCalcIn, ComposeIn, MultiYearIn, MonteCarloIn, CompareIn,
)
from pipeline.ai.scenario_analyzer import analyze_scenario_with_ai
from pipeline.db import LifeScenario
from pipeline.db.schema import HouseholdProfile, LifeEvent, EquityGrant
from pipeline.planning.life_scenarios import LifeScenarioEngine, SCENARIO_TEMPLATES
from pipeline.planning.monte_carlo import run_monte_carlo_simulation
from pipeline.planning.scenario_projection import (
    compose_scenarios,
    project_multi_year,
    compute_retirement_impact,
    compare_scenario_metrics,
    build_scenario_suggestions,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scenarios"])


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
async def compose_scenarios_endpoint(body: ComposeIn, session: AsyncSession = Depends(get_session)):
    """Combine multiple saved scenarios into an aggregate impact view."""
    result = await session.execute(
        select(LifeScenario).where(LifeScenario.id.in_(body.scenario_ids))
    )
    scenarios = result.scalars().all()
    if len(scenarios) < 2:
        raise HTTPException(400, "Need at least 2 scenarios to compose")
    return compose_scenarios(list(scenarios))


@router.post("/{scenario_id}/multi-year")
async def multi_year_projection(scenario_id: int, body: MultiYearIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scenario not found")
    return project_multi_year(s, years=body.years)


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
    return compute_retirement_impact(s, r)


@router.post("/{scenario_id}/monte-carlo")
async def monte_carlo(scenario_id: int, body: MonteCarloIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scenario not found")

    savings = (s.current_savings or 0) + (s.current_investments or 0)
    annual_contribution = ((s.monthly_take_home or 0) - (s.current_monthly_expenses or 0) - (s.new_monthly_payment or 0)) * 12

    return run_monte_carlo_simulation({
        "initial_balance": savings,
        "annual_contribution": annual_contribution,
        "runs": body.runs,
    })


@router.post("/compare")
async def compare_scenarios_endpoint(body: CompareIn, session: AsyncSession = Depends(get_session)):
    a_result = await session.execute(select(LifeScenario).where(LifeScenario.id == body.scenario_a_id))
    b_result = await session.execute(select(LifeScenario).where(LifeScenario.id == body.scenario_b_id))
    a = a_result.scalar_one_or_none()
    b = b_result.scalar_one_or_none()
    if not a or not b:
        raise HTTPException(404, "One or both scenarios not found")
    return compare_scenario_metrics(a, b)


@router.post("/{scenario_id}/ai-analysis")
async def ai_scenario_analysis(scenario_id: int, session: AsyncSession = Depends(get_session)):
    """Generate AI analysis for a life scenario using Claude."""
    result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    hp_result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = hp_result.scalar_one_or_none()

    household_context: dict = {}
    if household:
        household_context = {
            "income": (household.spouse_a_income or 0) + (household.spouse_b_income or 0),
            "filing_status": household.filing_status,
            "state": household.state,
        }

    params: dict = {}
    if scenario.parameters:
        try:
            params = json.loads(scenario.parameters) if isinstance(scenario.parameters, str) else scenario.parameters
        except (json.JSONDecodeError, TypeError):
            pass

    scenario_data = {
        "name": scenario.name,
        "scenario_type": scenario.scenario_type,
        "total_cost": scenario.total_cost or 0,
        "new_monthly_payment": scenario.new_monthly_payment or 0,
        "monthly_surplus_after": scenario.monthly_surplus_after or 0,
        "savings_rate_before_pct": scenario.savings_rate_before_pct or 0,
        "savings_rate_after_pct": scenario.savings_rate_after_pct or 0,
        "dti_before_pct": scenario.dti_before_pct or 0,
        "dti_after_pct": scenario.dti_after_pct or 0,
        "affordability_score": scenario.affordability_score or 0,
        "verdict": scenario.verdict,
        "parameters": params,
    }

    ai_result = analyze_scenario_with_ai(scenario_data, household_context)
    analysis = ai_result["analysis"]

    scenario.ai_analysis = analysis
    await session.flush()

    return {"analysis": analysis, "scenario_id": scenario_id}


@router.get("/suggestions")
async def scenario_suggestions(session: AsyncSession = Depends(get_session)):
    """Return scenario suggestions based on life events and financial data."""
    events_result = await session.execute(
        select(LifeEvent).order_by(LifeEvent.created_at.desc()).limit(20)
    )
    events = list(events_result.scalars().all())

    grants_result = await session.execute(
        select(EquityGrant).where(EquityGrant.is_active == True).limit(5)
    )
    grants = list(grants_result.scalars().all())

    return {"suggestions": build_scenario_suggestions(events, grants)}
