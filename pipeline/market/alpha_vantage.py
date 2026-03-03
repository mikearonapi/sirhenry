"""
Alpha Vantage service for fundamental data, technical indicators, and economic data.
Uses httpx for direct API calls (no extra dependency needed).
Free tier: 25 requests/day.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

AV_BASE_URL = "https://www.alphavantage.co/query"


def _get_api_key() -> Optional[str]:
    return os.environ.get("ALPHA_VANTAGE_API_KEY")


class AlphaVantageService:
    """Alpha Vantage API wrapper for fundamentals and economic indicators."""

    @staticmethod
    async def _fetch(params: dict) -> Optional[dict]:
        key = _get_api_key()
        if not key:
            logger.warning("ALPHA_VANTAGE_API_KEY not set")
            return None
        params["apikey"] = key
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(AV_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                if "Error Message" in data or "Note" in data:
                    logger.warning(f"Alpha Vantage API issue: {data.get('Error Message') or data.get('Note')}")
                    return None
                return data
        except Exception as e:
            logger.error(f"Alpha Vantage request failed: {e}")
            return None

    @staticmethod
    async def get_company_overview(ticker: str) -> Optional[dict]:
        """Fetch company fundamental overview."""
        data = await AlphaVantageService._fetch({
            "function": "OVERVIEW",
            "symbol": ticker,
        })
        if not data or "Symbol" not in data:
            return None
        return {
            "ticker": data.get("Symbol"),
            "name": data.get("Name"),
            "description": data.get("Description"),
            "sector": data.get("Sector"),
            "industry": data.get("Industry"),
            "market_cap": _safe_float(data.get("MarketCapitalization")),
            "pe_ratio": _safe_float(data.get("PERatio")),
            "peg_ratio": _safe_float(data.get("PEGRatio")),
            "book_value": _safe_float(data.get("BookValue")),
            "dividend_yield": _safe_float(data.get("DividendYield")),
            "eps": _safe_float(data.get("EPS")),
            "revenue_per_share": _safe_float(data.get("RevenuePerShareTTM")),
            "profit_margin": _safe_float(data.get("ProfitMargin")),
            "operating_margin": _safe_float(data.get("OperatingMarginTTM")),
            "roe": _safe_float(data.get("ReturnOnEquityTTM")),
            "target_price": _safe_float(data.get("AnalystTargetPrice")),
            "fifty_two_week_high": _safe_float(data.get("52WeekHigh")),
            "fifty_two_week_low": _safe_float(data.get("52WeekLow")),
            "beta": _safe_float(data.get("Beta")),
        }

    @staticmethod
    async def get_economic_indicator(
        function: str,
        interval: str = "annual",
    ) -> list[dict]:
        """
        Fetch economic indicator data.
        Functions: REAL_GDP, CPI, INFLATION, FEDERAL_FUNDS_RATE,
                   UNEMPLOYMENT, TREASURY_YIELD, RETAIL_SALES, NONFARM_PAYROLL
        """
        params = {"function": function}
        if function == "TREASURY_YIELD":
            params["maturity"] = "10year"
        if function in ("REAL_GDP", "CPI"):
            params["interval"] = interval
        data = await AlphaVantageService._fetch(params)
        if not data or "data" not in data:
            return []
        label = data.get("name", function)
        unit = data.get("unit", "")
        records = []
        for entry in data["data"][:60]:  # last 60 data points
            val = _safe_float(entry.get("value"))
            if val is not None:
                records.append({
                    "date": entry.get("date"),
                    "value": val,
                    "label": label,
                    "unit": unit,
                })
        return records

    @staticmethod
    async def get_sma(ticker: str, period: int = 50, interval: str = "daily") -> list[dict]:
        """Fetch Simple Moving Average."""
        data = await AlphaVantageService._fetch({
            "function": "SMA",
            "symbol": ticker,
            "interval": interval,
            "time_period": str(period),
            "series_type": "close",
        })
        key = f"Technical Analysis: SMA"
        if not data or key not in data:
            return []
        return [
            {"date": d, "sma": float(v["SMA"])}
            for d, v in list(data[key].items())[:100]
        ]

    @staticmethod
    async def get_rsi(ticker: str, period: int = 14, interval: str = "daily") -> list[dict]:
        """Fetch Relative Strength Index."""
        data = await AlphaVantageService._fetch({
            "function": "RSI",
            "symbol": ticker,
            "interval": interval,
            "time_period": str(period),
            "series_type": "close",
        })
        key = f"Technical Analysis: RSI"
        if not data or key not in data:
            return []
        return [
            {"date": d, "rsi": float(v["RSI"])}
            for d, v in list(data[key].items())[:100]
        ]


def _safe_float(val) -> Optional[float]:
    if val is None or val == "None" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
