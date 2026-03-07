"""Tests for the life scenario affordability engine."""
import pytest

from pipeline.planning.life_scenarios import (
    SCENARIO_TEMPLATES,
    LifeScenarioEngine,
    _calc_monthly_payment,
    _compute_affordability_score,
    _score_to_verdict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _henry_context(
    annual_income: float = 350_000,
    monthly_take_home: float = 20_000,
    current_monthly_expenses: float = 10_000,
    current_monthly_debt: float = 3_000,
    current_savings: float = 200_000,
    current_investments: float = 500_000,
) -> dict:
    """Typical HENRY financial profile for scenario calculations."""
    return dict(
        annual_income=annual_income,
        monthly_take_home=monthly_take_home,
        current_monthly_expenses=current_monthly_expenses,
        current_monthly_debt=current_monthly_debt,
        current_savings=current_savings,
        current_investments=current_investments,
    )


def _run(scenario_type: str, params: dict | None = None, **ctx_overrides) -> dict:
    """Shortcut: run a scenario with HENRY defaults and optional overrides."""
    ctx = _henry_context(**ctx_overrides)
    return LifeScenarioEngine.calculate(
        scenario_type=scenario_type,
        params=params or {},
        **ctx,
    )


# ---------------------------------------------------------------------------
# Monthly payment helper
# ---------------------------------------------------------------------------

class TestMonthlyPaymentHelper:
    def test_standard_mortgage(self):
        """30-year $400k mortgage at 6.5% -> ~$2,528/mo."""
        pmt = _calc_monthly_payment(400_000, 6.5, 360)
        assert 2500 < pmt < 2600

    def test_zero_rate(self):
        """0% interest -> principal / months."""
        pmt = _calc_monthly_payment(12_000, 0, 12)
        assert pmt == pytest.approx(1_000, abs=1)

    def test_zero_months(self):
        """Term of 0 -> full principal returned."""
        pmt = _calc_monthly_payment(10_000, 5, 0)
        assert pmt == 10_000


# ---------------------------------------------------------------------------
# Score / verdict helpers
# ---------------------------------------------------------------------------

class TestAffordabilityScore:
    def test_perfect_score_caps_at_100(self):
        result = {
            "monthly_surplus_after": 10_000,
            "savings_rate_after_pct": 30,
            "dti_after_pct": 10,
            "total_cost": 10_000,
        }
        ctx = {
            "monthly_take_home": 20_000,
            "current_savings": 500_000,
            "current_investments": 500_000,
        }
        score = _compute_affordability_score(result, ctx)
        assert score <= 100

    def test_terrible_score_floors_at_0(self):
        result = {
            "monthly_surplus_after": -50_000,
            "savings_rate_after_pct": -50,
            "dti_after_pct": 90,
            "total_cost": 10_000_000,
        }
        ctx = {
            "monthly_take_home": 5_000,
            "current_savings": 1_000,
            "current_investments": 0,
        }
        score = _compute_affordability_score(result, ctx)
        assert score >= 0


class TestScoreToVerdict:
    @pytest.mark.parametrize("score,expected", [
        (95, "comfortable"),
        (80, "comfortable"),
        (70, "feasible"),
        (60, "feasible"),
        (50, "stretch"),
        (40, "stretch"),
        (30, "risky"),
        (20, "risky"),
        (10, "not_recommended"),
        (0, "not_recommended"),
    ])
    def test_verdict_thresholds(self, score, expected):
        assert _score_to_verdict(score) == expected


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

class TestScenarioTemplates:
    def test_get_templates_returns_all(self):
        templates = LifeScenarioEngine.get_templates()
        assert isinstance(templates, dict)
        assert len(templates) == 8

    def test_expected_scenario_types(self):
        templates = LifeScenarioEngine.get_templates()
        expected_types = {
            "second_home", "vehicle", "home_renovation", "college_fund",
            "starting_business", "sabbatical", "lifestyle_upgrade",
            "early_retirement",
        }
        assert set(templates.keys()) == expected_types

    def test_each_template_has_params(self):
        templates = LifeScenarioEngine.get_templates()
        for key, tmpl in templates.items():
            assert "label" in tmpl, f"{key} missing label"
            assert "parameters" in tmpl, f"{key} missing parameters"
            assert isinstance(tmpl["parameters"], dict), f"{key} parameters not dict"

    def test_unknown_scenario_returns_error(self):
        result = _run("nonexistent_type")
        assert "error" in result


# ---------------------------------------------------------------------------
# Second Home
# ---------------------------------------------------------------------------

class TestSecondHome:
    def test_typical_henry(self):
        result = _run("second_home", {
            "purchase_price": 500_000,
            "down_payment_pct": 20,
            "mortgage_rate_pct": 6.5,
            "mortgage_term_years": 30,
        })
        assert "affordability_score" in result
        assert "verdict" in result
        assert result["down_payment_needed"] == 100_000
        assert result["new_monthly_payment"] > 0
        assert "breakdown" in result

    def test_output_shape(self):
        result = _run("second_home")
        expected_keys = {
            "total_cost", "new_monthly_payment", "monthly_surplus_after",
            "savings_rate_after_pct", "dti_after_pct", "down_payment_needed",
            "can_afford_down_payment", "breakdown", "affordability_score",
            "verdict", "savings_rate_before_pct", "dti_before_pct",
        }
        assert expected_keys.issubset(result.keys())

    def test_higher_income_more_affordable(self):
        low = _run("second_home", annual_income=200_000, monthly_take_home=12_000)
        high = _run("second_home", annual_income=500_000, monthly_take_home=30_000)
        assert high["affordability_score"] >= low["affordability_score"]

    def test_rental_income_reduces_net_payment(self):
        no_rental = _run("second_home", {"rental_income_monthly": 0})
        with_rental = _run("second_home", {"rental_income_monthly": 2_000})
        assert with_rental["new_monthly_payment"] < no_rental["new_monthly_payment"]

    def test_can_afford_down_payment_with_savings(self):
        result = _run("second_home", {
            "purchase_price": 200_000,
            "down_payment_pct": 20,
        }, current_savings=500_000)
        # 20% of 200k = 40k, 70% of 500k = 350k -> can afford
        assert result["can_afford_down_payment"] is True

    def test_cannot_afford_down_payment_low_savings(self):
        result = _run("second_home", {
            "purchase_price": 1_000_000,
            "down_payment_pct": 20,
        }, current_savings=50_000)
        # 20% of 1M = 200k, 70% of 50k = 35k -> cannot afford
        assert result["can_afford_down_payment"] is False


# ---------------------------------------------------------------------------
# Vehicle Purchase
# ---------------------------------------------------------------------------

class TestVehiclePurchase:
    def test_typical_vehicle(self):
        result = _run("vehicle", {
            "purchase_price": 60_000,
            "down_payment": 10_000,
            "loan_rate_pct": 5.5,
            "loan_term_months": 60,
        })
        assert result["loan_amount"] == 50_000
        assert result["new_monthly_payment"] > 0
        assert "verdict" in result

    def test_trade_in_reduces_loan(self):
        no_trade = _run("vehicle", {"purchase_price": 60_000, "down_payment": 10_000, "trade_in_value": 0})
        with_trade = _run("vehicle", {"purchase_price": 60_000, "down_payment": 10_000, "trade_in_value": 20_000})
        assert with_trade["loan_amount"] < no_trade["loan_amount"]

    def test_output_shape(self):
        result = _run("vehicle")
        expected_keys = {
            "total_cost", "new_monthly_payment", "monthly_surplus_after",
            "savings_rate_after_pct", "dti_after_pct", "loan_amount", "breakdown",
        }
        assert expected_keys.issubset(result.keys())

    def test_zero_income_no_division_error(self):
        result = _run("vehicle", annual_income=0, monthly_take_home=0)
        assert result["dti_after_pct"] == 0
        assert result["savings_rate_after_pct"] == 0


# ---------------------------------------------------------------------------
# Home Renovation
# ---------------------------------------------------------------------------

class TestRenovation:
    def test_cash_renovation_no_monthly_payment(self):
        result = _run("home_renovation", {
            "renovation_cost": 50_000,
            "financing_pct": 0,
        })
        assert result["new_monthly_payment"] == 0
        assert result["out_of_pocket"] == 50_000

    def test_financed_renovation_has_payment(self):
        result = _run("home_renovation", {
            "renovation_cost": 50_000,
            "financing_pct": 80,
            "loan_rate_pct": 7.0,
            "loan_term_years": 10,
        })
        assert result["new_monthly_payment"] > 0

    def test_positive_roi(self):
        result = _run("home_renovation", {
            "renovation_cost": 50_000,
            "expected_value_increase": 70_000,
        })
        assert result["roi_pct"] > 0

    def test_negative_roi(self):
        result = _run("home_renovation", {
            "renovation_cost": 50_000,
            "expected_value_increase": 20_000,
        })
        assert result["roi_pct"] < 0


# ---------------------------------------------------------------------------
# College Fund
# ---------------------------------------------------------------------------

class TestCollegeFund:
    def test_typical_529(self):
        result = _run("college_fund", {
            "child_current_age": 5,
            "college_start_age": 18,
            "annual_tuition_today": 40_000,
            "years_of_college": 4,
        })
        assert result["years_until_college"] == 13
        assert result["total_cost"] > 0
        assert result["new_monthly_payment"] > 0

    def test_existing_balance_reduces_contribution(self):
        no_balance = _run("college_fund", {
            "child_current_age": 5,
            "current_529_balance": 0,
        })
        with_balance = _run("college_fund", {
            "child_current_age": 5,
            "current_529_balance": 100_000,
        })
        assert with_balance["new_monthly_payment"] < no_balance["new_monthly_payment"]

    def test_child_already_at_college_age(self):
        result = _run("college_fund", {
            "child_current_age": 18,
            "college_start_age": 18,
        })
        assert result["years_until_college"] == 0

    def test_dti_unchanged(self):
        """College savings is not debt, so DTI should not change."""
        result = _run("college_fund")
        assert result["dti_after_pct"] == result["dti_before_pct"]


# ---------------------------------------------------------------------------
# Starting a Business
# ---------------------------------------------------------------------------

class TestStartingBusiness:
    def test_typical_startup(self):
        result = _run("starting_business", {
            "startup_costs": 50_000,
            "monthly_operating_costs": 5_000,
            "months_to_revenue": 6,
            "expected_monthly_revenue_year1": 15_000,
            "salary_replacement_needed": 8_000,
        })
        assert result["runway_needed"] > 0
        assert result["months_to_breakeven"] > 0

    def test_can_self_fund_with_high_savings(self):
        result = _run("starting_business", {
            "startup_costs": 20_000,
            "monthly_operating_costs": 3_000,
            "months_to_revenue": 3,
            "salary_replacement_needed": 5_000,
            "emergency_fund_months": 3,
        }, current_savings=200_000, current_investments=500_000)
        assert result["can_self_fund"] is True

    def test_cannot_self_fund_with_low_savings(self):
        result = _run("starting_business", {
            "startup_costs": 200_000,
            "monthly_operating_costs": 20_000,
            "months_to_revenue": 12,
            "salary_replacement_needed": 15_000,
            "emergency_fund_months": 6,
        }, current_savings=10_000, current_investments=10_000)
        assert result["can_self_fund"] is False

    def test_revenue_exceeding_costs_positive_surplus(self):
        result = _run("starting_business", {
            "expected_monthly_revenue_year1": 30_000,
            "monthly_operating_costs": 5_000,
            "salary_replacement_needed": 8_000,
        })
        # net = 30k - 5k - 8k = 17k
        assert result["monthly_surplus_after"] > 0


# ---------------------------------------------------------------------------
# Sabbatical
# ---------------------------------------------------------------------------

class TestSabbatical:
    def test_typical_sabbatical(self):
        result = _run("sabbatical", {
            "duration_months": 6,
            "monthly_expenses_during": 6_000,
            "health_insurance_monthly": 800,
            "travel_budget": 10_000,
        })
        assert result["total_cost"] > 0
        assert result["lost_income"] > 0
        assert result["total_financial_impact"] > result["total_cost"]

    def test_higher_income_longer_sabbatical_lost_income(self):
        low = _run("sabbatical", {"duration_months": 3}, annual_income=200_000)
        high = _run("sabbatical", {"duration_months": 12}, annual_income=500_000)
        assert high["lost_income"] > low["lost_income"]

    def test_can_afford_with_large_savings(self):
        result = _run("sabbatical", {
            "duration_months": 6,
            "monthly_expenses_during": 5_000,
            "health_insurance_monthly": 500,
            "travel_budget": 5_000,
        }, current_savings=1_000_000)
        assert result["can_afford_from_savings"] is True

    def test_cannot_afford_with_small_savings(self):
        result = _run("sabbatical", {
            "duration_months": 12,
            "monthly_expenses_during": 10_000,
            "health_insurance_monthly": 1_500,
            "travel_budget": 20_000,
        }, current_savings=50_000)
        assert result["can_afford_from_savings"] is False

    def test_income_during_reduces_cost(self):
        no_income = _run("sabbatical", {
            "expected_income_during": 0,
            "duration_months": 6,
        })
        with_income = _run("sabbatical", {
            "expected_income_during": 3_000,
            "duration_months": 6,
        })
        assert with_income["total_cost"] < no_income["total_cost"]


# ---------------------------------------------------------------------------
# Lifestyle Upgrade
# ---------------------------------------------------------------------------

class TestLifestyleUpgrade:
    def test_typical_upgrade(self):
        result = _run("lifestyle_upgrade", {
            "monthly_cost_increase": 500,
            "one_time_cost": 2_000,
        })
        assert result["annual_recurring"] == 6_000
        assert result["one_time_cost"] == 2_000
        assert result["total_cost"] == 8_000  # 6000 + 2000

    def test_no_one_time_cost(self):
        result = _run("lifestyle_upgrade", {
            "monthly_cost_increase": 1_000,
            "one_time_cost": 0,
        })
        assert result["total_cost"] == 12_000

    def test_surplus_decreases(self):
        base = _run("lifestyle_upgrade", {"monthly_cost_increase": 0, "one_time_cost": 0})
        upgrade = _run("lifestyle_upgrade", {"monthly_cost_increase": 2_000, "one_time_cost": 0})
        assert upgrade["monthly_surplus_after"] < base["monthly_surplus_after"]


# ---------------------------------------------------------------------------
# Early Retirement
# ---------------------------------------------------------------------------

class TestEarlyRetirement:
    def test_fire_number_25x(self):
        result = _run("early_retirement", {
            "annual_expenses_in_retirement": 80_000,
        })
        assert result["fire_number"] == 2_000_000  # 80k * 25

    def test_feasible_with_large_savings(self):
        result = _run("early_retirement", {
            "current_age": 35,
            "target_retirement_age": 55,
            "annual_expenses_in_retirement": 60_000,
            "current_savings": 1_000_000,
            "monthly_savings": 10_000,
            "expected_return_pct": 7,
        })
        # 20 years of compounding $1M + $10k/mo at 7% -> should be well above $1.5M (60k*25)
        assert result["feasible"] is True
        assert result["gap"] > 0

    def test_not_feasible_short_timeframe(self):
        result = _run("early_retirement", {
            "current_age": 45,
            "target_retirement_age": 48,
            "annual_expenses_in_retirement": 120_000,
            "current_savings": 100_000,
            "monthly_savings": 2_000,
            "expected_return_pct": 7,
        })
        # Fire number: 3M, only 3 years to save -> unlikely
        assert result["fire_number"] == 3_000_000
        assert result["feasible"] is False

    def test_years_until_ss(self):
        result = _run("early_retirement", {
            "target_retirement_age": 50,
            "social_security_age": 67,
        })
        assert result["years_until_ss"] == 17

    def test_projected_savings_grows_with_time(self):
        short = _run("early_retirement", {
            "current_age": 40,
            "target_retirement_age": 45,
            "current_savings": 500_000,
            "monthly_savings": 5_000,
        })
        long = _run("early_retirement", {
            "current_age": 40,
            "target_retirement_age": 60,
            "current_savings": 500_000,
            "monthly_savings": 5_000,
        })
        assert long["projected_at_target_age"] > short["projected_at_target_age"]


# ---------------------------------------------------------------------------
# Common output validation
# ---------------------------------------------------------------------------

class TestCommonOutputFields:
    """Every scenario calculator should produce these standard fields."""

    @pytest.mark.parametrize("scenario_type", [
        "second_home", "vehicle", "home_renovation", "college_fund",
        "starting_business", "sabbatical", "lifestyle_upgrade",
        "early_retirement",
    ])
    def test_standard_fields_present(self, scenario_type):
        result = _run(scenario_type)
        for key in [
            "affordability_score", "verdict", "savings_rate_before_pct",
            "dti_before_pct", "total_cost", "new_monthly_payment",
            "monthly_surplus_after",
        ]:
            assert key in result, f"{key} missing from {scenario_type}"

    @pytest.mark.parametrize("scenario_type", [
        "second_home", "vehicle", "home_renovation", "college_fund",
        "starting_business", "sabbatical", "lifestyle_upgrade",
        "early_retirement",
    ])
    def test_verdict_is_valid(self, scenario_type):
        result = _run(scenario_type)
        valid = {"comfortable", "feasible", "stretch", "risky", "not_recommended"}
        assert result["verdict"] in valid

    @pytest.mark.parametrize("scenario_type", [
        "second_home", "vehicle", "home_renovation", "college_fund",
        "starting_business", "sabbatical", "lifestyle_upgrade",
        "early_retirement",
    ])
    def test_score_in_range(self, scenario_type):
        result = _run(scenario_type)
        assert 0 <= result["affordability_score"] <= 100


# ---------------------------------------------------------------------------
# Edge cases (zero/extreme inputs)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_income_second_home(self):
        result = _run("second_home", annual_income=0, monthly_take_home=0)
        assert result["dti_after_pct"] == 0
        assert result["affordability_score"] >= 0

    def test_very_large_purchase_price(self):
        result = _run("second_home", {"purchase_price": 10_000_000})
        assert result["affordability_score"] <= 40  # should be stretch at best

    def test_zero_income_vehicle(self):
        result = _run("vehicle", annual_income=0, monthly_take_home=0)
        assert "verdict" in result

    def test_zero_savings_sabbatical(self):
        result = _run("sabbatical", current_savings=0)
        assert result["can_afford_from_savings"] is False

    def test_zero_startup_costs(self):
        result = _run("starting_business", {"startup_costs": 0, "months_to_revenue": 0})
        assert result["runway_needed"] >= 0
