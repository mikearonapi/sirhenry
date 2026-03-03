"""
Economic data service combining Alpha Vantage economic endpoints.
Provides macro context for HENRY financial decisions: GDP, CPI, rates, unemployment.
"""
import logging
from typing import Optional

from .alpha_vantage import AlphaVantageService

logger = logging.getLogger(__name__)

INDICATOR_METADATA = {
    "REAL_GDP": {
        "label": "Real GDP",
        "unit": "billions USD",
        "description": "Quarterly US Real Gross Domestic Product",
        "category": "growth",
    },
    "CPI": {
        "label": "Consumer Price Index",
        "unit": "index",
        "description": "Monthly consumer price index (inflation measure)",
        "category": "inflation",
    },
    "INFLATION": {
        "label": "Inflation Rate",
        "unit": "percent",
        "description": "Annual inflation rate",
        "category": "inflation",
    },
    "FEDERAL_FUNDS_RATE": {
        "label": "Federal Funds Rate",
        "unit": "percent",
        "description": "Federal Reserve target interest rate",
        "category": "rates",
    },
    "TREASURY_YIELD": {
        "label": "10-Year Treasury Yield",
        "unit": "percent",
        "description": "10-year US Treasury bond yield",
        "category": "rates",
    },
    "UNEMPLOYMENT": {
        "label": "Unemployment Rate",
        "unit": "percent",
        "description": "US unemployment rate",
        "category": "employment",
    },
    "RETAIL_SALES": {
        "label": "Retail Sales",
        "unit": "millions USD",
        "description": "Monthly advance retail sales",
        "category": "consumer",
    },
    "NONFARM_PAYROLL": {
        "label": "Nonfarm Payrolls",
        "unit": "thousands",
        "description": "Monthly change in nonfarm employment",
        "category": "employment",
    },
}


class EconomicDataService:
    """Aggregates macro-economic indicators for HENRY decision context."""

    @staticmethod
    async def get_indicator(series_id: str, interval: str = "annual") -> Optional[dict]:
        """
        Fetch a single economic indicator with metadata.
        Returns: {series_id, label, unit, description, category, data: [{date, value}]}
        """
        meta = INDICATOR_METADATA.get(series_id)
        if not meta:
            logger.warning(f"Unknown economic indicator: {series_id}")
            return None

        records = await AlphaVantageService.get_economic_indicator(series_id, interval)
        if not records:
            return None

        return {
            "series_id": series_id,
            **meta,
            "data": records,
            "latest_value": records[0]["value"] if records else None,
            "latest_date": records[0]["date"] if records else None,
        }

    @staticmethod
    async def get_dashboard_indicators() -> list[dict]:
        """
        Fetch key indicators for the HENRY dashboard:
        Fed Funds Rate, 10Y Treasury, Inflation, Unemployment.
        """
        key_indicators = [
            "FEDERAL_FUNDS_RATE",
            "TREASURY_YIELD",
            "INFLATION",
            "UNEMPLOYMENT",
        ]
        results = []
        for sid in key_indicators:
            data = await EconomicDataService.get_indicator(sid)
            if data:
                results.append({
                    "series_id": data["series_id"],
                    "label": data["label"],
                    "unit": data["unit"],
                    "category": data["category"],
                    "latest_value": data["latest_value"],
                    "latest_date": data["latest_date"],
                    "trend": data["data"][:12],  # last 12 data points for sparkline
                })
        return results

    @staticmethod
    async def get_mortgage_context() -> dict:
        """
        Get mortgage-relevant economic context for life scenario calculations.
        Returns current rates and trends useful for affordability decisions.
        """
        fed = await EconomicDataService.get_indicator("FEDERAL_FUNDS_RATE")
        treasury = await EconomicDataService.get_indicator("TREASURY_YIELD")
        inflation = await EconomicDataService.get_indicator("INFLATION")

        return {
            "fed_funds_rate": fed["latest_value"] if fed else None,
            "ten_year_treasury": treasury["latest_value"] if treasury else None,
            "inflation_rate": inflation["latest_value"] if inflation else None,
            "estimated_30yr_mortgage": (
                round(treasury["latest_value"] + 1.75, 2) if treasury and treasury["latest_value"] else None
            ),
            "rate_environment": _classify_rate_environment(
                fed["latest_value"] if fed else None
            ),
        }


def _classify_rate_environment(fed_rate: Optional[float]) -> str:
    if fed_rate is None:
        return "unknown"
    if fed_rate < 2.0:
        return "low"
    if fed_rate < 4.0:
        return "moderate"
    if fed_rate < 6.0:
        return "elevated"
    return "high"
