"""Tests for the Financial Order of Operations engine with real data scenarios."""
import pytest
from pipeline.planning.benchmarks import BenchmarkEngine


class TestFOOWithRealData:
    """Test FOO steps are computed correctly from various financial scenarios."""

    def test_all_hardcoded_defaults_produce_steps(self):
        steps = BenchmarkEngine.financial_order_of_operations()
        assert len(steps) >= 8
        statuses = [s["status"] for s in steps]
        assert "next" in statuses or "done" in statuses

    def test_credit_card_debt_blocks_progress(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            high_interest_debt=15000,
            emergency_fund_months=0,
        )
        debt_step = next(s for s in steps if "High-Interest" in s["name"])
        assert debt_step["status"] == "next"
        assert "$15,000" in debt_step["description"]
        ef_step = next(s for s in steps if "Emergency" in s["name"])
        assert ef_step["status"] == "locked"

    def test_no_debt_progresses_to_emergency_fund(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            high_interest_debt=0,
            emergency_fund_months=1.5,
            monthly_expenses=6000,
        )
        debt_step = next(s for s in steps if "High-Interest" in s["name"])
        assert debt_step["status"] == "done"
        ef_step = next(s for s in steps if "Emergency" in s["name"])
        assert ef_step["status"] == "next"
        assert ef_step["target_value"] == 36000.0

    def test_healthy_emergency_fund_progresses_to_hsa(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            high_interest_debt=0,
            emergency_fund_months=5,
            hsa_contributions=2000,
            hsa_limit=8300,
        )
        hsa_step = next(s for s in steps if "HSA" in s["name"])
        assert hsa_step["status"] == "next"
        assert "$6,300" in hsa_step["description"]

    def test_maxed_hsa_progresses_to_roth(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            high_interest_debt=0,
            emergency_fund_months=6,
            hsa_contributions=8300,
            roth_contributions=0,
        )
        hsa_step = next(s for s in steps if "HSA" in s["name"])
        assert hsa_step["status"] == "done"
        roth_step = next(s for s in steps if "Roth IRA" in s["name"])
        assert roth_step["status"] == "next"

    def test_everything_maxed_shows_taxable_investing(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            has_employer_match=True,
            employer_match_captured=True,
            high_interest_debt=0,
            emergency_fund_months=6,
            hsa_contributions=8300,
            roth_contributions=7000,
            contrib_401k=23500,
            taxable_investing=50000,
        )
        taxable_step = next(s for s in steps if "Taxable" in s["name"])
        assert taxable_step["status"] == "in_progress"
        assert "$50,000" in taxable_step["description"]

    def test_mega_backdoor_included_when_available(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            has_mega_backdoor=True,
            mega_backdoor_contrib=10000,
            mega_backdoor_limit=46000,
        )
        mega_step = next(s for s in steps if "Mega" in s["name"])
        assert mega_step is not None
        assert mega_step["current_value"] == 10000
        assert mega_step["target_value"] == 46000

    def test_mega_backdoor_excluded_when_unavailable(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            has_mega_backdoor=False,
        )
        mega_steps = [s for s in steps if "Mega" in s["name"]]
        assert len(mega_steps) == 0

    def test_low_interest_debt_tracked(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            low_interest_debt=85000,
        )
        debt_step = next(s for s in steps if "Low-Interest" in s["name"])
        assert debt_step["current_value"] == 85000
        assert "$85,000" in debt_step["description"]

    def test_only_one_next_step(self):
        steps = BenchmarkEngine.financial_order_of_operations(
            high_interest_debt=5000,
            emergency_fund_months=0,
            hsa_contributions=0,
            roth_contributions=0,
            contrib_401k=0,
        )
        next_count = sum(1 for s in steps if s["status"] == "next")
        assert next_count == 1

    def test_step_numbers_sequential(self):
        steps = BenchmarkEngine.financial_order_of_operations()
        for i, step in enumerate(steps):
            assert step["step"] == i + 1

    def test_dynamic_descriptions_with_amounts(self):
        """Descriptions should include real dollar amounts, not generic text."""
        steps = BenchmarkEngine.financial_order_of_operations(
            hsa_contributions=3500,
            hsa_limit=8300,
            monthly_expenses=7000,
            emergency_fund_months=2,
        )
        ef_step = next(s for s in steps if "Emergency" in s["name"])
        assert "2.0 months" in ef_step["description"]
        hsa_step = next(s for s in steps if "HSA" in s["name"])
        assert "$4,800" in hsa_step["description"]


class TestBenchmarks:
    """Test benchmark computations."""

    def test_compute_benchmarks_basic(self):
        result = BenchmarkEngine.compute_benchmarks(
            age=35, income=250000, net_worth=300000, savings_rate=18
        )
        assert "nw_percentile" in result
        assert "savings_percentile" in result
        assert result["user_age"] == 35
        assert result["income"] == 250000
        assert 0 <= result["nw_percentile"] <= 99
        assert 0 <= result["savings_percentile"] <= 99

    def test_high_net_worth_high_percentile(self):
        result = BenchmarkEngine.compute_benchmarks(
            age=35, income=200000, net_worth=1000000, savings_rate=30
        )
        assert result["nw_percentile"] > 90
        assert result["savings_percentile"] >= 75

    def test_negative_net_worth(self):
        result = BenchmarkEngine.compute_benchmarks(
            age=30, income=150000, net_worth=-50000, savings_rate=5
        )
        assert result["nw_percentile"] < 10
