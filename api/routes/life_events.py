"""Life Events admin endpoints — factual log of major financial life events."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import LifeEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/life-events", tags=["life-events"])


# ---------------------------------------------------------------------------
# Action item templates by event type
# ---------------------------------------------------------------------------

_ACTION_TEMPLATES: dict[str, list[dict]] = {
    "real_estate_purchase": [
        {"text": "Add mortgage account to track loan balance", "completed": False, "link": "/accounts"},
        {"text": "Set up property tax reminder", "completed": False, "link": "/admin"},
        {"text": "Update homeowner's insurance policy", "completed": False, "link": "/insurance"},
        {"text": "Update net worth — add property as manual asset", "completed": False, "link": "/accounts"},
        {"text": "Record mortgage points paid (deductible first year)", "completed": False},
        {"text": "Review mortgage interest deduction vs standard deduction", "completed": False},
    ],
    "real_estate_sale": [
        {"text": "Document sale price and cost basis for capital gains calculation", "completed": False},
        {"text": "Confirm $500k MFJ / $250k single exclusion eligibility (2-of-5 year rule)", "completed": False},
        {"text": "Remove property from manual assets, record proceeds", "completed": False, "link": "/accounts"},
        {"text": "Update homeowner's insurance — cancel or transfer policy", "completed": False, "link": "/insurance"},
    ],
    "real_estate_rental": [
        {"text": "Set up separate account to track rental income", "completed": False, "link": "/accounts"},
        {"text": "Document rental property for Schedule E", "completed": False},
        {"text": "Update landlord insurance policy", "completed": False, "link": "/insurance"},
        {"text": "Track depreciation basis for annual deduction", "completed": False},
    ],
    "vehicle_purchase": [
        {"text": "Update auto insurance policy", "completed": False, "link": "/insurance"},
        {"text": "Check EV tax credit eligibility (Form 8936) if applicable", "completed": False},
        {"text": "Add vehicle as manual asset if significant value", "completed": False, "link": "/accounts"},
        {"text": "Track business-use percentage if used for work", "completed": False},
    ],
    "vehicle_sale": [
        {"text": "Document sale price vs purchase price for tax purposes", "completed": False},
        {"text": "Cancel or update auto insurance", "completed": False, "link": "/insurance"},
        {"text": "Remove vehicle from manual assets", "completed": False, "link": "/accounts"},
    ],
    "family_birth": [
        {"text": "Update dependents on household profile", "completed": False, "link": "/household"},
        {"text": "Review Child Tax Credit eligibility ($2,000/child)", "completed": False},
        {"text": "Update Dependent Care FSA elections during special enrollment", "completed": False},
        {"text": "Recalculate life insurance coverage needs", "completed": False, "link": "/insurance"},
        {"text": "Open 529 college savings account", "completed": False},
        {"text": "Add child as beneficiary on life insurance and retirement accounts", "completed": False},
        {"text": "Update estate documents (will, guardian designation)", "completed": False},
    ],
    "family_adoption": [
        {"text": "Update dependents on household profile", "completed": False, "link": "/household"},
        {"text": "Document adoption expenses — Adoption Tax Credit up to $16,810 (2025)", "completed": False},
        {"text": "Review Child Tax Credit eligibility", "completed": False},
        {"text": "Update life insurance and estate documents", "completed": False},
    ],
    "family_marriage": [
        {"text": "Update filing status on household profile", "completed": False, "link": "/household"},
        {"text": "Run MFJ vs MFS comparison to determine optimal filing status", "completed": False, "link": "/household"},
        {"text": "Update W-4 for both employers using new W-4 optimization tool", "completed": False, "link": "/household"},
        {"text": "Review and update beneficiaries on all accounts", "completed": False},
        {"text": "Update estate documents (will, POA, beneficiaries)", "completed": False},
        {"text": "Combine or coordinate health insurance plans", "completed": False, "link": "/insurance"},
    ],
    "family_divorce": [
        {"text": "Update filing status on household profile to Single/HoH", "completed": False, "link": "/household"},
        {"text": "Review QDRO for retirement account division", "completed": False},
        {"text": "Update all beneficiary designations", "completed": False},
        {"text": "Update insurance policies — health, life, auto, home", "completed": False, "link": "/insurance"},
        {"text": "Update estate documents", "completed": False},
        {"text": "Review alimony tax treatment (deductible pre-2019 divorces)", "completed": False},
    ],
    "employment_job_change": [
        {"text": "Update income on household profile", "completed": False, "link": "/household"},
        {"text": "Update W-4 for new employer using W-4 optimization tool", "completed": False, "link": "/household"},
        {"text": "Roll over old 401k to IRA or new employer plan", "completed": False},
        {"text": "Review COBRA vs new employer health plan", "completed": False, "link": "/insurance"},
        {"text": "Update benefits on household profile", "completed": False, "link": "/household"},
        {"text": "Track any signing bonus — taxed at supplemental rate (22% federal)", "completed": False},
        {"text": "Review equity comp vesting acceleration if leaving employer", "completed": False, "link": "/equity-comp"},
    ],
    "employment_layoff": [
        {"text": "Evaluate COBRA vs marketplace health insurance within 60-day window", "completed": False, "link": "/insurance"},
        {"text": "Roll over 401k before any employer deadlines", "completed": False},
        {"text": "Track severance — taxed as ordinary income", "completed": False},
        {"text": "Update income on household profile", "completed": False, "link": "/household"},
        {"text": "Review unemployment tax implications (UI benefits are taxable)", "completed": False},
        {"text": "Check if stock option exercise window is shortened post-termination", "completed": False, "link": "/equity-comp"},
    ],
    "employment_start_business": [
        {"text": "Set up business entity tracking", "completed": False, "link": "/accounts"},
        {"text": "Set up separate business account for tracking income/expenses", "completed": False, "link": "/accounts"},
        {"text": "Calculate quarterly estimated tax payments (SE tax is 15.3%)", "completed": False},
        {"text": "Review S-Corp election if net income likely exceeds $40k", "completed": False},
        {"text": "Set up SEP-IRA or Solo 401k for self-employed retirement savings", "completed": False},
        {"text": "Review health insurance deductibility as self-employed", "completed": False},
    ],
    "medical_major": [
        {"text": "Log all out-of-pocket expenses for HSA reimbursement", "completed": False},
        {"text": "Check if expenses exceed 7.5% AGI threshold for itemized deduction", "completed": False},
        {"text": "Review short-term and long-term disability coverage gaps", "completed": False, "link": "/insurance"},
        {"text": "Check if medical leave qualifies for FMLA / state programs", "completed": False},
    ],
    "education_college": [
        {"text": "Document tuition payments for American Opportunity / Lifetime Learning Credit", "completed": False},
        {"text": "Check 529 qualified distribution tracking", "completed": False},
        {"text": "Review student loan interest deduction eligibility ($2,500 cap)", "completed": False},
    ],
    "education_529_open": [
        {"text": "Add 529 account to manual assets", "completed": False, "link": "/accounts"},
        {"text": "Set up recurring contribution goal", "completed": False, "link": "/goals"},
        {"text": "Note: up to $18,000/year per beneficiary gift-tax-free (2025)", "completed": False},
        {"text": "Consider superfunding: 5-year election to front-load $90k", "completed": False},
    ],
    "estate_inheritance": [
        {"text": "Document inherited assets — receive step-up in cost basis at date of death", "completed": False},
        {"text": "Update net worth with inherited assets", "completed": False, "link": "/accounts"},
        {"text": "Review estate/gift tax filing requirements (Form 706/709)", "completed": False},
        {"text": "Update your own estate documents if financial picture changed significantly", "completed": False},
    ],
    "estate_gift": [
        {"text": "Document gift amount and recipient — annual exclusion is $18,000/person (2025)", "completed": False},
        {"text": "File Form 709 if gift exceeds annual exclusion", "completed": False},
        {"text": "Track lifetime exemption usage ($13.6M per person 2025, sunsets 2026)", "completed": False},
    ],
    "business_asset_sale": [
        {"text": "Document purchase price and sale price for capital gains calculation", "completed": False},
        {"text": "Determine short-term vs long-term holding period", "completed": False},
        {"text": "Review installment sale treatment if spread over multiple years", "completed": False},
        {"text": "Check Section 1202 QSBS exclusion eligibility (C-Corps)", "completed": False},
    ],
}


def _get_action_items(event_type: str, event_subtype: Optional[str]) -> list[dict]:
    """Return auto-generated action items for an event type/subtype combination."""
    key = f"{event_type}_{event_subtype}" if event_subtype else event_type
    items = _ACTION_TEMPLATES.get(key, _ACTION_TEMPLATES.get(event_type, []))
    return [dict(item) for item in items]  # return copies


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LifeEventIn(BaseModel):
    household_id: Optional[int] = None
    event_type: str
    event_subtype: Optional[str] = None
    title: str
    event_date: Optional[str] = None
    tax_year: Optional[int] = None
    amounts_json: Optional[str] = None
    status: str = "completed"
    action_items_json: Optional[str] = None
    document_ids_json: Optional[str] = None
    notes: Optional[str] = None


class ActionItemUpdate(BaseModel):
    index: int
    completed: bool


class LifeEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: Optional[int]
    event_type: str
    event_subtype: Optional[str]
    title: str
    event_date: Optional[str] = None
    tax_year: Optional[int]
    amounts_json: Optional[str]
    status: str
    action_items_json: Optional[str]
    document_ids_json: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[LifeEventOut])
async def list_events(
    household_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    tax_year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    q = select(LifeEvent).order_by(LifeEvent.event_date.desc().nullslast(), LifeEvent.created_at.desc())
    if household_id is not None:
        q = q.where(LifeEvent.household_id == household_id)
    if event_type:
        q = q.where(LifeEvent.event_type == event_type)
    if tax_year is not None:
        q = q.where(LifeEvent.tax_year == tax_year)
    result = await session.execute(q)
    return result.scalars().all()


@router.post("/", response_model=LifeEventOut, status_code=201)
async def create_event(body: LifeEventIn, session: AsyncSession = Depends(get_session)):
    data = body.model_dump()
    # Auto-generate action items if not provided
    if not data.get("action_items_json"):
        items = _get_action_items(body.event_type, body.event_subtype)
        if items:
            data["action_items_json"] = json.dumps(items)
    event = LifeEvent(**data)
    session.add(event)
    await session.flush()
    await session.refresh(event)
    logger.info(f"Life event created: {event.event_type}/{event.event_subtype} — {event.title}")
    return event


@router.get("/{event_id}", response_model=LifeEventOut)
async def get_event(event_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeEvent).where(LifeEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Life event not found")
    return event


@router.patch("/{event_id}", response_model=LifeEventOut)
async def update_event(event_id: int, body: LifeEventIn, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeEvent).where(LifeEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Life event not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(event, k, v)
    event.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(event)
    return event


@router.patch("/{event_id}/action-items/{item_index}")
async def toggle_action_item(event_id: int, item_index: int, body: ActionItemUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeEvent).where(LifeEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Life event not found")
    items = json.loads(event.action_items_json or "[]")
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(400, "Action item index out of range")
    items[item_index]["completed"] = body.completed
    event.action_items_json = json.dumps(items)
    event.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return {"status": "ok", "items": items}


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LifeEvent).where(LifeEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Life event not found")
    await session.delete(event)
    await session.flush()


@router.get("/action-templates/{event_type}")
async def get_action_templates(event_type: str, event_subtype: Optional[str] = Query(None)):
    """Return the auto-generated action item template for a given event type."""
    return {"items": _get_action_items(event_type, event_subtype)}
