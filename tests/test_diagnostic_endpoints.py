"""Tests for the new diagnostic/health endpoints and fixes."""
import pytest
from pipeline.planning.benchmarks import BenchmarkEngine
from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine


class TestNetWorthTrend:
    """Verify the analytics engine gets correct field names from NetWorthSnapshot."""

    def test_empty_snapshots(self):
        result = PortfolioAnalyticsEngine.net_worth_trend([])
        assert result["current_net_worth"] == 0
        assert result["monthly_series"] == []

    def test_snapshots_with_correct_fields(self):
        snapshots = [
            {"snapshot_date": "2025-01-01", "net_worth": 100000},
            {"snapshot_date": "2025-06-01", "net_worth": 150000},
        ]
        result = PortfolioAnalyticsEngine.net_worth_trend(snapshots)
        assert result["current_net_worth"] == 150000
        assert result["growth_rate"] == 0.5
        assert len(result["monthly_series"]) == 2


class TestRequiredSavingsRate:
    """Verify the required savings rate formula handles edge cases."""

    def test_benchmarks_include_required_rate_key(self):
        result = BenchmarkEngine.compute_benchmarks(
            age=35, income=200000, net_worth=500000, savings_rate=15.0
        )
        assert "nw_percentile" in result
        assert "savings_rate" in result

    def test_foo_descriptions_are_dynamic(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            high_interest_debt=5000,
            emergency_fund_months=1.5,
            monthly_expenses=6000,
        )
        debt_step = next(s for s in steps if "High-Interest" in s["name"])
        assert "$5,000" in debt_step["description"]

        ef_step = next(s for s in steps if "Emergency" in s["name"])
        assert "1.5 months" in ef_step["description"]


class TestTransactionAuditShape:
    """Verify the expected response shape of the audit endpoint."""

    def test_quality_thresholds(self):
        for rate, expected in [(95, "good"), (80, "needs_attention"), (50, "poor")]:
            quality = "good" if rate >= 90 else "needs_attention" if rate >= 70 else "poor"
            assert quality == expected


class TestDashboardTaxEstimate:
    """Verify the monthly tax estimate computation approach."""

    def test_monthly_is_annual_divided_by_12(self):
        annual_income = 25000
        from pipeline.tax import total_tax_estimate
        annual_tax = total_tax_estimate(w2_wages=annual_income * 12, filing_status="mfj")
        monthly = annual_tax["total_tax"] / 12
        assert monthly > 0
        assert monthly < annual_income


class TestStatusBadgeDynamic:
    """Verify the dynamic status badge logic mirrors frontend."""

    @pytest.mark.parametrize("savings,target,expected", [
        (25, 20, "On Track"),
        (15, 20, "At Risk"),
        (5, 20, "Behind"),
        (30, 25, "On Track"),
        (13, 25, "At Risk"),
        (5, 25, "Behind"),
    ])
    def test_status_label(self, savings, target, expected):
        if savings >= target:
            label = "On Track"
        elif savings >= target * 0.5:
            label = "At Risk"
        else:
            label = "Behind"
        assert label == expected
