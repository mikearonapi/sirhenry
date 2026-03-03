"""
CRUD routes for manual assets / liabilities (real estate, vehicles, loans, etc.).
These are non-transaction assets that contribute to net worth.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import ManualAssetCreateIn, ManualAssetOut, ManualAssetUpdateIn
from pipeline.db import ManualAsset

logger = logging.getLogger(__name__)

ASSET_TYPES = {"real_estate", "vehicle", "investment", "other_asset"}
LIABILITY_TYPES = {"mortgage", "loan", "other_liability"}

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[ManualAssetOut])
async def list_assets(
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_session),
):
    q = select(ManualAsset).order_by(ManualAsset.asset_type, ManualAsset.name)
    if not include_inactive:
        q = q.where(ManualAsset.is_active == True)
    result = await session.execute(q)
    return list(result.scalars().all())


@router.post("", response_model=ManualAssetOut, status_code=201)
async def create_asset(
    body: ManualAssetCreateIn,
    session: AsyncSession = Depends(get_session),
):
    is_liability = body.asset_type in LIABILITY_TYPES
    asset = ManualAsset(
        name=body.name,
        asset_type=body.asset_type,
        is_liability=is_liability,
        current_value=body.current_value,
        purchase_price=body.purchase_price,
        purchase_date=body.purchase_date,
        institution=body.institution,
        address=body.address,
        description=body.description,
        notes=body.notes,
        owner=body.owner,
        account_subtype=body.account_subtype,
        custodian=body.custodian,
        employer=body.employer,
        tax_treatment=body.tax_treatment,
        is_retirement_account=body.is_retirement_account,
        as_of_date=body.as_of_date,
        vested_balance=body.vested_balance,
        contribution_type=body.contribution_type,
        contribution_rate_pct=body.contribution_rate_pct,
        employee_contribution_ytd=body.employee_contribution_ytd,
        employer_contribution_ytd=body.employer_contribution_ytd,
        employer_match_pct=body.employer_match_pct,
        employer_match_limit_pct=body.employer_match_limit_pct,
        annual_return_pct=body.annual_return_pct,
        allocation_json=body.allocation_json,
        beneficiary=body.beneficiary,
    )
    session.add(asset)
    await session.flush()
    await session.refresh(asset)
    logger.info(f"Created manual asset: {asset.name} ({asset.asset_type}) = ${asset.current_value:,.2f}")
    return asset


@router.patch("/{asset_id}", response_model=ManualAssetOut)
async def update_asset(
    asset_id: int,
    body: ManualAssetUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(ManualAsset).where(ManualAsset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(asset, field, value)
    asset.updated_at = datetime.now(timezone.utc)

    await session.flush()
    await session.refresh(asset)
    logger.info(f"Updated manual asset {asset_id}: {asset.name} = ${asset.current_value:,.2f}")
    return asset


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(ManualAsset).where(ManualAsset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    await session.delete(asset)
    await session.flush()
    logger.info(f"Deleted manual asset {asset_id}: {asset.name}")


@router.get("/summary")
async def asset_summary(session: AsyncSession = Depends(get_session)):
    """Aggregated totals for manual assets and liabilities."""
    result = await session.execute(
        select(ManualAsset).where(ManualAsset.is_active == True)
    )
    assets = list(result.scalars().all())

    total_assets = sum(a.current_value for a in assets if not a.is_liability)
    total_liabilities = sum(a.current_value for a in assets if a.is_liability)

    by_type: dict[str, float] = {}
    for a in assets:
        by_type[a.asset_type] = by_type.get(a.asset_type, 0.0) + a.current_value

    return {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "net": total_assets - total_liabilities,
        "count": len(assets),
        "by_type": by_type,
    }
