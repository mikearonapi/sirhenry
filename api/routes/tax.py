"""Tax routes — tax items CRUD + sub-router registration."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import TaxItemOut
from pipeline.db import get_tax_items

from api.routes.tax_strategies import router as strategies_router
from api.routes.tax_analysis import router as analysis_router

router = APIRouter(prefix="/tax", tags=["tax"])

# Include sub-routers (no extra prefix — they define paths relative to /tax)
router.include_router(strategies_router)
router.include_router(analysis_router)


@router.get("/items", response_model=list[TaxItemOut])
async def list_tax_items(
    tax_year: Optional[int] = Query(None),
    form_type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    items = await get_tax_items(session, tax_year=tax_year, form_type=form_type)
    return [TaxItemOut.model_validate(i) for i in items]
