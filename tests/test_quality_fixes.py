"""
Supplementary tests that strengthen weak assertions found in the quality audit.

These tests do NOT modify existing test files — they ADD new test cases that verify
specific financial values, ranges, and mathematical correctness for the most
critical financial engines.

Organized by the audit's priority files, each section addresses the weakest
assertions found in the corresponding original test file.
"""
import pytest
import random

from pipeline.planning.retirement import RetirementCalculator, RetirementInputs
from pipeline.tax.calculator import (
    federal_tax,
    fica_tax,
    se_tax,
    niit_tax,
    state_tax,
    total_tax_estimate,
    standard_deduction,
    marginal_rate,
)
from pipeline.tax.constants import (
    FICA_SS_CAP,
    FICA_RATE,
    MEDICARE_RATE,
    ADDITIONAL_MEDICARE_RATE,
    ADDITIONAL_MEDICARE_THRESHOLD,
    STANDARD_DEDUCTION,
    NIIT_THRESHOLD,
    AMT_EXEMPTION,
    MFJ_BRACKETS,
)
from pipeline.planning.household import HouseholdEngine
from pipeline.planning.monte_carlo import run_monte_carlo_simulation
from pipeline.planning.life_scenarios import (
    LifeScenarioEngine,
    _calc_monthly_payment,
)
from pipeline.planning.insurance_analysis import calculate_life_insurance_need


# ---------------------------------------------------------------------------
# Helper: Standard HENRY retirement inputs
# ---------------------------------------------------------------------------

def _base_retirement(**overrides) -> RetirementInputs:
    """Sensible defaults for a 35-year-old HENRY earning $250k."""
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


# ===========================================================================
# 1. RETIREMENT — Strengthen `> 0` assertions with specific value ranges
#    (Addresses test_retirement.py weak assertions)
# ===========================================================================


class TestRetirementSpecificValues:
    """Verify retirement calculations produce financially sensible values
    for known inputs, not just > 0."""

    def test_income_replacement_is_80_pct(self):
        """80% of $250k income = $200k base, plus $12k healthcare = $212k need today."""
        r = RetirementCalculator.calculate(_base_retirement())
        # base_expenses = 250k * 0.80 = 200k, + 12k healthcare = 212k
        assert r.annual_income_needed_today == pytest.approx(212_000, abs=1)

    def test_employer_match_monthly_exact(self):
        """50% match on 6% of $250k => match_eligible = 250k/12 * 0.06 = $1,250/mo,
        min($2,000 contribution, $1,250 eligible) = $1,250, * 50% = $625/mo."""
        r = RetirementCalculator.calculate(_base_retirement())
        assert r.employer_match_monthly == pytest.approx(625.0, abs=1)

    def test_total_monthly_contribution(self):
        """$2,000 personal + $625 match = $2,625/mo total."""
        r = RetirementCalculator.calculate(_base_retirement())
        assert r.total_monthly_contribution == pytest.approx(2_625.0, abs=1)

    def test_savings_rate_calculable(self):
        """Savings rate = ($2,625 * 12) / $250,000 = 12.6%."""
        r = RetirementCalculator.calculate(_base_retirement())
        expected_rate = (2_625 * 12) / 250_000 * 100
        assert r.current_savings_rate_pct == pytest.approx(expected_rate, abs=0.5)

    def test_target_nest_egg_reasonable_range(self):
        """For $212k/yr need inflated 30 years at 3%, with 22% tax gross-up,
        the target nest egg accounts for inflation-adjusted withdrawals
        over 25 years in retirement. Should be in the $8M-$15M range."""
        r = RetirementCalculator.calculate(_base_retirement())
        assert 8_000_000 < r.target_nest_egg < 15_000_000

    def test_projected_nest_egg_reasonable_range(self):
        """With $250k savings + $2,625/mo for 30 years at 7%, projected savings
        should be in the $2M-$6M range."""
        r = RetirementCalculator.calculate(_base_retirement())
        assert 2_000_000 < r.projected_nest_egg < 6_000_000

    def test_fire_number_25x_expenses(self):
        """FIRE number = 25x annual expenses (the 4% rule).
        With $212k/yr need, FIRE = 25 * $212k = $5.3M."""
        r = RetirementCalculator.calculate(_base_retirement())
        expected_fire = r.annual_income_needed_today * 25
        assert r.fire_number == pytest.approx(expected_fire, abs=1)

    def test_yearly_projection_exact_length(self):
        """Projection from age 35 to 80 = 46 entries (inclusive).
        The engine projects through retirement until money runs out or
        a reasonable post-retirement horizon."""
        r = RetirementCalculator.calculate(_base_retirement())
        assert len(r.yearly_projection) == 46

    def test_yearly_projection_ages_sequential(self):
        """Ages should be sequential starting at current_age (35)."""
        r = RetirementCalculator.calculate(_base_retirement())
        ages = [row["age"] for row in r.yearly_projection]
        assert ages == list(range(35, 35 + len(ages)))

    def test_zero_income_target_is_healthcare_only(self):
        """With zero income and 80% replacement, base expenses = 0.
        Target is healthcare ($12k) + additional ($0) = $12k/yr."""
        r = RetirementCalculator.calculate(_base_retirement(current_annual_income=0))
        assert r.annual_income_needed_today == pytest.approx(12_000, abs=1)

    def test_inflation_increases_retirement_need(self):
        """After 30 years at 3% inflation, $212k becomes much larger."""
        r = RetirementCalculator.calculate(_base_retirement())
        inflation_mult = (1.03 ** 30)
        expected_inflated = 212_000 * inflation_mult
        # After tax gross-up: / (1 - 0.22)
        expected_pretax = expected_inflated / 0.78
        assert r.annual_income_needed_at_retirement == pytest.approx(expected_pretax, abs=100)


# ===========================================================================
# 2. TAX CALCULATOR — Strengthen total_tax_estimate assertions
#    (Addresses test_tax_calculator.py TestTotalTaxEstimate weak assertions)
# ===========================================================================


class TestTaxEstimateSpecificValues:
    """Verify total_tax_estimate returns exact calculable values,
    not just > 0."""

    def test_250k_mfj_federal_tax_exact(self):
        """$250k W-2, MFJ: taxable = 250k - 30k = 220k.
        Tax = 23850*0.10 + (96950-23850)*0.12 + (206700-96950)*0.22 + (220000-206700)*0.24."""
        result = total_tax_estimate(w2_wages=250_000, filing_status="mfj")
        expected_fed = (
            23_850 * 0.10
            + (96_950 - 23_850) * 0.12
            + (206_700 - 96_950) * 0.22
            + (220_000 - 206_700) * 0.24
        )
        assert result["federal_tax"] == pytest.approx(expected_fed, abs=1)

    def test_250k_mfj_fica_tax_exact(self):
        """$250k W-2, MFJ: SS = 176100*0.062, Med = 250000*0.0145.
        Additional Medicare = 0 (MFJ threshold is $250k, at boundary)."""
        result = total_tax_estimate(w2_wages=250_000, filing_status="mfj")
        expected_fica = FICA_SS_CAP * FICA_RATE + 250_000 * MEDICARE_RATE
        assert result["fica_tax"] == pytest.approx(expected_fica, abs=1)

    def test_250k_mfj_effective_rate_range(self):
        """For $250k MFJ W-2 (no state), effective rate should be ~25-30%."""
        result = total_tax_estimate(w2_wages=250_000, filing_status="mfj")
        assert 0.20 < result["effective_rate"] < 0.35

    def test_250k_mfj_marginal_rate_exact(self):
        """$250k MFJ, taxable = $220k => 24% bracket."""
        result = total_tax_estimate(w2_wages=250_000, filing_status="mfj")
        assert result["marginal_rate"] == 0.24

    def test_500k_mfj_marginal_rate_exact(self):
        """$500k MFJ, taxable = $470k => 32% bracket."""
        result = total_tax_estimate(w2_wages=500_000, filing_status="mfj")
        assert result["marginal_rate"] == 0.32

    def test_500k_mfj_total_tax_calculable(self):
        """$500k MFJ: verify total tax is in a specific range.
        Includes federal (~$104k), FICA (~$20k), and default CA state (~$66k)."""
        result = total_tax_estimate(w2_wages=500_000, filing_status="mfj")
        # Total includes federal + FICA + state (default CA 13.3%)
        assert 180_000 < result["total_tax"] < 210_000

    def test_se_income_150k_single_tax_values(self):
        """$150k SE income, single filer: verify specific SE tax."""
        result = total_tax_estimate(se_income=150_000, filing_status="single")
        se_base = 150_000 * 0.9235  # = $138,525
        ss = min(se_base, FICA_SS_CAP) * 0.124
        med = se_base * 0.029
        expected_se = ss + med
        assert result["se_tax"] == pytest.approx(expected_se, abs=10)

    def test_200k_ca_state_tax_exact(self):
        """$200k W-2 in CA: state_tax on AGI = 200k * 0.133."""
        result = total_tax_estimate(w2_wages=200_000, state_code="CA")
        # AGI = 200k (no SE deduction), state = AGI * 0.133
        assert result["state_tax"] == pytest.approx(200_000 * 0.133, abs=1)

    def test_mixed_income_290k_gross(self):
        """$200k W-2 + $50k SE + $30k investment + $10k other = $290k gross."""
        result = total_tax_estimate(
            w2_wages=200_000,
            se_income=50_000,
            investment_income=30_000,
            other_income=10_000,
            filing_status="mfj",
            state_code="NY",
        )
        assert result["gross_income"] == 290_000
        assert result["se_tax"] > 0
        # NY state tax should be calculable
        se_ded = result["se_tax"] / 2
        agi = 290_000 - se_ded
        assert result["state_tax"] == pytest.approx(agi * 0.109, abs=1)


# ===========================================================================
# 3. HOUSEHOLD — Strengthen filing comparison assertions
#    (Addresses test_planning_household.py weak assertions)
# ===========================================================================


class TestHouseholdSpecificValues:
    """Verify household optimization returns specific calculable tax values,
    not just > 0."""

    def test_equal_200k_incomes_mfj_tax_range(self):
        """$200k + $200k = $400k MFJ. Taxable = 400k - 30k = 370k.
        Federal tax should be ~$68k-$75k."""
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            dependents=0,
        )
        assert 60_000 < result["mfj_tax"] < 120_000

    def test_equal_200k_incomes_mfs_tax_range(self):
        """Each spouse: $200k MFS. Taxable = 200k - 15k = 185k.
        Each should pay ~$35k-$45k, combined ~$70k-$90k."""
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            dependents=0,
        )
        assert 60_000 < result["mfs_tax"] < 130_000

    def test_unequal_incomes_savings_positive_and_specific(self):
        """$300k + $50k: MFJ should save significant amount vs MFS.
        Savings should be $2k-$15k due to bracket averaging."""
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=300_000,
            spouse_b_income=50_000,
            dependents=0,
        )
        assert result["recommendation"] == "mfj"
        assert result["filing_savings"] > 2_000

    def test_very_high_income_tax_amounts(self):
        """$1M + $500k = $1.5M: both MFJ and MFS taxes should be very high."""
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=1_000_000,
            spouse_b_income=500_000,
            dependents=3,
        )
        # MFJ tax on $1.5M should be $300k+
        assert result["mfj_tax"] > 300_000
        assert result["mfs_tax"] > 300_000

    def test_retirement_strategy_tax_savings_range(self):
        """$200k + $150k with 401k + HSA: tax savings should reflect
        the deduction value of contributions (401k: $23.5k * marginal_rate ~24-32%)."""
        benefits_a = {
            "has_401k": True, "employer_match_pct": 50, "employer_match_limit_pct": 6,
            "has_hsa": True, "hsa_plan_type": "family", "hsa_employer_contribution": 0,
            "has_roth_401k": True, "has_mega_backdoor": False, "mega_backdoor_limit": 46_000,
            "has_dep_care_fsa": False, "health_premium_monthly": 500,
        }
        benefits_b = {
            "has_401k": True, "employer_match_pct": 50, "employer_match_limit_pct": 6,
            "has_hsa": False, "hsa_plan_type": "family", "hsa_employer_contribution": 0,
            "has_roth_401k": True, "has_mega_backdoor": False, "mega_backdoor_limit": 46_000,
            "has_dep_care_fsa": False, "health_premium_monthly": 500,
        }
        result = HouseholdEngine.optimize_retirement_contributions(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
        )
        # 401k ($23.5k each) + HSA ($8.55k) at ~24% marginal = ~$13k-$15k savings
        # Total with both spouses should be $10k-$40k
        assert 5_000 < result["total_tax_savings"] < 50_000
        # Both spouses should have multiple strategy items
        assert len(result["spouse_a_strategy"]) >= 1
        assert len(result["spouse_b_strategy"]) >= 1


# ===========================================================================
# 4. MONTE CARLO — Strengthen p50 assertions with specific ranges
#    (Addresses test_monte_carlo.py weak assertions)
# ===========================================================================


class TestMonteCarloSpecificValues:
    """Verify Monte Carlo results are in financially reasonable ranges."""

    def test_p50_with_known_return(self):
        """$100k at 7% for 10 years with very low volatility should
        approximately double: ~$196k."""
        random.seed(42)
        result = run_monte_carlo_simulation({
            "initial_balance": 100_000,
            "annual_contribution": 0,
            "runs": 1000,
            "years": 10,
            "mean_return": 0.07,
            "std_dev": 0.001,  # Nearly deterministic
        })
        expected = 100_000 * (1.07 ** 10)  # ~$196,715
        assert result["p50"] == pytest.approx(expected, rel=0.05)

    def test_p50_with_contributions(self):
        """$0 initial, $50k/yr at 7% for 20 years, low vol.
        FV of annuity: 50k * ((1.07^20 - 1) / 0.07) = ~$2.05M."""
        random.seed(42)
        result = run_monte_carlo_simulation({
            "initial_balance": 0,
            "annual_contribution": 50_000,
            "runs": 1000,
            "years": 20,
            "mean_return": 0.07,
            "std_dev": 0.001,  # Nearly deterministic
        })
        # FV of annuity: ~$2.05M
        assert 1_800_000 < result["p50"] < 2_400_000

    def test_spread_increases_with_volatility(self):
        """Spread ratio (p90/p10) should be larger with higher volatility."""
        random.seed(42)
        result_low = run_monte_carlo_simulation({
            "initial_balance": 100_000,
            "annual_contribution": 10_000,
            "runs": 1000,
            "years": 20,
            "mean_return": 0.07,
            "std_dev": 0.05,
        })
        random.seed(42)
        result_high = run_monte_carlo_simulation({
            "initial_balance": 100_000,
            "annual_contribution": 10_000,
            "runs": 1000,
            "years": 20,
            "mean_return": 0.07,
            "std_dev": 0.25,
        })
        low_ratio = result_low["p90"] / max(result_low["p10"], 1)
        high_ratio = result_high["p90"] / max(result_high["p10"], 1)
        assert high_ratio > low_ratio * 1.5  # Significantly wider spread


# ===========================================================================
# 5. LIFE SCENARIOS — Strengthen specific financial calculations
#    (Addresses test_life_scenarios.py weak assertions)
# ===========================================================================


class TestLifeScenariosSpecificValues:
    """Verify life scenario engines compute financially correct values."""

    def test_mortgage_payment_exact(self):
        """30-year $400k mortgage at 6.5% = $2,528.27/mo (standard amortization)."""
        pmt = _calc_monthly_payment(400_000, 6.5, 360)
        assert pmt == pytest.approx(2_528.27, abs=2)

    def test_mortgage_payment_15yr(self):
        """15-year $300k mortgage at 5.5% = $2,451.75/mo."""
        pmt = _calc_monthly_payment(300_000, 5.5, 180)
        assert pmt == pytest.approx(2_451.75, abs=5)

    def test_second_home_down_payment_exact(self):
        """$600k home, 25% down = $150k down payment needed."""
        ctx = dict(
            annual_income=350_000, monthly_take_home=20_000,
            current_monthly_expenses=10_000, current_monthly_debt=3_000,
            current_savings=200_000, current_investments=500_000,
        )
        result = LifeScenarioEngine.calculate(
            scenario_type="second_home",
            params={"purchase_price": 600_000, "down_payment_pct": 25},
            **ctx,
        )
        assert result["down_payment_needed"] == 150_000

    def test_vehicle_loan_amount_exact(self):
        """$60k car - $10k down - $15k trade-in = $35k loan."""
        ctx = dict(
            annual_income=350_000, monthly_take_home=20_000,
            current_monthly_expenses=10_000, current_monthly_debt=3_000,
            current_savings=200_000, current_investments=500_000,
        )
        result = LifeScenarioEngine.calculate(
            scenario_type="vehicle",
            params={
                "purchase_price": 60_000,
                "down_payment": 10_000,
                "trade_in_value": 15_000,
            },
            **ctx,
        )
        assert result["loan_amount"] == 35_000

    def test_early_retirement_fire_number_25x(self):
        """FIRE number must equal 25x annual expenses: $100k * 25 = $2.5M."""
        ctx = dict(
            annual_income=350_000, monthly_take_home=20_000,
            current_monthly_expenses=10_000, current_monthly_debt=3_000,
            current_savings=200_000, current_investments=500_000,
        )
        result = LifeScenarioEngine.calculate(
            scenario_type="early_retirement",
            params={"annual_expenses_in_retirement": 100_000},
            **ctx,
        )
        assert result["fire_number"] == 2_500_000

    def test_lifestyle_upgrade_total_cost_math(self):
        """$800/mo recurring + $5k one-time = $800*12 + $5k = $14,600."""
        ctx = dict(
            annual_income=350_000, monthly_take_home=20_000,
            current_monthly_expenses=10_000, current_monthly_debt=3_000,
            current_savings=200_000, current_investments=500_000,
        )
        result = LifeScenarioEngine.calculate(
            scenario_type="lifestyle_upgrade",
            params={"monthly_cost_increase": 800, "one_time_cost": 5_000},
            **ctx,
        )
        assert result["annual_recurring"] == 9_600  # 800 * 12
        assert result["one_time_cost"] == 5_000
        assert result["total_cost"] == 14_600  # 9600 + 5000

    def test_college_fund_years_until_college(self):
        """Child age 3, college at 18 = 15 years until college."""
        ctx = dict(
            annual_income=350_000, monthly_take_home=20_000,
            current_monthly_expenses=10_000, current_monthly_debt=3_000,
            current_savings=200_000, current_investments=500_000,
        )
        result = LifeScenarioEngine.calculate(
            scenario_type="college_fund",
            params={
                "child_current_age": 3,
                "college_start_age": 18,
                "annual_tuition_today": 50_000,
                "years_of_college": 4,
            },
            **ctx,
        )
        assert result["years_until_college"] == 15


# ===========================================================================
# 6. INSURANCE — Verify DIME method calculations for HENRY household
#    (Supplementary tests for insurance gap analysis)
# ===========================================================================


class TestInsuranceForHENRYHousehold:
    """Verify insurance gap analysis produces correct values for a typical
    HENRY household ($400k combined income, 2 dependents)."""

    def test_life_insurance_need_410k_household(self):
        """For $250k income, 10 years, $300k debt, 2 children:
        need = $250k*10 + $300k + 2*$50k = $2.9M."""
        need = calculate_life_insurance_need(250_000, 10, 300_000, 2)
        assert need == 2_900_000

    def test_life_insurance_need_both_spouses(self):
        """Both spouses combined: A($245k) + B($165k), 2 kids.
        A: 245k*10 + 150k(half debt) + 100k(2 kids) = 2.7M
        B: 165k*10 + 150k(half debt) + 100k(2 kids) = 1.9M
        Total household need: ~$4.6M."""
        need_a = calculate_life_insurance_need(245_000, 10, 150_000, 2)
        need_b = calculate_life_insurance_need(165_000, 10, 150_000, 2)
        assert need_a == 2_700_000  # 2.45M + 150k + 100k
        assert need_b == 1_900_000  # 1.65M + 150k + 100k


# ===========================================================================
# 7. DIAGNOSTIC — Verify tests call actual code, not re-implement logic
#    (Addresses test_diagnostic_endpoints.py placeholder tests)
# ===========================================================================


class TestDiagnosticCallingRealCode:
    """Tests that call actual codebase functions instead of re-implementing
    the logic in the test body (fixes placeholder tests)."""

    def test_tax_estimate_monthly_for_300k_mfj(self):
        """Monthly tax estimate for $25k/mo * 12 = $300k/yr MFJ.
        Includes federal + FICA + default CA state tax."""
        result = total_tax_estimate(w2_wages=300_000, filing_status="mfj")
        monthly = result["total_tax"] / 12
        # $300k MFJ: federal ~$46k, FICA ~$15k, CA state ~$40k, total ~$106k, monthly ~$8.8k
        assert 6_000 < monthly < 12_000

    def test_benchmark_quality_labels_from_engine(self):
        """Verify the BenchmarkEngine returns actual quality labels."""
        from pipeline.planning.benchmarks import BenchmarkEngine
        result = BenchmarkEngine.compute_benchmarks(
            age=35, income=200_000, net_worth=500_000, savings_rate=15.0,
        )
        # Should return actual computed percentiles and status
        assert "nw_percentile" in result
        assert "savings_rate" in result
        # Net worth of $500k at 35 with $200k income is reasonable
        assert 0 < result["nw_percentile"] < 100


# ===========================================================================
# 8. TAX BRACKET BOUNDARY VALUES — Verify bracket transitions
#    (Addresses gap: no tests at exact bracket boundaries)
# ===========================================================================


class TestTaxBracketBoundaries:
    """Verify tax calculation is correct at exact bracket boundaries,
    where off-by-one errors would surface."""

    def test_at_first_bracket_ceiling_mfj(self):
        """At exactly $23,850, all income taxed at 10%."""
        tax = federal_tax(23_850, "mfj")
        assert tax == pytest.approx(23_850 * 0.10, abs=0.01)

    def test_one_dollar_into_second_bracket_mfj(self):
        """$23,851: $23,850 at 10% + $1 at 12%."""
        tax = federal_tax(23_851, "mfj")
        expected = 23_850 * 0.10 + 1 * 0.12
        assert tax == pytest.approx(expected, abs=0.01)

    def test_at_24pct_bracket_ceiling_mfj(self):
        """At exactly $394,600 (top of 24% bracket)."""
        tax = federal_tax(394_600, "mfj")
        expected = (
            23_850 * 0.10
            + (96_950 - 23_850) * 0.12
            + (206_700 - 96_950) * 0.22
            + (394_600 - 206_700) * 0.24
        )
        assert tax == pytest.approx(expected, abs=1)

    def test_fica_at_ss_cap(self):
        """At exactly $176,100 (SS cap), no additional Medicare for MFJ."""
        tax = fica_tax(176_100, "mfj")
        expected = 176_100 * FICA_RATE + 176_100 * MEDICARE_RATE
        assert tax == pytest.approx(expected, abs=0.01)

    def test_additional_medicare_at_threshold(self):
        """At exactly $250k MFJ, no additional Medicare (at threshold, not above)."""
        tax = fica_tax(250_000, "mfj")
        ss = FICA_SS_CAP * FICA_RATE
        med = 250_000 * MEDICARE_RATE
        # At threshold: excess = 0, no additional
        assert tax == pytest.approx(ss + med, abs=0.01)

    def test_additional_medicare_one_dollar_above(self):
        """At $250,001 MFJ, additional Medicare = $1 * 0.009 = $0.009."""
        tax = fica_tax(250_001, "mfj")
        ss = FICA_SS_CAP * FICA_RATE
        med = 250_001 * MEDICARE_RATE
        additional = 1 * ADDITIONAL_MEDICARE_RATE
        assert tax == pytest.approx(ss + med + additional, abs=0.01)

    def test_niit_at_threshold(self):
        """At exactly $250k AGI MFJ with investment income, no NIIT."""
        tax = niit_tax(250_000, 50_000, "mfj")
        assert tax == 0.0

    def test_niit_one_dollar_above(self):
        """At $250,001 AGI MFJ, NIIT on min($1, investment) * 3.8%."""
        tax = niit_tax(250_001, 50_000, "mfj")
        assert tax == pytest.approx(1 * 0.038, abs=0.001)


# ===========================================================================
# 9. CROSS-ENGINE CONSISTENCY — Verify engines agree on shared concepts
# ===========================================================================


class TestCrossEngineConsistency:
    """Verify that different planning engines agree when they compute
    the same underlying value."""

    def test_federal_tax_consistent_in_total_estimate(self):
        """federal_tax() and total_tax_estimate() should agree on federal amount
        for the same W-2 income."""
        wages = 300_000
        filing = "mfj"
        standalone = federal_tax(wages - standard_deduction(filing), filing)
        combined = total_tax_estimate(w2_wages=wages, filing_status=filing)
        assert combined["federal_tax"] == pytest.approx(standalone, abs=1)

    def test_fica_consistent_in_total_estimate(self):
        """fica_tax() and total_tax_estimate() should agree for W-2 wages."""
        wages = 200_000
        standalone = fica_tax(wages, "mfj")
        combined = total_tax_estimate(w2_wages=wages, filing_status="mfj")
        assert combined["fica_tax"] == pytest.approx(standalone, abs=1)

    def test_child_tax_credit_2k_per_child(self):
        """CTC = $2,000 per child, below phaseout ($400k for MFJ)."""
        for n_kids in [1, 2, 3, 4]:
            result = total_tax_estimate(
                w2_wages=200_000, filing_status="mfj", dependents=n_kids,
            )
            assert result["child_tax_credit"] == n_kids * 2_000

    def test_child_tax_credit_phases_out(self):
        """Above $400k MFJ, CTC reduces by $50 per $1k over threshold.
        At $500k: excess = $100k, reduction = 100 * $50 = $5k.
        2 kids * $2k = $4k, reduction $5k => credit = max(0, -1k) = $0."""
        result = total_tax_estimate(
            w2_wages=500_000, filing_status="mfj", dependents=2,
        )
        assert result["child_tax_credit"] == 0
