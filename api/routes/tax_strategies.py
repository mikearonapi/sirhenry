"""Tax strategy endpoints — analyze, list, dismiss strategies."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import TaxStrategyOut
from pipeline.db import dismiss_strategy, get_tax_strategies

router = APIRouter(tags=["tax"])


@router.get("/strategies", response_model=list[TaxStrategyOut])
async def list_strategies(
    tax_year: Optional[int] = Query(None),
    include_dismissed: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    strategies = await get_tax_strategies(
        session, tax_year=tax_year, include_dismissed=include_dismissed
    )
    return [TaxStrategyOut.model_validate(s) for s in strategies]


@router.post("/strategies/analyze")
async def run_tax_analysis(
    tax_year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Run Claude tax analysis and store new strategies."""
    from pipeline.ai.tax_analyzer import run_tax_analysis as _analyze
    year = tax_year or datetime.now(timezone.utc).year
    strategies = await _analyze(session, tax_year=year)
    return {"generated": len(strategies), "tax_year": year}


@router.patch("/strategies/{strategy_id}/dismiss")
async def dismiss_tax_strategy(
    strategy_id: int,
    session: AsyncSession = Depends(get_session),
):
    await dismiss_strategy(session, strategy_id)
    return {"dismissed": strategy_id}
