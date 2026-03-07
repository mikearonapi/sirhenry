"""Tests for pipeline/planning/portfolio_summary.py — portfolio aggregation."""
import pytest

from pipeline.planning.portfolio_summary import build_portfolio_summary, SUBTYPE_TO_CLASS


class _MockHolding:
    """Minimal mock for InvestmentHolding ORM object."""
    def __init__(self, ticker="AAPL", name="Apple", asset_class="stock",
                 current_value=10000, total_cost_basis=8000,
                 unrealized_gain_loss_pct=25.0, sector="Technology"):
        self.ticker = ticker
        self.name = name
        self.asset_class = asset_class
        self.current_value = current_value
        self.total_cost_basis = total_cost_basis
        self.unrealized_gain_loss_pct = unrealized_gain_loss_pct
        self.sector = sector


class _MockCrypto:
    """Minimal mock for CryptoHolding ORM object."""
    def __init__(self, symbol="BTC", name="Bitcoin", current_value=5000,
                 total_cost_basis=3000):
        self.symbol = symbol
        self.name = name
        self.current_value = current_value
        self.total_cost_basis = total_cost_basis


class _MockManualAsset:
    """Minimal mock for ManualAsset ORM object."""
    def __init__(self, name="401k Vanguard", account_subtype="401k",
                 current_value=50000, purchase_price=40000,
                 annual_return_pct=7.5):
        self.name = name
        self.account_subtype = account_subtype
        self.current_value = current_value
        self.purchase_price = purchase_price
        self.annual_return_pct = annual_return_pct


class TestEmptyPortfolio:
    def test_all_empty(self):
        result = build_portfolio_summary([], [], [])
        assert result["total_value"] == 0
        assert result["total_cost_basis"] == 0
        assert result["total_gain_loss"] == 0
        assert result["holdings_count"] == 0
        assert result["accounts_count"] == 0
        assert result["top_holdings"] == []


class TestSingleHolding:
    def test_single_stock(self):
        h = _MockHolding(current_value=10000, total_cost_basis=8000)
        result = build_portfolio_summary([h], [], [])
        assert result["total_value"] == 10000
        assert result["stock_value"] == 10000
        assert result["total_gain_loss"] == 2000
        assert result["total_gain_loss_pct"] == 25.0
        assert result["holdings_count"] == 1

    def test_single_crypto(self):
        c = _MockCrypto(current_value=5000, total_cost_basis=3000)
        result = build_portfolio_summary([], [c], [])
        assert result["crypto_value"] == 5000
        assert result["total_gain_loss"] == 2000

    def test_single_manual(self):
        a = _MockManualAsset(current_value=50000, purchase_price=40000)
        result = build_portfolio_summary([], [], [a])
        assert result["manual_investment_value"] == 50000
        assert result["accounts_count"] == 1


class TestMixedPortfolio:
    def test_total_aggregation(self):
        holdings = [
            _MockHolding(ticker="AAPL", asset_class="stock", current_value=10000, total_cost_basis=8000),
            _MockHolding(ticker="VTI", asset_class="etf", current_value=20000, total_cost_basis=15000),
        ]
        cryptos = [_MockCrypto(current_value=5000, total_cost_basis=3000)]
        manuals = [_MockManualAsset(current_value=50000, purchase_price=40000)]

        result = build_portfolio_summary(holdings, cryptos, manuals)
        assert result["total_value"] == 85000
        assert result["stock_value"] == 10000
        assert result["etf_value"] == 20000
        assert result["crypto_value"] == 5000
        assert result["manual_investment_value"] == 50000

    def test_cost_basis_sum(self):
        holdings = [_MockHolding(total_cost_basis=8000)]
        cryptos = [_MockCrypto(total_cost_basis=3000)]
        manuals = [_MockManualAsset(purchase_price=40000)]
        result = build_portfolio_summary(holdings, cryptos, manuals)
        assert result["total_cost_basis"] == 51000


class TestSectorAllocation:
    def test_sector_grouping(self):
        holdings = [
            _MockHolding(ticker="AAPL", sector="Technology", current_value=10000),
            _MockHolding(ticker="MSFT", sector="Technology", current_value=8000),
            _MockHolding(ticker="JNJ", sector="Healthcare", current_value=5000),
        ]
        result = build_portfolio_summary(holdings, [], [])
        assert result["sector_allocation"]["Technology"] == 18000
        assert result["sector_allocation"]["Healthcare"] == 5000

    def test_unknown_sector(self):
        h = _MockHolding(sector=None, current_value=5000)
        result = build_portfolio_summary([h], [], [])
        assert "Unknown" in result["sector_allocation"]


class TestAssetClassAllocation:
    def test_manual_subtype_mapping(self):
        a = _MockManualAsset(account_subtype="roth_ira", current_value=30000)
        result = build_portfolio_summary([], [], [a])
        assert result["asset_class_allocation"]["roth_ira"] == 30000

    def test_crypto_class(self):
        c = _MockCrypto(current_value=5000)
        result = build_portfolio_summary([], [c], [])
        assert result["asset_class_allocation"]["crypto"] == 5000


class TestTopHoldings:
    def test_sorted_by_value(self):
        holdings = [
            _MockHolding(ticker="SMALL", current_value=1000, total_cost_basis=900),
            _MockHolding(ticker="BIG", current_value=50000, total_cost_basis=40000),
        ]
        result = build_portfolio_summary(holdings, [], [])
        assert result["top_holdings"][0]["ticker"] == "BIG"

    def test_max_ten(self):
        holdings = [
            _MockHolding(ticker=f"T{i}", current_value=1000 * i, total_cost_basis=800 * i)
            for i in range(1, 15)
        ]
        result = build_portfolio_summary(holdings, [], [])
        assert len(result["top_holdings"]) == 10


class TestWeightedReturn:
    def test_weighted_average(self):
        manuals = [
            _MockManualAsset(current_value=60000, annual_return_pct=8.0),
            _MockManualAsset(current_value=40000, annual_return_pct=6.0),
        ]
        result = build_portfolio_summary([], [], manuals)
        # (60000*8 + 40000*6) / (60000+40000) = 7.2
        assert result["weighted_avg_return"] == 7.2

    def test_no_return_data(self):
        a = _MockManualAsset(annual_return_pct=None)
        result = build_portfolio_summary([], [], [a])
        assert result["weighted_avg_return"] is None


class TestSubtypeMapping:
    def test_known_subtypes(self):
        assert SUBTYPE_TO_CLASS["401k"] == "retirement_401k"
        assert SUBTYPE_TO_CLASS["roth_ira"] == "roth_ira"
        assert SUBTYPE_TO_CLASS["hsa"] == "hsa"
        assert SUBTYPE_TO_CLASS["529"] == "education_529"

    def test_unknown_subtype_falls_back(self):
        a = _MockManualAsset(account_subtype="weird_type")
        result = build_portfolio_summary([], [], [a])
        assert "other" in result["asset_class_allocation"]
