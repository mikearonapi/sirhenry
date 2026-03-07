"""Tests for pipeline/planning/tax_loss_harvest.py — TLH analysis engine."""
from datetime import date, timedelta

import pytest

from pipeline.planning.tax_loss_harvest import TaxLossHarvestEngine, HarvestSummary


def _holding(
    ticker="AAPL", cost=10000, value=8000, purchase_date=None, **kw
):
    """Helper to build a holding dict."""
    return {
        "id": kw.get("id", 1),
        "ticker": ticker,
        "name": kw.get("name", ticker),
        "shares": kw.get("shares", 100),
        "total_cost_basis": cost,
        "current_value": value,
        "purchase_date": purchase_date,
        "current_price": value / max(kw.get("shares", 100), 1),
        "cost_basis_per_share": cost / max(kw.get("shares", 100), 1),
    }


class TestTaxLossHarvestBasic:
    """Basic TLH analysis behaviour."""

    def test_empty_portfolio(self):
        result = TaxLossHarvestEngine.analyze([])
        assert result.total_unrealized_losses == 0
        assert result.total_unrealized_gains == 0
        assert len(result.candidates) == 0

    def test_all_gains_no_candidates(self):
        holdings = [_holding(cost=5000, value=10000)]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert len(result.candidates) == 0
        assert result.total_unrealized_gains == 5000

    def test_single_loss(self):
        holdings = [_holding(cost=10000, value=7000)]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert len(result.candidates) == 1
        assert result.total_unrealized_losses == 3000
        assert result.harvestable_losses == 3000

    def test_mixed_portfolio(self):
        holdings = [
            _holding(ticker="AAPL", cost=10000, value=12000, id=1),
            _holding(ticker="TSLA", cost=8000, value=5000, id=2),
            _holding(ticker="GOOG", cost=6000, value=4000, id=3),
        ]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert result.total_unrealized_gains == 2000
        assert result.total_unrealized_losses == 5000
        assert len(result.candidates) == 2

    def test_net_unrealized(self):
        holdings = [
            _holding(cost=10000, value=12000, id=1),
            _holding(cost=8000, value=5000, id=2),
        ]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert result.net_unrealized == 2000 - 3000  # gains - losses = -1000


class TestTermClassification:
    """Long-term vs short-term based on holding period."""

    def test_short_term_no_date(self):
        """Holdings with no purchase date default to short-term."""
        holdings = [_holding(cost=10000, value=8000, purchase_date=None)]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert result.candidates[0].term == "short"

    def test_short_term_recent(self):
        recent = (date.today() - timedelta(days=100)).isoformat()
        holdings = [_holding(cost=10000, value=8000, purchase_date=recent)]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert result.candidates[0].term == "short"

    def test_long_term(self):
        old = (date.today() - timedelta(days=400)).isoformat()
        holdings = [_holding(cost=10000, value=8000, purchase_date=old)]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert result.candidates[0].term == "long"

    def test_boundary_365_is_short(self):
        """Exactly 365 days is still short-term (needs >365)."""
        boundary = (date.today() - timedelta(days=365)).isoformat()
        holdings = [_holding(cost=10000, value=8000, purchase_date=boundary)]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert result.candidates[0].term == "short"

    def test_boundary_366_is_long(self):
        boundary = (date.today() - timedelta(days=366)).isoformat()
        holdings = [_holding(cost=10000, value=8000, purchase_date=boundary)]
        result = TaxLossHarvestEngine.analyze(holdings)
        assert result.candidates[0].term == "long"


class TestWashSale:
    """Wash sale detection (±30 days)."""

    def test_no_recent_purchases(self):
        holdings = [_holding(cost=10000, value=8000)]
        result = TaxLossHarvestEngine.analyze(holdings, recent_purchases=None)
        assert result.candidates[0].wash_sale_risk is False

    def test_recent_purchase_triggers_wash(self):
        today = date.today()
        holdings = [_holding(ticker="AAPL", cost=10000, value=8000)]
        recent = [{"ticker": "AAPL", "date": (today - timedelta(days=10)).isoformat()}]
        result = TaxLossHarvestEngine.analyze(holdings, recent_purchases=recent)
        assert result.candidates[0].wash_sale_risk is True

    def test_old_purchase_no_wash(self):
        today = date.today()
        holdings = [_holding(ticker="AAPL", cost=10000, value=8000)]
        recent = [{"ticker": "AAPL", "date": (today - timedelta(days=60)).isoformat()}]
        result = TaxLossHarvestEngine.analyze(holdings, recent_purchases=recent)
        assert result.candidates[0].wash_sale_risk is False

    def test_different_ticker_no_wash(self):
        today = date.today()
        holdings = [_holding(ticker="AAPL", cost=10000, value=8000)]
        recent = [{"ticker": "GOOG", "date": (today - timedelta(days=10)).isoformat()}]
        result = TaxLossHarvestEngine.analyze(holdings, recent_purchases=recent)
        assert result.candidates[0].wash_sale_risk is False

    def test_wash_sale_excludes_from_harvestable(self):
        today = date.today()
        holdings = [_holding(ticker="AAPL", cost=10000, value=7000)]
        recent = [{"ticker": "AAPL", "date": today.isoformat()}]
        result = TaxLossHarvestEngine.analyze(holdings, recent_purchases=recent)
        assert result.harvestable_losses == 0  # Excluded due to wash sale
        assert result.total_unrealized_losses == 3000  # Still tracked


class TestCarryoverAndSavings:
    """Capital loss carryover and tax savings calculations."""

    def test_gains_offset_first(self):
        holdings = [_holding(cost=20000, value=10000)]  # $10k loss
        result = TaxLossHarvestEngine.analyze(
            holdings, realized_short_gains=5000, realized_long_gains=0
        )
        # Offset $5k gains, then $3k ordinary → carryover = $2k
        assert result.capital_loss_carryover_available == 2000

    def test_ordinary_income_deduction_capped_3k(self):
        holdings = [_holding(cost=10000, value=5000)]  # $5k loss
        result = TaxLossHarvestEngine.analyze(holdings)
        # No realized gains, so $3k ordinary income deduction, $2k carryover
        assert result.capital_loss_carryover_available == 2000

    def test_small_loss_no_carryover(self):
        holdings = [_holding(cost=10000, value=8000)]  # $2k loss
        result = TaxLossHarvestEngine.analyze(holdings)
        # $2k < $3k ordinary deduction limit → no carryover
        assert result.capital_loss_carryover_available == 0

    def test_tax_savings_positive(self):
        holdings = [_holding(cost=10000, value=5000)]
        result = TaxLossHarvestEngine.analyze(holdings, marginal_tax_rate=0.37)
        assert result.estimated_tax_savings > 0


class TestToDict:
    """to_dict() serializes summary to JSON-safe dict."""

    def test_roundtrip(self):
        holdings = [
            _holding(cost=10000, value=8000, purchase_date=(date.today() - timedelta(days=400)).isoformat()),
        ]
        summary = TaxLossHarvestEngine.analyze(holdings)
        d = TaxLossHarvestEngine.to_dict(summary)
        assert "total_unrealized_losses" in d
        assert "candidates" in d
        assert isinstance(d["candidates"], list)
        assert d["candidates"][0]["term"] == "long"
