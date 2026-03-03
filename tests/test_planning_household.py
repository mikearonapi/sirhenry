"""Tests for the household optimization engine."""
import json
import pytest

from pipeline.planning.household import HouseholdEngine
from pipeline.tax.constants import (
    STANDARD_DEDUCTION,
    LIMIT_401K,
    HSA_LIMIT,
    DEP_CARE_FSA_LIMIT,
    CHILD_TAX_CREDIT,
)


def _benefits(
    has_401k=True,
    employer_match_pct=50,
    employer_match_limit_pct=6,
    has_hsa=True,
    hsa_plan_type="family",
    hsa_employer_contribution=0,
    has_roth_401k=True,
    has_mega_backdoor=False,
    mega_backdoor_limit=46_000,
    has_dep_care_fsa=False,
    health_premium_monthly=500,
) -> dict:
    return {
        "has_401k": has_401k,
        "employer_match_pct": employer_match_pct,
        "employer_match_limit_pct": employer_match_limit_pct,
        "has_hsa": has_hsa,
        "hsa_plan_type": hsa_plan_type,
        "hsa_employer_contribution": hsa_employer_contribution,
        "has_roth_401k": has_roth_401k,
        "has_mega_backdoor": has_mega_backdoor,
        "mega_backdoor_limit": mega_backdoor_limit,
        "has_dep_care_fsa": has_dep_care_fsa,
        "health_premium_monthly": health_premium_monthly,
    }


class TestFilingStatusComparison:
    """Test MFJ vs MFS filing status comparison."""

    def test_mfj_recommended_for_equal_incomes(self):
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            dependents=0,
        )
        assert result["recommendation"] in ("mfj", "mfs")
        assert result["mfj_tax"] > 0
        assert result["mfs_tax"] > 0

    def test_mfj_usually_better_for_unequal_incomes(self):
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=300_000,
            spouse_b_income=50_000,
            dependents=0,
        )
        # MFJ is typically better when there is a large income disparity
        assert result["recommendation"] == "mfj"
        assert result["filing_savings"] > 0

    def test_dependents_affect_tax(self):
        result_no_deps = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            dependents=0,
        )
        result_with_deps = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            dependents=2,
        )
        # CTC should reduce at least one filing option
        assert result_with_deps["mfj_tax"] < result_no_deps["mfj_tax"]

    def test_filing_savings_non_negative(self):
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=150_000,
            spouse_b_income=150_000,
        )
        assert result["filing_savings"] >= 0

    def test_explanation_text_populated(self):
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=100_000,
        )
        assert len(result["explanation"]) > 0
        assert "$" in result["explanation"]


class TestRetirementContributionOptimization:
    """Test W-4 / retirement contribution optimization."""

    def test_basic_401k_strategy(self):
        benefits_a = _benefits(has_401k=True, has_hsa=False, has_dep_care_fsa=False)
        benefits_b = _benefits(has_401k=True, has_hsa=False, has_dep_care_fsa=False)
        result = HouseholdEngine.optimize_retirement_contributions(
            spouse_a_income=200_000,
            spouse_b_income=150_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
        )
        assert len(result["spouse_a_strategy"]) > 0
        assert len(result["spouse_b_strategy"]) > 0
        assert result["total_tax_savings"] > 0

    def test_hsa_included_when_available(self):
        benefits_a = _benefits(has_hsa=True)
        benefits_b = _benefits(has_hsa=False)
        result = HouseholdEngine.optimize_retirement_contributions(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
        )
        a_actions = [s["action"] for s in result["spouse_a_strategy"]]
        assert any("HSA" in a for a in a_actions)

    def test_mega_backdoor_included_when_available(self):
        benefits_a = _benefits(has_mega_backdoor=True)
        benefits_b = _benefits(has_mega_backdoor=False)
        result = HouseholdEngine.optimize_retirement_contributions(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
        )
        a_actions = [s["action"] for s in result["spouse_a_strategy"]]
        assert any("Mega" in a for a in a_actions)

    def test_dep_care_fsa_savings(self):
        benefits_a = _benefits(has_dep_care_fsa=True)
        benefits_b = _benefits(has_dep_care_fsa=False)
        result = HouseholdEngine.optimize_retirement_contributions(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
        )
        a_actions = [s["action"] for s in result["spouse_a_strategy"]]
        assert any("Dependent Care" in a for a in a_actions)

    def test_no_benefits_yields_empty_strategy(self):
        no_benefits = {
            "has_401k": False,
            "has_hsa": False,
            "has_mega_backdoor": False,
            "has_dep_care_fsa": False,
        }
        result = HouseholdEngine.optimize_retirement_contributions(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            benefits_a=no_benefits,
            benefits_b=no_benefits,
        )
        assert len(result["spouse_a_strategy"]) == 0
        assert len(result["spouse_b_strategy"]) == 0
        assert result["total_tax_savings"] == 0.0


class TestInsuranceOptimization:
    """Test insurance plan comparison."""

    def test_hsa_plan_preferred(self):
        benefits_a = _benefits(has_hsa=True, health_premium_monthly=600)
        benefits_b = _benefits(has_hsa=False, health_premium_monthly=400)
        result = HouseholdEngine.optimize_insurance(benefits_a, benefits_b)
        # HSA plan should be recommended for tax benefit even if costlier
        assert "HSA" in result["recommendation"]

    def test_lower_premium_when_no_hsa(self):
        benefits_a = _benefits(has_hsa=False, health_premium_monthly=300)
        benefits_b = _benefits(has_hsa=False, health_premium_monthly=500)
        result = HouseholdEngine.optimize_insurance(benefits_a, benefits_b)
        assert "Spouse A" in result["recommendation"]
        assert "lower premium" in result["recommendation"]

    def test_hsa_recommendation_when_available(self):
        benefits_a = _benefits(has_hsa=True)
        benefits_b = _benefits(has_hsa=False)
        result = HouseholdEngine.optimize_insurance(benefits_a, benefits_b)
        assert "triple tax" in result["hsa_recommendation"].lower()

    def test_no_hsa_suggests_switch(self):
        benefits_a = _benefits(has_hsa=False)
        benefits_b = _benefits(has_hsa=False)
        result = HouseholdEngine.optimize_insurance(benefits_a, benefits_b)
        assert "HDHP" in result["hsa_recommendation"]


class TestChildcareStrategy:
    """Test childcare cost and tax optimization."""

    def test_fsa_recommended_when_available(self):
        dependents = json.dumps([{"name": "Child", "age": 3, "care_cost_annual": 20_000}])
        result = HouseholdEngine.childcare_strategy(
            dependents_json=dependents,
            income_a=200_000,
            income_b=150_000,
            dep_care_fsa_available=True,
        )
        assert result["children_under_13"] == 1
        assert result["fsa_tax_savings"] > 0
        assert result["recommendation"] == "Use Dependent Care FSA"

    def test_credit_when_no_fsa(self):
        dependents = json.dumps([{"name": "Child", "age": 3, "care_cost_annual": 10_000}])
        result = HouseholdEngine.childcare_strategy(
            dependents_json=dependents,
            income_a=200_000,
            income_b=150_000,
            dep_care_fsa_available=False,
        )
        assert result["child_care_credit"] > 0
        assert result["fsa_tax_savings"] == 0

    def test_no_children_under_13(self):
        dependents = json.dumps([{"name": "Teen", "age": 15}])
        result = HouseholdEngine.childcare_strategy(
            dependents_json=dependents,
            income_a=200_000,
            income_b=150_000,
            dep_care_fsa_available=True,
        )
        assert result["children_under_13"] == 0
        assert result["total_annual_childcare"] == 0

    def test_empty_dependents(self):
        result = HouseholdEngine.childcare_strategy(
            dependents_json="[]",
            income_a=200_000,
            income_b=150_000,
            dep_care_fsa_available=True,
        )
        assert result["children_under_13"] == 0

    def test_net_second_income_calculated(self):
        dependents = json.dumps([{"name": "Child", "age": 3, "care_cost_annual": 20_000}])
        result = HouseholdEngine.childcare_strategy(
            dependents_json=dependents,
            income_a=200_000,
            income_b=80_000,
            dep_care_fsa_available=True,
        )
        # Net second income should account for childcare, FICA, and taxes
        assert result["net_second_income_after_childcare"] < 80_000


class TestFullOptimization:
    """Test the combined full_optimization orchestrator."""

    def test_full_optimization_returns_all_sections(self):
        benefits_a = _benefits(has_dep_care_fsa=True)
        benefits_b = _benefits(has_dep_care_fsa=False, has_hsa=False)
        dependents = json.dumps([{"name": "Child", "age": 5, "care_cost_annual": 15_000}])

        result = HouseholdEngine.full_optimization(
            spouse_a_income=250_000,
            spouse_b_income=150_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
            dependents_json=dependents,
            state="CA",
        )
        assert "filing" in result
        assert "retirement" in result
        assert "insurance" in result
        assert "childcare" in result
        assert "total_annual_savings" in result
        assert "recommendations" in result

    def test_total_savings_is_sum_of_parts(self):
        benefits_a = _benefits()
        benefits_b = _benefits(has_hsa=False)
        result = HouseholdEngine.full_optimization(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
        )
        expected_total = (
            result["filing"]["filing_savings"]
            + result["retirement"]["total_tax_savings"]
            + result["insurance"]["estimated_annual_savings"]
            + result["childcare"]["fsa_tax_savings"]
        )
        assert result["total_annual_savings"] == pytest.approx(expected_total, abs=0.01)

    def test_recommendations_list_populated(self):
        benefits_a = _benefits()
        benefits_b = _benefits()
        result = HouseholdEngine.full_optimization(
            spouse_a_income=250_000,
            spouse_b_income=150_000,
            benefits_a=benefits_a,
            benefits_b=benefits_b,
        )
        assert len(result["recommendations"]) > 0
        for rec in result["recommendations"]:
            assert "area" in rec
            assert "savings" in rec


class TestEdgeCases:
    """Test edge cases for household optimization."""

    def test_single_filer_filing_comparison(self):
        # Single filer scenario (one income = 0)
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=0,
            dependents=0,
        )
        assert result["mfj_tax"] >= 0
        assert result["mfs_tax"] >= 0

    def test_no_state_tax_scenario(self):
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=200_000,
            spouse_b_income=200_000,
            dependents=0,
            state="TX",
        )
        # Should still compute federal tax comparisons
        assert result["mfj_tax"] > 0

    def test_very_high_income(self):
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=1_000_000,
            spouse_b_income=500_000,
            dependents=3,
        )
        assert result["mfj_tax"] > 0
        assert result["mfs_tax"] > 0
        # With very high income, CTC should be fully phased out
        # (so deps don't change much)

    def test_zero_income_both_spouses(self):
        result = HouseholdEngine.optimize_filing_status(
            spouse_a_income=0,
            spouse_b_income=0,
            dependents=0,
        )
        assert result["mfj_tax"] == 0
        assert result["mfs_tax"] == 0
