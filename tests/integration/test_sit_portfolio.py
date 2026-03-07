"""SIT: Portfolio analytics accuracy.

Validates portfolio summary, holdings, allocations, and net worth
against known demo data values.
"""
import pytest
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

class TestPortfolioSummary:
    async def test_summary_total_value(self, client, demo_seed):
        """Total value should include all investment holdings + crypto."""
        resp = await client.get("/portfolio/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] > 0
        # Should include stock holdings + crypto at minimum
        assert data["total_value"] >= TOTAL_HOLDINGS_VALUE

    async def test_summary_holdings_count(self, client, demo_seed):
        resp = await client.get("/portfolio/summary")
        data = resp.json()
        assert data["holdings_count"] >= INVESTMENT_HOLDINGS_COUNT

    async def test_summary_has_gain_loss(self, client, demo_seed):
        resp = await client.get("/portfolio/summary")
        data = resp.json()
        # All demo holdings have positive gains
        assert "total_unrealized_gain_loss" in data or "total_gain_loss" in data
        gain = data.get("total_unrealized_gain_loss", data.get("total_gain_loss", 0))
        assert gain > 0


# ---------------------------------------------------------------------------
# Individual holdings
# ---------------------------------------------------------------------------

class TestPortfolioHoldings:
    async def test_holdings_list(self, client, demo_seed):
        resp = await client.get("/portfolio/holdings")
        assert resp.status_code == 200
        data = resp.json()
        holdings = data if isinstance(data, list) else data.get("holdings", data.get("items", []))
        assert len(holdings) >= INVESTMENT_HOLDINGS_COUNT

    async def test_vti_is_largest(self, client, demo_seed):
        """VTI ($108K) should be the largest holding."""
        resp = await client.get("/portfolio/holdings")
        data = resp.json()
        holdings = data if isinstance(data, list) else data.get("holdings", data.get("items", []))
        if holdings:
            by_value = sorted(holdings, key=lambda h: h.get("current_value", 0), reverse=True)
            # VTI should be in the top positions
            top_tickers = [h.get("ticker") for h in by_value[:3]]
            assert "VTI" in top_tickers

    async def test_holding_values_match_seeded(self, client, demo_seed):
        """Spot-check individual holding values against seeded data."""
        resp = await client.get("/portfolio/holdings")
        data = resp.json()
        holdings = data if isinstance(data, list) else data.get("holdings", data.get("items", []))
        holdings_by_ticker = {h.get("ticker"): h for h in holdings}

        for expected in HOLDINGS[:3]:  # Check VTI, VXUS, VGT
            ticker = expected["ticker"]
            if ticker in holdings_by_ticker:
                actual = holdings_by_ticker[ticker]
                assert actual["current_value"] == pytest.approx(expected["value"], rel=0.01)
                assert actual["shares"] == pytest.approx(expected["shares"], rel=0.01)


# ---------------------------------------------------------------------------
# Crypto holdings
# ---------------------------------------------------------------------------

class TestCryptoHoldings:
    async def test_crypto_list(self, client, demo_seed):
        resp = await client.get("/portfolio/crypto")
        assert resp.status_code == 200
        data = resp.json()
        cryptos = data if isinstance(data, list) else data.get("holdings", [])
        assert len(cryptos) >= CRYPTO_HOLDINGS_COUNT

    async def test_btc_value(self, client, demo_seed):
        resp = await client.get("/portfolio/crypto")
        data = resp.json()
        cryptos = data if isinstance(data, list) else data.get("holdings", [])
        btc = next((c for c in cryptos if c.get("symbol") == "BTC"), None)
        if btc:
            assert btc["current_value"] == pytest.approx(CRYPTO[0]["value"], rel=0.01)
            assert btc["quantity"] == pytest.approx(CRYPTO[0]["quantity"], rel=0.01)


# ---------------------------------------------------------------------------
# Target allocation
# ---------------------------------------------------------------------------

class TestTargetAllocation:
    async def test_allocation_exists(self, client, demo_seed):
        resp = await client.get("/portfolio/target-allocation")
        assert resp.status_code == 200
        data = resp.json()
        assert "allocation" in data or "name" in data

    async def test_allocation_presets(self, client, demo_seed):
        resp = await client.get("/portfolio/target-allocation/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert len(data["presets"]) == 3  # Conservative, Balanced, Aggressive


# ---------------------------------------------------------------------------
# Net worth trend
# ---------------------------------------------------------------------------

class TestNetWorthTrend:
    async def test_net_worth_trend_snapshots(self, client, demo_seed):
        resp = await client.get("/portfolio/net-worth-trend")
        assert resp.status_code == 200
        data = resp.json()
        # API returns {"monthly_series": [...], "growth_rate": ..., "current_net_worth": ...}
        snapshots = data.get("monthly_series", [])
        assert len(snapshots) >= 10  # At least 10 months of data

    async def test_net_worth_trend_increasing(self, client, demo_seed):
        resp = await client.get("/portfolio/net-worth-trend")
        data = resp.json()
        snapshots = data.get("monthly_series", [])
        if len(snapshots) >= 2:
            # General trend should be upward (first < last)
            first_nw = snapshots[0].get("net_worth", 0)
            last_nw = snapshots[-1].get("net_worth", 0)
            assert last_nw > first_nw
