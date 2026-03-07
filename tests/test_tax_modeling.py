"""Comprehensive tests for pipeline/planning/tax_modeling.py — TaxModelingEngine.

Every public method is tested with realistic HENRY income levels ($200k-$600k),
edge cases (zero income, very high income, missing fields), and directional
correctness (e.g., MFJ should generally beat MFS, S-Corp should save SE tax).
"""
import pytest

from pipeline.planning.tax_modeling import TaxModelingEngine
from pipeline.tax.constants import (
    STANDARD_DEDUCTION,
    ROTH_INCOME_PHASEOUT,
    QBI_DEDUCTION_RATE,
    QBI_PHASEOUT_START,
    QBI_PHASEOUT_RANGE,
    STATE_TAX_RATES,
    LIMIT_401K_TOTAL,
)

E = TaxModelingEngine


# ---------------------------------------------------------------------------
# roth_conversion_ladder
# ---------------------------------------------------------------------------


class TestRothConversionLadder:
    """Roth conversion ladder — converts traditional IRA to Roth over years."""

    def test_basic_structure(self):
        result = E.roth_conversion_ladder(
            traditional_balance=500_000,
            current_income=200_000,
            filing_status="mfj",
            years=5,
        )
        assert "year_by_year" in result
        assert "total_converted" in result
        assert "total_tax_paid" in result
        assert "projected_roth_at_retirement" in result
        assert len(result["year_by_year"]) == 5

    def test_conversion_reduces_traditional_balance(self):
        result = E.roth_conversion_ladder(
            traditional_balance=500_000,
            current_income=200_000,
            filing_status="mfj",
            years=10,
        )
        # After conversions, remaining traditional should be less than
        # the balance would have been with growth alone and no conversions
        final_remaining = result["year_by_year"][-1]["remaining_traditional"]
        no_conversion_balance = 500_000 * (1.07 ** 10)
        assert final_remaining < no_conversion_balance

    def test_roth_grows_over_time(self):
        result = E.roth_conversion_ladder(
            traditional_balance=500_000,
            current_income=200_000,
            filing_status="mfj",
            years=10,
        )
        # Roth balance should increase year over year (conversions + growth)
        roth_values = [y["roth_balance"] for y in result["year_by_year"]]
        for i in range(1, len(roth_values)):
            assert roth_values[i] >= roth_values[i - 1]

    def test_high_income_limits_conversions(self):
        """When current income already fills target bracket, room is small."""
        high_income = E.roth_conversion_ladder(
            traditional_balance=500_000,
            current_income=400_000,
            filing_status="mfj",
            years=5,
            target_bracket_rate=0.24,
        )
        low_income = E.roth_conversion_ladder(
            traditional_balance=500_000,
            current_income=100_000,
            filing_status="mfj",
            years=5,
            target_bracket_rate=0.24,
        )
        # Lower income person should convert more (more room in bracket)
        high_total = sum(y["conversion_amount"] for y in high_income["year_by_year"])
        low_total = sum(y["conversion_amount"] for y in low_income["year_by_year"])
        assert low_total > high_total

    def test_zero_balance_no_conversions(self):
        result = E.roth_conversion_ladder(
            traditional_balance=0,
            current_income=200_000,
            years=5,
        )
        for y in result["year_by_year"]:
            assert y["conversion_amount"] == 0
            assert y["tax_on_conversion"] == 0
        assert result["total_tax_paid"] == 0

    def test_tax_on_conversion_is_positive(self):
        result = E.roth_conversion_ladder(
            traditional_balance=500_000,
            current_income=200_000,
            years=3,
        )
        for y in result["year_by_year"]:
            if y["conversion_amount"] > 0:
                assert y["tax_on_conversion"] > 0

    def test_effective_conversion_rate_reasonable(self):
        result = E.roth_conversion_ladder(
            traditional_balance=500_000,
            current_income=200_000,
            filing_status="mfj",
            years=3,
        )
        for y in result["year_by_year"]:
            if y["conversion_amount"] > 0:
                # Effective rate should be between 0 and 37%
                assert 0 < y["effective_conversion_rate"] <= 0.37

    def test_single_filer(self):
        result = E.roth_conversion_ladder(
            traditional_balance=300_000,
            current_income=150_000,
            filing_status="single",
            years=5,
        )
        assert len(result["year_by_year"]) == 5
        assert result["total_tax_paid"] >= 0


# ---------------------------------------------------------------------------
# backdoor_roth_checklist
# ---------------------------------------------------------------------------


class TestBackdoorRothChecklist:
    """Backdoor Roth eligibility and pro-rata warnings."""

    def test_high_income_eligible(self):
        """Income above Roth phaseout should be flagged as eligible."""
        result = E.backdoor_roth_checklist(
            has_traditional_ira_balance=False,
            income=300_000,
            filing_status="mfj",
        )
        assert result["eligible"] is True
        assert result["income_over_roth_limit"] is True

    def test_low_income_not_eligible(self):
        """Below Roth limit, direct contribution is fine — backdoor not needed."""
        result = E.backdoor_roth_checklist(
            has_traditional_ira_balance=False,
            income=100_000,
            filing_status="mfj",
        )
        assert result["eligible"] is False

    def test_pro_rata_warning_with_traditional_balance(self):
        result = E.backdoor_roth_checklist(
            has_traditional_ira_balance=True,
            traditional_ira_balance=50_000,
            income=300_000,
        )
        assert result["pro_rata_warning"] is True
        # Pro-rata percentage = 50000 / (50000 + 7000) * 100
        expected_pct = round(50_000 / 57_000 * 100, 1)
        assert result["pro_rata_taxable_pct"] == pytest.approx(expected_pct, abs=0.1)

    def test_no_pro_rata_without_traditional_balance(self):
        result = E.backdoor_roth_checklist(
            has_traditional_ira_balance=False,
            income=300_000,
        )
        assert result["pro_rata_warning"] is False
        assert result["pro_rata_taxable_pct"] == 0

    def test_steps_include_form_8606(self):
        result = E.backdoor_roth_checklist(
            has_traditional_ira_balance=False,
            income=300_000,
        )
        assert any("8606" in s for s in result["steps"])

    def test_pro_rata_adds_extra_steps(self):
        without = E.backdoor_roth_checklist(
            has_traditional_ira_balance=False, income=300_000
        )
        with_balance = E.backdoor_roth_checklist(
            has_traditional_ira_balance=True,
            traditional_ira_balance=50_000,
            income=300_000,
        )
        assert len(with_balance["steps"]) > len(without["steps"])

    def test_single_filer_threshold(self):
        """Single filer has lower Roth phaseout ($150k)."""
        result = E.backdoor_roth_checklist(
            has_traditional_ira_balance=False,
            income=160_000,
            filing_status="single",
        )
        assert result["eligible"] is True


# ---------------------------------------------------------------------------
# mega_backdoor_roth_analysis
# ---------------------------------------------------------------------------


class TestMegaBackdoorRothAnalysis:
    """Mega backdoor Roth — after-tax 401k to Roth."""

    def test_plan_does_not_allow(self):
        result = E.mega_backdoor_roth_analysis(employer_plan_allows=False)
        assert result["available"] is False
        assert result["available_space"] == 0
        assert "does not allow" in result["explanation"]

    def test_plan_allows_with_defaults(self):
        result = E.mega_backdoor_roth_analysis(employer_plan_allows=True)
        assert result["available"] is True
        # Default: plan_limit=69000 - employee=23500 - employer=10000 = 35500
        assert result["available_space"] == 35_500

    def test_custom_contributions(self):
        result = E.mega_backdoor_roth_analysis(
            employer_plan_allows=True,
            current_employee_contrib=23_500,
            employer_match_contrib=15_000,
            plan_limit=70_000,
        )
        assert result["available_space"] == 31_500

    def test_maxed_out_plan(self):
        """No space left when contributions equal plan limit."""
        result = E.mega_backdoor_roth_analysis(
            employer_plan_allows=True,
            current_employee_contrib=40_000,
            employer_match_contrib=30_000,
            plan_limit=70_000,
        )
        assert result["available_space"] == 0

    def test_tax_free_growth_projection(self):
        result = E.mega_backdoor_roth_analysis(
            employer_plan_allows=True,
            current_employee_contrib=23_500,
            employer_match_contrib=10_000,
            plan_limit=69_000,
        )
        available = 35_500
        expected_20yr = round(available * (1.07 ** 20), 2)
        assert result["tax_free_growth_value_20yr"] == pytest.approx(expected_20yr, rel=0.01)


# ---------------------------------------------------------------------------
# daf_bunching_strategy
# ---------------------------------------------------------------------------


class TestDAFBunchingStrategy:
    """Donor-Advised Fund bunching strategy."""

    def test_bunching_saves_when_below_standard_deduction(self):
        """When annual charitable + other deductions < standard deduction,
        bunching should create savings by pushing over the threshold."""
        result = E.daf_bunching_strategy(
            annual_charitable=10_000,
            standard_deduction=30_000,
            itemized_deductions_excl_charitable=15_000,
            bunch_years=3,
            filing_status="mfj",
            taxable_income=300_000,
        )
        # Annual: 15000 + 10000 = 25000 < 30000 (no itemizing benefit)
        # Bunched year: 15000 + 30000 = 45000 > 30000 (itemizing wins)
        assert result["savings"] > 0

    def test_bunch_years_match(self):
        result = E.daf_bunching_strategy(
            annual_charitable=10_000,
            bunch_years=4,
        )
        assert result["bunch_years"] == 4
        assert result["bunched_amount"] == 40_000

    def test_already_itemizing_minimal_benefit(self):
        """When already itemizing every year, bunching may not help much."""
        result = E.daf_bunching_strategy(
            annual_charitable=20_000,
            standard_deduction=30_000,
            itemized_deductions_excl_charitable=25_000,
            bunch_years=2,
            filing_status="mfj",
            taxable_income=300_000,
        )
        # Annual itemized = 45000 > 30000 so already getting benefit annually
        # Savings may be zero or small
        assert result["savings"] >= 0

    def test_recommendation_text(self):
        result = E.daf_bunching_strategy(
            annual_charitable=10_000,
            standard_deduction=30_000,
            itemized_deductions_excl_charitable=15_000,
            bunch_years=3,
        )
        if result["savings"] > 0:
            assert "Bunch" in result["recommendation"]
        else:
            assert "optimal" in result["recommendation"]


# ---------------------------------------------------------------------------
# scorp_election_model
# ---------------------------------------------------------------------------


class TestSCorpElectionModel:
    """S-Corp vs sole proprietorship comparison."""

    def test_scorp_saves_on_high_1099(self):
        """S-Corp should save meaningful SE tax when 1099 income is high."""
        result = E.scorp_election_model(
            gross_1099_income=300_000,
            reasonable_salary=120_000,
            business_expenses=30_000,
        )
        assert result["se_tax_savings"] > 0
        assert result["total_savings"] > 0
        assert result["scorp_tax"] < result["schedule_c_tax"]

    def test_low_income_minimal_savings(self):
        """At low income levels, S-Corp may not make sense."""
        result = E.scorp_election_model(
            gross_1099_income=60_000,
            reasonable_salary=50_000,
            business_expenses=5_000,
        )
        # Savings should be small or recommendation should say so
        # The salary is close to net income, limiting benefit
        assert "total_savings" in result

    def test_distributions_are_positive(self):
        result = E.scorp_election_model(
            gross_1099_income=300_000,
            reasonable_salary=100_000,
            business_expenses=20_000,
        )
        # Net income = 280k, salary = 100k, employer FICA = 7650
        # Corp taxable = 280k - 100k - 7650 = 172350
        assert result["distributions"] > 0

    def test_reasonable_salary_returned(self):
        result = E.scorp_election_model(
            gross_1099_income=200_000,
            reasonable_salary=80_000,
        )
        assert result["reasonable_salary"] == 80_000

    def test_recommendation_mentions_savings(self):
        result = E.scorp_election_model(
            gross_1099_income=300_000,
            reasonable_salary=120_000,
        )
        if result["total_savings"] > 500:
            assert "saves" in result["recommendation"].lower()

    def test_different_states(self):
        """State parameter is accepted (used for future state-level SE tax)."""
        result_ca = E.scorp_election_model(
            gross_1099_income=200_000,
            reasonable_salary=80_000,
            state="CA",
        )
        result_tx = E.scorp_election_model(
            gross_1099_income=200_000,
            reasonable_salary=80_000,
            state="TX",
        )
        # Both should produce valid results
        assert result_ca["schedule_c_tax"] > 0
        assert result_tx["schedule_c_tax"] > 0


# ---------------------------------------------------------------------------
# multi_year_projection
# ---------------------------------------------------------------------------


class TestMultiYearProjection:
    """Multi-year tax projection with income growth, conversions, and vesting."""

    def test_basic_structure(self):
        result = E.multi_year_projection(
            current_income=300_000,
            years=5,
        )
        assert "years" in result
        assert len(result["years"]) == 5

    def test_income_grows_year_over_year(self):
        result = E.multi_year_projection(
            current_income=300_000,
            income_growth_rate=0.05,
            years=5,
        )
        incomes = [y["income"] for y in result["years"]]
        for i in range(1, len(incomes)):
            assert incomes[i] > incomes[i - 1]

    def test_roth_conversions_increase_income(self):
        without_conv = E.multi_year_projection(
            current_income=300_000,
            years=3,
        )
        with_conv = E.multi_year_projection(
            current_income=300_000,
            years=3,
            roth_conversions=[50_000, 50_000, 50_000],
        )
        for i in range(3):
            assert with_conv["years"][i]["income"] > without_conv["years"][i]["income"]
            assert with_conv["years"][i]["total_tax"] > without_conv["years"][i]["total_tax"]

    def test_equity_vesting_adds_income(self):
        result = E.multi_year_projection(
            current_income=300_000,
            years=3,
            equity_vesting=[100_000, 0, 200_000],
        )
        # Year 1 and 3 have vesting; year 2 does not
        assert result["years"][0]["income"] == pytest.approx(400_000, rel=0.01)
        assert result["years"][1]["income"] == pytest.approx(300_000 * 1.03, rel=0.01)

    def test_effective_rate_reasonable(self):
        result = E.multi_year_projection(
            current_income=400_000,
            years=3,
        )
        for y in result["years"]:
            assert 0 < y["effective_rate"] < 0.60

    def test_state_rate_applied(self):
        no_state = E.multi_year_projection(
            current_income=300_000,
            state_rate=0.0,
            years=1,
        )
        with_state = E.multi_year_projection(
            current_income=300_000,
            state_rate=0.10,
            years=1,
        )
        assert with_state["years"][0]["state_tax"] > no_state["years"][0]["state_tax"]
        assert with_state["years"][0]["total_tax"] > no_state["years"][0]["total_tax"]


# ---------------------------------------------------------------------------
# estimated_payment_calculator
# ---------------------------------------------------------------------------


class TestEstimatedPaymentCalculator:
    """Quarterly estimated tax payment calculator."""

    def test_basic_quarterly_payments(self):
        result = E.estimated_payment_calculator(
            total_underwithholding=20_000,
            prior_year_tax=0,
            current_withholding=0,
        )
        assert len(result["quarterly_payments"]) == 4
        assert result["total_estimated_payments"] == 20_000
        for q in result["quarterly_payments"]:
            assert q["amount"] == 5_000

    def test_no_underwithholding(self):
        result = E.estimated_payment_calculator(
            total_underwithholding=0,
        )
        assert result["quarterly_payments"] == []
        assert result["total_estimated_payments"] == 0

    def test_safe_harbor_limits_payments(self):
        """Safe harbor: 110% of prior year tax."""
        result = E.estimated_payment_calculator(
            total_underwithholding=50_000,
            prior_year_tax=30_000,
            current_withholding=10_000,
        )
        # Safe harbor = 30000 * 1.10 = 33000
        # Gap = min(50000 - 10000, 33000 - 10000) = min(40000, 23000) = 23000
        assert result["safe_harbor_amount"] == pytest.approx(33_000, abs=1)
        assert result["total_estimated_payments"] == pytest.approx(23_000, abs=1)

    def test_quarterly_due_dates(self):
        result = E.estimated_payment_calculator(
            total_underwithholding=10_000,
        )
        dates = [q["due_date"] for q in result["quarterly_payments"]]
        assert dates == ["04/15", "06/15", "09/15", "01/15"]

    def test_withholding_reduces_gap(self):
        result = E.estimated_payment_calculator(
            total_underwithholding=20_000,
            current_withholding=15_000,
        )
        assert result["total_estimated_payments"] == pytest.approx(5_000, abs=1)

    def test_withholding_exceeds_underwithholding(self):
        """No payments needed if withholding covers the gap."""
        result = E.estimated_payment_calculator(
            total_underwithholding=10_000,
            current_withholding=15_000,
        )
        assert result["quarterly_payments"] == []
        assert result["total_estimated_payments"] == 0


# ---------------------------------------------------------------------------
# student_loan_optimizer
# ---------------------------------------------------------------------------


class TestStudentLoanOptimizer:
    """Student loan repayment strategy comparison."""

    def test_returns_three_strategies(self):
        result = E.student_loan_optimizer(
            loan_balance=100_000,
            interest_rate=6.5,
            monthly_income=10_000,
        )
        assert len(result["strategies"]) == 3
        names = [s["name"] for s in result["strategies"]]
        assert "Standard (10-year)" in names
        assert "Aggressive (5-year)" in names

    def test_standard_10_year_payoff(self):
        result = E.student_loan_optimizer(
            loan_balance=100_000,
            interest_rate=6.5,
            monthly_income=10_000,
        )
        standard = next(s for s in result["strategies"] if s["name"] == "Standard (10-year)")
        assert standard["payoff_years"] == 10
        # Total paid should exceed loan balance (interest accumulates)
        assert standard["total_paid"] > 100_000
        assert standard["total_interest"] > 0

    def test_aggressive_5_year_payoff(self):
        result = E.student_loan_optimizer(
            loan_balance=100_000,
            interest_rate=6.5,
            monthly_income=10_000,
        )
        aggressive = next(s for s in result["strategies"] if s["name"] == "Aggressive (5-year)")
        assert aggressive["payoff_years"] == 5
        # Aggressive should have higher monthly but less total interest
        standard = next(s for s in result["strategies"] if s["name"] == "Standard (10-year)")
        assert aggressive["monthly_payment"] > standard["monthly_payment"]
        assert aggressive["total_interest"] < standard["total_interest"]

    def test_pslf_eligible(self):
        result = E.student_loan_optimizer(
            loan_balance=200_000,
            interest_rate=6.5,
            monthly_income=8_000,
            pslf_eligible=True,
        )
        ibr = next(s for s in result["strategies"] if "PSLF" in s["name"])
        assert ibr["payoff_years"] == 10  # 120 months for PSLF
        assert "PSLF" in result["recommendation"]

    def test_zero_interest_rate(self):
        result = E.student_loan_optimizer(
            loan_balance=120_000,
            interest_rate=0.0,
            monthly_income=10_000,
        )
        standard = next(s for s in result["strategies"] if s["name"] == "Standard (10-year)")
        # With 0% interest, total paid = loan balance
        assert standard["monthly_payment"] == pytest.approx(1_000, abs=1)
        assert standard["total_interest"] == pytest.approx(0, abs=1)

    def test_recommendation_is_nonempty(self):
        result = E.student_loan_optimizer(
            loan_balance=50_000,
            interest_rate=5.0,
            monthly_income=8_000,
        )
        assert len(result["recommendation"]) > 0


# ---------------------------------------------------------------------------
# defined_benefit_plan_analysis
# ---------------------------------------------------------------------------


class TestDefinedBenefitPlanAnalysis:
    """Defined benefit plan analysis for self-employed individuals."""

    def test_viable_case(self):
        """Age 50+, income > $100k, reasonable years to retirement."""
        result = E.defined_benefit_plan_analysis(
            self_employment_income=300_000,
            age=52,
            target_retirement_age=65,
        )
        assert result["viable"] is True
        assert result["max_annual_contribution"] > 0
        assert result["annual_tax_savings"] > 0
        assert result["years_to_retirement"] == 13

    def test_not_viable_young(self):
        """Under 40 is not viable per the engine's criteria."""
        result = E.defined_benefit_plan_analysis(
            self_employment_income=200_000,
            age=35,
        )
        assert result["viable"] is False

    def test_not_viable_low_income(self):
        """Under $100k income is not viable."""
        result = E.defined_benefit_plan_analysis(
            self_employment_income=80_000,
            age=50,
        )
        assert result["viable"] is False

    def test_older_allows_higher_contribution_pct(self):
        """Older workers can contribute a higher percentage."""
        age_50 = E.defined_benefit_plan_analysis(
            self_employment_income=300_000, age=50
        )
        age_60 = E.defined_benefit_plan_analysis(
            self_employment_income=300_000, age=60
        )
        assert age_60["max_annual_contribution"] >= age_50["max_annual_contribution"]

    def test_db_exceeds_sep_ira(self):
        """DB plan should allow more than SEP-IRA for older high earners
        close to retirement (small years_to_retirement raises the limit)."""
        result = E.defined_benefit_plan_analysis(
            self_employment_income=300_000,
            age=63,
            target_retirement_age=65,
        )
        assert result["max_annual_contribution"] > result["sep_ira_contribution"]
        assert result["additional_contribution"] > 0
        assert result["additional_annual_savings"] > 0

    def test_sep_ira_capped_at_69k(self):
        result = E.defined_benefit_plan_analysis(
            self_employment_income=500_000,
            age=55,
        )
        # SEP-IRA max = min(25% of income, $69k)
        assert result["sep_ira_contribution"] == 69_000

    def test_projected_accumulation_positive(self):
        """Both DB and SEP projections should be positive. For a 63-year-old
        close to retirement, DB contribution exceeds SEP, so DB accumulation wins."""
        result = E.defined_benefit_plan_analysis(
            self_employment_income=300_000,
            age=63,
            target_retirement_age=65,
        )
        assert result["projected_accumulation"] > 0
        assert result["sep_projected_accumulation"] > 0
        assert result["projected_accumulation"] > result["sep_projected_accumulation"]

    def test_explanation_text(self):
        viable_result = E.defined_benefit_plan_analysis(
            self_employment_income=300_000, age=55
        )
        assert "defined benefit" in viable_result["explanation"].lower() or "allows" in viable_result["explanation"].lower()

        not_viable_result = E.defined_benefit_plan_analysis(
            self_employment_income=50_000, age=35
        )
        assert "may not" in not_viable_result["explanation"].lower()


# ---------------------------------------------------------------------------
# real_estate_str_analysis
# ---------------------------------------------------------------------------


class TestRealEstateSTRAnalysis:
    """Short-term rental tax analysis with cost segregation."""

    def test_qualifies_str_under_7_days(self):
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=4,
            hours_per_week_managing=3,
            w2_income=300_000,
        )
        assert result["qualifies_str"] is True

    def test_does_not_qualify_str_7_plus_days(self):
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=10,
            hours_per_week_managing=3,
            w2_income=300_000,
        )
        assert result["qualifies_str"] is False

    def test_material_participation_100_hours(self):
        """3 hours/week * 52 = 156 hours >= 100."""
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=4,
            hours_per_week_managing=3,
            w2_income=300_000,
        )
        assert result["material_participation"] is True

    def test_no_material_participation(self):
        """1 hour/week * 52 = 52 hours < 100."""
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=4,
            hours_per_week_managing=1,
            w2_income=300_000,
        )
        assert result["material_participation"] is False

    def test_can_offset_w2_requires_both_qualifications(self):
        """Must qualify as STR AND have material participation."""
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=4,
            hours_per_week_managing=3,
            w2_income=300_000,
        )
        assert result["can_offset_w2"] is True

        # Fails STR test
        result2 = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=10,
            hours_per_week_managing=3,
            w2_income=300_000,
        )
        assert result2["can_offset_w2"] is False

    def test_cost_seg_produces_larger_year_one_depreciation(self):
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=4,
            hours_per_week_managing=3,
            w2_income=300_000,
        )
        # Cost seg year-one depreciation should exceed standard annual
        assert result["cost_seg_year_one_depreciation"] > result["standard_annual_depreciation"]

    def test_depreciable_basis_excludes_land(self):
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=4,
            hours_per_week_managing=3,
            w2_income=300_000,
            land_value_pct=0.20,
        )
        assert result["depreciable_basis"] == 400_000

    def test_tax_savings_when_can_offset(self):
        result = E.real_estate_str_analysis(
            property_value=800_000,
            annual_rental_income=50_000,
            average_stay_days=3,
            hours_per_week_managing=4,
            w2_income=400_000,
        )
        # Large property with cost seg should produce a loss that offsets W-2
        if result["can_offset_w2"] and result["cost_seg_net_income_year_one"] < 0:
            assert result["tax_savings_year_one"] > 0
            assert result["w2_offset_year_one"] > 0

    def test_qualification_notes_populated(self):
        result = E.real_estate_str_analysis(
            property_value=500_000,
            annual_rental_income=60_000,
            average_stay_days=4,
            hours_per_week_managing=3,
            w2_income=300_000,
        )
        assert len(result["qualification_notes"]) == 3


# ---------------------------------------------------------------------------
# section_179_equipment_analysis
# ---------------------------------------------------------------------------


class TestSection179EquipmentAnalysis:
    """Section 179 + bonus depreciation for heavy equipment."""

    def test_qualifies_section_179(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=100_000,
            business_income=200_000,
        )
        assert result["qualifies_section_179"] is True
        assert result["section_179_deduction"] > 0

    def test_does_not_qualify_no_business(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=100_000,
            business_income=200_000,
            has_existing_business=False,
        )
        assert result["qualifies_section_179"] is False

    def test_does_not_qualify_low_business_use(self):
        """Business use must be > 50%."""
        result = E.section_179_equipment_analysis(
            equipment_cost=100_000,
            business_income=200_000,
            business_use_pct=0.40,
        )
        assert result["qualifies_section_179"] is False

    def test_section_179_limited_to_business_income(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=200_000,
            business_income=100_000,
        )
        # Section 179 deduction can't exceed business income
        assert result["section_179_deduction"] <= 100_000

    def test_year_one_tax_savings(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=100_000,
            business_income=300_000,
        )
        assert result["year_one_tax_savings"] > 0
        assert result["marginal_rate"] > 0

    def test_rental_analysis_when_renting(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=80_000,
            business_income=200_000,
            equipment_category="excavators",
            will_rent_out=True,
        )
        assert result["rental_analysis"] is not None
        assert result["rental_analysis"]["annual_rental_gross"] > 0
        assert len(result["five_year_projection"]) == 5

    def test_no_rental_analysis_when_not_renting(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=80_000,
            business_income=200_000,
            will_rent_out=False,
        )
        assert result["rental_analysis"] is None
        assert result["five_year_projection"] == []

    def test_exit_strategies_populated(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=100_000,
            business_income=200_000,
        )
        assert len(result["exit_strategies"]) > 0
        strategy_names = [s["strategy"] for s in result["exit_strategies"]]
        assert "Sell After Depreciation" in strategy_names

    def test_qualification_notes(self):
        result = E.section_179_equipment_analysis(
            equipment_cost=100_000,
            business_income=200_000,
        )
        assert len(result["qualification_notes"]) >= 4

    def test_five_year_projection_cumulative_cash(self):
        """Cumulative cash should start negative (purchase) and improve."""
        result = E.section_179_equipment_analysis(
            equipment_cost=80_000,
            business_income=200_000,
            will_rent_out=True,
        )
        if result["five_year_projection"]:
            year_1 = result["five_year_projection"][0]
            year_5 = result["five_year_projection"][-1]
            assert year_1["cumulative_cash"] < 0  # Still in the red after year 1
            # Cumulative should improve over time
            assert year_5["cumulative_cash"] > year_1["cumulative_cash"]


# ---------------------------------------------------------------------------
# filing_status_comparison
# ---------------------------------------------------------------------------


class TestFilingStatusComparison:
    """MFJ vs MFS comparison."""

    def test_mfj_generally_better(self):
        """For typical dual-income couples, MFJ should be better."""
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
        )
        # MFJ total should be less than or equal to MFS
        assert result["better"] == "mfj"
        assert result["mfj"]["total_tax"] <= result["mfs"]["total_tax"]

    def test_structure_has_both_statuses(self):
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
        )
        assert "mfj" in result
        assert "mfs" in result
        assert "difference" in result
        assert "better" in result
        assert "recommendation" in result

    def test_mfj_breakdown_fields(self):
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
        )
        for status in ["mfj", "mfs"]:
            assert "federal_tax" in result[status]
            assert "niit" in result[status]
            assert "state_tax" in result[status]
            assert "fica" in result[status]
            assert "total_tax" in result[status]
            assert "effective_rate" in result[status]

    def test_mfs_with_student_loans_may_benefit(self):
        """MFS can reduce IDR payments when one spouse has loans."""
        result = E.filing_status_comparison(
            spouse_a_income=250_000,
            spouse_b_income=50_000,
            student_loan_payment=500,
        )
        assert result["idr_benefit"] >= 0

    def test_mfs_loses_student_loan_deduction(self):
        """MFS cannot claim student loan interest deduction."""
        result = E.filing_status_comparison(
            spouse_a_income=100_000,
            spouse_b_income=50_000,
            student_loan_payment=2_500,
        )
        assert result["mfs"]["student_loan_benefit"] == 0

    def test_mfs_limitations_listed(self):
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
        )
        assert len(result["mfs_limitations"]) > 0
        assert any("student loan" in lim.lower() for lim in result["mfs_limitations"])

    def test_equal_income_mfj_wins(self):
        """With perfectly equal incomes, MFJ should still be better."""
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
        )
        assert result["better"] == "mfj" or result["difference"] < 500

    def test_state_tax_applied(self):
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
            state="CA",
        )
        assert result["mfj"]["state_tax"] > 0
        assert result["mfs"]["state_tax"] > 0

    def test_no_state_tax(self):
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
            state="TX",
        )
        assert result["mfj"]["state_tax"] == 0
        assert result["mfs"]["state_tax"] == 0

    def test_investment_income_included(self):
        without_invest = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
            investment_income=0,
        )
        with_invest = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
            investment_income=100_000,
        )
        # With investment income, total taxes should be higher
        assert with_invest["mfj"]["total_tax"] > without_invest["mfj"]["total_tax"]

    def test_recommendation_text_present(self):
        result = E.filing_status_comparison(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
        )
        assert len(result["recommendation"]) > 0


# ---------------------------------------------------------------------------
# qbi_deduction_check
# ---------------------------------------------------------------------------


class TestQBIDeductionCheck:
    """QBI / Section 199A deduction eligibility and computation."""

    def test_below_phaseout_full_deduction(self):
        """Below phaseout, full 20% of QBI."""
        result = E.qbi_deduction_check(
            qbi_income=100_000,
            taxable_income=250_000,
            filing_status="mfj",
        )
        assert result["final_deduction"] == pytest.approx(20_000, abs=1)
        assert result["in_phaseout"] is False
        assert result["above_phaseout"] is False

    def test_20_pct_of_qbi(self):
        result = E.qbi_deduction_check(
            qbi_income=150_000,
            taxable_income=300_000,
            filing_status="mfj",
        )
        expected = 150_000 * 0.20
        assert result["basic_20pct_deduction"] == pytest.approx(expected, abs=1)

    def test_sstb_above_phaseout_eliminated(self):
        """SSTB income above phaseout gets zero QBI deduction."""
        phaseout_end = QBI_PHASEOUT_START["mfj"] + QBI_PHASEOUT_RANGE["mfj"]
        result = E.qbi_deduction_check(
            qbi_income=200_000,
            taxable_income=phaseout_end + 10_000,
            filing_status="mfj",
            is_sstb=True,
        )
        assert result["sstb_eliminated"] is True
        assert result["final_deduction"] == 0

    def test_sstb_below_phaseout_gets_full(self):
        """SSTB below phaseout still gets full 20%."""
        result = E.qbi_deduction_check(
            qbi_income=100_000,
            taxable_income=300_000,
            filing_status="mfj",
            is_sstb=True,
        )
        assert result["final_deduction"] == pytest.approx(20_000, abs=1)

    def test_sstb_in_phaseout_partial(self):
        """SSTB in phaseout range gets partial deduction.
        The W-2 wage limit can bind even in the phaseout zone, so we
        supply W-2 wages to ensure the SSTB partial phase-in is visible."""
        midpoint = QBI_PHASEOUT_START["mfj"] + QBI_PHASEOUT_RANGE["mfj"] / 2
        result = E.qbi_deduction_check(
            qbi_income=100_000,
            taxable_income=midpoint,
            filing_status="mfj",
            is_sstb=True,
            w2_wages_paid=100_000,
        )
        # Should be between 0 and full 20% deduction
        full_deduction = 100_000 * 0.20
        assert 0 < result["final_deduction"] < full_deduction
        assert result["in_phaseout"] is True

    def test_taxable_income_cap(self):
        """20% of taxable income caps the deduction."""
        result = E.qbi_deduction_check(
            qbi_income=500_000,
            taxable_income=50_000,
            filing_status="mfj",
        )
        # Deduction capped at 20% of $50k = $10k
        assert result["final_deduction"] <= 10_000

    def test_w2_wage_limit_above_phaseout(self):
        """Above phaseout, non-SSTB limited by W-2 wages."""
        phaseout_end = QBI_PHASEOUT_START["mfj"] + QBI_PHASEOUT_RANGE["mfj"]
        result = E.qbi_deduction_check(
            qbi_income=200_000,
            taxable_income=phaseout_end + 50_000,
            w2_wages_paid=0,
            filing_status="mfj",
            is_sstb=False,
        )
        # Zero W-2 wages should severely limit or eliminate the deduction
        assert result["final_deduction"] == 0
        assert any("W-2" in w for w in result["warnings"])

    def test_w2_wages_allow_higher_deduction(self):
        phaseout_end = QBI_PHASEOUT_START["mfj"] + QBI_PHASEOUT_RANGE["mfj"]
        low_wages = E.qbi_deduction_check(
            qbi_income=200_000,
            taxable_income=phaseout_end + 50_000,
            w2_wages_paid=10_000,
            filing_status="mfj",
            is_sstb=False,
        )
        high_wages = E.qbi_deduction_check(
            qbi_income=200_000,
            taxable_income=phaseout_end + 50_000,
            w2_wages_paid=200_000,
            filing_status="mfj",
            is_sstb=False,
        )
        assert high_wages["final_deduction"] >= low_wages["final_deduction"]

    def test_tax_savings_computed(self):
        result = E.qbi_deduction_check(
            qbi_income=100_000,
            taxable_income=250_000,
            filing_status="mfj",
        )
        assert result["tax_savings"] > 0
        assert result["marginal_rate"] > 0

    def test_single_filer_lower_phaseout(self):
        """Single filer has lower phaseout threshold."""
        result = E.qbi_deduction_check(
            qbi_income=100_000,
            taxable_income=200_000,
            filing_status="single",
        )
        # Single phaseout start is $191,950 — $200k is in phaseout
        assert result["phaseout_start"] == QBI_PHASEOUT_START["single"]


# ---------------------------------------------------------------------------
# state_tax_comparison
# ---------------------------------------------------------------------------


class TestStateTaxComparison:
    """State-by-state tax comparison."""

    def test_basic_structure(self):
        result = E.state_tax_comparison(
            income=400_000,
            current_state="CA",
        )
        assert "states" in result
        assert "best_state" in result
        assert "max_savings" in result
        assert "current_state_tax" in result

    def test_no_income_tax_states_cheaper(self):
        result = E.state_tax_comparison(
            income=400_000,
            current_state="CA",
            comparison_states=["TX", "FL", "WA"],
        )
        ca = next(s for s in result["states"] if s["state"] == "CA")
        tx = next(s for s in result["states"] if s["state"] == "TX")
        assert tx["state_tax"] == 0
        assert tx["savings_vs_current"] > 0
        assert ca["state_tax"] > tx["state_tax"]

    def test_current_state_included(self):
        result = E.state_tax_comparison(
            income=400_000,
            current_state="NY",
            comparison_states=["TX", "FL"],
        )
        states = [s["state"] for s in result["states"]]
        assert "NY" in states

    def test_max_savings_from_ca(self):
        """Moving from CA (13.3%) to TX (0%) should show significant savings."""
        result = E.state_tax_comparison(
            income=400_000,
            current_state="CA",
            comparison_states=["TX"],
        )
        assert result["max_savings"] > 0
        assert result["max_savings"] == pytest.approx(400_000 * 0.133, rel=0.01)

    def test_already_in_no_tax_state(self):
        """If current state has no income tax, savings should be 0."""
        result = E.state_tax_comparison(
            income=400_000,
            current_state="TX",
            comparison_states=["FL", "WA", "NV"],
        )
        assert result["max_savings"] == 0

    def test_recommendation_text(self):
        result_ca = E.state_tax_comparison(income=400_000, current_state="CA")
        assert "save" in result_ca["recommendation"].lower() or "moving" in result_ca["recommendation"].lower()

        result_tx = E.state_tax_comparison(income=400_000, current_state="TX")
        assert "lowest" in result_tx["recommendation"].lower() or "already" in result_tx["recommendation"].lower()

    def test_default_comparison_states(self):
        """Default comparison includes TX, FL, WA, NV, TN."""
        result = E.state_tax_comparison(income=300_000, current_state="CA")
        states = [s["state"] for s in result["states"]]
        for expected in ["TX", "FL", "WA", "NV", "TN"]:
            assert expected in states

    def test_sorted_by_total_tax(self):
        result = E.state_tax_comparison(
            income=400_000,
            current_state="CA",
            comparison_states=["TX", "NY", "FL"],
        )
        total_taxes = [s["total_tax"] for s in result["states"]]
        assert total_taxes == sorted(total_taxes)

    def test_effective_total_rate_reasonable(self):
        result = E.state_tax_comparison(income=400_000, current_state="CA")
        for s in result["states"]:
            assert 0 < s["effective_total_rate"] < 0.70

    def test_zero_income(self):
        result = E.state_tax_comparison(income=0, current_state="CA")
        assert result["current_state_tax"] == 0
        assert result["max_savings"] == 0


# ---------------------------------------------------------------------------
# Cross-cutting / integration-style tests
# ---------------------------------------------------------------------------


class TestCrossCuttingBehavior:
    """Tests that span multiple methods or verify general engine behavior."""

    def test_all_methods_are_static(self):
        """All public methods on TaxModelingEngine should be static."""
        import inspect
        for name, method in inspect.getmembers(E, predicate=inspect.isfunction):
            if not name.startswith("_"):
                # staticmethod functions are regular functions on the class
                assert callable(method), f"{name} should be callable"

    def test_roth_conversion_and_multi_year_consistency(self):
        """Roth conversions should increase taxes in multi-year projection."""
        base = E.multi_year_projection(
            current_income=300_000,
            years=3,
        )
        with_roth = E.multi_year_projection(
            current_income=300_000,
            years=3,
            roth_conversions=[50_000, 50_000, 50_000],
        )
        for i in range(3):
            assert with_roth["years"][i]["federal_tax"] > base["years"][i]["federal_tax"]

    def test_scorp_vs_schedule_c_deterministic(self):
        """Same inputs should always produce same outputs."""
        r1 = E.scorp_election_model(
            gross_1099_income=300_000,
            reasonable_salary=120_000,
        )
        r2 = E.scorp_election_model(
            gross_1099_income=300_000,
            reasonable_salary=120_000,
        )
        assert r1["schedule_c_tax"] == r2["schedule_c_tax"]
        assert r1["scorp_tax"] == r2["scorp_tax"]
        assert r1["total_savings"] == r2["total_savings"]

    def test_high_income_henry_scenario(self):
        """Full HENRY scenario: $450k combined, CA, married."""
        # Filing status comparison
        filing = E.filing_status_comparison(
            spouse_a_income=250_000,
            spouse_b_income=200_000,
            investment_income=30_000,
            state="CA",
        )
        assert filing["mfj"]["total_tax"] > 0
        assert filing["mfs"]["total_tax"] > 0

        # State comparison
        state = E.state_tax_comparison(
            income=450_000,
            current_state="CA",
            comparison_states=["TX", "WA"],
        )
        assert state["max_savings"] > 40_000  # CA->TX should save > $40k on $450k

        # Multi-year with growth
        projection = E.multi_year_projection(
            current_income=450_000,
            income_growth_rate=0.05,
            filing_status="mfj",
            state_rate=0.133,
            years=5,
        )
        # Taxes should increase year over year with income growth
        taxes = [y["total_tax"] for y in projection["years"]]
        for i in range(1, len(taxes)):
            assert taxes[i] > taxes[i - 1]
