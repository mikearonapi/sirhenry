"""Portfolio — investment holdings CRUD and snapshots."""
import logging
from datetime import datetime, date, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import InvestmentHolding

from api.routes.portfolio_crypto import router as crypto_router
from api.routes.portfolio_analytics import router as analytics_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Include sub-routers
router.include_router(crypto_router)
router.include_router(analytics_router)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class HoldingIn(BaseModel):
    ticker: str
    name: Optional[str] = None
    asset_class: str = "stock"
    shares: float
    cost_basis_per_share: Optional[float] = None
    purchase_date: Optional[str] = None
    account_id: Optional[int] = None
    tax_lot_id: Optional[str] = None
    notes: Optional[str] = None


class HoldingUpdateIn(BaseModel):
    shares: Optional[float] = None
    cost_basis_per_share: Optional[float] = None
    name: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: Optional[int]
    ticker: str
    name: Optional[str]
    asset_class: str
    shares: float
    cost_basis_per_share: Optional[float]
    total_cost_basis: Optional[float]
    purchase_date: Optional[str]
    current_price: Optional[float]
    current_value: Optional[float]
    unrealized_gain_loss: Optional[float]
    unrealized_gain_loss_pct: Optional[float]
    term: Optional[str]
    sector: Optional[str]
    dividend_yield: Optional[float]
    last_price_update: Optional[str]
    is_active: bool
    notes: Optional[str]


# ---------------------------------------------------------------------------
# Stock/ETF Holdings CRUD
# ---------------------------------------------------------------------------
@router.get("/holdings", response_model=list[HoldingOut])
async def list_holdings(
    active_only: bool = True,
    session: AsyncSession = Depends(get_session),
):
    q = select(InvestmentHolding)
    if active_only:
        q = q.where(InvestmentHolding.is_active == True)
    q = q.order_by(InvestmentHolding.current_value.desc().nullslast())
    result = await session.execute(q)
    holdings = list(result.scalars().all())
    return [_holding_out(h) for h in holdings]


@router.post("/holdings", response_model=HoldingOut)
async def create_holding(body: HoldingIn, session: AsyncSession = Depends(get_session)):
    cost = body.cost_basis_per_share * body.shares if body.cost_basis_per_share else None
    h = InvestmentHolding(
        ticker=body.ticker.upper(),
        name=body.name,
        asset_class=body.asset_class,
        shares=body.shares,
        cost_basis_per_share=body.cost_basis_per_share,
        total_cost_basis=cost,
        purchase_date=date.fromisoformat(body.purchase_date) if body.purchase_date else None,
        account_id=body.account_id,
        tax_lot_id=body.tax_lot_id,
        notes=body.notes,
    )
    session.add(h)
    await session.flush()
    return _holding_out(h)


@router.patch("/holdings/{holding_id}", response_model=HoldingOut)
async def update_holding(
    holding_id: int,
    body: HoldingUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(InvestmentHolding).where(InvestmentHolding.id == holding_id))
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(404, "Holding not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    for k, v in updates.items():
        setattr(h, k, v)
    if "shares" in updates or "cost_basis_per_share" in updates:
        h.total_cost_basis = (h.cost_basis_per_share or 0) * (h.shares or 0)
    h.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return _holding_out(h)


@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(InvestmentHolding).where(InvestmentHolding.id == holding_id))
    return {"deleted": holding_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _holding_out(h: InvestmentHolding) -> HoldingOut:
    return HoldingOut(
        id=h.id,
        account_id=h.account_id,
        ticker=h.ticker,
        name=h.name,
        asset_class=h.asset_class,
        shares=h.shares,
        cost_basis_per_share=h.cost_basis_per_share,
        total_cost_basis=h.total_cost_basis,
        purchase_date=h.purchase_date.isoformat() if h.purchase_date else None,
        current_price=h.current_price,
        current_value=h.current_value,
        unrealized_gain_loss=h.unrealized_gain_loss,
        unrealized_gain_loss_pct=h.unrealized_gain_loss_pct,
        term=h.term,
        sector=h.sector,
        dividend_yield=h.dividend_yield,
        last_price_update=h.last_price_update.isoformat() if h.last_price_update else None,
        is_active=h.is_active,
        notes=h.notes,
    )
