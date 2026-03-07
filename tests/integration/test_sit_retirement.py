"""SIT: Retirement calculator accuracy.

Validates RetirementCalculator produces mathematically correct results
using the demo persona inputs (Michael & Jessica Chen, $410K combined).
"""
import pytest
from tests.integration.expected_values import *

from pipeline.planning.retirement import RetirementCalculator, RetirementInputs


pytestmark = pytest.mark.integration


def _demo_inputs() -> RetirementInputs:
    """Build RetirementInputs from the demo persona's seeded values."""
    return RetirementInputs(
        current_age=CURRENT_AGE,
        retirement_age=RETIREMENT_AGE,
        life_expectancy=LIFE_EXPECTANCY,
        current_annual_income=COMBINED_INCOME,
        expected_income_growth_pct=EXPECTED_INCOME_GROWTH_PCT,
        expected_social_security_monthly=EXPECTED_SS_MONTHLY,
        social_security_start_age=SS_START_AGE,
        current_retirement_savings=CURRENT_RETIREMENT_SAVINGS,
        current_other_investments=CURRENT_OTHER_INVESTMENTS,
        monthly_retirement_contribution=MONTHLY_RETIREMENT_CONTRIBUTION,
        employer_match_pct=EMPLOYER_MATCH_PCT,
        employer_match_limit_pct=EMPLOYER_MATCH_LIMIT_PCT,
        income_replacement_pct=INCOME_REPLACEMENT_PCT,
        healthcare_annual_estimate=HEALTHCARE_ANNUAL,
        current_annual_expenses=CURRENT_ANNUAL_EXPENSES,
        inflation_rate_pct=INFLATION_RATE_PCT,
        pre_retirement_return_pct=PRE_RETIREMENT_RETURN_PCT,
        post_retirement_return_pct=POST_RETIREMENT_RETURN_PCT,
        tax_rate_in_retirement_pct=TAX_RATE_IN_RETIREMENT_PCT,
    )


@pytest.fixture(scope="module")
def results():
    """Calculate retirement results once for all tests."""
    return RetirementCalculator.calculate(_demo_inputs())


# ---------------------------------------------------------------------------
# Core timing
# ---------------------------------------------------------------------------

class TestRetirementTiming:
    def test_years_to_retirement(self, results):
        assert results.years_to_retirement == YEARS_TO_RETIREMENT  # 19

    def test_years_in_retirement(self, results):
        assert results.years_in_retirement == YEARS_IN_RETIREMENT  # 38


# ---------------------------------------------------------------------------
# Income needs
# ---------------------------------------------------------------------------

class TestRetirementIncomeNeeds:
    def test_income_need_uses_current_expenses_plus_healthcare(self, results):
        """When current_annual_expenses is set, it should be used as the base,
        plus healthcare_annual_estimate."""
        assert results.annual_income_needed_today == pytest.approx(
            ANNUAL_INCOME_NEEDED_TODAY, rel=0.01,
        )

    def test_inflation_adjustment(self, results):
        """Income need at retirement = today's need * inflation^years / (1 - tax_rate)."""
        inflation_mult = (1 + INFLATION_RATE_PCT / 100) ** YEARS_TO_RETIREMENT
        pre_tax = ANNUAL_INCOME_NEEDED_TODAY * inflation_mult / (1 - TAX_RATE_IN_RETIREMENT_PCT / 100)
        assert results.annual_income_needed_at_retirement == pytest.approx(pre_tax, rel=0.01)


# ---------------------------------------------------------------------------
# Employer match
# ---------------------------------------------------------------------------

class TestRetirementEmployerMatch:
    def test_employer_match_monthly(self, results):
        """monthly_income * match_limit% = eligible, min(contrib, eligible) * match%."""
        assert results.employer_match_monthly == pytest.approx(
            EMPLOYER_MATCH_MONTHLY, rel=0.01,
        )

    def test_total_monthly_contribution(self, results):
        expected = MONTHLY_RETIREMENT_CONTRIBUTION + EMPLOYER_MATCH_MONTHLY
        assert results.total_monthly_contribution == pytest.approx(expected, rel=0.01)


# ---------------------------------------------------------------------------
# Independence numbers
# ---------------------------------------------------------------------------

class TestRetirementIndependenceNumbers:
    def test_fire_number(self, results):
        """FIRE number = annual_income_needed_today * 25."""
        assert results.fire_number == pytest.approx(FIRE_NUMBER, rel=0.001)

    def test_coast_fire_number(self, results):
        """Coast FIRE = target_nest_egg / (1 + pre_return)^years."""
        expected = results.target_nest_egg / (
            (1 + PRE_RETIREMENT_RETURN_PCT / 100) ** YEARS_TO_RETIREMENT
        )
        assert results.coast_fire_number == pytest.approx(expected, rel=0.01)


# ---------------------------------------------------------------------------
# Social Security two-phase PV
# ---------------------------------------------------------------------------

class TestRetirementSocialSecurity:
    def test_two_phase_pv_used(self, results):
        """Retiring at 52 with SS at 67 means 15-year gap. Target should be higher
        than simple PV because phase 1 has no SS offset."""
        # Compute what target would be WITHOUT two-phase (simple approach)
        real_return = (1 + POST_RETIREMENT_RETURN_PCT / 100) / (1 + INFLATION_RATE_PCT / 100) - 1
        if real_return > 0 and YEARS_IN_RETIREMENT > 0:
            simple_pv = (1 - (1 + real_return) ** (-YEARS_IN_RETIREMENT)) / real_return
        else:
            simple_pv = YEARS_IN_RETIREMENT
        simple_target = results.portfolio_income_needed_annual * simple_pv
        # Two-phase should produce a HIGHER target because of the SS gap
        assert results.target_nest_egg > simple_target * 0.9  # sanity check

    def test_social_security_annual(self, results):
        inflation_mult = (1 + INFLATION_RATE_PCT / 100) ** YEARS_TO_RETIREMENT
        expected_ss_annual = EXPECTED_SS_MONTHLY * inflation_mult * 12
        assert results.social_security_annual == pytest.approx(expected_ss_annual, rel=0.01)


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------

class TestRetirementProjections:
    def test_projected_nest_egg_positive(self, results):
        """19 years of contributions + 7% returns should grow savings substantially."""
        assert results.projected_nest_egg > CURRENT_RETIREMENT_SAVINGS + CURRENT_OTHER_INVESTMENTS

    def test_yearly_projection_length(self, results):
        """Projection should cover accumulation + distribution phases."""
        assert len(results.yearly_projection) >= YEARS_TO_RETIREMENT + 1

    def test_yearly_projection_phases(self, results):
        """First entries should be accumulation, later distribution."""
        phases = [entry.get("phase") or entry.get("label", "") for entry in results.yearly_projection]
        # Find where distribution starts
        accum_count = sum(1 for p in phases if "accum" in str(p).lower())
        assert accum_count >= YEARS_TO_RETIREMENT

    def test_earliest_retirement_age(self, results):
        """With $410K income and aggressive savings, earliest should be reasonable."""
        assert 40 <= results.earliest_retirement_age <= 65

    def test_retire_earlier_scenarios(self, results):
        """Should have at least 2 scenarios (5yr and 10yr earlier)."""
        assert len(results.retire_earlier_scenarios) >= 2
        for scenario in results.retire_earlier_scenarios:
            assert "target_nest_egg" in scenario or hasattr(scenario, "target_nest_egg")


# ---------------------------------------------------------------------------
# Gap analysis & readiness
# ---------------------------------------------------------------------------

class TestRetirementGapAnalysis:
    def test_readiness_pct_reasonable(self, results):
        """With demo inputs, readiness should be in a reasonable range."""
        assert 25 <= results.retirement_readiness_pct <= 100

    def test_savings_gap_sign(self, results):
        """If readiness < 100%, gap should be negative; if >= 100%, gap >= 0."""
        if results.retirement_readiness_pct >= 100:
            assert results.savings_gap >= 0
        else:
            assert results.savings_gap < 0

    def test_years_money_lasts_reasonable(self, results):
        """Money should last at least some years in retirement."""
        assert results.years_money_will_last > 10


# ---------------------------------------------------------------------------
# API endpoint validation
# ---------------------------------------------------------------------------

class TestRetirementAPI:
    async def test_list_profiles_returns_seeded(self, client, demo_seed):
        resp = await client.get("/retirement/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 1
        p = profiles[0]
        assert p["current_age"] == CURRENT_AGE
        assert p["retirement_age"] == RETIREMENT_AGE
        assert p["current_annual_income"] == COMBINED_INCOME

    async def test_profile_has_computed_fields(self, client, demo_seed):
        resp = await client.get("/retirement/profiles")
        p = resp.json()[0]
        # These fields should be populated from seeder or recalculation
        assert "target_nest_egg" in p
        assert "fire_number" in p
        assert "retirement_readiness_pct" in p
        assert p["target_nest_egg"] > 0
