"""Tests for the retirement calculator engine."""
import pytest
from pipeline.planning.retirement import RetirementCalculator, RetirementInputs


def _base_inputs(**overrides) -> RetirementInputs:
    """Sensible defaults for a 35-year-old HENRY."""
    defaults = dict(
        current_age=35,
        retirement_age=65,
        life_expectancy=90,
        current_annual_income=250_000,
        expected_income_growth_pct=3.0,
        expected_social_security_monthly=3_000,
        social_security_start_age=67,
        pension_monthly=0,
        other_retirement_income_monthly=0,
        current_retirement_savings=200_000,
        current_other_investments=50_000,
        monthly_retirement_contribution=2_000,
        employer_match_pct=50,
        employer_match_limit_pct=6.0,
        desired_annual_retirement_income=None,
        income_replacement_pct=80.0,
        healthcare_annual_estimate=12_000,
        additional_annual_expenses=0,
        inflation_rate_pct=3.0,
        pre_retirement_return_pct=7.0,
        post_retirement_return_pct=5.0,
        tax_rate_in_retirement_pct=22.0,
    )
    defaults.update(overrides)
    return RetirementInputs(**defaults)


class TestRetirementCalculatorBasic:
    def test_years_to_retirement(self):
        r = RetirementCalculator.calculate(_base_inputs(current_age=40, retirement_age=60))
        assert r.years_to_retirement == 20

    def test_years_in_retirement(self):
        r = RetirementCalculator.calculate(_base_inputs(retirement_age=65, life_expectancy=90))
        assert r.years_in_retirement == 25

    def test_already_retired(self):
        r = RetirementCalculator.calculate(_base_inputs(current_age=70, retirement_age=65))
        assert r.years_to_retirement == 0

    def test_positive_target_nest_egg(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert r.target_nest_egg > 0

    def test_projected_nest_egg_positive(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert r.projected_nest_egg > 0

    def test_readiness_bounded(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert 0 <= r.retirement_readiness_pct <= 500  # can exceed 100%


class TestRetirementCalculatorIncomeNeeds:
    def test_income_replacement_default(self):
        r = RetirementCalculator.calculate(_base_inputs(
            income_replacement_pct=80,
            desired_annual_retirement_income=None,
            current_annual_expenses=None,
        ))
        assert r.annual_income_needed_today > 0

    def test_desired_income_overrides_replacement(self):
        r = RetirementCalculator.calculate(_base_inputs(
            desired_annual_retirement_income=150_000,
        ))
        assert r.annual_income_needed_today >= 150_000

    def test_current_expenses_override(self):
        r_with = RetirementCalculator.calculate(_base_inputs(
            current_annual_expenses=100_000,
            desired_annual_retirement_income=None,
        ))
        r_without = RetirementCalculator.calculate(_base_inputs(
            current_annual_expenses=None,
            desired_annual_retirement_income=None,
            income_replacement_pct=80,
        ))
        assert r_with.annual_income_needed_today != r_without.annual_income_needed_today


class TestRetirementCalculatorContributions:
    def test_employer_match_computed(self):
        r = RetirementCalculator.calculate(_base_inputs(
            employer_match_pct=50,
            employer_match_limit_pct=6.0,
        ))
        assert r.employer_match_monthly > 0

    def test_zero_match_when_no_employer(self):
        r = RetirementCalculator.calculate(_base_inputs(
            employer_match_pct=0,
        ))
        assert r.employer_match_monthly == 0

    def test_savings_rate_positive(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert r.current_savings_rate_pct > 0


class TestRetirementCalculatorFireNumbers:
    def test_fire_number_positive(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert r.fire_number > 0

    def test_coast_fire_less_than_fire(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert r.coast_fire_number <= r.fire_number

    def test_lean_fire_less_than_fire(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert r.lean_fire_number <= r.fire_number


class TestRetirementCalculatorProjection:
    def test_yearly_projection_populated(self):
        r = RetirementCalculator.calculate(_base_inputs())
        assert len(r.yearly_projection) > 0

    def test_projection_has_expected_keys(self):
        r = RetirementCalculator.calculate(_base_inputs())
        row = r.yearly_projection[0]
        assert "age" in row
        assert "year" in row
        assert "balance" in row
        assert "phase" in row

    def test_projection_starts_at_current_age(self):
        inputs = _base_inputs(current_age=35, retirement_age=65, life_expectancy=90)
        r = RetirementCalculator.calculate(inputs)
        ages = [row["age"] for row in r.yearly_projection]
        assert ages[0] == 35
        assert len(ages) >= inputs.retirement_age - inputs.current_age


class TestRetirementCalculatorDebtPayoff:
    def test_debt_payoff_reduces_expenses(self):
        r_no_debt = RetirementCalculator.calculate(_base_inputs())
        r_debt = RetirementCalculator.calculate(_base_inputs(
            debt_payoffs=[{"name": "Mortgage", "monthly_payment": 2000, "payoff_age": 55}],
        ))
        assert r_debt.annual_income_needed_today < r_no_debt.annual_income_needed_today

    def test_debt_after_retirement_no_reduction(self):
        r = RetirementCalculator.calculate(_base_inputs(
            debt_payoffs=[{"name": "Late Mortgage", "monthly_payment": 2000, "payoff_age": 70}],
            retirement_age=65,
        ))
        assert r.debt_payoff_savings_annual == 0


class TestRetirementCalculatorEdgeCases:
    def test_zero_income(self):
        r = RetirementCalculator.calculate(_base_inputs(current_annual_income=0))
        assert r.target_nest_egg >= 0

    def test_high_inflation(self):
        r = RetirementCalculator.calculate(_base_inputs(inflation_rate_pct=10.0))
        assert r.annual_income_needed_at_retirement > r.annual_income_needed_today

    def test_no_contributions(self):
        r = RetirementCalculator.calculate(_base_inputs(
            monthly_retirement_contribution=0,
            employer_match_pct=0,
        ))
        assert r.total_monthly_contribution == 0
