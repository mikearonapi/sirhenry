"""
Comprehensive tests for two pure pipeline modules:
  - pipeline.planning.thresholds: compute_tax_thresholds()
  - pipeline.planning.w4: compute_w4_recommendations()

No database fixtures needed — both modules are pure functions.
All tax constants sourced from pipeline.tax.constants (2025/2026 tax year).
"""
import pytest

from pipeline.planning.thresholds import compute_tax_thresholds
from pipeline.planning.w4 import compute_w4_recommendations
from pipeline.tax.constants import (
    ADDITIONAL_MEDICARE_THRESHOLD,
    AMT_EXEMPTION,
    CHILD_TAX_CREDIT,
    CHILD_TAX_CREDIT_PHASEOUT,
    NIIT_THRESHOLD,
    ROTH_INCOME_PHASEOUT,
    ROTH_INCOME_PHASEOUT_END,
    SALT_CAP,
    STANDARD_DEDUCTION,
)


# ---------------------------------------------------------------------------
# compute_tax_thresholds() tests
# ---------------------------------------------------------------------------


class TestComputeTaxThresholds:
    """Tests for pipeline.planning.thresholds.compute_tax_thresholds()."""

    # --- Income and MAGI arithmetic ---

    def test_combined_income_correct(self):
        """combined_income must equal spouse_a + spouse_b exactly."""
        result = compute_tax_thresholds(120_000, 95_000)
        assert result["combined_income"] == 215_000

    def test_magi_estimate_adds_investment_subtracts_deductions(self):
        """MAGI = combined + capital_gains + qualified_dividends - pre_tax_deductions."""
        result = compute_tax_thresholds(
            100_000,
            50_000,
            capital_gains=20_000,
            qualified_dividends=5_000,
            pre_tax_deductions=10_000,
        )
        # 150_000 + 20_000 + 5_000 - 10_000 = 165_000
        assert result["magi_estimate"] == 165_000

    def test_magi_estimate_no_optional_params_equals_combined(self):
        """With no investment income or deductions, MAGI equals combined income."""
        result = compute_tax_thresholds(80_000, 70_000)
        assert result["magi_estimate"] == 150_000

    def test_pre_tax_deductions_reduce_magi(self):
        """Pre-tax deductions (401k, HSA) should lower the MAGI estimate."""
        r_base = compute_tax_thresholds(150_000, 150_000)
        r_deduct = compute_tax_thresholds(150_000, 150_000, pre_tax_deductions=30_000)
        assert r_deduct["magi_estimate"] == r_base["magi_estimate"] - 30_000

    # --- Low income — below all thresholds ---

    def test_below_all_thresholds_exceeded_count_zero(self):
        """At $50k + $50k MFJ, no threshold should be exceeded."""
        result = compute_tax_thresholds(50_000, 50_000)
        assert result["exceeded_count"] == 0
        for threshold in result["thresholds"]:
            assert threshold["exceeded"] is False, (
                f"Threshold '{threshold['id']}' was unexpectedly exceeded"
            )

    # --- Additional Medicare Tax ---

    def test_medicare_exceeded_when_magi_over_mfj_threshold(self):
        """MAGI of $251k MFJ puts household above the $250k Additional Medicare threshold."""
        mfj_threshold = ADDITIONAL_MEDICARE_THRESHOLD["mfj"]  # 250_000
        result = compute_tax_thresholds(251_000, 0)
        medicare = next(t for t in result["thresholds"] if t["id"] == "additional_medicare")
        assert medicare["exceeded"] is True
        assert medicare["threshold"] == mfj_threshold
        assert medicare["exposure"] == pytest.approx(251_000 - mfj_threshold, abs=1)

    def test_medicare_not_exceeded_at_exact_mfj_threshold(self):
        """MAGI exactly equal to $250k MFJ is NOT exceeded (threshold is strictly greater-than)."""
        result = compute_tax_thresholds(250_000, 0)
        medicare = next(t for t in result["thresholds"] if t["id"] == "additional_medicare")
        assert medicare["exceeded"] is False
        assert medicare["exposure"] == 0

    def test_medicare_tax_impact_is_09_pct_of_exposure(self):
        """Additional Medicare tax_impact = exposure * 0.9%."""
        result = compute_tax_thresholds(300_000, 0)  # magi=300k, threshold=250k, exposure=50k
        medicare = next(t for t in result["thresholds"] if t["id"] == "additional_medicare")
        assert medicare["tax_impact"] == pytest.approx(medicare["exposure"] * 0.009, abs=1)

    # --- NIIT ---

    def test_niit_triggered_with_investment_income_above_threshold(self):
        """Capital gains push MAGI above NIIT threshold and create taxable NIIT exposure."""
        # magi = 150k + 100k wages + 50k cap gains = 300k > 250k NIIT threshold MFJ
        result = compute_tax_thresholds(150_000, 100_000, capital_gains=50_000)
        niit = next(t for t in result["thresholds"] if t["id"] == "niit")
        assert niit["exceeded"] is True
        # exposure = min(investment_income, magi - threshold) = min(50k, 50k) = 50k
        assert niit["exposure"] == 50_000
        assert niit["tax_impact"] == pytest.approx(50_000 * 0.038, abs=1)

    def test_niit_no_exposure_without_investment_income(self):
        """High wages above NIIT threshold but zero cap gains → no NIIT exposure (exposure=0)."""
        # magi = 200k + 150k = 350k > 250k NIIT threshold, but no investment income
        result = compute_tax_thresholds(200_000, 150_000, capital_gains=0)
        niit = next(t for t in result["thresholds"] if t["id"] == "niit")
        assert niit["exceeded"] is True  # MAGI is above threshold
        assert niit["exposure"] == 0    # but no investment income to expose
        assert niit["tax_impact"] == 0

    def test_niit_not_exceeded_low_income_with_gains(self):
        """MAGI below NIIT threshold even with capital gains → not exceeded."""
        # magi = 50k + 50k + 30k CG = 130k < 250k
        result = compute_tax_thresholds(50_000, 50_000, capital_gains=30_000)
        niit = next(t for t in result["thresholds"] if t["id"] == "niit")
        assert niit["exceeded"] is False
        assert niit["exposure"] == 0

    # --- Roth IRA phase-out ---

    def test_roth_partially_exceeded_in_mfj_phaseout_range(self):
        """MAGI between $236k and $246k MFJ is partially phased out (not fully exceeded)."""
        roth_start = ROTH_INCOME_PHASEOUT["mfj"]       # 236_000
        roth_end = ROTH_INCOME_PHASEOUT_END["mfj"]     # 246_000
        # 240k is inside the phase-out range
        result = compute_tax_thresholds(120_000, 120_000)  # combined = 240k
        roth = next(t for t in result["thresholds"] if t["id"] == "roth_ira")
        assert result["magi_estimate"] > roth_start
        assert result["magi_estimate"] < roth_end
        assert roth["exceeded"] is False
        assert roth.get("partially_exceeded") is True
        assert roth["threshold"] == roth_start
        assert roth["threshold_end"] == roth_end

    def test_roth_exceeded_above_mfj_phaseout_end(self):
        """MAGI above $246k MFJ means direct Roth contributions are fully eliminated."""
        result = compute_tax_thresholds(130_000, 120_000)  # combined = 250k > 246k
        roth = next(t for t in result["thresholds"] if t["id"] == "roth_ira")
        assert roth["exceeded"] is True
        assert roth.get("partially_exceeded") is False

    def test_roth_not_exceeded_low_income(self):
        """MAGI well below $236k MFJ phase-out start → Roth is fully available."""
        result = compute_tax_thresholds(50_000, 50_000)  # combined = 100k
        roth = next(t for t in result["thresholds"] if t["id"] == "roth_ira")
        assert roth["exceeded"] is False
        assert roth.get("partially_exceeded") is False

    # --- Child Tax Credit phase-out ---

    def test_child_tax_credit_exceeded_with_dependents_above_threshold(self):
        """$500k MAGI with 2 dependents should exceed the $400k CTC phase-out."""
        ctc_threshold = CHILD_TAX_CREDIT_PHASEOUT["mfj"]  # 400_000
        result = compute_tax_thresholds(300_000, 200_000, dependents=2)
        ctc = next(t for t in result["thresholds"] if t["id"] == "child_tax_credit")
        assert ctc["exceeded"] is True
        assert ctc["threshold"] == ctc_threshold
        # excess = 500k - 400k = 100k; reduction = min(2*2000, (100k/1000)*50) = min(4000, 5000) = 4000
        assert ctc["tax_impact"] == 4_000

    def test_child_tax_credit_threshold_absent_when_no_dependents(self):
        """With 0 dependents the CTC threshold should not appear in the list at all."""
        result = compute_tax_thresholds(500_000, 0, dependents=0)
        ids = [t["id"] for t in result["thresholds"]]
        assert "child_tax_credit" not in ids

    def test_child_tax_credit_not_exceeded_below_threshold_with_dependents(self):
        """With dependents but MAGI below $400k MFJ, CTC is not reduced."""
        result = compute_tax_thresholds(150_000, 100_000, dependents=2)  # 250k < 400k
        ctc = next((t for t in result["thresholds"] if t["id"] == "child_tax_credit"), None)
        assert ctc is not None
        assert ctc["exceeded"] is False
        assert ctc["tax_impact"] == 0

    # --- SALT cap ---

    def test_salt_cap_exceeded_when_estimated_state_tax_above_10k(self):
        """At $300k MAGI, estimated SALT (5% * 300k = $15k) exceeds the $10k cap."""
        result = compute_tax_thresholds(150_000, 150_000)  # magi = 300k
        salt = next(t for t in result["thresholds"] if t["id"] == "salt_cap")
        assert salt["exceeded"] is True  # 300k * 0.05 = 15k > 10k
        assert salt["threshold"] == SALT_CAP  # 10_000

    def test_salt_cap_not_exceeded_at_200k_magi(self):
        """At exactly $200k MAGI, estimated SALT = $10k which is NOT strictly greater than the cap."""
        result = compute_tax_thresholds(100_000, 100_000)  # magi = 200k
        salt = next(t for t in result["thresholds"] if t["id"] == "salt_cap")
        # 200k * 0.05 = 10k, not strictly > 10k cap
        assert salt["exceeded"] is False

    # --- AMT ---

    def test_amt_threshold_always_present_in_response(self):
        """The AMT threshold dict must always be included, even when not exceeded."""
        result = compute_tax_thresholds(100_000, 0)
        amt = next((t for t in result["thresholds"] if t["id"] == "amt"), None)
        assert amt is not None
        assert amt["threshold"] == AMT_EXEMPTION["mfj"]  # 137_000

    def test_amt_exceeded_when_pre_tax_adds_back_push_amt_income_high(self):
        """High pre-tax deductions are added back in the AMT calculation, triggering AMT."""
        # magi = 300k+200k=500k - 100k deductions = 400k
        # amt_income_est = 400k + 100k = 500k - 137k exemption = 363k * 26% = 94k
        # regular_tax on (400k - 100k - 30k) = 270k is lower, so AMT should apply
        result = compute_tax_thresholds(300_000, 200_000, pre_tax_deductions=100_000)
        amt = next(t for t in result["thresholds"] if t["id"] == "amt")
        assert amt["exceeded"] is True
        assert amt["tax_impact"] > 0

    # --- Single filer thresholds ---

    def test_single_filer_uses_single_threshold_values(self):
        """filing_status='single' should use the single-filer threshold constants."""
        result = compute_tax_thresholds(180_000, 0, filing_status="single")
        medicare = next(t for t in result["thresholds"] if t["id"] == "additional_medicare")
        niit = next(t for t in result["thresholds"] if t["id"] == "niit")
        roth = next(t for t in result["thresholds"] if t["id"] == "roth_ira")
        # Single thresholds are $200k for medicare/NIIT, $150k for Roth start
        assert medicare["threshold"] == ADDITIONAL_MEDICARE_THRESHOLD["single"]  # 200_000
        assert niit["threshold"] == NIIT_THRESHOLD["single"]                     # 200_000
        assert roth["threshold"] == ROTH_INCOME_PHASEOUT["single"]               # 150_000

    def test_single_filer_roth_partially_exceeded_in_range(self):
        """$155k single MAGI is inside the single Roth phase-out range ($150k-$165k)."""
        result = compute_tax_thresholds(155_000, 0, filing_status="single")
        roth = next(t for t in result["thresholds"] if t["id"] == "roth_ira")
        assert roth.get("partially_exceeded") is True
        assert roth["exceeded"] is False

    # --- Response shape ---

    def test_threshold_response_shape_top_level(self):
        """Top-level response must have all expected keys."""
        result = compute_tax_thresholds(200_000, 100_000)
        required_keys = {
            "combined_income",
            "magi_estimate",
            "filing_status",
            "thresholds",
            "exceeded_count",
            "total_estimated_additional_tax",
        }
        assert required_keys.issubset(result.keys())

    def test_threshold_response_shape_each_threshold_dict(self):
        """Each threshold dict must contain all required fields."""
        result = compute_tax_thresholds(200_000, 100_000)
        required_threshold_keys = {
            "id",
            "label",
            "threshold",
            "current_magi",
            "exposure",
            "tax_impact",
            "proximity_pct",
            "exceeded",
            "description",
            "actions",
        }
        for t in result["thresholds"]:
            assert required_threshold_keys.issubset(t.keys()), (
                f"Threshold '{t.get('id')}' is missing required keys: "
                f"{required_threshold_keys - t.keys()}"
            )

    def test_threshold_actions_is_nonempty_list(self):
        """Each threshold must have at least one suggested action."""
        result = compute_tax_thresholds(200_000, 100_000)
        for t in result["thresholds"]:
            assert isinstance(t["actions"], list)
            assert len(t["actions"]) >= 1, f"Threshold '{t['id']}' has no actions"

    def test_filing_status_echoed_in_response(self):
        """The response should echo back the filing_status parameter."""
        r_mfj = compute_tax_thresholds(100_000, 100_000, filing_status="mfj")
        r_single = compute_tax_thresholds(100_000, 0, filing_status="single")
        assert r_mfj["filing_status"] == "mfj"
        assert r_single["filing_status"] == "single"

    # --- All thresholds exceeded ---

    def test_all_thresholds_exceeded_high_income(self):
        """At $500k + $500k + $100k cap gains, 100k deductions, and 2 dependents,
        all non-AMT thresholds are exceeded. AMT doesn't apply at this income
        because regular tax (37% bracket) exceeds the flat 26% AMT rate."""
        result = compute_tax_thresholds(
            500_000,
            500_000,
            capital_gains=100_000,
            pre_tax_deductions=100_000,
            dependents=2,
        )
        non_amt = [t for t in result["thresholds"] if t["id"] != "amt"]
        for t in non_amt:
            assert t["exceeded"] is True, (
                f"Expected threshold '{t['id']}' to be exceeded at this income level"
            )
        # AMT typically doesn't apply at very high incomes where regular tax > AMT
        amt = next(t for t in result["thresholds"] if t["id"] == "amt")
        assert amt["exceeded"] is False

    def test_exceeded_count_matches_exceeded_flags(self):
        """exceeded_count must equal the actual number of threshold dicts with exceeded=True."""
        result = compute_tax_thresholds(300_000, 200_000, capital_gains=50_000, dependents=1)
        actual_count = sum(1 for t in result["thresholds"] if t["exceeded"])
        assert result["exceeded_count"] == actual_count


# ---------------------------------------------------------------------------
# compute_w4_recommendations() tests
# ---------------------------------------------------------------------------


class TestComputeW4Recommendations:
    """Tests for pipeline.planning.w4.compute_w4_recommendations()."""

    # --- Income arithmetic ---

    def test_combined_income_includes_other_income(self):
        """combined_income must equal spouse_a + spouse_b + other_income."""
        result = compute_w4_recommendations(100_000, 80_000, other_income=20_000)
        assert result["combined_income"] == 200_000

    def test_combined_income_zero_other_income(self):
        """combined_income with no other_income is the sum of both spouses."""
        result = compute_w4_recommendations(120_000, 80_000)
        assert result["combined_income"] == 200_000

    # --- Shortfall mechanics ---

    def test_dual_income_creates_shortfall_at_very_high_income(self):
        """$500k + $500k dual earners should produce a positive shortfall > $500."""
        result = compute_w4_recommendations(500_000, 500_000)
        assert result["estimated_shortfall"] > 500, (
            "Dual $500k earners should have a meaningful withholding shortfall"
        )

    def test_other_income_increases_shortfall(self):
        """Adding unwithheld other_income ($50k) should increase the shortfall."""
        r_base = compute_w4_recommendations(200_000, 200_000)
        r_other = compute_w4_recommendations(200_000, 200_000, other_income=50_000)
        assert r_other["estimated_shortfall"] > r_base["estimated_shortfall"]

    def test_single_income_produces_refund_not_shortfall(self):
        """With only one earner ($200k), withholding as single exceeds MFJ tax → refund."""
        result = compute_w4_recommendations(200_000, 0)
        # Single withholding bracket on 200k (minus single std ded) vs
        # MFJ tax on 200k (minus MFJ std ded) — single withholding is higher → negative shortfall
        assert result["estimated_shortfall"] < 0

    def test_extra_per_paycheck_positive_when_shortfall_exceeds_500(self):
        """When shortfall > $500, extra withholding per paycheck should be > 0."""
        # 200k+200k with 100k other income creates shortfall ~$30k
        result = compute_w4_recommendations(200_000, 200_000, other_income=100_000)
        assert result["estimated_shortfall"] > 500
        assert result["extra_per_paycheck_a"] > 0
        assert result["extra_per_paycheck_b"] > 0

    def test_extra_per_paycheck_zero_when_no_shortfall(self):
        """When shortfall is zero or negative (refund territory), extra amounts must be 0."""
        result = compute_w4_recommendations(50_000, 0)
        assert result["estimated_shortfall"] <= 0
        assert result["extra_per_paycheck_a"] == 0
        assert result["extra_per_paycheck_b"] == 0

    def test_extra_per_paycheck_proportional_to_pay_periods(self):
        """More pay periods per year should reduce the extra per-paycheck amount."""
        r_26 = compute_w4_recommendations(
            200_000, 200_000, other_income=100_000,
            spouse_a_pay_periods=26, spouse_b_pay_periods=26,
        )
        r_52 = compute_w4_recommendations(
            200_000, 200_000, other_income=100_000,
            spouse_a_pay_periods=52, spouse_b_pay_periods=52,
        )
        # Both shortfalls are equal; 52 periods → smaller per-paycheck amount
        assert r_52["extra_per_paycheck_a"] < r_26["extra_per_paycheck_a"]
        assert r_52["extra_per_paycheck_b"] < r_26["extra_per_paycheck_b"]

    # --- Tax rates ---

    def test_marginal_rate_is_37pct_at_1m_combined(self):
        """$500k + $500k combined income ($970k taxable) should be in the 37% MFJ bracket."""
        result = compute_w4_recommendations(500_000, 500_000)
        assert result["marginal_rate"] == pytest.approx(0.37)

    def test_marginal_rate_moderate_income(self):
        """$300k + $200k ($470k taxable after MFJ std ded) falls in the 32% MFJ bracket."""
        result = compute_w4_recommendations(300_000, 200_000)
        assert result["marginal_rate"] == pytest.approx(0.32)

    def test_effective_rate_between_zero_and_50pct(self):
        """Effective tax rate must be a plausible positive fraction for working earners."""
        result = compute_w4_recommendations(200_000, 200_000)
        assert 0 < result["effective_rate"] < 0.50

    def test_effective_rate_is_zero_for_zero_income(self):
        """Zero combined income should produce an effective rate of 0."""
        result = compute_w4_recommendations(0, 0)
        assert result["effective_rate"] == 0

    # --- Pre-tax deductions ---

    def test_pre_tax_deductions_reduce_estimated_tax(self):
        """Adding $20k pre-tax deductions per spouse should reduce the MFJ tax estimate."""
        r_base = compute_w4_recommendations(200_000, 200_000)
        r_deduct = compute_w4_recommendations(
            200_000, 200_000,
            pre_tax_deductions_a=20_000,
            pre_tax_deductions_b=20_000,
        )
        assert r_deduct["estimated_mfj_tax"] < r_base["estimated_mfj_tax"]

    # --- Recommendation text ---

    def test_recommendation_is_nonempty_string(self):
        """recommendation must always be a non-empty string regardless of shortfall."""
        for incomes in [(200_000, 200_000), (200_000, 0), (0, 0)]:
            result = compute_w4_recommendations(*incomes)
            assert isinstance(result["recommendation"], str)
            assert len(result["recommendation"]) > 0

    def test_recommendation_lines_is_list_with_content(self):
        """recommendation_lines must be a list with at least one string item."""
        result = compute_w4_recommendations(200_000, 200_000)
        assert isinstance(result["recommendation_lines"], list)
        assert len(result["recommendation_lines"]) >= 1
        assert all(isinstance(line, str) for line in result["recommendation_lines"])

    def test_recommendation_lines_has_4_items_when_large_shortfall(self):
        """When shortfall > $500, recommendation_lines should have 4 items (shortfall note + 2 spouse lines + IRS link)."""
        result = compute_w4_recommendations(200_000, 200_000, other_income=100_000)
        assert result["estimated_shortfall"] > 500
        assert len(result["recommendation_lines"]) == 4

    def test_recommendation_lines_has_1_item_for_safe_harbor(self):
        """When 0 < shortfall <= 500 (safe harbor), recommendation_lines has 1 item."""
        # 400k+400k gives shortfall ~$368 which is in safe harbor range
        result = compute_w4_recommendations(400_000, 400_000)
        assert 0 < result["estimated_shortfall"] <= 500
        assert len(result["recommendation_lines"]) == 1

    def test_recommendation_lines_has_1_item_when_no_shortfall(self):
        """When shortfall <= 0 (likely refund), recommendation_lines has 1 item."""
        result = compute_w4_recommendations(200_000, 0)
        assert result["estimated_shortfall"] <= 0
        assert len(result["recommendation_lines"]) == 1

    # --- Filing status ---

    def test_single_filing_status_works(self):
        """filing_status='single' should produce a valid result without errors."""
        result = compute_w4_recommendations(200_000, 0, filing_status="single")
        assert result["combined_income"] == 200_000
        assert isinstance(result["estimated_mfj_tax"], (int, float))
        assert result["effective_rate"] >= 0

    # --- Zero income ---

    def test_zero_income_produces_zero_tax_and_zero_withheld(self):
        """$0 + $0 income should produce $0 tax owed, $0 withheld, and $0 shortfall."""
        result = compute_w4_recommendations(0, 0)
        assert result["estimated_mfj_tax"] == 0
        assert result["estimated_withheld_a"] == 0
        assert result["estimated_withheld_b"] == 0
        assert result["total_estimated_withheld"] == 0
        assert result["estimated_shortfall"] == 0

    # --- Response shape ---

    def test_response_shape_all_expected_keys_present(self):
        """The response dict must contain all documented keys."""
        result = compute_w4_recommendations(150_000, 100_000)
        expected_keys = {
            "spouse_a_income",
            "spouse_b_income",
            "combined_income",
            "estimated_mfj_tax",
            "estimated_withheld_a",
            "estimated_withheld_b",
            "total_estimated_withheld",
            "estimated_shortfall",
            "extra_per_paycheck_a",
            "extra_per_paycheck_b",
            "marginal_rate",
            "effective_rate",
            "recommendation",
            "recommendation_lines",
        }
        assert expected_keys.issubset(result.keys())

    def test_total_withheld_equals_sum_of_both_spouses(self):
        """total_estimated_withheld should equal withheld_a + withheld_b."""
        result = compute_w4_recommendations(200_000, 150_000)
        assert result["total_estimated_withheld"] == pytest.approx(
            result["estimated_withheld_a"] + result["estimated_withheld_b"], abs=1
        )

    def test_spouse_incomes_echoed_in_response(self):
        """The response must include the original spouse income inputs."""
        result = compute_w4_recommendations(175_000, 125_000)
        assert result["spouse_a_income"] == 175_000
        assert result["spouse_b_income"] == 125_000
