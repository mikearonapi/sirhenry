"""Tax analysis endpoints — estimate, checklist, deduction opportunities, summary."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    DeductionOpportunityOut,
    TaxChecklistItemOut,
    TaxChecklistOut,
    TaxDeductionInsightsOut,
    TaxItemUpdate,
    TaxSummaryOut,
)
from pipeline.db.schema import TaxItem
from pipeline.tax.checklist import compute_tax_checklist
from pipeline.tax.deductions import compute_deduction_opportunities
from pipeline.tax.quarterly import compute_quarterly_estimate
from pipeline.tax.tax_estimate import compute_tax_estimate
from pipeline.tax.tax_summary import get_tax_summary_with_fallback

router = APIRouter(tags=["tax"])


@router.get("/summary", response_model=TaxSummaryOut)
async def get_tax_year_summary(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year - 1),
    session: AsyncSession = Depends(get_session),
):
    summary = await get_tax_summary_with_fallback(session, tax_year)
    return TaxSummaryOut(**summary)


@router.get("/estimate")
async def get_tax_estimate(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year),
    session: AsyncSession = Depends(get_session),
):
    """
    Compute a rough federal + SE tax estimate based on known income data.
    This is an estimate only — not professional tax advice.
    """
    return await compute_tax_estimate(session, tax_year)


# ---------------------------------------------------------------------------
# Tax Checklist
# ---------------------------------------------------------------------------

@router.get("/checklist", response_model=TaxChecklistOut)
async def get_tax_checklist(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year - 1),
    session: AsyncSession = Depends(get_session),
):
    """Computed tax filing readiness checklist based on actual data in the system."""
    result = await compute_tax_checklist(session, tax_year)
    return TaxChecklistOut(
        tax_year=result["tax_year"],
        items=[TaxChecklistItemOut(**item) for item in result["items"]],
        completed=result["completed"],
        total=result["total"],
        progress_pct=result["progress_pct"],
    )


# ---------------------------------------------------------------------------
# Deduction Opportunities
# ---------------------------------------------------------------------------

@router.get("/deduction-opportunities", response_model=TaxDeductionInsightsOut)
async def get_deduction_opportunities(
    tax_year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year),
    session: AsyncSession = Depends(get_session),
):
    """
    Smart deduction insights: shows what you could spend/invest to reduce
    your tax bill. Frames it as 'money leaves your account either way — IRS
    or as a business asset/deduction.'
    """
    result = await compute_deduction_opportunities(session, tax_year)
    return TaxDeductionInsightsOut(
        tax_year=result["tax_year"],
        estimated_balance_due=result["estimated_balance_due"],
        effective_rate=result["effective_rate"],
        marginal_rate=result["marginal_rate"],
        opportunities=[DeductionOpportunityOut(**opp) for opp in result["opportunities"]],
        summary=result["summary"],
        data_source=result["data_source"],
    )


# ---------------------------------------------------------------------------
# PATCH /tax/items/{item_id} — Inline editing of OCR-extracted tax item fields
# ---------------------------------------------------------------------------

@router.patch("/items/{item_id}")
async def update_tax_item(
    item_id: int,
    body: TaxItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update individual fields on a tax item (e.g., correcting OCR misreads)."""
    result = await session.execute(select(TaxItem).where(TaxItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Tax item not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in updates.items():
        setattr(item, field, value)

    await session.flush()
    return {"id": item.id, "updated_fields": list(updates.keys())}


@router.get("/estimated-quarterly")
async def estimated_quarterly_tax(
    tax_year: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Calculate quarterly estimated tax payments based on self-employment and non-withheld income."""
    return await compute_quarterly_estimate(session, tax_year)
