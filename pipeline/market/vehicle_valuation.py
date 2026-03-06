"""
Vehicle identification and valuation via NHTSA VIN Decoder (free, no key).
Pairs with depreciation model for value estimates.
"""
import logging
from datetime import date
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NHTSA_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"


class VehicleValuationService:
    """NHTSA VIN decoder + depreciation-based value estimation."""

    @staticmethod
    async def decode_vin(vin: str) -> Optional[dict]:
        """Decode VIN → year, make, model, trim, body, engine."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{NHTSA_BASE}/DecodeVinValues/{vin}",
                    params={"format": "json"},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("Results", [{}])[0]
                if not results.get("Make"):
                    return None
                return {
                    "vin": vin,
                    "year": int(results.get("ModelYear", 0)) or None,
                    "make": results.get("Make"),
                    "model": results.get("Model"),
                    "trim": results.get("Trim") or None,
                    "body_class": results.get("BodyClass") or None,
                    "engine_cylinders": results.get("EngineCylinders") or None,
                    "engine_displacement": results.get("DisplacementL") or None,
                    "fuel_type": results.get("FuelTypePrimary") or None,
                    "drive_type": results.get("DriveType") or None,
                    "vehicle_type": results.get("VehicleType") or None,
                }
        except Exception as e:
            logger.error("NHTSA VIN decode failed: %s", e)
            return None

    @staticmethod
    def estimate_value(
        year: int,
        make: str,
        model: str,
        purchase_price: Optional[float] = None,
        purchase_year: Optional[int] = None,
    ) -> Optional[dict]:
        """Estimate current value using depreciation curve.

        Year 1: -20%, Years 2-5: -15%/yr, Year 6+: -10%/yr. Floor at 10%.
        """
        current_year = date.today().year
        age = current_year - year
        if age < 0:
            return None

        if purchase_price and purchase_price > 0:
            base = purchase_price
            years_since = current_year - (purchase_year or year)
        else:
            base = _estimate_msrp(make, model)
            years_since = age

        value = base
        for y in range(max(0, years_since)):
            if y == 0:
                value *= 0.80
            elif y < 5:
                value *= 0.85
            else:
                value *= 0.90

        value = max(value, base * 0.10)

        return {
            "estimated_value": round(value, -2),
            "confidence": "low" if not purchase_price else "medium",
            "method": "depreciation_curve",
            "age_years": age,
            "base_value": base,
        }


def _estimate_msrp(make: str, model: str) -> float:
    """Rough MSRP estimate by segment."""
    luxury = {"bmw", "mercedes", "mercedes-benz", "audi", "lexus", "porsche", "tesla", "rivian", "lucid"}
    if make.lower() in luxury:
        return 55000.0
    trucks = {"f-150", "silverado", "ram", "tundra", "tacoma", "colorado", "ranger"}
    if model.lower() in trucks:
        return 45000.0
    return 35000.0
