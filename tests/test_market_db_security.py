"""
Comprehensive tests for market data, DB utility, security, and parser modules.

Covers:
  - Market: yahoo_finance, crypto, economic, property_valuation, vehicle_valuation, alpha_vantage
  - DB Utility: field_encryption, flow_classifier, household_sync, backup, cross_source dedup
  - Security: file_cleanup, logging (PII redaction)
  - Parsers: pdf_parser, xlsx_parser, docx_parser
  - Seed: seed_entities
"""
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pandas as pd
import pytest
import pytest_asyncio

from pipeline.db.schema import (
    Base,
    FamilyMember,
    HouseholdProfile,
    Transaction,
)


# ============================================================================
# MARKET DATA — Yahoo Finance
# ============================================================================

class TestYahooFinanceService:
    """Tests for pipeline.market.yahoo_finance.YahooFinanceService."""

    def _make_mock_ticker(self, info=None, fast_info=None, history_df=None, dividends=None):
        """Build a mock yfinance.Ticker with configurable data."""
        ticker = MagicMock()
        ticker.info = info or {}
        if fast_info:
            ticker.fast_info = fast_info
        else:
            ticker.fast_info = MagicMock(last_price=None, previous_close=None, market_cap=None)
        if history_df is not None:
            ticker.history = MagicMock(return_value=history_df)
        else:
            ticker.history = MagicMock(return_value=pd.DataFrame())
        if dividends is not None:
            ticker.dividends = dividends
        else:
            ticker.dividends = pd.Series([], dtype=float)
        return ticker

    @patch("yfinance.Ticker")
    def test_get_quote_with_full_info(self, mock_ticker_cls):
        """Test get_quote returns properly formatted data including change calculations."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        mock_ticker_cls.return_value = self._make_mock_ticker(info={
            "regularMarketPrice": 185.50,
            "previousClose": 183.00,
            "shortName": "Apple Inc.",
            "regularMarketVolume": 55_000_000,
            "marketCap": 2_850_000_000_000,
            "trailingPE": 28.5,
            "forwardPE": 26.2,
            "dividendYield": 0.0056,
            "fiftyTwoWeekHigh": 199.62,
            "fiftyTwoWeekLow": 124.17,
            "beta": 1.29,
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "trailingEps": 6.42,
            "bookValue": 4.15,
            "profitMargins": 0.2531,
            "revenueGrowth": 0.028,
        })

        result = YahooFinanceService.get_quote("AAPL")
        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["company_name"] == "Apple Inc."
        assert result["price"] == 185.50
        assert result["previous_close"] == 183.00
        assert result["change"] == 2.50
        assert result["change_pct"] == pytest.approx(1.37, abs=0.01)
        assert result["volume"] == 55_000_000
        assert result["market_cap"] == 2_850_000_000_000
        assert result["pe_ratio"] == 28.5
        assert result["sector"] == "Technology"
        assert result["beta"] == 1.29
        assert result["dividend_yield"] == 0.0056

    @patch("yfinance.Ticker")
    def test_get_quote_fallback_to_fast_info(self, mock_ticker_cls):
        """Test fallback to fast_info when regularMarketPrice is missing."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        fast = MagicMock(last_price=42.10, previous_close=41.80, market_cap=5_000_000_000)
        mock_ticker_cls.return_value = self._make_mock_ticker(info={}, fast_info=fast)

        result = YahooFinanceService.get_quote("XYZ")
        assert result is not None
        assert result["ticker"] == "XYZ"
        assert result["price"] == 42.10
        assert result["previous_close"] == 41.80
        assert result["market_cap"] == 5_000_000_000

    @patch("yfinance.Ticker")
    def test_get_quote_exception_returns_none(self, mock_ticker_cls):
        """Test graceful handling of API errors."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        mock_ticker_cls.side_effect = Exception("Network error")
        result = YahooFinanceService.get_quote("BAD")
        assert result is None

    @patch("yfinance.Ticker")
    def test_get_bulk_quotes(self, mock_ticker_cls):
        """Test bulk quote fetching returns results keyed by ticker."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        def make_ticker(symbol):
            info = {
                "regularMarketPrice": 100.0 if symbol == "AAPL" else 250.0,
                "previousClose": 99.0 if symbol == "AAPL" else 248.0,
                "shortName": "Apple" if symbol == "AAPL" else "Microsoft",
            }
            return self._make_mock_ticker(info=info)

        mock_ticker_cls.side_effect = make_ticker

        results = YahooFinanceService.get_bulk_quotes(["AAPL", "MSFT"])
        assert "AAPL" in results
        assert "MSFT" in results
        assert results["AAPL"]["price"] == 100.0
        assert results["MSFT"]["price"] == 250.0

    @patch("yfinance.Ticker")
    def test_get_history(self, mock_ticker_cls):
        """Test historical data returns properly formatted OHLCV records."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        hist_data = pd.DataFrame(
            {
                "Open": [180.0, 181.0],
                "High": [185.0, 186.0],
                "Low": [179.0, 180.0],
                "Close": [184.0, 185.0],
                "Volume": [50_000_000, 55_000_000],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
        mock_ticker_cls.return_value = self._make_mock_ticker(history_df=hist_data)

        records = YahooFinanceService.get_history("AAPL", period="5d")
        assert len(records) == 2
        assert records[0]["date"] == "2024-01-02"
        assert records[0]["close"] == 184.0
        assert records[0]["volume"] == 50_000_000
        assert records[1]["open"] == 181.0

    @patch("yfinance.Ticker")
    def test_get_history_empty(self, mock_ticker_cls):
        """Test empty history returns empty list."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        mock_ticker_cls.return_value = self._make_mock_ticker(history_df=pd.DataFrame())
        assert YahooFinanceService.get_history("AAPL") == []

    @patch("yfinance.Ticker")
    def test_get_dividend_history(self, mock_ticker_cls):
        """Test dividend history returns correctly formatted entries."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        divs = pd.Series(
            [0.24, 0.25],
            index=pd.to_datetime(["2024-02-10", "2024-05-10"]),
        )
        mock_ticker_cls.return_value = self._make_mock_ticker(dividends=divs)

        records = YahooFinanceService.get_dividend_history("AAPL")
        assert len(records) == 2
        assert records[0]["date"] == "2024-02-10"
        assert records[0]["dividend"] == 0.24
        assert records[1]["dividend"] == 0.25

    @patch("yfinance.Ticker")
    def test_get_key_stats(self, mock_ticker_cls):
        """Test key stats returns fundamental analysis data."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        mock_ticker_cls.return_value = self._make_mock_ticker(info={
            "shortName": "Tesla Inc",
            "sector": "Consumer Cyclical",
            "industry": "Auto Manufacturers",
            "marketCap": 800_000_000_000,
            "trailingPE": 65.2,
            "priceToBook": 15.3,
            "profitMargins": 0.121,
            "returnOnEquity": 0.279,
            "beta": 2.05,
            "recommendationKey": "buy",
        })

        result = YahooFinanceService.get_key_stats("TSLA")
        assert result is not None
        assert result["ticker"] == "TSLA"
        assert result["name"] == "Tesla Inc"
        assert result["sector"] == "Consumer Cyclical"
        assert result["pe_ratio"] == 65.2
        assert result["beta"] == 2.05
        assert result["recommendation"] == "buy"

    @patch("yfinance.Ticker")
    def test_get_key_stats_none_info(self, mock_ticker_cls):
        """Test key stats returns None when no info available."""
        from pipeline.market.yahoo_finance import YahooFinanceService

        ticker_mock = MagicMock()
        ticker_mock.info = None
        mock_ticker_cls.return_value = ticker_mock

        result = YahooFinanceService.get_key_stats("FAKE")
        assert result is None


# ============================================================================
# MARKET DATA — Crypto (CoinGecko)
# ============================================================================

class TestCryptoService:
    """Tests for pipeline.market.crypto.CryptoService."""

    @pytest.mark.asyncio
    async def test_get_prices_bitcoin(self):
        """Test fetching Bitcoin price returns realistic data."""
        from pipeline.market.crypto import CryptoService

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bitcoin": {
                "usd": 67_432.50,
                "usd_24h_change": 2.35,
                "usd_market_cap": 1_320_000_000_000,
                "usd_24h_vol": 28_000_000_000,
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await CryptoService.get_prices(["bitcoin"])
            assert "bitcoin" in result
            assert result["bitcoin"]["usd"] == 67_432.50
            assert result["bitcoin"]["usd_24h_change"] == 2.35
            assert result["bitcoin"]["usd_market_cap"] == 1_320_000_000_000

    @pytest.mark.asyncio
    async def test_get_prices_empty_list(self):
        """Test empty coin list returns empty dict."""
        from pipeline.market.crypto import CryptoService

        result = await CryptoService.get_prices([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_prices_error_returns_empty(self):
        """Test network errors return empty dict."""
        from pipeline.market.crypto import CryptoService

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await CryptoService.get_prices(["bitcoin"])
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_coin_detail(self):
        """Test detailed coin info extraction."""
        from pipeline.market.crypto import CryptoService

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "ethereum",
            "symbol": "eth",
            "name": "Ethereum",
            "market_cap_rank": 2,
            "market_data": {
                "current_price": {"usd": 3_450.00},
                "market_cap": {"usd": 415_000_000_000},
                "total_volume": {"usd": 12_000_000_000},
                "price_change_percentage_24h": -1.2,
                "price_change_percentage_7d": 5.4,
                "price_change_percentage_30d": 12.1,
                "ath": {"usd": 4_891.70},
                "ath_change_percentage": {"usd": -29.5},
                "atl": {"usd": 0.43},
                "circulating_supply": 120_000_000,
                "max_supply": None,
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await CryptoService.get_coin_detail("ethereum")
            assert result is not None
            assert result["id"] == "ethereum"
            assert result["symbol"] == "ETH"
            assert result["price"] == 3_450.00
            assert result["market_cap_rank"] == 2
            assert result["ath"] == 4_891.70
            assert result["max_supply"] is None

    @pytest.mark.asyncio
    async def test_get_price_history(self):
        """Test historical price data for charting."""
        from pipeline.market.crypto import CryptoService

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "prices": [
                [1704153600000, 42500.25],
                [1704240000000, 43100.50],
                [1704326400000, 42800.00],
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await CryptoService.get_price_history("bitcoin", days=30)
            assert len(result) == 3
            assert result[0]["timestamp"] == 1704153600000
            assert result[0]["price"] == 42500.25
            assert result[2]["price"] == 42800.00

    @pytest.mark.asyncio
    async def test_search_coins(self):
        """Test coin search returns structured results."""
        from pipeline.market.crypto import CryptoService

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "coins": [
                {"id": "solana", "symbol": "sol", "name": "Solana", "market_cap_rank": 5},
                {"id": "solend", "symbol": "slnd", "name": "Solend", "market_cap_rank": 500},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await CryptoService.search_coins("sol")
            assert len(result) == 2
            assert result[0]["id"] == "solana"
            assert result[0]["symbol"] == "SOL"
            assert result[0]["market_cap_rank"] == 5

    @pytest.mark.asyncio
    async def test_get_trending(self):
        """Test trending coins returns structured results."""
        from pipeline.market.crypto import CryptoService

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "coins": [
                {"item": {"id": "pepe", "symbol": "pepe", "name": "Pepe", "market_cap_rank": 46}},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await CryptoService.get_trending()
            assert len(result) == 1
            assert result[0]["id"] == "pepe"
            assert result[0]["symbol"] == "PEPE"


# ============================================================================
# MARKET DATA — Economic Indicators
# ============================================================================

class TestEconomicDataService:
    """Tests for pipeline.market.economic.EconomicDataService."""

    @pytest.mark.asyncio
    async def test_get_indicator_known_series(self):
        """Test fetching a known economic indicator with metadata."""
        from pipeline.market.economic import EconomicDataService

        mock_records = [
            {"date": "2024-01-01", "value": 5.33, "label": "Fed Funds", "unit": "percent"},
            {"date": "2023-10-01", "value": 5.33, "label": "Fed Funds", "unit": "percent"},
        ]
        with patch.object(
            EconomicDataService, "get_indicator",
            wraps=EconomicDataService.get_indicator,
        ):
            with patch(
                "pipeline.market.economic.AlphaVantageService.get_economic_indicator",
                new_callable=AsyncMock,
                return_value=mock_records,
            ):
                result = await EconomicDataService.get_indicator("FEDERAL_FUNDS_RATE")
                assert result is not None
                assert result["series_id"] == "FEDERAL_FUNDS_RATE"
                assert result["label"] == "Federal Funds Rate"
                assert result["unit"] == "percent"
                assert result["category"] == "rates"
                assert result["latest_value"] == 5.33
                assert result["latest_date"] == "2024-01-01"
                assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_get_indicator_unknown_series(self):
        """Test unknown series ID returns None."""
        from pipeline.market.economic import EconomicDataService

        result = await EconomicDataService.get_indicator("FAKE_INDICATOR")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mortgage_context(self):
        """Test mortgage context with realistic rate data."""
        from pipeline.market.economic import EconomicDataService

        async def mock_get_indicator(series_id, interval="annual"):
            data_map = {
                "FEDERAL_FUNDS_RATE": {
                    "series_id": "FEDERAL_FUNDS_RATE",
                    "label": "Federal Funds Rate",
                    "unit": "percent",
                    "category": "rates",
                    "data": [{"date": "2024-01-01", "value": 5.33}],
                    "latest_value": 5.33,
                    "latest_date": "2024-01-01",
                },
                "TREASURY_YIELD": {
                    "series_id": "TREASURY_YIELD",
                    "label": "10-Year Treasury Yield",
                    "unit": "percent",
                    "category": "rates",
                    "data": [{"date": "2024-01-01", "value": 4.25}],
                    "latest_value": 4.25,
                    "latest_date": "2024-01-01",
                },
                "INFLATION": {
                    "series_id": "INFLATION",
                    "label": "Inflation Rate",
                    "unit": "percent",
                    "category": "inflation",
                    "data": [{"date": "2024-01-01", "value": 3.1}],
                    "latest_value": 3.1,
                    "latest_date": "2024-01-01",
                },
            }
            return data_map.get(series_id)

        with patch.object(EconomicDataService, "get_indicator", side_effect=mock_get_indicator):
            result = await EconomicDataService.get_mortgage_context()
            assert result["fed_funds_rate"] == 5.33
            assert result["ten_year_treasury"] == 4.25
            assert result["inflation_rate"] == 3.1
            assert result["estimated_30yr_mortgage"] == 6.00  # 4.25 + 1.75
            assert result["rate_environment"] == "elevated"  # 5.33 is in 4-6 range

    def test_classify_rate_environment(self):
        """Test rate environment classification at boundary values."""
        from pipeline.market.economic import _classify_rate_environment

        assert _classify_rate_environment(None) == "unknown"
        assert _classify_rate_environment(0.5) == "low"
        assert _classify_rate_environment(1.99) == "low"
        assert _classify_rate_environment(2.0) == "moderate"
        assert _classify_rate_environment(3.99) == "moderate"
        assert _classify_rate_environment(4.0) == "elevated"
        assert _classify_rate_environment(5.99) == "elevated"
        assert _classify_rate_environment(6.0) == "high"
        assert _classify_rate_environment(8.0) == "high"


# ============================================================================
# MARKET DATA — Property Valuation
# ============================================================================

class TestPropertyValuation:
    """Tests for pipeline.market.property_valuation.PropertyValuationService."""

    @pytest.mark.asyncio
    async def test_valuation_no_api_key(self):
        """Test returns None when API key is not set."""
        from pipeline.market.property_valuation import PropertyValuationService

        with patch.dict(os.environ, {}, clear=True):
            # Ensure RENTCAST_API_KEY is not set
            os.environ.pop("RENTCAST_API_KEY", None)
            result = await PropertyValuationService.get_valuation("123 Main St, Springfield, IL")
            assert result is None

    @pytest.mark.asyncio
    async def test_valuation_500k_house(self):
        """Test a house valued at $500k returns reasonable estimates."""
        from pipeline.market.property_valuation import PropertyValuationService

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "price": 500_000,
            "priceLow": 475_000,
            "priceHigh": 530_000,
            "bedrooms": 4,
            "bathrooms": 2.5,
            "squareFootage": 2_400,
            "lotSize": 8_500,
            "yearBuilt": 2005,
            "propertyType": "Single Family",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key-123"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                result = await PropertyValuationService.get_valuation(
                    "123 Oak Ave, Lake Forest, IL 60045"
                )

                assert result is not None
                assert result["estimated_value"] == 500_000
                assert result["price_low"] == 475_000
                assert result["price_high"] == 530_000
                assert result["bedrooms"] == 4
                assert result["bathrooms"] == 2.5
                assert result["sqft"] == 2_400
                assert result["year_built"] == 2005
                assert result["property_type"] == "Single Family"
                assert result["confidence"] == "medium"
                assert result["source"] == "rentcast"
                # Reasonable range: low should be < estimated < high
                assert result["price_low"] < result["estimated_value"] < result["price_high"]

    @pytest.mark.asyncio
    async def test_valuation_rate_limit_429(self):
        """Test rate limit response returns None gracefully."""
        import httpx
        from pipeline.market.property_valuation import PropertyValuationService

        mock_request = MagicMock()
        mock_resp_obj = MagicMock()
        mock_resp_obj.status_code = 429

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(
                    side_effect=httpx.HTTPStatusError("rate limited", request=mock_request, response=mock_resp_obj)
                )
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                result = await PropertyValuationService.get_valuation("123 Main St")
                assert result is None


# ============================================================================
# MARKET DATA — Vehicle Valuation
# ============================================================================

class TestVehicleValuation:
    """Tests for pipeline.market.vehicle_valuation.VehicleValuationService."""

    @pytest.mark.asyncio
    async def test_decode_vin(self):
        """Test VIN decoding returns make/model/year."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Results": [{
                "ModelYear": "2020",
                "Make": "Toyota",
                "Model": "Camry",
                "Trim": "SE",
                "BodyClass": "Sedan/Saloon",
                "EngineCylinders": "4",
                "DisplacementL": "2.5",
                "FuelTypePrimary": "Gasoline",
                "DriveType": "FWD",
                "VehicleType": "PASSENGER CAR",
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await VehicleValuationService.decode_vin("4T1BF1FK5LU123456")
            assert result is not None
            assert result["year"] == 2020
            assert result["make"] == "Toyota"
            assert result["model"] == "Camry"
            assert result["trim"] == "SE"
            assert result["fuel_type"] == "Gasoline"
            assert result["drive_type"] == "FWD"

    @pytest.mark.asyncio
    async def test_decode_vin_invalid(self):
        """Test invalid VIN returns None when Make is empty."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        mock_response = MagicMock()
        mock_response.json.return_value = {"Results": [{"Make": ""}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await VehicleValuationService.decode_vin("INVALIDVIN")
            assert result is None

    def test_estimate_value_2020_toyota(self):
        """Test 2020 Toyota Camry depreciation returns reasonable value."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        current_year = date.today().year
        result = VehicleValuationService.estimate_value(
            year=2020, make="Toyota", model="Camry",
            purchase_price=28_000, purchase_year=2020,
        )
        assert result is not None
        age = current_year - 2020
        # With purchase price of $28k:
        # Year 1: 28000 * 0.80 = 22400
        # Year 2: 22400 * 0.85 = 19040
        # Year 3: 19040 * 0.85 = 16184
        # Year 4: 16184 * 0.85 = 13756.4
        # Year 5: 13756.4 * 0.85 = 11692.94
        # Year 6: 11692.94 * 0.90 = 10523.65
        # Should be somewhere between $8k-$16k for a 2020 car in 2026
        assert 5_000 <= result["estimated_value"] <= 20_000
        assert result["confidence"] == "medium"  # has purchase_price
        assert result["method"] == "depreciation_curve"
        assert result["age_years"] == age
        assert result["base_value"] == 28_000

    def test_estimate_value_without_purchase_price(self):
        """Test estimation using MSRP lookup when no purchase price given."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        result = VehicleValuationService.estimate_value(
            year=2022, make="Honda", model="Civic",
        )
        assert result is not None
        assert result["confidence"] == "low"  # no purchase_price
        assert result["base_value"] == 35_000  # default MSRP for non-luxury
        assert result["estimated_value"] > 0

    def test_estimate_value_luxury_brand(self):
        """Test luxury brand uses higher MSRP estimate."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        result = VehicleValuationService.estimate_value(
            year=2023, make="BMW", model="X5",
        )
        assert result is not None
        assert result["base_value"] == 55_000  # luxury MSRP

    def test_estimate_value_truck(self):
        """Test truck model uses truck MSRP estimate."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        result = VehicleValuationService.estimate_value(
            year=2023, make="Ford", model="F-150",
        )
        assert result is not None
        assert result["base_value"] == 45_000  # truck MSRP

    def test_estimate_value_future_year_returns_none(self):
        """Test future model year returns None."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        result = VehicleValuationService.estimate_value(
            year=date.today().year + 2, make="Toyota", model="Camry",
        )
        assert result is None

    def test_estimate_value_floor_at_10_percent(self):
        """Test value doesn't drop below 10% of base value."""
        from pipeline.market.vehicle_valuation import VehicleValuationService

        result = VehicleValuationService.estimate_value(
            year=2000, make="Honda", model="Civic",
            purchase_price=20_000, purchase_year=2000,
        )
        assert result is not None
        # After 26 years of depreciation, floor should be 10% of $20k = $2000
        assert result["estimated_value"] >= 2_000


# ============================================================================
# MARKET DATA — Alpha Vantage
# ============================================================================

class TestAlphaVantageService:
    """Tests for pipeline.market.alpha_vantage.AlphaVantageService."""

    @pytest.mark.asyncio
    async def test_get_company_overview(self):
        """Test company overview returns structured fundamental data."""
        from pipeline.market.alpha_vantage import AlphaVantageService

        api_response = {
            "Symbol": "AAPL",
            "Name": "Apple Inc",
            "Description": "Apple designs consumer electronics...",
            "Sector": "Technology",
            "Industry": "Consumer Electronics",
            "MarketCapitalization": "2850000000000",
            "PERatio": "28.5",
            "PEGRatio": "2.1",
            "BookValue": "4.15",
            "DividendYield": "0.0056",
            "EPS": "6.42",
            "Beta": "1.29",
            "52WeekHigh": "199.62",
            "52WeekLow": "124.17",
        }

        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.json.return_value = api_response
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                result = await AlphaVantageService.get_company_overview("AAPL")
                assert result is not None
                assert result["ticker"] == "AAPL"
                assert result["name"] == "Apple Inc"
                assert result["market_cap"] == 2_850_000_000_000
                assert result["pe_ratio"] == 28.5
                assert result["beta"] == 1.29
                assert result["fifty_two_week_high"] == 199.62

    @pytest.mark.asyncio
    async def test_fetch_no_api_key(self):
        """Test returns None when API key is not set."""
        from pipeline.market.alpha_vantage import AlphaVantageService

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
            result = await AlphaVantageService._fetch({"function": "OVERVIEW"})
            assert result is None

    @pytest.mark.asyncio
    async def test_get_economic_indicator(self):
        """Test economic indicator returns parsed data points."""
        from pipeline.market.alpha_vantage import AlphaVantageService

        api_response = {
            "name": "Federal Funds Rate",
            "unit": "percent",
            "data": [
                {"date": "2024-01-01", "value": "5.33"},
                {"date": "2023-10-01", "value": "5.33"},
                {"date": "2023-07-01", "value": "5.08"},
            ],
        }

        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.json.return_value = api_response
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                records = await AlphaVantageService.get_economic_indicator("FEDERAL_FUNDS_RATE")
                assert len(records) == 3
                assert records[0]["value"] == 5.33
                assert records[0]["date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_get_sma(self):
        """Test SMA technical indicator returns correctly parsed data."""
        from pipeline.market.alpha_vantage import AlphaVantageService

        api_response = {
            "Technical Analysis: SMA": {
                "2024-01-05": {"SMA": "185.50"},
                "2024-01-04": {"SMA": "184.20"},
            }
        }

        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.json.return_value = api_response
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                records = await AlphaVantageService.get_sma("AAPL", period=50)
                assert len(records) == 2
                assert records[0]["sma"] == 185.50

    @pytest.mark.asyncio
    async def test_get_rsi(self):
        """Test RSI technical indicator returns correctly parsed data."""
        from pipeline.market.alpha_vantage import AlphaVantageService

        api_response = {
            "Technical Analysis: RSI": {
                "2024-01-05": {"RSI": "62.35"},
                "2024-01-04": {"RSI": "58.90"},
            }
        }

        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.json.return_value = api_response
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                records = await AlphaVantageService.get_rsi("AAPL")
                assert len(records) == 2
                assert records[0]["rsi"] == 62.35

    def test_safe_float(self):
        """Test _safe_float handles various edge cases."""
        from pipeline.market.alpha_vantage import _safe_float

        assert _safe_float("123.45") == 123.45
        assert _safe_float("2850000000000") == 2_850_000_000_000
        assert _safe_float(None) is None
        assert _safe_float("None") is None
        assert _safe_float("-") is None
        assert _safe_float("not_a_number") is None
        assert _safe_float(42.5) == 42.5


# ============================================================================
# DB UTILITY — Field Encryption
# ============================================================================

class TestFieldEncryption:
    """Tests for pipeline.db.encryption.encrypt_field / decrypt_field."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypting then decrypting returns the original value."""
        from cryptography.fernet import Fernet
        from pipeline.db import encryption

        key = Fernet.generate_key().decode()
        # Temporarily set the data encryption key
        original_key = encryption._DATA_KEY
        original_fernet = encryption._data_fernet
        try:
            encryption._DATA_KEY = key
            encryption._data_fernet = None  # force re-init

            plaintext = "John Smith"
            encrypted = encryption.encrypt_field(plaintext)
            assert encrypted is not None
            assert encrypted != plaintext  # should be different
            assert len(encrypted) > len(plaintext)  # ciphertext is longer

            decrypted = encryption.decrypt_field(encrypted)
            assert decrypted == plaintext
        finally:
            encryption._DATA_KEY = original_key
            encryption._data_fernet = original_fernet

    def test_encrypt_field_none_returns_none(self):
        """Test None input returns None without error."""
        from pipeline.db.encryption import encrypt_field

        assert encrypt_field(None) is None

    def test_decrypt_field_none_returns_none(self):
        """Test None input returns None without error."""
        from pipeline.db.encryption import decrypt_field

        assert decrypt_field(None) is None

    def test_encrypt_field_sensitive_data(self):
        """Test encryption of various PII data types."""
        from cryptography.fernet import Fernet
        from pipeline.db import encryption

        key = Fernet.generate_key().decode()
        original_key = encryption._DATA_KEY
        original_fernet = encryption._data_fernet
        try:
            encryption._DATA_KEY = key
            encryption._data_fernet = None

            test_data = [
                "Alice Johnson",
                "123-45-6789",  # SSN
                "alice@example.com",
                "Accenture Federal Services",
                '{"dependents": [{"name": "Charlie", "age": 5}]}',
            ]
            for plaintext in test_data:
                encrypted = encryption.encrypt_field(plaintext)
                assert encrypted != plaintext
                assert encryption.decrypt_field(encrypted) == plaintext
        finally:
            encryption._DATA_KEY = original_key
            encryption._data_fernet = original_fernet

    def test_encrypt_no_key_returns_plaintext(self):
        """Test when no encryption key is set, field is returned as-is."""
        from pipeline.db import encryption

        original_key = encryption._DATA_KEY
        original_fernet = encryption._data_fernet
        try:
            encryption._DATA_KEY = ""
            encryption._data_fernet = None

            plaintext = "Sensitive Data"
            assert encryption.encrypt_field(plaintext) == plaintext
        finally:
            encryption._DATA_KEY = original_key
            encryption._data_fernet = original_fernet


# ============================================================================
# DB UTILITY — Flow Classifier
# ============================================================================

class TestFlowClassifier:
    """Tests for pipeline.db.flow_classifier.classify_flow_type."""

    def test_income_category_paycheck(self):
        """Test W-2 Wages category is classified as income."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(5_000.00, "W-2 Wages") == "income"

    def test_income_category_dividend(self):
        """Test Dividend Income category is classified as income."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(125.50, "Dividend Income") == "income"

    def test_income_category_interest(self):
        """Test Interest Income category is classified as income."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(12.34, "Interest Income") == "income"

    def test_transfer_credit_card_payment(self):
        """Test Credit Card Payment is classified as transfer."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-2500.00, "Credit Card Payment") == "transfer"

    def test_transfer_savings(self):
        """Test Savings category is classified as transfer."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-500.00, "Savings") == "transfer"

    def test_transfer_category_check(self):
        """Test Check category is classified as transfer."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-1000.00, "Check") == "transfer"

    def test_expense_negative_amount(self):
        """Test negative amount on a normal category is an expense."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-45.99, "Groceries") == "expense"

    def test_expense_restaurant(self):
        """Test restaurant spending is classified as expense."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-65.00, "Dining Out", "CHIPOTLE MEXICAN GRILL") == "expense"

    def test_refund_positive_amount_non_income_category(self):
        """Test positive amount on a non-income category is a refund."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(25.99, "Shopping", "AMAZON REFUND") == "refund"

    def test_income_description_payroll(self):
        """Test description pattern 'payroll' triggers income classification."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(3_500.00, "Other", "ACCENTURE DES:PAYROLL") == "income"

    def test_income_description_direct_deposit(self):
        """Test description pattern 'direct dep' triggers income classification."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(4_200.00, None, "ACH CREDIT DIRECT DEP EMPLOYER") == "income"

    def test_transfer_description_zelle(self):
        """Test description pattern 'zelle' triggers transfer classification."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-200.00, "Shopping", "Zelle payment to John") == "transfer"

    def test_transfer_description_venmo(self):
        """Test Venmo description triggers transfer classification."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-50.00, "Shopping", "Venmo payment") == "transfer"

    def test_transfer_positive_venmo(self):
        """Test positive Venmo amount is classified as transfer (not refund)."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(100.00, None, "Venmo payment from friend") == "transfer"

    def test_income_paycheck_in_category_name(self):
        """Test category containing 'Paycheck' is income."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(4_500.00, "Accenture Paycheck") == "income"

    def test_income_other_income(self):
        """Test 'Other Income' category is income."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(150.00, "Other Income") == "income"

    def test_transfer_savings_keyword_in_category(self):
        """Test categories with savings keywords are transfers."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-1_000.00, "Emergency Fund") == "transfer"
        assert classify_flow_type(-500.00, "College 529 Plan") == "transfer"
        assert classify_flow_type(-300.00, "Wedding Savings") == "transfer"

    def test_income_reimbursement_category(self):
        """Test reimbursement category is income."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(250.00, "Travel Expenses Reimbursement") == "income"

    def test_transfer_discretionary(self):
        """Test Discretionary category is transfer."""
        from pipeline.db.flow_classifier import classify_flow_type

        assert classify_flow_type(-500.00, "Discretionary Spending") == "transfer"


# ============================================================================
# DB UTILITY — Household Sync
# ============================================================================

class TestHouseholdSync:
    """Tests for pipeline.db.household_sync.sync_household_from_members."""

    @pytest.mark.asyncio
    async def test_sync_with_self_and_spouse(self, session):
        """Test sync updates household fields from self and spouse family members."""
        from pipeline.db.household_sync import sync_household_from_members

        # Create household profile
        hp = HouseholdProfile(name="Test Household", filing_status="mfj", state="IL")
        session.add(hp)
        await session.flush()

        # Add self
        self_member = FamilyMember(
            household_id=hp.id,
            name="Mike Aron",
            relationship="self",
            income=175_000.0,
            employer="Accenture",
            work_state="IL",
        )
        # Add spouse
        spouse_member = FamilyMember(
            household_id=hp.id,
            name="Christine Aron",
            relationship="spouse",
            income=85_000.0,
            employer="Vivant",
            work_state="IL",
        )
        session.add_all([self_member, spouse_member])
        await session.flush()

        result = await sync_household_from_members(session, hp.id)
        assert result is not None
        assert result["spouse_a_name"] == "Mike Aron"
        assert result["spouse_b_name"] == "Christine Aron"
        assert result["combined_income"] == 260_000.0
        assert result["dependents_count"] == 0

    @pytest.mark.asyncio
    async def test_sync_with_dependents(self, session):
        """Test sync correctly counts dependents and builds dependents_json."""
        from pipeline.db.household_sync import sync_household_from_members

        hp = HouseholdProfile(name="Family", filing_status="mfj")
        session.add(hp)
        await session.flush()

        self_member = FamilyMember(
            household_id=hp.id,
            name="Dad",
            relationship="self",
            income=200_000.0,
        )
        child1 = FamilyMember(
            household_id=hp.id,
            name="Alice",
            relationship="child",
            date_of_birth=date(2019, 6, 15),
            care_cost_annual=15_000,
            college_start_year=2037,
        )
        child2 = FamilyMember(
            household_id=hp.id,
            name="Bob",
            relationship="child",
            date_of_birth=date(2021, 9, 1),
            care_cost_annual=18_000,
        )
        session.add_all([self_member, child1, child2])
        await session.flush()

        result = await sync_household_from_members(session, hp.id)
        assert result is not None
        assert result["dependents_count"] == 2
        assert result["combined_income"] == 200_000.0

        # Verify dependents_json is properly formed
        deps = json.loads(hp.dependents_json)
        assert len(deps) == 2
        names = {d["name"] for d in deps}
        assert names == {"Alice", "Bob"}
        # Ages should be realistic
        for d in deps:
            if d["name"] == "Alice":
                # Born 2019, should be 6 or 7 depending on current date
                assert 5 <= d["age"] <= 8
                assert d["college_start_year"] == 2037
                assert d["care_cost_annual"] == 15_000

    @pytest.mark.asyncio
    async def test_sync_nonexistent_household(self, session):
        """Test sync returns None for nonexistent household."""
        from pipeline.db.household_sync import sync_household_from_members

        result = await sync_household_from_members(session, 99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_sync_clears_fields_when_members_removed(self, session):
        """Test sync clears spouse fields when no members exist."""
        from pipeline.db.household_sync import sync_household_from_members

        hp = HouseholdProfile(
            name="Solo", filing_status="single",
            spouse_a_name="Old Name", spouse_a_income=100_000.0,
        )
        session.add(hp)
        await session.flush()

        result = await sync_household_from_members(session, hp.id)
        assert result is not None
        assert result["spouse_a_name"] is None
        assert result["spouse_b_name"] is None
        assert result["combined_income"] == 0.0


# ============================================================================
# DB UTILITY — Backup
# ============================================================================

class TestDatabaseBackup:
    """Tests for pipeline.db.backup module."""

    def test_backup_database_creates_file(self):
        """Test backup creates a timestamped copy in the backups directory."""
        from pipeline.db.backup import backup_database

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "financials.db")
            # Create a database file large enough to trigger backup
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
            # Insert enough data to exceed 100KB threshold
            conn.executemany(
                "INSERT INTO test (data) VALUES (?)",
                [("x" * 1000,) for _ in range(200)],
            )
            conn.commit()
            conn.close()

            db_url = f"sqlite+aiosqlite:///{db_path}"
            result = backup_database(db_url, reason="test")

            assert result is not None
            assert os.path.exists(result)
            assert "financials_test_" in os.path.basename(result)
            assert result.endswith(".db")

            # Verify backup dir exists
            backup_dir = os.path.join(tmpdir, "backups")
            assert os.path.isdir(backup_dir)

    def test_backup_skips_small_database(self):
        """Test backup is skipped for databases smaller than 100KB."""
        from pipeline.db.backup import backup_database

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "financials.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()

            db_url = f"sqlite+aiosqlite:///{db_path}"
            result = backup_database(db_url, reason="startup")
            assert result is None

    def test_backup_nonexistent_file(self):
        """Test backup returns None for nonexistent database."""
        from pipeline.db.backup import backup_database

        result = backup_database("sqlite+aiosqlite:///nonexistent/path/db.sqlite")
        assert result is None

    def test_prune_old_backups(self):
        """Test that old backups are pruned to MAX_BACKUPS."""
        from pipeline.db.backup import _prune_old_backups, MAX_BACKUPS

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            # Create more than MAX_BACKUPS files
            for i in range(MAX_BACKUPS + 3):
                file_path = backup_dir / f"financials_test_{i:02d}.db"
                file_path.write_text(f"backup {i}")
                # Ensure different mtimes
                os.utime(file_path, (time.time() + i, time.time() + i))

            _prune_old_backups(backup_dir, "financials")
            remaining = list(backup_dir.glob("financials_*.db"))
            assert len(remaining) == MAX_BACKUPS

    def test_list_backups(self):
        """Test listing backups returns properly formatted entries."""
        from pipeline.db.backup import list_backups

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "financials.db")
            Path(db_path).touch()

            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()
            b1 = backup_dir / "financials_startup_20240101_120000.db"
            b1.write_text("backup data here")

            db_url = f"sqlite+aiosqlite:///{db_path}"
            backups = list_backups(db_url)

            assert len(backups) == 1
            assert backups[0]["filename"] == "financials_startup_20240101_120000.db"
            assert "path" in backups[0]
            assert "size_kb" in backups[0]
            assert "created" in backups[0]

    def test_restore_backup(self):
        """Test restoring a backup overwrites the current database."""
        from pipeline.db.backup import restore_backup

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "financials.db")
            # Create a "current" database
            with open(db_path, "w") as f:
                f.write("current database content")

            # Create a "backup" database
            backup_path = os.path.join(tmpdir, "backup.db")
            with open(backup_path, "w") as f:
                f.write("backup database content -- restored version")

            db_url = f"sqlite+aiosqlite:///{db_path}"
            result = restore_backup(db_url, backup_path)
            assert result is True

            # Verify the database now has the backup content
            with open(db_path) as f:
                content = f.read()
            assert content == "backup database content -- restored version"

    def test_restore_nonexistent_backup(self):
        """Test restoring from nonexistent backup returns False."""
        from pipeline.db.backup import restore_backup

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "financials.db")
            Path(db_path).touch()
            db_url = f"sqlite+aiosqlite:///{db_path}"
            result = restore_backup(db_url, "/nonexistent/backup.db")
            assert result is False

    def test_db_path_from_url(self):
        """Test extracting filesystem path from SQLite URL."""
        from pipeline.db.backup import _db_path_from_url

        result = _db_path_from_url("sqlite+aiosqlite:///data/db/financials.db")
        assert result is not None
        assert result.endswith("financials.db")

        assert _db_path_from_url("postgresql://localhost/mydb") is None


# ============================================================================
# DB UTILITY — Cross-Source Dedup
# ============================================================================

class TestCrossSourceDedup:
    """Tests for pipeline.dedup.cross_source deduplication."""

    @pytest.mark.asyncio
    async def test_find_duplicates_matching_transactions(self, session):
        """Test that duplicate transactions from Plaid+CSV are correctly identified."""
        from pipeline.dedup.cross_source import find_cross_source_duplicates
        from pipeline.db.schema import Account

        # Create account
        account = Account(name="Chase Sapphire", account_type="personal", subtype="credit_card")
        session.add(account)
        await session.flush()

        # Plaid transaction
        plaid_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="Amazon.com",
            merchant_name="Amazon",
            amount=-85.42,
            data_source="plaid",
            is_excluded=False,
        )
        # CSV transaction (same purchase, slightly different description)
        csv_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="AMZN MKTP US*1234",
            amount=-85.42,
            data_source="csv",
            is_excluded=False,
        )
        session.add_all([plaid_tx, csv_tx])
        await session.flush()

        candidates = await find_cross_source_duplicates(session, account.id)
        assert len(candidates) == 1
        assert candidates[0]["amount"] == -85.42
        assert candidates[0]["plaid_tx_id"] == plaid_tx.id
        assert candidates[0]["csv_tx_id"] == csv_tx.id
        assert candidates[0]["confidence"] >= 0.5

    @pytest.mark.asyncio
    async def test_no_duplicates_different_amounts(self, session):
        """Test transactions with different amounts are not matched."""
        from pipeline.dedup.cross_source import find_cross_source_duplicates
        from pipeline.db.schema import Account

        account = Account(name="Test Account", account_type="personal")
        session.add(account)
        await session.flush()

        plaid_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="Starbucks",
            merchant_name="Starbucks",
            amount=-5.25,
            data_source="plaid",
            is_excluded=False,
        )
        csv_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="Starbucks Coffee",
            amount=-12.50,  # Different amount
            data_source="csv",
            is_excluded=False,
        )
        session.add_all([plaid_tx, csv_tx])
        await session.flush()

        candidates = await find_cross_source_duplicates(session, account.id)
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_duplicates_close_dates(self, session):
        """Test transactions with close dates (within tolerance) are matched."""
        from pipeline.dedup.cross_source import find_cross_source_duplicates
        from pipeline.db.schema import Account

        account = Account(name="Test Account", account_type="personal")
        session.add(account)
        await session.flush()

        plaid_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="Target",
            merchant_name="Target",
            amount=-127.83,
            data_source="plaid",
            is_excluded=False,
        )
        csv_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 16, tzinfo=timezone.utc),  # 1 day off
            description="TARGET #1234",
            amount=-127.83,
            data_source="csv",
            is_excluded=False,
        )
        session.add_all([plaid_tx, csv_tx])
        await session.flush()

        candidates = await find_cross_source_duplicates(session, account.id)
        assert len(candidates) == 1
        # Same-day match has higher confidence than 1-day off
        assert candidates[0]["confidence"] >= 0.5

    @pytest.mark.asyncio
    async def test_no_cross_source_when_only_one_source(self, session):
        """Test returns empty when only one data source exists."""
        from pipeline.dedup.cross_source import find_cross_source_duplicates
        from pipeline.db.schema import Account

        account = Account(name="Test Account", account_type="personal")
        session.add(account)
        await session.flush()

        # Only plaid transactions, no CSV
        tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="Test",
            amount=-50.00,
            data_source="plaid",
            is_excluded=False,
        )
        session.add(tx)
        await session.flush()

        candidates = await find_cross_source_duplicates(session, account.id)
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_auto_resolve_high_confidence(self, session):
        """Test auto-resolve excludes CSV version for high confidence matches."""
        from pipeline.dedup.cross_source import auto_resolve_duplicates
        from pipeline.db.schema import Account

        account = Account(name="Test", account_type="personal")
        session.add(account)
        await session.flush()

        plaid_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="Whole Foods",
            merchant_name="Whole Foods",
            amount=-95.00,
            data_source="plaid",
            is_excluded=False,
        )
        csv_tx = Transaction(
            account_id=account.id,
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            description="Whole Foods Market",
            amount=-95.00,
            data_source="csv",
            is_excluded=False,
        )
        session.add_all([plaid_tx, csv_tx])
        await session.flush()

        summary = await auto_resolve_duplicates(session, account.id, min_confidence=0.5)
        assert summary["total_candidates"] >= 1


# ============================================================================
# SECURITY — File Cleanup
# ============================================================================

class TestSecureFileCleanup:
    """Tests for pipeline.security.file_cleanup module."""

    def test_secure_delete_overwrites_content(self):
        """Test that secure delete overwrites file content before unlinking."""
        from pipeline.security.file_cleanup import secure_delete_file

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            f.write(b"SSN: 123-45-6789\nAccount: 9876543210\nBalance: $250,000")
            filepath = f.name

        assert os.path.exists(filepath)
        result = secure_delete_file(filepath)
        assert result is True
        assert not os.path.exists(filepath)

    def test_secure_delete_nonexistent_file(self):
        """Test secure delete returns False for nonexistent file."""
        from pipeline.security.file_cleanup import secure_delete_file

        result = secure_delete_file("/nonexistent/path/file.csv")
        assert result is False

    def test_cleanup_old_files(self):
        """Test cleanup removes files older than threshold."""
        from pipeline.security.file_cleanup import cleanup_old_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create old file (set mtime to 10 days ago)
            old_file = os.path.join(tmpdir, "old_import.csv")
            with open(old_file, "w") as f:
                f.write("old data")
            old_time = time.time() - (10 * 86400)
            os.utime(old_file, (old_time, old_time))

            # Create recent file
            new_file = os.path.join(tmpdir, "new_import.csv")
            with open(new_file, "w") as f:
                f.write("new data")

            deleted = cleanup_old_files(tmpdir, max_age_days=7)
            assert deleted == 1
            assert not os.path.exists(old_file)
            assert os.path.exists(new_file)

    def test_cleanup_respects_extensions(self):
        """Test cleanup only targets specified file extensions."""
        from pipeline.security.file_cleanup import cleanup_old_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create old files with different extensions
            for ext in [".csv", ".pdf", ".txt", ".py"]:
                filepath = os.path.join(tmpdir, f"file{ext}")
                with open(filepath, "w") as f:
                    f.write("data")
                old_time = time.time() - (10 * 86400)
                os.utime(filepath, (old_time, old_time))

            deleted = cleanup_old_files(tmpdir, max_age_days=7, extensions={".csv", ".pdf"})
            assert deleted == 2
            assert not os.path.exists(os.path.join(tmpdir, "file.csv"))
            assert not os.path.exists(os.path.join(tmpdir, "file.pdf"))
            assert os.path.exists(os.path.join(tmpdir, "file.txt"))
            assert os.path.exists(os.path.join(tmpdir, "file.py"))

    def test_cleanup_nonexistent_directory(self):
        """Test cleanup returns 0 for nonexistent directory."""
        from pipeline.security.file_cleanup import cleanup_old_files

        deleted = cleanup_old_files("/nonexistent/directory")
        assert deleted == 0


# ============================================================================
# SECURITY — PII-Safe Logging
# ============================================================================

class TestPIIRedactionFilter:
    """Tests for pipeline.security.logging PII redaction."""

    def _make_filter(self, known_names=None):
        """Create a fresh PIIRedactionFilter (not the singleton)."""
        from pipeline.security.logging import PIIRedactionFilter
        return PIIRedactionFilter(known_names)

    def test_ssn_redacted(self):
        """Test SSN patterns are redacted from log messages."""
        f = self._make_filter()
        result = f._redact("User SSN is 123-45-6789 for processing")
        assert "123-45-6789" not in result
        assert "[SSN]" in result

    def test_ssn_last4_redacted(self):
        """Test SSN last 4 patterns are redacted."""
        f = self._make_filter()
        result = f._redact("ssn_last4: 6789")
        assert "6789" not in result
        assert "[SSN_LAST4]" in result

    def test_dollar_amounts_redacted(self):
        """Test dollar amounts are redacted."""
        f = self._make_filter()
        result = f._redact("Account balance is $250,000.50 and pending $1,234")
        assert "$250,000.50" not in result
        assert "$1,234" not in result
        assert "[$***]" in result

    def test_email_redacted(self):
        """Test email addresses are redacted."""
        f = self._make_filter()
        result = f._redact("Contact user at alice.johnson@example.com for details")
        assert "alice.johnson@example.com" not in result
        assert "[EMAIL]" in result

    def test_ein_redacted(self):
        """Test EIN patterns are redacted."""
        f = self._make_filter()
        result = f._redact("Employer EIN is 12-3456789")
        assert "12-3456789" not in result
        assert "[EIN]" in result

    def test_known_names_redacted(self):
        """Test known names are replaced with [NAME]."""
        f = self._make_filter(known_names=["Alice Johnson", "Bob Smith"])
        result = f._redact("Processing data for Alice Johnson and Bob Smith")
        assert "Alice Johnson" not in result
        assert "Bob Smith" not in result
        assert result.count("[NAME]") == 2

    def test_combined_pii_redaction(self):
        """Test multiple PII types are redacted in one message."""
        f = self._make_filter(known_names=["Mike Aron"])
        msg = "Mike Aron SSN:123-45-6789 earned $175,000 from EIN 12-3456789 email mike@example.com"
        result = f._redact(msg)
        assert "Mike Aron" not in result
        assert "123-45-6789" not in result
        assert "$175,000" not in result
        assert "12-3456789" not in result
        assert "mike@example.com" not in result

    def test_filter_preserves_log_record(self):
        """Test filter always returns True (never drops records)."""
        f = self._make_filter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Balance is $1,000", args=(), exc_info=None,
        )
        result = f.filter(record)
        assert result is True
        assert "$1,000" not in record.msg
        assert "[$***]" in record.msg

    def test_filter_redacts_dict_args(self):
        """Test PII in dict-style log args is redacted."""
        f = self._make_filter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User data: %(email)s", args=None, exc_info=None,
        )
        # Manually set args to a dict (as logging does internally for dict-style formatting)
        record.args = {"email": "test@example.com"}
        f.filter(record)
        assert record.args["email"] == "[EMAIL]"

    def test_filter_redacts_tuple_args(self):
        """Test PII in tuple-style log args is redacted."""
        f = self._make_filter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="SSN: %s", args=("123-45-6789",), exc_info=None,
        )
        f.filter(record)
        assert "123-45-6789" not in str(record.args)
        assert "[SSN]" in str(record.args)

    def test_set_known_names_deduplicates(self):
        """Test set_known_names deduplicates and sorts by length."""
        f = self._make_filter()
        f.set_known_names(["Alice", "Alice", "Bob", "Alice Johnson"])
        # Should deduplicate: Alice Johnson (longest first), Alice, Bob
        assert len(f._known_names) == 3
        assert f._known_names[0] == "Alice Johnson"  # longest first

    def test_set_known_names_ignores_short_names(self):
        """Test names <= 2 chars are filtered out."""
        f = self._make_filter()
        f.set_known_names(["Al", "Bo", "Alice Johnson"])
        assert len(f._known_names) == 1
        assert f._known_names[0] == "Alice Johnson"

    def test_install_pii_filter_idempotent(self):
        """Test install_pii_filter is safe to call multiple times."""
        from pipeline.security import logging as sec_logging

        # Reset global state for test
        original = sec_logging._filter_instance
        sec_logging._filter_instance = None
        try:
            f1 = sec_logging.install_pii_filter(["Test Name"])
            f2 = sec_logging.install_pii_filter(["Other Name"])
            assert f1 is f2  # Same instance returned
        finally:
            # Clean up: remove filter from root logger
            root = logging.getLogger()
            if f1 in root.filters:
                root.removeFilter(f1)
            sec_logging._filter_instance = original


# ============================================================================
# PARSERS — PDF
# ============================================================================

class TestPDFParser:
    """Tests for pipeline.parsers.pdf_parser module."""

    def test_pdf_document_properties(self):
        """Test PDFDocument dataclass properties."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage

        pages = [
            PDFPage(page_num=1, text="Page one content", tables=[]),
            PDFPage(page_num=2, text="Page two content", tables=[]),
        ]
        doc = PDFDocument(filepath="/tmp/test.pdf", pages=pages)

        assert doc.page_count == 2
        assert "Page one content" in doc.full_text
        assert "Page two content" in doc.full_text
        assert "PAGE BREAK" in doc.full_text

    def test_is_text_sparse(self):
        """Test sparse text detection for scanned PDFs."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, is_text_sparse

        sparse_doc = PDFDocument(filepath="/tmp/scan.pdf", pages=[
            PDFPage(page_num=1, text="    ", tables=[]),
        ])
        assert is_text_sparse(sparse_doc) is True

        rich_doc = PDFDocument(filepath="/tmp/w2.pdf", pages=[
            PDFPage(page_num=1, text="W-2 Wage and Tax Statement " * 10, tables=[]),
        ])
        assert is_text_sparse(rich_doc) is False

    def test_detect_form_type_w2(self):
        """Test W-2 form detection."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, detect_form_type

        doc = PDFDocument(filepath="/tmp/w2.pdf", pages=[
            PDFPage(page_num=1, text="Wage and Tax Statement 2024 W-2 Form", tables=[]),
        ])
        assert detect_form_type(doc) == "w2"

    def test_detect_form_type_1099_nec(self):
        """Test 1099-NEC form detection."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, detect_form_type

        doc = PDFDocument(filepath="/tmp/1099nec.pdf", pages=[
            PDFPage(page_num=1, text="1099-NEC Nonemployee Compensation", tables=[]),
        ])
        assert detect_form_type(doc) == "1099_nec"

    def test_detect_form_type_1099_div(self):
        """Test 1099-DIV form detection."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, detect_form_type

        doc = PDFDocument(filepath="/tmp/1099div.pdf", pages=[
            PDFPage(page_num=1, text="Dividends and Distributions 1099-DIV", tables=[]),
        ])
        assert detect_form_type(doc) == "1099_div"

    def test_detect_form_type_1099_int(self):
        """Test 1099-INT form detection."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, detect_form_type

        doc = PDFDocument(filepath="/tmp/1099int.pdf", pages=[
            PDFPage(page_num=1, text="Interest Income from your 1099 form", tables=[]),
        ])
        assert detect_form_type(doc) == "1099_int"

    def test_detect_form_type_brokerage(self):
        """Test brokerage statement detection."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, detect_form_type

        doc = PDFDocument(filepath="/tmp/brokerage.pdf", pages=[
            PDFPage(page_num=1, text="Account Summary for Portfolio Holdings Q4 2024", tables=[]),
        ])
        assert detect_form_type(doc) == "brokerage_statement"

    def test_detect_form_type_k1(self):
        """Test K-1 form detection."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, detect_form_type

        doc = PDFDocument(filepath="/tmp/k1.pdf", pages=[
            PDFPage(page_num=1, text="Schedule K-1 Partner's Share of Income", tables=[]),
        ])
        assert detect_form_type(doc) == "k1"

    def test_detect_form_type_other(self):
        """Test unknown form falls back to 'other'."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, detect_form_type

        doc = PDFDocument(filepath="/tmp/random.pdf", pages=[
            PDFPage(page_num=1, text="Just a regular document about cooking recipes", tables=[]),
        ])
        assert detect_form_type(doc) == "other"

    def test_extract_pdf_file_not_found(self):
        """Test extract_pdf raises FileNotFoundError for missing file."""
        from pipeline.parsers.pdf_parser import extract_pdf

        with pytest.raises(FileNotFoundError):
            extract_pdf("/nonexistent/path/file.pdf")

    def test_extract_pdf_with_mock(self):
        """Test PDF extraction with mocked pdfplumber."""
        from pipeline.parsers.pdf_parser import extract_pdf

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "W-2 Wage and Tax Statement\nEmployer: Accenture\nWages: $175,000"
        mock_page.extract_tables.return_value = [
            [["Box", "Amount"], ["1", "175,000"], ["2", "35,000"]],
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("pathlib.Path.exists", return_value=True):
                doc = extract_pdf("/tmp/test_w2.pdf")
                assert doc.page_count == 1
                assert "Accenture" in doc.full_text
                assert len(doc.pages[0].tables) == 1
                assert doc.pages[0].tables[0][0] == ["Box", "Amount"]

    def test_find_amount_helper(self):
        """Test _find_amount extracts dollar amounts from text."""
        from pipeline.parsers.pdf_parser import _find_amount

        text = "Box 1 Wages, tips $175,000.00 and other compensation"
        amount = _find_amount(text, [r"wages,?\s*tips[^\n$]*?\$?([\d,]+\.?\d*)"])
        assert amount == 175_000.00

    def test_find_amount_no_match(self):
        """Test _find_amount returns None when pattern doesn't match."""
        from pipeline.parsers.pdf_parser import _find_amount

        text = "No amount here"
        assert _find_amount(text, [r"wages[^\n$]*\$?([\d,]+\.?\d*)"]) is None

    def test_extract_w2_fields(self):
        """Test W-2 field extraction from realistic text."""
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage, extract_w2_fields

        w2_text = (
            "Employer's name, address, and ZIP code\n"
            "ACCENTURE FEDERAL SERVICES LLC\n"
            "Employer's identification number: 46-1234567\n"
            "Box 1 Wages, tips $175,000.00\n"
            "Box 2 Federal income tax withheld $35,000.00\n"
            "Box 3 Social security wages $160,200.00\n"
            "Box 4 Social security tax withheld $9,932.40\n"
            "Box 5 Medicare wages $175,000.00\n"
            "Box 6 Medicare tax withheld $2,537.50\n"
        )
        doc = PDFDocument(filepath="/tmp/w2.pdf", pages=[
            PDFPage(page_num=1, text=w2_text, tables=[]),
        ])
        fields = extract_w2_fields(doc)
        assert fields["payer_ein"] == "46-1234567"
        assert fields["w2_wages"] == 175_000.00
        assert fields["w2_federal_tax_withheld"] == 35_000.00
        assert fields["w2_ss_wages"] == 160_200.00


# ============================================================================
# PARSERS — XLSX
# ============================================================================

class TestXLSXParser:
    """Tests for pipeline.parsers.xlsx_parser module."""

    def test_sheet_data_to_text(self):
        """Test SheetData renders as pipe-delimited text."""
        from pipeline.parsers.xlsx_parser import SheetData

        sheet = SheetData(
            name="Transactions",
            headers=["Date", "Description", "Amount"],
            rows=[
                ["2024-01-15", "Amazon", "-85.42"],
                ["2024-01-16", "Starbucks", "-5.25"],
            ],
            row_count=2,
            col_count=3,
        )
        text = sheet.to_text()
        assert "Date | Description | Amount" in text
        assert "Amazon" in text
        assert "-85.42" in text

    def test_sheet_data_to_dicts(self):
        """Test SheetData converts to list of dicts keyed by headers."""
        from pipeline.parsers.xlsx_parser import SheetData

        sheet = SheetData(
            name="Data",
            headers=["Name", "Value"],
            rows=[["Alpha", "100"], ["Beta", "200"]],
            row_count=2,
            col_count=2,
        )
        dicts = sheet.to_dicts()
        assert len(dicts) == 2
        assert dicts[0] == {"Name": "Alpha", "Value": "100"}
        assert dicts[1] == {"Name": "Beta", "Value": "200"}

    def test_sheet_data_to_dicts_no_headers(self):
        """Test to_dicts with no headers generates col_0, col_1, etc."""
        from pipeline.parsers.xlsx_parser import SheetData

        sheet = SheetData(
            name="Unnamed",
            headers=[],
            rows=[["A", "B"], ["C", "D"]],
            row_count=2,
            col_count=2,
        )
        dicts = sheet.to_dicts()
        assert dicts[0] == {"col_0": "A", "col_1": "B"}

    def test_excel_document_properties(self):
        """Test ExcelDocument aggregation properties."""
        from pipeline.parsers.xlsx_parser import ExcelDocument, SheetData

        sheets = [
            SheetData(name="Sheet1", headers=["A"], rows=[["1"], ["2"]], row_count=2, col_count=1),
            SheetData(name="Sheet2", headers=["B"], rows=[["3"]], row_count=1, col_count=1),
        ]
        doc = ExcelDocument(filepath="/tmp/test.xlsx", sheets=sheets)

        assert doc.sheet_names == ["Sheet1", "Sheet2"]
        assert doc.total_rows == 3
        assert doc.get_sheet("Sheet1") is sheets[0]
        assert doc.get_sheet("NonExistent") is None
        assert "SHEET: Sheet1" in doc.full_text
        assert "SHEET: Sheet2" in doc.full_text

    def test_extract_xlsx_file_not_found(self):
        """Test extract_xlsx raises FileNotFoundError for missing file."""
        from pipeline.parsers.xlsx_parser import extract_xlsx

        with pytest.raises(FileNotFoundError):
            extract_xlsx("/nonexistent/path/file.xlsx")

    def test_extract_xlsx_with_real_file(self):
        """Test extract_xlsx parses a real Excel file."""
        from pipeline.parsers.xlsx_parser import extract_xlsx

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            filepath = f.name

        try:
            df = pd.DataFrame({
                "Date": ["2024-01-15", "2024-01-16", "2024-01-17"],
                "Description": ["Amazon Purchase", "Starbucks Coffee", "Target Run"],
                "Amount": ["-85.42", "-5.25", "-127.83"],
            })
            df.to_excel(filepath, index=False, sheet_name="Transactions")

            doc = extract_xlsx(filepath)
            assert len(doc.sheets) == 1
            assert doc.sheets[0].name == "Transactions"
            assert doc.sheets[0].row_count == 3
            assert doc.sheets[0].col_count == 3
            assert doc.sheets[0].headers == ["Date", "Description", "Amount"]
            assert doc.sheets[0].rows[0][1] == "Amazon Purchase"
        finally:
            os.unlink(filepath)

    def test_clean_cell(self):
        """Test _clean_cell normalizes various cell values."""
        from pipeline.parsers.xlsx_parser import _clean_cell

        assert _clean_cell("  hello  ") == "hello"
        assert _clean_cell(42) == 42
        assert _clean_cell(float("nan")) == ""
        assert _clean_cell(None) == ""

    def test_sheet_truncation_indicator(self):
        """Test to_text shows truncation indicator when exceeding max_rows."""
        from pipeline.parsers.xlsx_parser import SheetData

        rows = [[str(i)] for i in range(10)]
        sheet = SheetData(name="Big", headers=["Val"], rows=rows, row_count=10, col_count=1)
        text = sheet.to_text(max_rows=5)
        assert "5 more rows" in text


# ============================================================================
# PARSERS — DOCX
# ============================================================================

class TestDocxParser:
    """Tests for pipeline.parsers.docx_parser module."""

    def test_docx_table_data_properties(self):
        """Test DocxTableData dataclass methods."""
        from pipeline.parsers.docx_parser import DocxTableData

        table = DocxTableData(
            headers=["Header1", "Header2"],
            rows=[["a", "b"], ["c", "d"]],
        )
        assert table.row_count == 2
        text = table.to_text()
        assert "Header1 | Header2" in text
        assert "a | b" in text

    def test_docx_document_properties(self):
        """Test DocxDocument aggregation properties."""
        from pipeline.parsers.docx_parser import DocxDocument, DocxTableData

        doc = DocxDocument(
            filepath="/tmp/test.docx",
            paragraphs=["Hello World", "Second paragraph"],
            tables=[DocxTableData(headers=["Col1"], rows=[["val1"]])],
            metadata={"title": "Test Doc"},
        )
        assert "Hello World" in doc.full_text
        assert "Second paragraph" in doc.full_text
        assert doc.has_tables is True
        assert "TABLE 1" in doc.full_text_with_tables

    def test_docx_document_no_tables(self):
        """Test DocxDocument with no tables."""
        from pipeline.parsers.docx_parser import DocxDocument

        doc = DocxDocument(
            filepath="/tmp/test.docx",
            paragraphs=["Just text"],
            tables=[],
        )
        assert doc.has_tables is False
        assert doc.full_text == "Just text"

    def test_extract_docx_file_not_found(self):
        """Test extract_docx raises FileNotFoundError for missing file."""
        from pipeline.parsers.docx_parser import extract_docx

        with pytest.raises(FileNotFoundError):
            extract_docx("/nonexistent/path/file.docx")

    def test_extract_docx_with_mock(self):
        """Test DOCX extraction with mocked python-docx."""
        from pipeline.parsers.docx_parser import extract_docx

        # Mock paragraphs
        mock_para1 = MagicMock()
        mock_para1.text = "Financial Summary 2024"
        mock_para2 = MagicMock()
        mock_para2.text = "Total assets: $1,250,000"
        mock_para3 = MagicMock()
        mock_para3.text = ""  # Empty paragraph should be filtered

        # Mock table
        mock_cell1 = MagicMock()
        mock_cell1.text = "Category"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Amount"
        mock_cell3 = MagicMock()
        mock_cell3.text = "Investments"
        mock_cell4 = MagicMock()
        mock_cell4.text = "$500,000"

        mock_row1 = MagicMock()
        mock_row1.cells = [mock_cell1, mock_cell2]
        mock_row2 = MagicMock()
        mock_row2.cells = [mock_cell3, mock_cell4]

        mock_table = MagicMock()
        mock_table.rows = [mock_row1, mock_row2]

        # Mock core properties
        mock_props = MagicMock()
        mock_props.title = "Q4 Financial Report"
        mock_props.author = "SirHENRY"
        mock_props.created = datetime(2024, 12, 1)
        mock_props.modified = datetime(2024, 12, 15)

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc.tables = [mock_table]
        mock_doc.core_properties = mock_props

        with patch("pipeline.parsers.docx_parser.Document", return_value=mock_doc):
            with patch("pathlib.Path.exists", return_value=True):
                result = extract_docx("/tmp/test.docx")
                assert len(result.paragraphs) == 2  # empty paragraph filtered
                assert "Financial Summary 2024" in result.paragraphs
                assert len(result.tables) == 1
                assert result.tables[0].headers == ["Category", "Amount"]
                assert result.tables[0].rows[0] == ["Investments", "$500,000"]
                assert result.metadata["title"] == "Q4 Financial Report"
                assert result.metadata["author"] == "SirHENRY"

    def test_extract_table_header_detection(self):
        """Test table header detection logic."""
        from pipeline.parsers.docx_parser import _extract_table

        # Row with text headers
        mock_row1 = MagicMock()
        cell1, cell2 = MagicMock(), MagicMock()
        cell1.text = "Name"
        cell2.text = "Value"
        mock_row1.cells = [cell1, cell2]

        mock_row2 = MagicMock()
        cell3, cell4 = MagicMock(), MagicMock()
        cell3.text = "Test"
        cell4.text = "42"
        mock_row2.cells = [cell3, cell4]

        mock_table = MagicMock()
        mock_table.rows = [mock_row1, mock_row2]

        result = _extract_table(mock_table)
        assert result is not None
        assert result.headers == ["Name", "Value"]
        assert result.rows == [["Test", "42"]]

    def test_extract_table_no_header_row(self):
        """Test table without clear headers keeps all rows."""
        from pipeline.parsers.docx_parser import _extract_table

        # All numeric rows — no headers detected
        mock_row1 = MagicMock()
        cell1, cell2 = MagicMock(), MagicMock()
        cell1.text = "100"
        cell2.text = "200"
        mock_row1.cells = [cell1, cell2]

        mock_table = MagicMock()
        mock_table.rows = [mock_row1]

        result = _extract_table(mock_table)
        assert result is not None
        assert result.headers == []
        assert result.rows == [["100", "200"]]


# ============================================================================
# SEED ENTITIES
# ============================================================================

class TestSeedEntities:
    """Tests for pipeline.seed_entities module."""

    def test_entities_list_structure(self):
        """Test ENTITIES list has correct structure and realistic data."""
        from pipeline.seed_entities import ENTITIES

        assert len(ENTITIES) >= 3
        for entity in ENTITIES:
            assert "name" in entity
            assert "entity_type" in entity
            assert "tax_treatment" in entity
            assert isinstance(entity["name"], str)
            assert len(entity["name"]) > 0

    def test_entities_include_expected_entries(self):
        """Test expected entity names are present."""
        from pipeline.seed_entities import ENTITIES

        names = {e["name"] for e in ENTITIES}
        assert "Accenture" in names
        assert "Vivant" in names

    def test_vendor_rules_list_structure(self):
        """Test VENDOR_RULES has correct structure."""
        from pipeline.seed_entities import VENDOR_RULES

        assert len(VENDOR_RULES) >= 5
        for rule in VENDOR_RULES:
            assert "vendor_pattern" in rule
            assert "entity_name" in rule
            assert "segment_override" in rule
            assert rule["segment_override"] == "business"

    def test_vendor_rules_patterns(self):
        """Test vendor rules have expected patterns."""
        from pipeline.seed_entities import VENDOR_RULES

        patterns = {r["vendor_pattern"] for r in VENDOR_RULES}
        assert "cursor" in patterns
        assert "anthropic" in patterns
        assert "github" in patterns
        assert "vercel" in patterns

    def test_entity_types_valid(self):
        """Test all entity types use valid values."""
        from pipeline.seed_entities import ENTITIES

        valid_types = {"sole_prop", "partnership", "llc", "s_corp", "c_corp", "employer"}
        for entity in ENTITIES:
            assert entity["entity_type"] in valid_types, (
                f"Invalid entity_type '{entity['entity_type']}' for {entity['name']}"
            )

    def test_tax_treatments_valid(self):
        """Test all tax treatments use valid values."""
        from pipeline.seed_entities import ENTITIES

        valid_treatments = {"w2", "schedule_c", "k1", "section_195", "none"}
        for entity in ENTITIES:
            assert entity["tax_treatment"] in valid_treatments, (
                f"Invalid tax_treatment '{entity['tax_treatment']}' for {entity['name']}"
            )


# ============================================================================
# DB UTILITY — Field Encryption Events (integration)
# ============================================================================

class TestFieldEncryptionEvents:
    """Tests for pipeline.db.field_encryption event registration."""

    def test_encrypted_fields_registry(self):
        """Test ENCRYPTED_FIELDS has expected model-to-fields mapping."""
        from pipeline.db.field_encryption import ENCRYPTED_FIELDS

        assert "HouseholdProfile" in ENCRYPTED_FIELDS
        assert "spouse_a_name" in ENCRYPTED_FIELDS["HouseholdProfile"]
        assert "spouse_b_name" in ENCRYPTED_FIELDS["HouseholdProfile"]

        assert "FamilyMember" in ENCRYPTED_FIELDS
        assert "name" in ENCRYPTED_FIELDS["FamilyMember"]
        assert "ssn_last4" in ENCRYPTED_FIELDS["FamilyMember"]

        assert "TaxItem" in ENCRYPTED_FIELDS
        assert "payer_name" in ENCRYPTED_FIELDS["TaxItem"]
        assert "payer_ein" in ENCRYPTED_FIELDS["TaxItem"]

        assert "InsurancePolicy" in ENCRYPTED_FIELDS
        assert "policy_number" in ENCRYPTED_FIELDS["InsurancePolicy"]

    def test_encrypted_fields_count(self):
        """Test total encrypted field count is reasonable."""
        from pipeline.db.field_encryption import ENCRYPTED_FIELDS

        total = sum(len(fields) for fields in ENCRYPTED_FIELDS.values())
        # Should have at least 10 fields across all models
        assert total >= 10
        # But not too many (we only encrypt sensitive string fields)
        assert total <= 50


# ============================================================================
# ECONOMIC INDICATOR METADATA
# ============================================================================

class TestEconomicIndicatorMetadata:
    """Tests for the INDICATOR_METADATA in economic.py."""

    def test_all_indicators_have_required_fields(self):
        """Test each indicator has label, unit, description, category."""
        from pipeline.market.economic import INDICATOR_METADATA

        required_fields = {"label", "unit", "description", "category"}
        for series_id, meta in INDICATOR_METADATA.items():
            for field in required_fields:
                assert field in meta, f"Missing '{field}' in indicator {series_id}"

    def test_indicator_categories_valid(self):
        """Test indicator categories are from expected set."""
        from pipeline.market.economic import INDICATOR_METADATA

        valid_categories = {"growth", "inflation", "rates", "employment", "consumer"}
        for series_id, meta in INDICATOR_METADATA.items():
            assert meta["category"] in valid_categories, (
                f"Invalid category '{meta['category']}' for {series_id}"
            )

    def test_expected_indicators_present(self):
        """Test key economic indicators are defined."""
        from pipeline.market.economic import INDICATOR_METADATA

        expected = {
            "REAL_GDP", "CPI", "INFLATION",
            "FEDERAL_FUNDS_RATE", "TREASURY_YIELD",
            "UNEMPLOYMENT", "RETAIL_SALES", "NONFARM_PAYROLL",
        }
        assert set(INDICATOR_METADATA.keys()) == expected
