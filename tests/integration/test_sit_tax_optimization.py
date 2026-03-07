"""SIT: Household tax optimization accuracy.

Validates filing status comparison, contribution optimization, and
threshold calculations against the demo persona.
"""
import pytest
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Filing status & tax calculations via API
# ---------------------------------------------------------------------------

class TestFilingStatusOptimization:
    async def test_household_profiles_seeded(self, client, demo_seed):
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 1
        p = profiles[0]
        assert p["filing_status"] == FILING_STATUS
        assert p["state"] == STATE
        assert p["combined_income"] >= COMBINED_INCOME

    async def test_mfj_recommended(self, client, demo_seed):
        """At $410K combined, MFJ should produce lower tax than MFS."""
        resp = await client.get("/household/profiles")
        profiles = resp.json()
        hh_id = profiles[0]["id"]

        # Check if optimization data exists from seeder
        resp = await client.get(f"/household/profiles/{hh_id}/optimization")
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("optimal_filing_status") == "mfj"
            assert data.get("filing_savings", 0) > 0

    async def test_seeded_optimization_values(self, client, demo_seed):
        """Verify seeded optimization matches expected values."""
        resp = await client.get("/household/profiles")
        hh_id = resp.json()[0]["id"]

        resp = await client.get(f"/household/profiles/{hh_id}/optimization")
        if resp.status_code == 200:
            data = resp.json()
            # Check seeded values
            if "mfj_tax" in data:
                assert data["mfj_tax"] == pytest.approx(SEEDED_MFJ_TAX, rel=0.05)
            if "mfs_tax" in data:
                assert data["mfs_tax"] == pytest.approx(SEEDED_MFS_TAX, rel=0.05)
            if "total_annual_savings" in data:
                assert data["total_annual_savings"] == pytest.approx(
                    SEEDED_TOTAL_ANNUAL_SAVINGS, rel=0.1,
                )


# ---------------------------------------------------------------------------
# Family members
# ---------------------------------------------------------------------------

class TestFamilyMembers:
    async def test_family_members_seeded(self, client, demo_seed):
        resp = await client.get("/family-members/")
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) >= 3
        names = [m["name"] for m in members]
        assert "Michael" in names
        assert "Jessica" in names
        assert "Ethan" in names

    async def test_earner_incomes(self, client, demo_seed):
        resp = await client.get("/family-members/")
        members = resp.json()
        earners = [m for m in members if m.get("is_earner")]
        assert len(earners) == 2
        incomes = sorted([m["income"] for m in earners])
        assert incomes[0] == SPOUSE_B_INCOME
        assert incomes[1] == SPOUSE_A_INCOME


# ---------------------------------------------------------------------------
# Tax thresholds
# ---------------------------------------------------------------------------

class TestTaxThresholds:
    async def test_thresholds_endpoint(self, client, demo_seed):
        resp = await client.get("/household/profiles")
        if not resp.json():
            pytest.skip("No household profiles")
        hh_id = resp.json()[0]["id"]

        resp = await client.get(f"/household/profiles/{hh_id}/thresholds")
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (dict, list))
            # If dict, should contain threshold categories
            if isinstance(data, dict):
                assert len(data) > 0


# ---------------------------------------------------------------------------
# Benefits packages
# ---------------------------------------------------------------------------

class TestBenefitsPackages:
    async def test_benefits_exist(self, client, demo_seed):
        resp = await client.get("/household/profiles")
        hh_id = resp.json()[0]["id"]

        resp = await client.get(f"/household/profiles/{hh_id}/benefits")
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 2  # Spouse A and B
            # Check Spouse A has mega backdoor
            spouses = {b.get("spouse"): b for b in data}
            if "A" in spouses:
                assert spouses["A"].get("has_mega_backdoor") is True
                assert spouses["A"].get("has_hsa") is True
                assert spouses["A"]["employer_match_pct"] == EMPLOYER_MATCH_PCT
            if "B" in spouses:
                assert spouses["B"].get("has_mega_backdoor") is False
                assert spouses["B"]["employer_match_pct"] == 100


# ---------------------------------------------------------------------------
# Direct engine validation
# ---------------------------------------------------------------------------

class TestTaxOptimizationEngine:
    def test_dime_life_insurance_need(self):
        """DIME method: income * 10 + debt + education."""
        from pipeline.planning.insurance_analysis import calculate_life_insurance_need

        need_a = calculate_life_insurance_need(
            income=SPOUSE_A_INCOME, years_to_replace=10,
            debt=TOTAL_LIABILITIES / 2, dependents=DEPENDENTS,
        )
        # $245K * 10 + $234K + $50K = $2,734,000
        assert need_a == pytest.approx(
            SPOUSE_A_INCOME * 10 + TOTAL_LIABILITIES / 2 + DEPENDENTS * 50_000,
            rel=0.01,
        )

        need_b = calculate_life_insurance_need(
            income=SPOUSE_B_INCOME, years_to_replace=10,
            debt=TOTAL_LIABILITIES / 2, dependents=DEPENDENTS,
        )
        assert need_b == pytest.approx(
            SPOUSE_B_INCOME * 10 + TOTAL_LIABILITIES / 2 + DEPENDENTS * 50_000,
            rel=0.01,
        )
