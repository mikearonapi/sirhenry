"""Unified Rules & Learning API — category rules, vendor rules, user context."""
from datetime import date as DateType

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.ai.category_rules import (
    apply_rule_retroactively,
    deactivate_rule,
    list_rules,
    update_rule,
)
from pipeline.db.models import (
    get_active_user_context,
    get_all_vendor_rules,
)
from pipeline.db.schema import (
    BusinessEntity,
    CategoryRule,
    Transaction,
    UserContext,
    VendorEntityRule,
)

router = APIRouter(prefix="/rules", tags=["rules"])


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@router.get("/summary")
async def rules_summary(session: AsyncSession = Depends(get_session)):
    """Aggregate counts of all rule types and total matches."""
    cat_result = await session.execute(
        select(
            func.count(CategoryRule.id),
            func.coalesce(func.sum(CategoryRule.match_count), 0),
        ).where(CategoryRule.is_active == True)
    )
    cat_count, total_matches = cat_result.one()

    vendor_result = await session.execute(
        select(func.count(VendorEntityRule.id)).where(VendorEntityRule.is_active == True)
    )
    vendor_count = vendor_result.scalar() or 0

    ctx_result = await session.execute(
        select(func.count(UserContext.id)).where(UserContext.is_active == True)
    )
    context_count = ctx_result.scalar() or 0

    # Total non-excluded transactions (for rule coverage percentage)
    total_txn_result = await session.execute(
        select(func.count(Transaction.id)).where(Transaction.is_excluded.is_(False))
    )
    total_transactions = total_txn_result.scalar() or 0

    return {
        "category_rule_count": cat_count,
        "vendor_rule_count": vendor_count,
        "context_count": context_count,
        "total_matches": int(total_matches),
        "total_transactions": total_transactions,
    }


# ---------------------------------------------------------------------------
# Category Rules
# ---------------------------------------------------------------------------

@router.get("/category")
async def get_category_rules(session: AsyncSession = Depends(get_session)):
    """List all category rules with resolved entity names."""
    rules = await list_rules(session)

    # Resolve entity names
    entity_ids = {r["business_entity_id"] for r in rules if r.get("business_entity_id")}
    entity_names: dict[int, str] = {}
    if entity_ids:
        result = await session.execute(
            select(BusinessEntity.id, BusinessEntity.name).where(
                BusinessEntity.id.in_(entity_ids)
            )
        )
        entity_names = {row[0]: row[1] for row in result}

    for r in rules:
        r["entity_name"] = entity_names.get(r.get("business_entity_id")) if r.get("business_entity_id") else None

    return {"rules": rules}


class CategoryRuleUpdateIn(BaseModel):
    category: str | None = None
    tax_category: str | None = None
    segment: str | None = None
    business_entity_id: int | None = None
    is_active: bool | None = None
    effective_from: DateType | None = None
    effective_to: DateType | None = None


@router.patch("/category/{rule_id}")
async def patch_category_rule(
    rule_id: int,
    body: CategoryRuleUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    # exclude_unset lets clients send null to clear fields (e.g. dates, entity)
    data = body.model_dump(exclude_unset=True)
    result = await update_rule(session, rule_id, data)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/category/{rule_id}")
async def delete_category_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await deactivate_rule(session, rule_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/category/{rule_id}/apply")
async def apply_category_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Apply a category rule retroactively to all matching transactions."""
    result = await apply_rule_retroactively(session, rule_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Generate Rules
# ---------------------------------------------------------------------------

class GenerateApplyIn(BaseModel):
    rules: list[dict]


@router.post("/generate")
async def generate_rules(
    include_ai: bool = False,
    session: AsyncSession = Depends(get_session),
):
    """Analyze transactions and propose category rules.

    Pattern-based analysis is always run (free, instant).
    Set include_ai=true to also get AI suggestions for uncategorized merchants.
    """
    from pipeline.ai.rule_generator import (
        generate_rules_from_ai,
        generate_rules_from_patterns,
    )

    pattern_rules = await generate_rules_from_patterns(session)

    ai_rules: list[dict] = []
    if include_ai:
        ai_rules = await generate_rules_from_ai(session)

    all_rules = pattern_rules + ai_rules
    total_txns = sum(r["transaction_count"] for r in all_rules)

    # Count existing rules that were skipped
    existing_result = await session.execute(
        select(func.count(CategoryRule.id)).where(CategoryRule.is_active.is_(True))
    )
    existing_count = existing_result.scalar() or 0

    return {
        "rules": all_rules,
        "stats": {
            "from_patterns": len(pattern_rules),
            "from_ai": len(ai_rules),
            "total_transactions_covered": total_txns,
            "existing_rules_skipped": existing_count,
        },
    }


@router.post("/generate/apply")
async def apply_generated_rules(
    body: GenerateApplyIn,
    session: AsyncSession = Depends(get_session),
):
    """Create category rules from approved proposals and apply retroactively."""
    from pipeline.ai.rule_generator import create_rules_from_proposals

    result = await create_rules_from_proposals(session, body.rules)
    return result


# ---------------------------------------------------------------------------
# Vendor Rules (read-only here — CRUD at /entities/rules/vendor)
# ---------------------------------------------------------------------------

@router.get("/vendor")
async def get_vendor_rules(session: AsyncSession = Depends(get_session)):
    """List all vendor entity rules with resolved entity names."""
    rules = await get_all_vendor_rules(session, active_only=False)

    # Resolve entity names
    entity_ids = {r.business_entity_id for r in rules if r.business_entity_id}
    entity_names: dict[int, str] = {}
    if entity_ids:
        result = await session.execute(
            select(BusinessEntity.id, BusinessEntity.name).where(
                BusinessEntity.id.in_(entity_ids)
            )
        )
        entity_names = {row[0]: row[1] for row in result}

    return {
        "rules": [
            {
                "id": r.id,
                "vendor_pattern": r.vendor_pattern,
                "business_entity_id": r.business_entity_id,
                "entity_name": entity_names.get(r.business_entity_id),
                "segment_override": r.segment_override,
                "effective_from": str(r.effective_from) if r.effective_from else None,
                "effective_to": str(r.effective_to) if r.effective_to else None,
                "priority": r.priority,
                "is_active": r.is_active,
                "created_at": str(r.created_at),
            }
            for r in rules
        ],
    }


# ---------------------------------------------------------------------------
# Categories (for edit dropdowns)
# ---------------------------------------------------------------------------

@router.get("/categories")
async def get_rule_categories():
    """Return expense and tax category options for rule editing."""
    from pipeline.ai.categories import EXPENSE_CATEGORIES, TAX_CATEGORIES

    return {
        "categories": EXPENSE_CATEGORIES,
        "tax_categories": TAX_CATEGORIES,
    }
