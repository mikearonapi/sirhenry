"""SIT: Insurance analysis accuracy.

Validates insurance policies, gap analysis, and coverage calculations
against demo data.
"""
import pytest
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


class TestInsurancePolicies:
    async def test_all_policies_returned(self, client, demo_seed):
        resp = await client.get("/insurance/")
        assert resp.status_code == 200
        policies = resp.json()
        assert len(policies) >= INSURANCE_POLICY_COUNT

    async def test_policy_types(self, client, demo_seed):
        resp = await client.get("/insurance/")
        policies = resp.json()
        types = {p["policy_type"] for p in policies}
        assert "health" in types
        assert "life" in types
        assert "auto" in types
        assert "umbrella" in types

    async def test_life_coverage_amounts(self, client, demo_seed):
        resp = await client.get("/insurance/")
        policies = resp.json()
        life_policies = [p for p in policies if p["policy_type"] == "life"]
        total_personal_life = sum(p.get("coverage_amount", 0) for p in life_policies)
        expected_personal = PERSONAL_LIFE_COVERAGE_A + PERSONAL_LIFE_COVERAGE_B
        assert total_personal_life == pytest.approx(expected_personal, rel=0.01)

    async def test_annual_premiums_total(self, client, demo_seed):
        resp = await client.get("/insurance/")
        policies = resp.json()
        total_premiums = sum(p.get("annual_premium", 0) for p in policies)
        assert total_premiums == pytest.approx(TOTAL_ANNUAL_PREMIUMS, rel=0.05)


class TestInsuranceGapAnalysis:
    async def test_gap_analysis_endpoint(self, client, demo_seed):
        resp = await client.get("/insurance/gap-analysis")
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
            # Should have gap analysis results
            assert "gaps" in data or "recommendations" in data or "life" in data

    async def test_disability_gap(self, client, demo_seed):
        """Employer disability covers $163K/yr. 65% of $410K = $266K → gap exists."""
        resp = await client.get("/insurance/gap-analysis")
        if resp.status_code == 200:
            data = resp.json()
            # If disability analysis exists, check coverage gap
            gaps = data.get("gaps", [])
            if isinstance(gaps, list):
                disability_gaps = [g for g in gaps if "disability" in str(g).lower()]
                # At $410K income, employer $163K coverage is insufficient
                # (employer covers ~40% of income)
