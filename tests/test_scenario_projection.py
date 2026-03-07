"""Tests for pipeline/planning/scenario_projection.py — scenario modelling."""
import pytest

from pipeline.planning.scenario_projection import (
    compose_scenarios,
    project_multi_year,
    compute_retirement_impact,
    compare_scenario_metrics,
    build_scenario_suggestions,
    AFFORDABILITY_THRESHOLDS,
)


# ---------------------------------------------------------------------------
# Mock objects (duck-typed to match ORM scenario / retirement / event shapes)
# ---------------------------------------------------------------------------

class _Scenario:
    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.name = kw.get("name", "Test Scenario")
        self.new_monthly_payment = kw.get("new_monthly_payment", 2000)
        self.monthly_take_home = kw.get("monthly_take_home", 15000)
        self.current_monthly_expenses = kw.get("current_monthly_expenses", 8000)
        self.annual_income = kw.get("annual_income", 250000)
        self.current_savings = kw.get("current_savings", 50000)
        self.current_investments = kw.get("current_investments", 200000)
        self.total_cost = kw.get("total_cost", 500000)
        self.savings_rate_after_pct = kw.get("savings_rate_after_pct", 30)
        self.dti_after_pct = kw.get("dti_after_pct", 35)
        self.affordability_score = kw.get("affordability_score", 65)


class _RetirementProfile:
    def __init__(self, **kw):
        self.fire_number = kw.get("fire_number", 2_000_000)
        self.retirement_age = kw.get("retirement_age", 60)
        self.current_age = kw.get("current_age", 35)
        self.monthly_retirement_contribution = kw.get("monthly_retirement_contribution", 5000)


class _LifeEvent:
    def __init__(self, event_type, event_subtype=None, title="Event"):
        self.event_type = event_type
        self.event_subtype = event_subtype
        self.title = title


class _Grant:
    def __init__(self, unvested_shares=100, current_fmv=150):
        self.unvested_shares = unvested_shares
        self.current_fmv = current_fmv


# ---------------------------------------------------------------------------
# compose_scenarios
# ---------------------------------------------------------------------------

class TestComposeScenarios:
    def test_single_scenario(self):
        s = _Scenario(new_monthly_payment=2000, monthly_take_home=15000, current_monthly_expenses=8000)
        result = compose_scenarios([s])
        assert result["combined_monthly_impact"] == 2000
        assert "combined_verdict" in result

    def test_combined_payment(self):
        s1 = _Scenario(id=1, new_monthly_payment=2000)
        s2 = _Scenario(id=2, new_monthly_payment=1500)
        result = compose_scenarios([s1, s2])
        assert result["combined_monthly_impact"] == 3500

    def test_verdict_comfortable(self):
        # High take-home, low expenses + payment → comfortable
        s = _Scenario(
            new_monthly_payment=500,
            monthly_take_home=20000,
            current_monthly_expenses=5000,
            annual_income=300000,
        )
        result = compose_scenarios([s])
        assert result["combined_verdict"] == "comfortable"

    def test_verdict_risky(self):
        # Very high payment relative to take-home
        s = _Scenario(
            new_monthly_payment=10000,
            monthly_take_home=12000,
            current_monthly_expenses=8000,
            annual_income=180000,
        )
        result = compose_scenarios([s])
        # Surplus = 12000 - 8000 - 10000 = -6000 → negative → score capped at 0
        assert result["combined_verdict"] == "not_recommended"

    def test_savings_rate_after(self):
        s = _Scenario(
            new_monthly_payment=2000,
            monthly_take_home=15000,
            current_monthly_expenses=8000,
        )
        result = compose_scenarios([s])
        # surplus = 15000 - 8000 - 2000 = 5000; SR = 5000/15000 * 100 = 33.33
        assert pytest.approx(result["combined_savings_rate_after"], abs=0.1) == 33.33


# ---------------------------------------------------------------------------
# project_multi_year
# ---------------------------------------------------------------------------

class TestProjectMultiYear:
    def test_returns_year_data(self):
        s = _Scenario()
        result = project_multi_year(s, years=5)
        assert len(result["years"]) == 5
        for item in result["years"]:
            assert "year" in item
            assert "net_worth" in item

    def test_net_worth_grows(self):
        s = _Scenario(
            monthly_take_home=15000,
            current_monthly_expenses=8000,
            new_monthly_payment=0,
            current_savings=50000,
            current_investments=200000,
        )
        result = project_multi_year(s, years=10, investment_return=0.07)
        # Net worth at year 10 should be higher than initial
        assert result["years"][-1]["net_worth"] > 250000

    def test_year_numbers_sequential(self):
        result = project_multi_year(_Scenario(), years=3)
        years = [y["year"] for y in result["years"]]
        assert years == [1, 2, 3]

    def test_zero_income_shrinks(self):
        s = _Scenario(
            monthly_take_home=0,
            current_monthly_expenses=5000,
            new_monthly_payment=0,
            current_savings=100000,
            current_investments=0,
        )
        result = project_multi_year(s, years=5, investment_return=0.0)
        # Spending $60k/yr with no income → net worth should decline
        assert result["years"][-1]["net_worth"] < 100000


# ---------------------------------------------------------------------------
# compute_retirement_impact
# ---------------------------------------------------------------------------

class TestComputeRetirementImpact:
    def test_no_profile(self):
        result = compute_retirement_impact(_Scenario(), None)
        assert result["years_delayed"] == 0
        assert result["current_retirement_age"] == 65

    def test_with_profile(self):
        s = _Scenario(new_monthly_payment=2000)
        r = _RetirementProfile(
            fire_number=2_000_000,
            retirement_age=60,
            current_age=35,
            monthly_retirement_contribution=5000,
        )
        result = compute_retirement_impact(s, r)
        assert result["current_retirement_age"] == 60
        assert result["new_retirement_age"] >= 60
        assert result["years_delayed"] >= 0

    def test_zero_payment_no_delay(self):
        s = _Scenario(new_monthly_payment=0)
        r = _RetirementProfile()
        result = compute_retirement_impact(s, r)
        assert result["years_delayed"] == 0

    def test_capped_at_75(self):
        s = _Scenario(new_monthly_payment=4500)
        r = _RetirementProfile(monthly_retirement_contribution=5000)
        result = compute_retirement_impact(s, r)
        assert result["new_retirement_age"] <= 75

    def test_zero_savings_uses_default_delay(self):
        s = _Scenario(new_monthly_payment=1000)
        r = _RetirementProfile(monthly_retirement_contribution=0)
        result = compute_retirement_impact(s, r)
        assert result["years_delayed"] == 5  # Default when reduced_savings = 0


# ---------------------------------------------------------------------------
# compare_scenario_metrics
# ---------------------------------------------------------------------------

class TestCompareScenarioMetrics:
    def test_difference_calculation(self):
        a = _Scenario(id=1, name="A", new_monthly_payment=2000, total_cost=500000)
        b = _Scenario(id=2, name="B", new_monthly_payment=3000, total_cost=700000)
        result = compare_scenario_metrics(a, b)
        assert result["differences"]["monthly_payment"] == -1000
        assert result["differences"]["total_cost"] == -200000

    def test_structure(self):
        result = compare_scenario_metrics(
            _Scenario(id=1, name="A"), _Scenario(id=2, name="B")
        )
        assert result["scenario_a"]["name"] == "A"
        assert result["scenario_b"]["name"] == "B"
        assert "differences" in result


# ---------------------------------------------------------------------------
# build_scenario_suggestions
# ---------------------------------------------------------------------------

class TestBuildScenarioSuggestions:
    def test_no_events_gives_defaults(self):
        result = build_scenario_suggestions([], [])
        assert len(result) > 0
        types = {s["scenario_type"] for s in result}
        assert "second_home" in types  # Default Henry suggestion

    def test_real_estate_event(self):
        events = [_LifeEvent("real_estate_purchase", title="Bought a condo")]
        result = build_scenario_suggestions(events, [])
        types = {s["scenario_type"] for s in result}
        assert "second_home" in types

    def test_job_change_event(self):
        events = [_LifeEvent("employment_job_change", title="New job")]
        result = build_scenario_suggestions(events, [])
        types = {s["scenario_type"] for s in result}
        assert "lifestyle_upgrade" in types

    def test_equity_grants(self):
        grants = [_Grant(unvested_shares=500, current_fmv=200)]
        result = build_scenario_suggestions([], grants)
        types = {s["scenario_type"] for s in result}
        assert "lifestyle_upgrade" in types
        # Should mention equity
        equity_sug = [s for s in result if s.get("source") == "equity_grants"]
        assert len(equity_sug) == 1

    def test_no_duplicate_types(self):
        events = [
            _LifeEvent("employment_job_change", title="Job 1"),
            _LifeEvent("employment_job_change", title="Job 2"),
        ]
        result = build_scenario_suggestions(events, [])
        types = [s["scenario_type"] for s in result]
        assert len(types) == len(set(types))  # No duplicates
