"""Equity compensation management and analysis endpoints."""
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import EquityGrant, VestingEvent, EquityTaxProjection
from pipeline.planning.equity_comp import EquityCompEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/equity-comp", tags=["equity-comp"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class EquityGrantIn(BaseModel):
    employer_name: str
    grant_type: str = Field(pattern=r"^(rsu|iso|nso|espp)$")
    grant_date: date
    total_shares: float
    vested_shares: float = 0.0
    unvested_shares: float = 0.0
    vesting_schedule_json: Optional[str] = None
    strike_price: Optional[float] = None
    current_fmv: Optional[float] = None
    exercise_price: Optional[float] = None
    expiration_date: Optional[date] = None
    ticker: Optional[str] = None
    notes: Optional[str] = None


class EquityGrantUpdateIn(BaseModel):
    employer_name: Optional[str] = None
    grant_type: Optional[str] = None
    total_shares: Optional[float] = None
    vested_shares: Optional[float] = None
    unvested_shares: Optional[float] = None
    vesting_schedule_json: Optional[str] = None
    strike_price: Optional[float] = None
    current_fmv: Optional[float] = None
    exercise_price: Optional[float] = None
    expiration_date: Optional[date] = None
    ticker: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class EquityGrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employer_name: str
    grant_type: str
    grant_date: date
    total_shares: float
    vested_shares: float
    unvested_shares: float
    vesting_schedule_json: Optional[str]
    strike_price: Optional[float]
    current_fmv: Optional[float]
    exercise_price: Optional[float]
    expiration_date: Optional[date]
    ticker: Optional[str]
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class VestingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grant_id: int
    vest_date: date
    shares: float
    price_at_vest: Optional[float]
    withheld_shares: Optional[float]
    federal_withholding_pct: Optional[float]
    state_withholding_pct: Optional[float]
    is_sold: bool
    sale_price: Optional[float]
    sale_date: Optional[date]
    net_proceeds: Optional[float]
    tax_impact_json: Optional[str]
    status: str


class WithholdingGapIn(BaseModel):
    vest_income: float
    other_income: float
    filing_status: str = "mfj"
    state: str = "CA"


class AMTCrossoverIn(BaseModel):
    iso_shares_available: int
    strike_price: float
    current_fmv: float
    other_income: float
    filing_status: str = "mfj"


class SellStrategyIn(BaseModel):
    shares: float
    cost_basis_per_share: float
    current_price: float
    other_income: float
    filing_status: str = "mfj"
    holding_period_months: int = 0


class DepartureIn(BaseModel):
    leave_date: str
    grants: list[dict]
    other_income: float = 200_000
    filing_status: str = "mfj"


class ESPPAnalysisIn(BaseModel):
    purchase_price: float
    fmv_at_purchase: float
    fmv_at_sale: float
    shares: float
    purchase_date: str
    sale_date: str
    offering_date: str
    discount_pct: float = 15.0
    other_income: float = 200_000
    filing_status: str = "mfj"


class ConcentrationRiskIn(BaseModel):
    employer_stock_value: float
    total_net_worth: float


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/grants", response_model=list[EquityGrantOut])
async def list_grants(
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_session),
):
    q = select(EquityGrant).order_by(EquityGrant.grant_date.desc())
    if active_only:
        q = q.where(EquityGrant.is_active.is_(True))
    result = await session.execute(q)
    return result.scalars().all()


@router.post("/grants", response_model=EquityGrantOut, status_code=201)
async def create_grant(body: EquityGrantIn, session: AsyncSession = Depends(get_session)):
    grant = EquityGrant(**body.model_dump())
    if grant.unvested_shares == 0 and grant.vested_shares == 0:
        grant.unvested_shares = grant.total_shares
    session.add(grant)
    await session.flush()
    await session.refresh(grant)
    return grant


@router.patch("/grants/{grant_id}", response_model=EquityGrantOut)
async def update_grant(grant_id: int, body: EquityGrantUpdateIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(EquityGrant).where(EquityGrant.id == grant_id))
    grant = result.scalar_one_or_none()
    if not grant:
        raise HTTPException(404, "Grant not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(grant, k, v)
    grant.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(grant)
    return grant


@router.delete("/grants/{grant_id}", status_code=204)
async def delete_grant(grant_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(EquityGrant).where(EquityGrant.id == grant_id))
    grant = result.scalar_one_or_none()
    if not grant:
        raise HTTPException(404, "Grant not found")
    await session.delete(grant)
    await session.flush()


# ---------------------------------------------------------------------------
# Vesting calendar
# ---------------------------------------------------------------------------

@router.get("/grants/{grant_id}/vesting", response_model=list[VestingEventOut])
async def get_vesting_calendar(grant_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(VestingEvent).where(VestingEvent.grant_id == grant_id).order_by(VestingEvent.vest_date)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Dashboard aggregate
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def equity_dashboard(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(EquityGrant).where(EquityGrant.is_active.is_(True)))
    grants = result.scalars().all()

    total_value = 0.0
    upcoming_vest_value = 0.0
    total_withholding_gap = 0.0
    total_employer_stock = 0.0
    grants_summary = []

    today = date.today()
    one_year = today.replace(year=today.year + 1)

    # Fetch all upcoming vesting events for active grants in one query
    all_grant_ids = [g.id for g in grants]
    vest_result = await session.execute(
        select(VestingEvent)
        .where(
            VestingEvent.grant_id.in_(all_grant_ids),
            VestingEvent.vest_date > today,
            VestingEvent.vest_date <= one_year,
            VestingEvent.status == "upcoming",
        )
    )
    upcoming_by_grant: dict[int, list] = {}
    for ev in vest_result.scalars().all():
        upcoming_by_grant.setdefault(ev.grant_id, []).append(ev)

    for g in grants:
        fmv = g.current_fmv or 0
        strike = g.strike_price or 0
        spread = max(0, fmv - strike) if g.grant_type in ("iso", "nso") else fmv

        vested_value = (g.vested_shares or 0) * spread
        unvested_value = (g.unvested_shares or 0) * spread
        total_value += vested_value + unvested_value
        total_employer_stock += vested_value + unvested_value

        # Use pre-loaded upcoming vesting events
        upcoming_events = upcoming_by_grant.get(g.id, [])
        for ev in upcoming_events:
            upcoming_vest_value += (ev.shares or 0) * spread

        gap_result = EquityCompEngine.calculate_withholding_gap(
            vest_income=unvested_value * 0.25,
            other_income=150_000,
            filing_status="mfj",
        )
        total_withholding_gap += gap_result.withholding_gap

        grants_summary.append({
            "id": g.id,
            "employer": g.employer_name,
            "grant_type": g.grant_type,
            "total_shares": g.total_shares,
            "vested_shares": g.vested_shares,
            "unvested_shares": g.unvested_shares,
            "current_fmv": fmv,
            "total_value": round(vested_value + unvested_value, 2),
        })

    return {
        "total_equity_value": round(total_value, 2),
        "upcoming_vest_value_12mo": round(upcoming_vest_value, 2),
        "total_withholding_gap": round(total_withholding_gap, 2),
        "grants_count": len(grants),
        "grants": grants_summary,
    }


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------

@router.post("/withholding-gap")
async def calc_withholding_gap(body: WithholdingGapIn):
    result = EquityCompEngine.calculate_withholding_gap(
        vest_income=body.vest_income,
        other_income=body.other_income,
        filing_status=body.filing_status,
        state=body.state,
    )
    return result.__dict__


@router.post("/amt-crossover")
async def calc_amt_crossover(body: AMTCrossoverIn):
    result = EquityCompEngine.calculate_amt_crossover(
        iso_shares_available=body.iso_shares_available,
        strike_price=body.strike_price,
        current_fmv=body.current_fmv,
        other_income=body.other_income,
        filing_status=body.filing_status,
    )
    return result.__dict__


@router.post("/sell-strategy")
async def calc_sell_strategy(body: SellStrategyIn):
    result = EquityCompEngine.model_sell_strategy(
        shares=body.shares,
        cost_basis_per_share=body.cost_basis_per_share,
        current_price=body.current_price,
        other_income=body.other_income,
        filing_status=body.filing_status,
        holding_period_months=body.holding_period_months,
    )
    return {
        "immediate_sell": result.immediate_sell,
        "hold_one_year": result.hold_one_year,
        "staged_sell": result.staged_sell,
        "recommendation": result.recommendation,
    }


@router.post("/what-if-leave")
async def calc_departure(body: DepartureIn):
    result = EquityCompEngine.what_if_i_leave(
        grants=body.grants, leave_date=body.leave_date,
        other_income=body.other_income, filing_status=body.filing_status,
    )
    return result.__dict__


@router.post("/espp-analysis")
async def calc_espp(body: ESPPAnalysisIn):
    result = EquityCompEngine.espp_disposition_analysis(
        purchase_price=body.purchase_price,
        fmv_at_purchase=body.fmv_at_purchase,
        fmv_at_sale=body.fmv_at_sale,
        shares=body.shares,
        purchase_date=body.purchase_date,
        sale_date=body.sale_date,
        offering_date=body.offering_date,
        discount_pct=body.discount_pct,
        other_income=body.other_income,
        filing_status=body.filing_status,
    )
    return result.__dict__


@router.post("/concentration-risk")
async def calc_concentration(body: ConcentrationRiskIn):
    result = EquityCompEngine.concentration_risk(
        employer_stock_value=body.employer_stock_value,
        total_net_worth=body.total_net_worth,
    )
    return result.__dict__
