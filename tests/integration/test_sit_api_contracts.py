"""SIT: API contract validation.

Validates that every major API endpoint returns data matching
the expected response shape (fields, types, structure).
"""
import pytest
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


class TestAccountsContract:
    async def test_accounts_shape(self, client, demo_seed):
        resp = await client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= ACCOUNT_COUNT

        acct = data[0]
        assert isinstance(acct["id"], int)
        assert isinstance(acct["name"], str)
        assert "institution" in acct
        assert "account_type" in acct

    async def test_account_types_valid(self, client, demo_seed):
        resp = await client.get("/accounts")
        valid_types = {"personal", "business", "investment", "income"}
        for acct in resp.json():
            assert acct["account_type"] in valid_types


class TestTransactionsContract:
    async def test_transactions_shape(self, client, demo_seed):
        resp = await client.get("/transactions")
        assert resp.status_code == 200
        data = resp.json()
        # Might be a list or paginated dict
        if isinstance(data, dict):
            txns = data.get("items", [])
            assert isinstance(txns, list)
        else:
            txns = data
            assert isinstance(txns, list)
        assert len(txns) > 0

        txn = txns[0]
        assert isinstance(txn["id"], int)
        assert "description" in txn
        assert "amount" in txn
        assert isinstance(txn["amount"], (int, float))

    async def test_pagination(self, client, demo_seed):
        resp = await client.get("/transactions", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        txns = data.get("items", data) if isinstance(data, dict) else data
        assert len(txns) <= 5


class TestBudgetContract:
    async def test_budget_summary_shape(self, client, demo_seed):
        resp = await client.get("/budget/summary", params={"year": 2026, "month": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestHouseholdContract:
    async def test_profiles_shape(self, client, demo_seed):
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        p = data[0]
        assert isinstance(p["id"], int)
        assert "filing_status" in p
        assert "state" in p
        assert "combined_income" in p
        assert isinstance(p["combined_income"], (int, float))


class TestRetirementContract:
    async def test_profiles_shape(self, client, demo_seed):
        resp = await client.get("/retirement/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 1

        p = profiles[0]
        required_fields = [
            "id", "name", "current_age", "retirement_age",
            "current_annual_income", "monthly_retirement_contribution",
        ]
        for field in required_fields:
            assert field in p, f"Missing field: {field}"


class TestPortfolioContract:
    async def test_summary_shape(self, client, demo_seed):
        resp = await client.get("/portfolio/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_value" in data
        assert "holdings_count" in data
        assert isinstance(data["total_value"], (int, float))


class TestInsuranceContract:
    async def test_insurance_shape(self, client, demo_seed):
        resp = await client.get("/insurance/")
        assert resp.status_code == 200
        policies = resp.json()
        assert isinstance(policies, list)
        for p in policies:
            assert "policy_type" in p
            assert "provider" in p
            assert "is_active" in p


class TestEquityCompContract:
    async def test_grants_shape(self, client, demo_seed):
        resp = await client.get("/equity-comp/grants")
        assert resp.status_code == 200
        grants = resp.json()
        assert isinstance(grants, list)
        if grants:
            g = grants[0]
            assert "total_shares" in g
            assert "vested_shares" in g
            assert "ticker" in g

    async def test_dashboard_shape(self, client, demo_seed):
        resp = await client.get("/equity-comp/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestTaxContract:
    async def test_tax_summary_shape(self, client, demo_seed):
        resp = await client.get("/tax/summary", params={"tax_year": TAX_YEAR})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_tax_checklist_shape(self, client, demo_seed):
        resp = await client.get("/tax/checklist", params={"tax_year": TAX_YEAR})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


class TestGoalsContract:
    async def test_goals_shape(self, client, demo_seed):
        resp = await client.get("/goals")
        assert resp.status_code == 200
        goals = resp.json()
        assert isinstance(goals, list)
        if goals:
            g = goals[0]
            assert "name" in g
            assert "target_amount" in g
            assert "current_amount" in g
            assert "status" in g


class TestRecurringContract:
    async def test_recurring_shape(self, client, demo_seed):
        resp = await client.get("/recurring")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        if items:
            item = items[0]
            assert "name" in item
            assert "amount" in item
            assert "frequency" in item

    async def test_recurring_summary_shape(self, client, demo_seed):
        resp = await client.get("/recurring/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_monthly_cost" in data
        assert "total_annual_cost" in data


class TestLifeEventsContract:
    async def test_life_events_shape(self, client, demo_seed):
        resp = await client.get("/life-events/")
        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)
        assert len(events) >= LIFE_EVENT_COUNT
        if events:
            e = events[0]
            assert "event_type" in e
            assert "title" in e


class TestErrorResponses:
    async def test_404_format(self, client, demo_seed):
        resp = await client.get("/nonexistent-endpoint")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    async def test_invalid_param_returns_error(self, client, demo_seed):
        resp = await client.get("/transactions", params={"limit": "invalid"})
        # Should return 422 (validation error) or handle gracefully
        assert resp.status_code in (200, 422)


class TestSetupStatusContract:
    async def test_setup_status_shape(self, client, demo_seed):
        resp = await client.get("/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "household" in data
        assert "income" in data
        assert "accounts" in data
        assert "complete" in data
        assert isinstance(data["complete"], bool)
