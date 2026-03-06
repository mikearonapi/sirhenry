"""
Business entity and vendor rule CRUD endpoints, plus expense reporting.
"""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import (
    BusinessEntityCreateIn,
    BusinessEntityOut,
    BusinessEntityUpdateIn,
    EntityExpenseReportOut,
    EntityReassignIn,
    VendorEntityRuleCreateIn,
    VendorEntityRuleOut,
)
from pipeline.db import (
    apply_entity_rules,
    bulk_reassign_entity,
    create_vendor_rule,
    delete_business_entity,
    delete_vendor_rule,
    get_all_business_entities,
    get_all_vendor_rules,
    get_business_entity,
    update_transaction_entity,
    upsert_business_entity,
)

router = APIRouter(prefix="/entities", tags=["entities"])


# ---------------------------------------------------------------------------
# Business Entities
# ---------------------------------------------------------------------------

@router.get("", response_model=list[BusinessEntityOut])
async def list_entities(
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    entities = await get_all_business_entities(session, include_inactive=include_inactive)
    return [BusinessEntityOut.model_validate(e) for e in entities]


@router.get("/{entity_id}", response_model=BusinessEntityOut)
async def get_entity(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
):
    entity = await get_business_entity(session, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Business entity not found")
    return BusinessEntityOut.model_validate(entity)


@router.post("", response_model=BusinessEntityOut, status_code=201)
async def create_entity(
    body: BusinessEntityCreateIn,
    session: AsyncSession = Depends(get_session),
):
    entity = await upsert_business_entity(session, body.model_dump(exclude_none=True))
    await session.flush()
    return BusinessEntityOut.model_validate(entity)


@router.patch("/{entity_id}", response_model=BusinessEntityOut)
async def update_entity(
    entity_id: int,
    body: BusinessEntityUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    entity = await get_business_entity(session, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Business entity not found")
    data = body.model_dump(exclude_none=True)
    data["name"] = entity.name
    updated = await upsert_business_entity(session, data)
    await session.flush()
    return BusinessEntityOut.model_validate(updated)


@router.delete("/{entity_id}", status_code=204)
async def soft_delete_entity(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_business_entity(session, entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Business entity not found")


# ---------------------------------------------------------------------------
# Vendor Entity Rules
# ---------------------------------------------------------------------------

@router.get("/rules/vendor", response_model=list[VendorEntityRuleOut])
async def list_vendor_rules(
    entity_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    rules = await get_all_vendor_rules(session, entity_id=entity_id)
    return [VendorEntityRuleOut.model_validate(r) for r in rules]


@router.post("/rules/vendor", response_model=VendorEntityRuleOut, status_code=201)
async def create_rule(
    body: VendorEntityRuleCreateIn,
    session: AsyncSession = Depends(get_session),
):
    entity = await get_business_entity(session, body.business_entity_id)
    if not entity:
        raise HTTPException(status_code=400, detail="Referenced business entity not found")
    rule = await create_vendor_rule(session, body.model_dump())
    await session.flush()
    return VendorEntityRuleOut.model_validate(rule)


@router.delete("/rules/vendor/{rule_id}", status_code=204)
async def soft_delete_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_vendor_rule(session, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Vendor rule not found")


# ---------------------------------------------------------------------------
# Entity Assignment
# ---------------------------------------------------------------------------

@router.post("/apply-rules")
async def run_entity_rules(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    document_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Run entity assignment rules on transactions."""
    updated = await apply_entity_rules(
        session, document_id=document_id, year=year, month=month,
    )
    return {"updated": updated}


@router.post("/reassign")
async def reassign_entities(
    body: EntityReassignIn,
    session: AsyncSession = Depends(get_session),
):
    """Bulk reassign transactions from one entity to another."""
    count = await bulk_reassign_entity(
        session,
        from_entity_id=body.from_entity_id,
        to_entity_id=body.to_entity_id,
        date_from=body.date_from,
        date_to=body.date_to,
    )
    return {"reassigned": count}


@router.patch("/transactions/{transaction_id}/entity")
async def set_transaction_entity(
    transaction_id: int,
    business_entity_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Manually set the business entity for a single transaction."""
    await update_transaction_entity(session, transaction_id, business_entity_id)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Expense Reporting
# ---------------------------------------------------------------------------

@router.get("/{entity_id}/reimbursements")
async def get_entity_reimbursements(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get reimbursement tracking report for a business entity."""
    from pipeline.planning.business_reports import compute_reimbursement_report
    result = await compute_reimbursement_report(session, entity_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{entity_id}/expenses", response_model=EntityExpenseReportOut)
async def get_entity_expenses(
    entity_id: int,
    year: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Get monthly expense breakdown for a business entity."""
    from pipeline.planning.business_reports import compute_entity_expense_report
    result = await compute_entity_expense_report(session, entity_id, year)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{entity_id}/expenses/transactions")
async def list_entity_transactions(
    entity_id: int,
    year: int = Query(...),
    month: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Get transaction list for a business entity as JSON."""
    from pipeline.planning.business_reports import get_entity_transactions
    entity = await get_business_entity(session, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Business entity not found")
    return await get_entity_transactions(session, entity_id, year, month)


@router.get("/{entity_id}/expenses/csv")
async def export_entity_expenses_csv(
    entity_id: int,
    year: int = Query(...),
    month: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Download business entity transactions as CSV."""
    from pipeline.planning.business_reports import get_entity_transactions
    entity = await get_business_entity(session, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Business entity not found")

    transactions = await get_entity_transactions(session, entity_id, year, month)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Description", "Amount", "Category", "Tax Category", "Account", "Segment", "Notes"])
    for tx in transactions:
        writer.writerow([
            tx["date"], tx["description"], tx["amount"],
            tx["category"], tx["tax_category"], tx["account"],
            tx["segment"], tx["notes"],
        ])

    output.seek(0)
    period = f"{year}-{month:02d}" if month else str(year)
    filename = f"{entity.name.replace(' ', '-')}-{period}-expenses.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
