"""Portfolio crypto holdings endpoints."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import CryptoHolding

router = APIRouter(tags=["portfolio"])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class CryptoHoldingIn(BaseModel):
    coin_id: str
    symbol: str
    name: Optional[str] = None
    quantity: float
    cost_basis_per_unit: Optional[float] = None
    purchase_date: Optional[str] = None
    wallet_or_exchange: Optional[str] = None
    notes: Optional[str] = None


class CryptoHoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    coin_id: str
    symbol: str
    name: Optional[str]
    quantity: float
    cost_basis_per_unit: Optional[float]
    total_cost_basis: Optional[float]
    current_price: Optional[float]
    current_value: Optional[float]
    unrealized_gain_loss: Optional[float]
    price_change_24h_pct: Optional[float]
    wallet_or_exchange: Optional[str]
    is_active: bool
    notes: Optional[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/crypto", response_model=list[CryptoHoldingOut])
async def list_crypto(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(CryptoHolding).where(CryptoHolding.is_active == True)
        .order_by(CryptoHolding.current_value.desc().nullslast())
    )
    return [_crypto_out(c) for c in result.scalars().all()]


@router.post("/crypto", response_model=CryptoHoldingOut)
async def create_crypto(body: CryptoHoldingIn, session: AsyncSession = Depends(get_session)):
    cost = body.cost_basis_per_unit * body.quantity if body.cost_basis_per_unit else None
    c = CryptoHolding(
        coin_id=body.coin_id.lower(),
        symbol=body.symbol.upper(),
        name=body.name,
        quantity=body.quantity,
        cost_basis_per_unit=body.cost_basis_per_unit,
        total_cost_basis=cost,
        purchase_date=date.fromisoformat(body.purchase_date) if body.purchase_date else None,
        wallet_or_exchange=body.wallet_or_exchange,
        notes=body.notes,
    )
    session.add(c)
    await session.flush()
    return _crypto_out(c)


@router.delete("/crypto/{crypto_id}")
async def delete_crypto(crypto_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(CryptoHolding).where(CryptoHolding.id == crypto_id))
    return {"deleted": crypto_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _crypto_out(c: CryptoHolding) -> CryptoHoldingOut:
    return CryptoHoldingOut(
        id=c.id,
        coin_id=c.coin_id,
        symbol=c.symbol,
        name=c.name,
        quantity=c.quantity,
        cost_basis_per_unit=c.cost_basis_per_unit,
        total_cost_basis=c.total_cost_basis,
        current_price=c.current_price,
        current_value=c.current_value,
        unrealized_gain_loss=c.unrealized_gain_loss,
        price_change_24h_pct=c.price_change_24h_pct,
        wallet_or_exchange=c.wallet_or_exchange,
        is_active=c.is_active,
        notes=c.notes,
    )
