"""
Yahoo Finance market data service via yfinance.
Provides real-time quotes, historical data, and fundamental analysis.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

QUOTE_CACHE_TTL_MINUTES = 15


class YahooFinanceService:
    """Wraps yfinance for stock/ETF data retrieval with caching."""

    @staticmethod
    def get_quote(ticker: str) -> Optional[dict]:
        """Fetch current quote data for a single ticker."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            info = t.info
            if not info or "regularMarketPrice" not in info:
                fast = t.fast_info
                return {
                    "ticker": ticker.upper(),
                    "price": getattr(fast, "last_price", None),
                    "previous_close": getattr(fast, "previous_close", None),
                    "market_cap": getattr(fast, "market_cap", None),
                    "company_name": ticker.upper(),
                }
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            change = (price - prev) if price and prev else None
            change_pct = (change / prev * 100) if change and prev else None
            return {
                "ticker": ticker.upper(),
                "company_name": info.get("shortName") or info.get("longName", ticker),
                "price": price,
                "previous_close": prev,
                "change": round(change, 2) if change else None,
                "change_pct": round(change_pct, 2) if change_pct else None,
                "volume": info.get("regularMarketVolume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "dividend_yield": info.get("dividendYield"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "beta": info.get("beta"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "earnings_per_share": info.get("trailingEps"),
                "book_value": info.get("bookValue"),
                "profit_margin": info.get("profitMargins"),
                "revenue_growth": info.get("revenueGrowth"),
            }
        except Exception as e:
            logger.error(f"Failed to fetch quote for {ticker}: {e}")
            return None

    @staticmethod
    def get_bulk_quotes(tickers: list[str]) -> dict[str, dict]:
        """Fetch quotes for multiple tickers. Returns {ticker: quote_dict}."""
        results = {}
        for ticker in tickers:
            quote = YahooFinanceService.get_quote(ticker)
            if quote:
                results[ticker.upper()] = quote
        return results

    @staticmethod
    def get_history(ticker: str, period: str = "1y", interval: str = "1d") -> list[dict]:
        """Fetch historical OHLCV data."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period=period, interval=interval)
            if hist.empty:
                return []
            records = []
            for date, row in hist.iterrows():
                records.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })
            return records
        except Exception as e:
            logger.error(f"Failed to fetch history for {ticker}: {e}")
            return []

    @staticmethod
    def get_dividend_history(ticker: str) -> list[dict]:
        """Fetch dividend payment history."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            divs = t.dividends
            if divs.empty:
                return []
            return [
                {"date": d.strftime("%Y-%m-%d"), "dividend": round(float(v), 4)}
                for d, v in divs.items()
            ]
        except Exception as e:
            logger.error(f"Failed to fetch dividends for {ticker}: {e}")
            return []

    @staticmethod
    def get_key_stats(ticker: str) -> Optional[dict]:
        """Fetch fundamental key statistics for analysis."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            info = t.info
            if not info:
                return None
            return {
                "ticker": ticker.upper(),
                "name": info.get("shortName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "ev_to_ebitda": info.get("enterpriseToEbitda"),
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "revenue": info.get("totalRevenue"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "free_cash_flow": info.get("freeCashflow"),
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "dividend_yield": info.get("dividendYield"),
                "dividend_rate": info.get("dividendRate"),
                "payout_ratio": info.get("payoutRatio"),
                "beta": info.get("beta"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "analyst_target": info.get("targetMeanPrice"),
                "recommendation": info.get("recommendationKey"),
            }
        except Exception as e:
            logger.error(f"Failed to fetch stats for {ticker}: {e}")
            return None
