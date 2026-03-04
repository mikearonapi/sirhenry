"""Setup status — lightweight check of which onboarding steps are complete."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db.schema import HouseholdProfile, Account, ManualAsset

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status")
async def setup_status(session: AsyncSession = Depends(get_session)):
    """Return which setup steps are complete for contextual nudges on empty states."""

    # Check household profile exists with income
    hp_result = await session.execute(
        select(HouseholdProfile).limit(1)
    )
    household = hp_result.scalar_one_or_none()
    has_household = household is not None
    has_income = False
    if household:
        income = (household.primary_w2_income or 0) + (household.spouse_w2_income or 0)
        has_income = income > 0

    # Check if any accounts (Plaid or manual) exist
    accounts_count = await session.scalar(select(func.count()).select_from(Account))
    assets_count = await session.scalar(
        select(func.count()).select_from(ManualAsset).where(ManualAsset.is_active == True)
    )
    has_accounts = (accounts_count or 0) > 0 or (assets_count or 0) > 0

    return {
        "household": has_household,
        "income": has_income,
        "accounts": has_accounts,
        "complete": has_household and has_income and has_accounts,
    }
