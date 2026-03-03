"""Tests for the budget forecasting engine."""
import pytest
from pipeline.planning.budget_forecast import BudgetForecastEngine


def _make_transactions(
    category: str = "Groceries",
    months: dict[int, list[float]] | None = None,
) -> list[dict]:
    """Helper to create transaction dicts for testing."""
    txns = []
    if months is None:
        months = {1: [-200, -250], 2: [-180, -220], 3: [-300, -150]}
    for month, amounts in months.items():
        for amt in amounts:
            txns.append({
                "amount": amt,  # negative = expense
                "effective_category": category,
                "period_month": month,
            })
    return txns


class TestForecastNextMonth:
    """Test monthly forecast calculations."""

    def test_basic_forecast(self):
        txns = _make_transactions(months={1: [-200, -250], 2: [-180, -220], 3: [-300, -150]})
        result = BudgetForecastEngine.forecast_next_month(txns, target_month=1, target_year=2026)
        assert result["month"] == 1
        assert result["year"] == 2026
        assert result["total_predicted"] > 0
        assert len(result["categories"]) > 0

    def test_seasonal_data_used_for_target_month(self):
        # Month 12 historically high (holiday spending), others low
        txns = _make_transactions(months={
            6: [-100],
            7: [-100],
            12: [-500, -600],
        })
        result = BudgetForecastEngine.forecast_next_month(txns, target_month=12, target_year=2026)
        # Should predict close to December historical average (~$550)
        assert result["total_predicted"] > 400

    def test_fallback_to_overall_average_for_missing_month(self):
        txns = _make_transactions(months={1: [-100], 2: [-200], 3: [-300]})
        # Target month 7 has no data, should fall back to overall average
        result = BudgetForecastEngine.forecast_next_month(txns, target_month=7, target_year=2026)
        assert result["total_predicted"] > 0

    def test_confidence_higher_with_more_data(self):
        txns_sparse = _make_transactions(months={3: [-100]})
        txns_rich = _make_transactions(months={3: [-100, -110, -120, -130, -140]})
        result_sparse = BudgetForecastEngine.forecast_next_month(
            txns_sparse, target_month=3, target_year=2026
        )
        result_rich = BudgetForecastEngine.forecast_next_month(
            txns_rich, target_month=3, target_year=2026
        )
        sparse_confidence = result_sparse["categories"][0]["confidence"] if result_sparse["categories"] else 0
        rich_confidence = result_rich["categories"][0]["confidence"] if result_rich["categories"] else 0
        assert rich_confidence >= sparse_confidence

    def test_no_transactions_returns_empty(self):
        result = BudgetForecastEngine.forecast_next_month([], target_month=6, target_year=2026)
        assert result["total_predicted"] == 0
        assert result["categories"] == []

    def test_positive_amounts_ignored(self):
        # Income transactions (positive) should be excluded from expense forecast
        txns = [
            {"amount": 5000, "effective_category": "Salary", "period_month": 1},
            {"amount": -200, "effective_category": "Groceries", "period_month": 1},
        ]
        result = BudgetForecastEngine.forecast_next_month(txns, target_month=1, target_year=2026)
        cats = [c["category"] for c in result["categories"]]
        assert "Groceries" in cats
        assert "Salary" not in cats

    def test_multiple_categories(self):
        txns = (
            _make_transactions("Groceries", months={1: [-200], 2: [-250]})
            + _make_transactions("Gas", months={1: [-80], 2: [-90]})
            + _make_transactions("Dining", months={1: [-150], 2: [-120]})
        )
        result = BudgetForecastEngine.forecast_next_month(txns, target_month=1, target_year=2026)
        assert len(result["categories"]) == 3
        # Sorted by predicted amount descending
        amounts = [c["predicted_amount"] for c in result["categories"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_categories_sorted_by_predicted_amount(self):
        txns = (
            _make_transactions("Small", months={1: [-10]})
            + _make_transactions("Large", months={1: [-1000]})
            + _make_transactions("Medium", months={1: [-200]})
        )
        result = BudgetForecastEngine.forecast_next_month(txns, target_month=1, target_year=2026)
        assert result["categories"][0]["category"] == "Large"
        assert result["categories"][-1]["category"] == "Small"


class TestSeasonalPatterns:
    """Test seasonal pattern detection."""

    def test_detects_peak_months(self):
        # December spending is 3x other months
        txns = []
        for m in range(1, 13):
            amt = -1000 if m == 12 else -300
            txns.append({"amount": amt, "effective_category": "Shopping", "period_month": m})
        patterns = BudgetForecastEngine.detect_seasonal_patterns(txns)
        assert "Shopping" in patterns
        assert 12 in patterns["Shopping"]["peaks"]

    def test_no_patterns_for_flat_spending(self):
        # All months roughly equal = no peaks
        txns = []
        for m in range(1, 13):
            txns.append({"amount": -100, "effective_category": "Utilities", "period_month": m})
        patterns = BudgetForecastEngine.detect_seasonal_patterns(txns)
        # Flat spending shouldn't have peaks (no month is >1.5x average)
        if "Utilities" in patterns:
            assert len(patterns["Utilities"]["peaks"]) == 0

    def test_empty_transactions(self):
        patterns = BudgetForecastEngine.detect_seasonal_patterns([])
        assert patterns == {}

    def test_income_excluded(self):
        txns = [
            {"amount": 5000, "effective_category": "Salary", "period_month": 1},
            {"amount": -200, "effective_category": "Groceries", "period_month": 1},
        ]
        patterns = BudgetForecastEngine.detect_seasonal_patterns(txns)
        assert "Salary" not in patterns


class TestSpendingVelocity:
    """Test spending rate vs budget velocity tracking."""

    def test_on_track_spending(self):
        budget_items = [{"category": "Groceries", "budget_amount": 600}]
        mtd_spending = {"Groceries": -150}  # day 7 of 30 -> 25% spent, 23% elapsed
        results = BudgetForecastEngine.spending_velocity(budget_items, mtd_spending, day_of_month=7, days_in_month=30)
        assert len(results) == 1
        assert results[0]["status"] == "on_track"

    def test_over_budget_spending(self):
        budget_items = [{"category": "Dining", "budget_amount": 300}]
        mtd_spending = {"Dining": -250}  # 83% spent at day 10 of 30 (33% elapsed)
        results = BudgetForecastEngine.spending_velocity(budget_items, mtd_spending, day_of_month=10, days_in_month=30)
        assert results[0]["status"] == "over_budget"

    def test_watch_status(self):
        budget_items = [{"category": "Gas", "budget_amount": 200}]
        # ~40% spent at day 10 of 30 (33% elapsed) -> 1.2x pace -> "watch"
        mtd_spending = {"Gas": -80}
        results = BudgetForecastEngine.spending_velocity(budget_items, mtd_spending, day_of_month=10, days_in_month=30)
        assert results[0]["status"] == "watch"

    def test_projected_total_calculated(self):
        budget_items = [{"category": "Groceries", "budget_amount": 600}]
        mtd_spending = {"Groceries": -300}
        results = BudgetForecastEngine.spending_velocity(budget_items, mtd_spending, day_of_month=15, days_in_month=30)
        # Projected: $300 * (30/15) = $600
        assert results[0]["projected_total"] == pytest.approx(600, abs=1)

    def test_zero_budget_skipped(self):
        budget_items = [
            {"category": "Active", "budget_amount": 500},
            {"category": "Zero", "budget_amount": 0},
        ]
        mtd_spending = {"Active": -100, "Zero": -50}
        results = BudgetForecastEngine.spending_velocity(budget_items, mtd_spending, day_of_month=10, days_in_month=30)
        cats = [r["category"] for r in results]
        assert "Zero" not in cats

    def test_no_spending_is_on_track(self):
        budget_items = [{"category": "Travel", "budget_amount": 1000}]
        mtd_spending = {}
        results = BudgetForecastEngine.spending_velocity(budget_items, mtd_spending, day_of_month=10, days_in_month=30)
        assert results[0]["spent_so_far"] == 0
        assert results[0]["status"] == "on_track"

    def test_results_sorted_by_projected_total(self):
        budget_items = [
            {"category": "Small", "budget_amount": 100},
            {"category": "Large", "budget_amount": 1000},
        ]
        mtd_spending = {"Small": -50, "Large": -500}
        results = BudgetForecastEngine.spending_velocity(budget_items, mtd_spending, day_of_month=15, days_in_month=30)
        projected = [r["projected_total"] for r in results]
        assert projected == sorted(projected, reverse=True)

    def test_single_month_data(self):
        txns = _make_transactions(months={3: [-150]})
        result = BudgetForecastEngine.forecast_next_month(txns, target_month=3, target_year=2026)
        assert result["total_predicted"] == pytest.approx(150, abs=1)
        assert len(result["categories"]) == 1
