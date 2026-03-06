"""
Smart Defaults — single endpoint that returns aggregated data from all
domain tables so any page can auto-fill its forms.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/smart-defaults", tags=["smart-defaults"])


@router.get("")
async def get_smart_defaults(session: AsyncSession = Depends(get_session)):
    """Return aggregated smart defaults from all domain tables."""
    from pipeline.planning.smart_defaults import compute_smart_defaults
    return await compute_smart_defaults(session)


@router.get("/household-updates")
async def get_household_updates(session: AsyncSession = Depends(get_session)):
    """Compare W-2 data against household profile and return suggested updates."""
    from pipeline.planning.smart_defaults import detect_household_updates
    suggestions = await detect_household_updates(session)
    return {"suggestions": suggestions, "count": len(suggestions)}


class HouseholdUpdateRequest(BaseModel):
    updates: list[dict]


@router.post("/apply-household-updates")
async def apply_updates(
    body: HouseholdUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Apply selected household updates from W-2 data."""
    from pipeline.planning.smart_defaults import apply_household_updates
    result = await apply_household_updates(session, body.updates)
    return result


@router.get("/tax-carry-forward")
async def tax_carry_forward(
    from_year: int,
    to_year: int,
    session: AsyncSession = Depends(get_session),
):
    """Get prior year tax items for carry-forward expectations."""
    from pipeline.planning.smart_defaults import get_tax_carry_forward
    items = await get_tax_carry_forward(session, from_year, to_year)
    return {"items": items, "from_year": from_year, "to_year": to_year}


@router.get("/insights")
async def get_proactive_insights(session: AsyncSession = Depends(get_session)):
    """Return proactive financial insights and action items."""
    from pipeline.planning.proactive_insights import compute_proactive_insights
    insights = await compute_proactive_insights(session)
    return {"insights": insights, "count": len(insights)}


@router.get("/category-rules")
async def list_category_rules(session: AsyncSession = Depends(get_session)):
    """List all learned category rules."""
    from pipeline.ai.category_rules import list_rules
    rules = await list_rules(session)
    return {"rules": rules}


class LearnCategoryRequest(BaseModel):
    transaction_id: int
    category: Optional[str] = None
    tax_category: Optional[str] = None
    segment: Optional[str] = None
    business_entity_id: Optional[int] = None


@router.post("/learn-category")
async def learn_category(
    body: LearnCategoryRequest,
    session: AsyncSession = Depends(get_session),
):
    """Learn a category rule from a user's correction. Returns the rule and similar count."""
    from pipeline.ai.category_rules import learn_from_override
    result = await learn_from_override(
        session,
        transaction_id=body.transaction_id,
        new_category=body.category,
        new_tax_category=body.tax_category,
        new_segment=body.segment,
        new_business_entity_id=body.business_entity_id,
    )
    return result


@router.post("/apply-category-rule/{rule_id}")
async def apply_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    """Apply a category rule to all matching past transactions."""
    from pipeline.ai.category_rules import apply_rule_retroactively
    result = await apply_rule_retroactively(session, rule_id)
    return result
