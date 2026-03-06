"""Asset valuation endpoints: VIN decoding, property estimates, refresh triggers."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db.schema import ManualAsset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/valuations", tags=["valuations"])


@router.get("/vehicle/{vin}")
async def decode_vehicle(vin: str):
    """Decode VIN and estimate value."""
    from pipeline.market.vehicle_valuation import VehicleValuationService

    decoded = await VehicleValuationService.decode_vin(vin)
    if not decoded:
        raise HTTPException(400, f"Could not decode VIN: {vin}")

    estimate = VehicleValuationService.estimate_value(
        year=decoded.get("year") or 0,
        make=decoded.get("make") or "",
        model=decoded.get("model") or "",
    )
    return {"vehicle": decoded, "valuation": estimate}


@router.get("/property")
async def property_valuation(address: str):
    """Get property value estimate by address."""
    from pipeline.market.property_valuation import PropertyValuationService

    result = await PropertyValuationService.get_valuation(address)
    if not result:
        raise HTTPException(404, "Could not estimate property value. RENTCAST_API_KEY may not be set.")
    return result


class RefreshValuationIn(BaseModel):
    vin: str | None = None
    address: str | None = None


@router.post("/assets/{asset_id}/refresh")
async def refresh_asset_valuation(
    asset_id: int,
    body: RefreshValuationIn | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Refresh valuation for a manual asset from external API."""
    result = await session.execute(
        select(ManualAsset).where(ManualAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    if asset.asset_type == "vehicle":
        vin = (body.vin if body else None) or getattr(asset, "vin", None)
        if not vin:
            raise HTTPException(400, "VIN required for vehicle valuation")

        from pipeline.market.vehicle_valuation import VehicleValuationService

        decoded = await VehicleValuationService.decode_vin(vin)
        if decoded:
            estimate = VehicleValuationService.estimate_value(
                year=decoded["year"] or 0,
                make=decoded["make"] or "",
                model=decoded["model"] or "",
                purchase_price=asset.purchase_price,
            )
            if estimate:
                asset.current_value = estimate["estimated_value"]
                asset.vin = vin
                asset.valuation_source = "nhtsa"
                asset.valuation_date = datetime.now(timezone.utc)
                asset.valuation_api_data_json = json.dumps({"vehicle": decoded, "estimate": estimate})
                if decoded.get("year") and decoded.get("make") and decoded.get("model"):
                    asset.name = f"{decoded['year']} {decoded['make']} {decoded['model']}"
                await session.flush()
                return {"updated": True, "new_value": asset.current_value, "vehicle": decoded}

    elif asset.asset_type == "real_estate":
        address = (body.address if body else None) or asset.address
        if not address:
            raise HTTPException(400, "Address required for property valuation")

        from pipeline.market.property_valuation import PropertyValuationService

        val = await PropertyValuationService.get_valuation(address)
        if val and val.get("estimated_value"):
            asset.current_value = val["estimated_value"]
            asset.valuation_source = "rentcast"
            asset.valuation_date = datetime.now(timezone.utc)
            asset.valuation_api_data_json = json.dumps(val)
            await session.flush()
            return {"updated": True, "new_value": asset.current_value, "property": val}

    raise HTTPException(422, "Could not refresh valuation")
