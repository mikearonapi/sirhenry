"""
Property valuation via RentCast API (50 free calls/month).
Provides AVM (Automated Valuation Model) estimates for real estate assets.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RENTCAST_BASE = "https://api.rentcast.io/v1"


class PropertyValuationService:
    """RentCast API wrapper for home value estimates."""

    @staticmethod
    async def get_valuation(address: str) -> Optional[dict]:
        """Get property value estimate by address."""
        api_key = os.environ.get("RENTCAST_API_KEY")
        if not api_key:
            logger.warning("RENTCAST_API_KEY not set — property valuations unavailable")
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{RENTCAST_BASE}/avm/value",
                    params={"address": address},
                    headers={"X-Api-Key": api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "address": address,
                    "estimated_value": data.get("price"),
                    "price_low": data.get("priceLow"),
                    "price_high": data.get("priceHigh"),
                    "bedrooms": data.get("bedrooms"),
                    "bathrooms": data.get("bathrooms"),
                    "sqft": data.get("squareFootage"),
                    "lot_size": data.get("lotSize"),
                    "year_built": data.get("yearBuilt"),
                    "property_type": data.get("propertyType"),
                    "confidence": "medium",
                    "source": "rentcast",
                }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("RentCast rate limit reached (50/month free tier)")
            else:
                logger.error("RentCast valuation failed: %s", e)
            return None
        except Exception as e:
            logger.error("RentCast valuation failed: %s", e)
            return None
