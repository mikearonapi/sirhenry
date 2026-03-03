"""Market — economic indicators, market overview for HENRY dashboard."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.market.economic import EconomicDataService, INDICATOR_METADATA
from pipeline.market.alpha_vantage import AlphaVantageService
from pipeline.market.crypto import CryptoService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


# ---------------------------------------------------------------------------
# Economic Indicators
# ---------------------------------------------------------------------------
@router.get("/indicators")
async def get_dashboard_indicators():
    """Get key economic indicators for the HENRY dashboard."""
    data = await EconomicDataService.get_dashboard_indicators()
    return {"indicators": data}


@router.get("/indicators/{series_id}")
async def get_indicator(series_id: str, interval: str = "annual"):
    """Get detailed data for a specific economic indicator."""
    data = await EconomicDataService.get_indicator(series_id.upper(), interval)
    if not data:
        raise HTTPException(404, f"Indicator {series_id} not found or unavailable")
    return data


@router.get("/indicators-list")
async def list_available_indicators():
    """List all available economic indicator series."""
    return {
        "indicators": [
            {"series_id": k, **v}
            for k, v in INDICATOR_METADATA.items()
        ]
    }


# ---------------------------------------------------------------------------
# Mortgage Context
# ---------------------------------------------------------------------------
@router.get("/mortgage-context")
async def get_mortgage_context():
    """Get current rate environment for life scenario calculations."""
    return await EconomicDataService.get_mortgage_context()


# ---------------------------------------------------------------------------
# Company Research
# ---------------------------------------------------------------------------
@router.get("/research/{ticker}")
async def research_company(ticker: str):
    """Get Alpha Vantage fundamental overview for a company."""
    data = await AlphaVantageService.get_company_overview(ticker.upper())
    if not data:
        raise HTTPException(404, f"No data found for {ticker}")
    return data


# ---------------------------------------------------------------------------
# Technical Indicators
# ---------------------------------------------------------------------------
@router.get("/technicals/{ticker}/sma")
async def get_sma(ticker: str, period: int = 50):
    data = await AlphaVantageService.get_sma(ticker.upper(), period)
    return {"ticker": ticker.upper(), "indicator": "SMA", "period": period, "data": data}


@router.get("/technicals/{ticker}/rsi")
async def get_rsi(ticker: str, period: int = 14):
    data = await AlphaVantageService.get_rsi(ticker.upper(), period)
    return {"ticker": ticker.upper(), "indicator": "RSI", "period": period, "data": data}


# ---------------------------------------------------------------------------
# Crypto Market
# ---------------------------------------------------------------------------
@router.get("/crypto/search")
async def search_crypto(query: str):
    """Search for cryptocurrencies by name or symbol."""
    results = await CryptoService.search_coins(query)
    return {"results": results}


@router.get("/crypto/trending")
async def trending_crypto():
    """Get trending cryptocurrencies."""
    return {"coins": await CryptoService.get_trending()}


@router.get("/crypto/{coin_id}")
async def crypto_detail(coin_id: str):
    """Get detailed info for a cryptocurrency."""
    data = await CryptoService.get_coin_detail(coin_id)
    if not data:
        raise HTTPException(404, f"Coin {coin_id} not found")
    return data


@router.get("/crypto/{coin_id}/history")
async def crypto_history(coin_id: str, days: int = 365):
    """Get price history for a cryptocurrency."""
    data = await CryptoService.get_price_history(coin_id, days)
    return {"coin_id": coin_id, "days": days, "data": data}
