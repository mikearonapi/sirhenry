"""
CoinGecko crypto market data service.
Free API, no key required. Rate limit: ~10-30 requests/minute.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CG_BASE_URL = "https://api.coingecko.com/api/v3"


class CryptoService:
    """CoinGecko API wrapper for cryptocurrency price data."""

    @staticmethod
    async def get_prices(coin_ids: list[str]) -> dict[str, dict]:
        """
        Fetch current prices for multiple coins.
        coin_ids: CoinGecko IDs like ["bitcoin", "ethereum", "solana"]
        Returns: {coin_id: {usd, usd_24h_change, usd_market_cap, ...}}
        """
        if not coin_ids:
            return {}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{CG_BASE_URL}/simple/price", params={
                    "ids": ",".join(coin_ids),
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                })
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"CoinGecko price fetch failed: {e}")
            return {}

    @staticmethod
    async def get_coin_detail(coin_id: str) -> Optional[dict]:
        """Fetch detailed coin info including description, links, market data."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{CG_BASE_URL}/coins/{coin_id}",
                    params={"localization": "false", "tickers": "false", "community_data": "false"},
                )
                resp.raise_for_status()
                data = resp.json()
                md = data.get("market_data", {})
                return {
                    "id": data.get("id"),
                    "symbol": data.get("symbol", "").upper(),
                    "name": data.get("name"),
                    "price": md.get("current_price", {}).get("usd"),
                    "market_cap": md.get("market_cap", {}).get("usd"),
                    "market_cap_rank": data.get("market_cap_rank"),
                    "total_volume": md.get("total_volume", {}).get("usd"),
                    "price_change_24h_pct": md.get("price_change_percentage_24h"),
                    "price_change_7d_pct": md.get("price_change_percentage_7d"),
                    "price_change_30d_pct": md.get("price_change_percentage_30d"),
                    "ath": md.get("ath", {}).get("usd"),
                    "ath_change_pct": md.get("ath_change_percentage", {}).get("usd"),
                    "atl": md.get("atl", {}).get("usd"),
                    "circulating_supply": md.get("circulating_supply"),
                    "max_supply": md.get("max_supply"),
                }
        except Exception as e:
            logger.error(f"CoinGecko coin detail failed for {coin_id}: {e}")
            return None

    @staticmethod
    async def get_price_history(coin_id: str, days: int = 365) -> list[dict]:
        """Fetch historical price data for charting."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{CG_BASE_URL}/coins/{coin_id}/market_chart",
                    params={"vs_currency": "usd", "days": str(days)},
                )
                resp.raise_for_status()
                data = resp.json()
                prices = data.get("prices", [])
                return [
                    {"timestamp": int(p[0]), "price": round(p[1], 2)}
                    for p in prices
                ]
        except Exception as e:
            logger.error(f"CoinGecko history failed for {coin_id}: {e}")
            return []

    @staticmethod
    async def search_coins(query: str) -> list[dict]:
        """Search for coins by name or symbol."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{CG_BASE_URL}/search", params={"query": query})
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "id": c.get("id"),
                        "symbol": c.get("symbol", "").upper(),
                        "name": c.get("name"),
                        "market_cap_rank": c.get("market_cap_rank"),
                    }
                    for c in data.get("coins", [])[:20]
                ]
        except Exception as e:
            logger.error(f"CoinGecko search failed: {e}")
            return []

    @staticmethod
    async def get_trending() -> list[dict]:
        """Fetch trending coins."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{CG_BASE_URL}/search/trending")
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "id": c["item"]["id"],
                        "symbol": c["item"]["symbol"].upper(),
                        "name": c["item"]["name"],
                        "market_cap_rank": c["item"].get("market_cap_rank"),
                    }
                    for c in data.get("coins", [])[:10]
                ]
        except Exception as e:
            logger.error(f"CoinGecko trending failed: {e}")
            return []
