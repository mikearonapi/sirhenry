"""Setup status — lightweight check of which onboarding steps are complete."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db.schema import AppSettings, HouseholdProfile, Account, ManualAsset

logger = logging.getLogger(__name__)
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
        income = (household.spouse_a_income or 0) + (household.spouse_b_income or 0)
        has_income = income > 0

    # Check if any accounts (Plaid or manual) exist
    accounts_count = await session.scalar(select(func.count()).select_from(Account))
    assets_count = await session.scalar(
        select(func.count()).select_from(ManualAsset).where(ManualAsset.is_active == True)
    )
    has_accounts = (accounts_count or 0) > 0 or (assets_count or 0) > 0

    # Check if setup was marked complete
    completed_row = await session.execute(
        select(AppSettings).where(AppSettings.key == "setup_completed_at")
    )
    setup_completed_at = completed_row.scalar_one_or_none()

    return {
        "household": has_household,
        "income": has_income,
        "accounts": has_accounts,
        "complete": has_household and has_income and has_accounts,
        "setup_completed_at": setup_completed_at.value if setup_completed_at else None,
    }


@router.post("/complete")
async def mark_setup_complete(session: AsyncSession = Depends(get_session)):
    """Mark onboarding as complete. Idempotent — safe to call multiple times.

    Validates that essential setup steps are done (household + income).
    Logs a warning if steps are missing but still allows completion so
    the user isn't blocked if they chose to skip.
    """
    existing = await session.execute(
        select(AppSettings).where(AppSettings.key == "setup_completed_at")
    )
    row = existing.scalar_one_or_none()
    if row:
        return {"setup_completed_at": row.value}

    # Validate essential steps — warn but don't block
    hp_result = await session.execute(select(HouseholdProfile).limit(1))
    household = hp_result.scalar_one_or_none()
    warnings = []
    if not household:
        warnings.append("no_household")
        logger.warning("Setup marked complete without a household profile")
    elif (household.spouse_a_income or 0) + (household.spouse_b_income or 0) == 0:
        warnings.append("no_income")
        logger.warning("Setup marked complete without income configured")

    now = datetime.now(timezone.utc).isoformat()
    session.add(AppSettings(key="setup_completed_at", value=now))
    await session.flush()

    result = {"setup_completed_at": now}
    if warnings:
        result["warnings"] = warnings
    return result
