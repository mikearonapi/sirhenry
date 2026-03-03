"""Scenarios — life decision affordability engine for HENRYs. CRUD endpoints."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import LifeScenario
from pipeline.planning.life_scenarios import LifeScenarioEngine

from api.routes.scenarios_calc import router as calc_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scenarios", tags=["scenarios"])

# Include sub-routers
router.include_router(calc_router)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class ScenarioIn(BaseModel):
    name: str
    scenario_type: str
    parameters: dict
    annual_income: float
    monthly_take_home: float
    current_monthly_expenses: float
    current_monthly_debt_payments: float = 0
    current_savings: float = 0
    current_investments: float = 0
    notes: Optional[str] = None


class ScenarioUpdateIn(BaseModel):
    name: Optional[str] = None
    parameters: Optional[dict] = None
    is_favorite: Optional[bool] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    scenario_type: str
    parameters: dict
    annual_income: Optional[float]
    monthly_take_home: Optional[float]
    current_monthly_expenses: Optional[float]
    total_cost: Optional[float]
    new_monthly_payment: Optional[float]
    monthly_surplus_after: Optional[float]
    savings_rate_before_pct: Optional[float]
    savings_rate_after_pct: Optional[float]
    dti_before_pct: Optional[float]
    dti_after_pct: Optional[float]
    affordability_score: Optional[float]
    verdict: Optional[str]
    results_detail: Optional[dict]
    ai_analysis: Optional[str]
    status: str
    is_favorite: bool
    notes: Optional[str]
    created_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(
    status: Optional[str] = None,
    scenario_type: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(LifeScenario).order_by(LifeScenario.is_favorite.desc(), LifeScenario.created_at.desc())
    if status:
        q = q.where(LifeScenario.status == status)
    if scenario_type:
        q = q.where(LifeScenario.scenario_type == scenario_type)
    result = await session.execute(q)
    return [_scenario_out(s) for s in result.scalars().all()]


@router.post("", response_model=ScenarioOut)
async def create_scenario(body: ScenarioIn, session: AsyncSession = Depends(get_session)):
    # Run calculation
    calc_result = LifeScenarioEngine.calculate(
        scenario_type=body.scenario_type,
        params=body.parameters,
        annual_income=body.annual_income,
        monthly_take_home=body.monthly_take_home,
        current_monthly_expenses=body.current_monthly_expenses,
        current_monthly_debt=body.current_monthly_debt_payments,
        current_savings=body.current_savings,
        current_investments=body.current_investments,
    )
    if "error" in calc_result:
        raise HTTPException(400, calc_result["error"])

    scenario = LifeScenario(
        name=body.name,
        scenario_type=body.scenario_type,
        parameters=json.dumps(body.parameters),
        annual_income=body.annual_income,
        monthly_take_home=body.monthly_take_home,
        current_monthly_expenses=body.current_monthly_expenses,
        current_monthly_debt_payments=body.current_monthly_debt_payments,
        current_savings=body.current_savings,
        current_investments=body.current_investments,
        total_cost=calc_result.get("total_cost"),
        new_monthly_payment=calc_result.get("new_monthly_payment"),
        monthly_surplus_after=calc_result.get("monthly_surplus_after"),
        savings_rate_before_pct=calc_result.get("savings_rate_before_pct"),
        savings_rate_after_pct=calc_result.get("savings_rate_after_pct"),
        dti_before_pct=calc_result.get("dti_before_pct"),
        dti_after_pct=calc_result.get("dti_after_pct"),
        affordability_score=calc_result.get("affordability_score"),
        verdict=calc_result.get("verdict"),
        results_detail=json.dumps(calc_result),
        status="computed",
        notes=body.notes,
    )
    session.add(scenario)
    await session.flush()
    return _scenario_out(scenario)


@router.patch("/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(
    scenario_id: int,
    body: ScenarioUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(LifeScenario).where(LifeScenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "parameters" in updates:
        updates["parameters"] = json.dumps(updates["parameters"])
    for k, v in updates.items():
        setattr(scenario, k, v)
    scenario.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return _scenario_out(scenario)


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(LifeScenario).where(LifeScenario.id == scenario_id))
    return {"deleted": scenario_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scenario_out(s: LifeScenario) -> ScenarioOut:
    params = {}
    if s.parameters:
        try:
            params = json.loads(s.parameters) if isinstance(s.parameters, str) else s.parameters
        except (json.JSONDecodeError, TypeError):
            params = {}

    results = None
    if s.results_detail:
        try:
            results = json.loads(s.results_detail) if isinstance(s.results_detail, str) else s.results_detail
        except (json.JSONDecodeError, TypeError):
            results = None

    return ScenarioOut(
        id=s.id,
        name=s.name,
        scenario_type=s.scenario_type,
        parameters=params,
        annual_income=s.annual_income,
        monthly_take_home=s.monthly_take_home,
        current_monthly_expenses=s.current_monthly_expenses,
        total_cost=s.total_cost,
        new_monthly_payment=s.new_monthly_payment,
        monthly_surplus_after=s.monthly_surplus_after,
        savings_rate_before_pct=s.savings_rate_before_pct,
        savings_rate_after_pct=s.savings_rate_after_pct,
        dti_before_pct=s.dti_before_pct,
        dti_after_pct=s.dti_after_pct,
        affordability_score=s.affordability_score,
        verdict=s.verdict,
        results_detail=results,
        ai_analysis=s.ai_analysis,
        status=s.status,
        is_favorite=s.is_favorite,
        notes=s.notes,
        created_at=s.created_at.isoformat() if s.created_at else "",
    )
