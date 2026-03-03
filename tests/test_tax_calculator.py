"""Tests for the tax calculator engine and constants."""
import pytest

from pipeline.tax.calculator import (
    federal_tax,
    marginal_rate,
    standard_deduction,
    fica_tax,
    se_tax,
    niit_tax,
    amt_tax,
    state_tax,
    total_tax_estimate,
)
from pipeline.tax.constants import (
    MFJ_BRACKETS,
    SINGLE_BRACKETS,
    FICA_SS_CAP,
    FICA_RATE,
    MEDICARE_RATE,
    ADDITIONAL_MEDICARE_RATE,
    ADDITIONAL_MEDICARE_THRESHOLD,
    STANDARD_DEDUCTION,
    NIIT_THRESHOLD,
    AMT_EXEMPTION,
)


class TestFederalTaxBrackets:
    """Verify federal income tax calculations against known bracket values."""

    def test_10_percent_bracket_mfj(self):
        # First $23,850 taxed at 10% for MFJ
        tax = federal_tax(23_850, "mfj")
        assert tax == pytest.approx(2_385.0, abs=1)

    def test_12_percent_bracket_mfj(self):
        # $23,850 at 10% + ($96,950 - $23,850) at 12%
        tax = federal_tax(96_950, "mfj")
        expected = 23_850 * 0.10 + (96_950 - 23_850) * 0.12
        assert tax == pytest.approx(expected, abs=1)

    def test_22_percent_bracket_mfj(self):
        taxable = 150_000
        tax = federal_tax(taxable, "mfj")
        expected = 23_850 * 0.10 + (96_950 - 23_850) * 0.12 + (150_000 - 96_950) * 0.22
        assert tax == pytest.approx(expected, abs=1)

    def test_24_percent_bracket_mfj(self):
        taxable = 300_000
        tax = federal_tax(taxable, "mfj")
        expected = (
            23_850 * 0.10
            + (96_950 - 23_850) * 0.12
            + (206_700 - 96_950) * 0.22
            + (300_000 - 206_700) * 0.24
        )
        assert tax == pytest.approx(expected, abs=1)

    def test_37_percent_bracket_mfj(self):
        taxable = 1_000_000
        tax = federal_tax(taxable, "mfj")
        expected = (
            23_850 * 0.10
            + (96_950 - 23_850) * 0.12
            + (206_700 - 96_950) * 0.22
            + (394_600 - 206_700) * 0.24
            + (501_050 - 394_600) * 0.32
            + (751_600 - 501_050) * 0.35
            + (1_000_000 - 751_600) * 0.37
        )
        assert tax == pytest.approx(expected, abs=1)

    def test_zero_income(self):
        assert federal_tax(0, "mfj") == 0.0

    def test_negative_income_returns_zero(self):
        assert federal_tax(-10_000, "mfj") == 0.0

    def test_single_filer_10_percent(self):
        tax = federal_tax(11_925, "single")
        assert tax == pytest.approx(1_192.50, abs=1)

    def test_single_filer_higher_bracket(self):
        taxable = 100_000
        tax = federal_tax(taxable, "single")
        expected = 11_925 * 0.10 + (48_475 - 11_925) * 0.12 + (100_000 - 48_475) * 0.22
        assert tax == pytest.approx(expected, abs=1)


class TestMarginalRate:
    """Verify marginal rate lookup returns the correct bracket rate."""

    def test_marginal_rate_10_percent_mfj(self):
        assert marginal_rate(10_000, "mfj") == 0.10

    def test_marginal_rate_12_percent_mfj(self):
        assert marginal_rate(50_000, "mfj") == 0.12

    def test_marginal_rate_22_percent_mfj(self):
        assert marginal_rate(150_000, "mfj") == 0.22

    def test_marginal_rate_24_percent_mfj(self):
        assert marginal_rate(250_000, "mfj") == 0.24

    def test_marginal_rate_32_percent_mfj(self):
        assert marginal_rate(450_000, "mfj") == 0.32

    def test_marginal_rate_35_percent_mfj(self):
        assert marginal_rate(600_000, "mfj") == 0.35

    def test_marginal_rate_37_percent_mfj(self):
        assert marginal_rate(800_000, "mfj") == 0.37

    def test_marginal_rate_very_high_income(self):
        # Above all brackets should return 37%
        assert marginal_rate(10_000_000, "mfj") == 0.37

    def test_marginal_rate_single_filer(self):
        assert marginal_rate(150_000, "single") == 0.24

    def test_marginal_rate_head_of_household(self):
        assert marginal_rate(50_000, "hoh") == 0.12


class TestStandardDeduction:
    """Verify standard deduction values by filing status."""

    def test_mfj_deduction(self):
        assert standard_deduction("mfj") == 30_000

    def test_single_deduction(self):
        assert standard_deduction("single") == 15_000

    def test_mfs_deduction(self):
        assert standard_deduction("mfs") == 15_000

    def test_hoh_deduction(self):
        assert standard_deduction("hoh") == 22_500

    def test_unknown_filing_status_fallback(self):
        result = standard_deduction("unknown")
        assert result == 15_000


class TestFICA:
    """Verify FICA (Social Security + Medicare) calculations."""

    def test_fica_below_ss_cap(self):
        wages = 100_000
        tax = fica_tax(wages, "mfj")
        expected = wages * FICA_RATE + wages * MEDICARE_RATE
        assert tax == pytest.approx(expected, abs=1)

    def test_fica_above_ss_cap(self):
        wages = 200_000
        tax = fica_tax(wages, "mfj")
        ss = FICA_SS_CAP * FICA_RATE
        med = wages * MEDICARE_RATE
        # No additional Medicare for MFJ under $250k
        assert tax == pytest.approx(ss + med, abs=1)

    def test_additional_medicare_tax_mfj(self):
        wages = 300_000
        tax = fica_tax(wages, "mfj")
        threshold = ADDITIONAL_MEDICARE_THRESHOLD["mfj"]  # $250,000
        ss = FICA_SS_CAP * FICA_RATE
        med = wages * MEDICARE_RATE
        additional = (wages - threshold) * ADDITIONAL_MEDICARE_RATE
        assert tax == pytest.approx(ss + med + additional, abs=1)

    def test_additional_medicare_tax_single(self):
        wages = 250_000
        tax = fica_tax(wages, "single")
        threshold = ADDITIONAL_MEDICARE_THRESHOLD["single"]  # $200,000
        ss = FICA_SS_CAP * FICA_RATE
        med = wages * MEDICARE_RATE
        additional = (wages - threshold) * ADDITIONAL_MEDICARE_RATE
        assert tax == pytest.approx(ss + med + additional, abs=1)

    def test_zero_wages(self):
        assert fica_tax(0, "mfj") == 0.0


class TestSelfEmploymentTax:
    """Verify SE tax on 1099 / Schedule C income."""

    def test_basic_se_tax(self):
        net_se = 100_000
        tax = se_tax(net_se, "mfj")
        se_base = net_se * 0.9235
        expected = min(se_base, FICA_SS_CAP) * 0.124 + se_base * 0.029
        assert tax == pytest.approx(expected, abs=1)

    def test_se_tax_above_ss_cap(self):
        net_se = 250_000
        tax = se_tax(net_se, "mfj")
        se_base = net_se * 0.9235
        ss = min(se_base, FICA_SS_CAP) * 0.124
        med = se_base * 0.029
        # Additional Medicare on income above MFJ threshold
        threshold = ADDITIONAL_MEDICARE_THRESHOLD["mfj"]
        additional = max(0, se_base - threshold) * ADDITIONAL_MEDICARE_RATE
        assert tax == pytest.approx(ss + med + additional, abs=1)

    def test_zero_se_income(self):
        assert se_tax(0, "mfj") == 0.0


class TestNIIT:
    """Verify Net Investment Income Tax (3.8%)."""

    def test_niit_above_threshold_mfj(self):
        agi = 350_000
        investment = 100_000
        tax = niit_tax(agi, investment, "mfj")
        threshold = NIIT_THRESHOLD["mfj"]  # $250,000
        excess = agi - threshold  # $100,000
        expected = min(excess, investment) * 0.038
        assert tax == pytest.approx(expected, abs=0.01)

    def test_niit_below_threshold(self):
        tax = niit_tax(200_000, 50_000, "mfj")
        assert tax == 0.0

    def test_niit_excess_less_than_investment(self):
        agi = 270_000
        investment = 100_000
        tax = niit_tax(agi, investment, "mfj")
        excess = agi - 250_000  # $20,000
        expected = excess * 0.038  # tax on the lesser amount
        assert tax == pytest.approx(expected, abs=0.01)

    def test_niit_zero_investment(self):
        assert niit_tax(500_000, 0, "mfj") == 0.0


class TestAMT:
    """Verify Alternative Minimum Tax calculations."""

    def test_amt_below_exemption(self):
        # Income below AMT exemption should result in zero AMT
        amti = 100_000
        tax = amt_tax(amti, "mfj")
        exemption = AMT_EXEMPTION["mfj"]  # $137,000
        assert tax == 0.0

    def test_amt_above_exemption(self):
        amti = 300_000
        tax = amt_tax(amti, "mfj")
        assert tax > 0

    def test_amt_phaseout_reduces_exemption(self):
        # At very high income, exemption phases out
        amti_low = 300_000
        amti_high = 1_500_000
        tax_low = amt_tax(amti_low, "mfj")
        tax_high = amt_tax(amti_high, "mfj")
        assert tax_high > tax_low

    def test_amt_single_filer(self):
        amti = 200_000
        tax = amt_tax(amti, "single")
        exemption = AMT_EXEMPTION["single"]
        amt_base = max(0, amti - exemption)
        expected = amt_base * 0.26
        assert tax == pytest.approx(expected, abs=1)


class TestStateTax:
    """Verify simplified state tax calculations."""

    def test_california_tax(self):
        income = 200_000
        tax = state_tax(income, "CA")
        expected = 200_000 * 0.133
        assert tax == pytest.approx(expected, abs=0.01)

    def test_texas_no_state_tax(self):
        assert state_tax(200_000, "TX") == 0.0

    def test_florida_no_state_tax(self):
        assert state_tax(200_000, "FL") == 0.0

    def test_new_york_tax(self):
        income = 200_000
        tax = state_tax(income, "NY")
        expected = 200_000 * 0.109
        assert tax == pytest.approx(expected, abs=0.01)

    def test_case_insensitive(self):
        assert state_tax(100_000, "ca") == state_tax(100_000, "CA")


class TestTotalTaxEstimate:
    """Verify the full tax estimate combining all sources."""

    def test_w2_only_mfj(self):
        result = total_tax_estimate(w2_wages=250_000, filing_status="mfj")
        assert result["gross_income"] == 250_000
        assert result["federal_tax"] > 0
        assert result["fica_tax"] > 0
        assert result["se_tax"] == 0
        assert result["total_tax"] > 0
        assert 0 < result["effective_rate"] < 1

    def test_high_income_w2(self):
        result = total_tax_estimate(w2_wages=500_000, filing_status="mfj")
        assert result["marginal_rate"] >= 0.32
        assert result["total_tax"] > 100_000

    def test_se_income(self):
        result = total_tax_estimate(se_income=150_000, filing_status="single")
        assert result["se_tax"] > 0
        assert result["federal_tax"] > 0

    def test_investment_income_triggers_niit(self):
        result = total_tax_estimate(
            w2_wages=200_000,
            investment_income=100_000,
            filing_status="mfj",
        )
        assert result["niit"] > 0

    def test_investment_income_below_niit_threshold(self):
        result = total_tax_estimate(
            w2_wages=100_000,
            investment_income=50_000,
            filing_status="mfj",
        )
        assert result["niit"] == 0.0

    def test_state_tax_included(self):
        result = total_tax_estimate(w2_wages=200_000, state_code="CA")
        assert result["state_tax"] > 0

    def test_no_state_tax_in_texas(self):
        result = total_tax_estimate(w2_wages=200_000, state_code="TX")
        assert result["state_tax"] == 0.0

    def test_child_tax_credit_applied(self):
        result_no_kids = total_tax_estimate(w2_wages=200_000, filing_status="mfj", dependents=0)
        result_with_kids = total_tax_estimate(w2_wages=200_000, filing_status="mfj", dependents=2)
        assert result_with_kids["child_tax_credit"] > 0
        assert result_with_kids["total_tax"] < result_no_kids["total_tax"]

    def test_child_tax_credit_value(self):
        result = total_tax_estimate(w2_wages=200_000, filing_status="mfj", dependents=2)
        # 2 kids * $2,000 = $4,000 (income well below MFJ phaseout of $400k)
        assert result["child_tax_credit"] == 4_000

    def test_zero_income(self):
        result = total_tax_estimate(w2_wages=0, filing_status="mfj")
        assert result["total_tax"] == 0.0
        assert result["effective_rate"] == 0

    def test_mixed_income_sources(self):
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
        assert result["state_tax"] > 0
        assert result["total_tax"] > 0
