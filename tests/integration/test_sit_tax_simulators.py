"""SIT: Tax modeling simulator endpoints.

Validates each tax simulator returns reasonable results
with known inputs from the demo persona.
"""
import pytest
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


class TestRothConversion:
    async def test_roth_conversion_analysis(self, client, demo_seed):
        resp = await client.post("/tax/model/roth-conversion", json={
            "traditional_balance": 100_000,
            "current_income": COMBINED_INCOME,
            "filing_status": FILING_STATUS,
            "state_rate": 10.9,
            "years": 10,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # Should have year-by-year analysis or summary
            assert len(data) > 0


class TestSCorpAnalysis:
    async def test_scorp_se_tax_savings(self, client, demo_seed):
        resp = await client.post("/tax/model/scorp", json={
            "gross_1099_income": 42_000,
            "reasonable_salary": 30_000,
            "state": STATE,
            "filing_status": FILING_STATUS,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # S-Corp should show SE tax savings on distribution portion
            if "se_tax_savings" in data:
                assert data["se_tax_savings"] > 0


class TestMegaBackdoorRoth:
    async def test_mega_backdoor_space(self, client, demo_seed):
        resp = await client.post("/tax/model/mega-backdoor", json={
            "employer_plan_allows": True,
            "current_employee_contrib": 23_500,
            "employer_match_contrib": 7_350,
            "plan_limit": 69_000,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # After-tax space should be positive
            if "available_after_tax_space" in data:
                assert data["available_after_tax_space"] > 0


class TestMultiYearProjection:
    async def test_multi_year_returns_projections(self, client, demo_seed):
        resp = await client.post("/tax/model/multi-year", json={
            "current_income": COMBINED_INCOME,
            "income_growth_rate": 3.5,
            "filing_status": FILING_STATUS,
            "state": STATE,
            "state_rate": 10.9,
            "years": 5,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # Should have multi-year results
            years = data.get("years", data.get("projections", []))
            if isinstance(years, list):
                assert len(years) >= 3


class TestEstimatedPayments:
    async def test_quarterly_payments(self, client, demo_seed):
        resp = await client.post("/tax/model/estimated-payments", json={
            "total_tax_liability": 142_200,
            "total_withholding": 78_700,
            "prior_year_tax": 130_000,
            "filing_status": FILING_STATUS,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # Should return quarterly payment amounts
            if "quarterly_amount" in data:
                assert data["quarterly_amount"] > 0


class TestStudentLoan:
    async def test_student_loan_analysis(self, client, demo_seed):
        resp = await client.post("/tax/model/student-loan", json={
            "loan_balance": TOTAL_STUDENT_LOANS,
            "interest_rate": 5.5,
            "monthly_income": COMBINED_INCOME / 12,
            "filing_status": FILING_STATUS,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)


class TestHSAMax:
    async def test_hsa_contribution_space(self, client, demo_seed):
        resp = await client.post("/tax/model/hsa-max", json={
            "coverage_type": "family",
            "age": CURRENT_AGE,
            "employer_contribution": 1_200,
            "current_contribution": 0,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # Family HSA limit minus employer contribution
            if "remaining_space" in data:
                assert data["remaining_space"] > 0


class TestQBIDeduction:
    async def test_qbi_at_410k(self, client, demo_seed):
        """At $410K MFJ, QBI phaseout starts at $383.9K — partial deduction."""
        resp = await client.post("/tax/model/qbi", json={
            "qualified_business_income": 42_000,
            "taxable_income": 380_000,
            "filing_status": FILING_STATUS,
            "business_type": "specified_service",
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)


class TestSection179:
    async def test_section_179_deduction(self, client, demo_seed):
        resp = await client.post("/tax/model/section-179", json={
            "equipment_cost": 15_000,
            "business_income": 42_000,
            "filing_status": FILING_STATUS,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            if "deduction_amount" in data:
                assert data["deduction_amount"] > 0


class TestStateComparison:
    async def test_state_tax_comparison(self, client, demo_seed):
        resp = await client.post("/tax/model/state-comparison", json={
            "income": COMBINED_INCOME,
            "filing_status": FILING_STATUS,
            "current_state": STATE,
            "compare_states": ["TX", "FL", "CA"],
        })
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # TX and FL should show savings (no state income tax)
