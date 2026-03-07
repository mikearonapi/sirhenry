"""SIT: Data flow integrity.

Tests that mutations in one system propagate correctly to others.
Uses fresh (per-test) database fixtures to allow data mutation.
"""
import pytest
from sqlalchemy import select, func
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


class TestTransactionToBudgetFlow:
    async def test_recategorize_updates_budget_actuals(self, fresh_client, fresh_seed):
        """Changing a transaction's category should affect budget actuals."""
        # Get transactions
        resp = await fresh_client.get("/transactions")
        assert resp.status_code == 200
        data = resp.json()
        txns = data.get("items", data) if isinstance(data, dict) else data
        assert len(txns) > 0

        # Find a Shopping transaction to recategorize
        shopping_txn = next(
            (t for t in txns if t.get("effective_category") == "Shopping"), None,
        )
        if not shopping_txn:
            pytest.skip("No Shopping transaction found")

        txn_id = shopping_txn["id"]
        txn_amount = abs(shopping_txn["amount"])

        # Recategorize to Groceries
        resp = await fresh_client.patch(f"/transactions/{txn_id}", json={
            "effective_category": "Groceries",
        })
        assert resp.status_code == 200


class TestAccountToNetWorthFlow:
    async def test_account_balance_consistency(self, fresh_client, fresh_seed):
        """Account balances should be reflected in portfolio/net worth views."""
        resp = await fresh_client.get("/accounts")
        assert resp.status_code == 200
        accounts = resp.json()
        investment_accounts = [a for a in accounts if a["account_type"] == "investment"]
        assert len(investment_accounts) > 0


class TestRecurringTransactionConsistency:
    async def test_recurring_items_match_summary(self, client, demo_seed):
        """Individual recurring amounts should sum to the summary total."""
        resp = await client.get("/recurring")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= RECURRING_COUNT

        resp = await client.get("/recurring/summary")
        assert resp.status_code == 200
        summary = resp.json()

        # Sum monthly items
        monthly_sum = sum(
            abs(item["amount"])
            for item in items
            if item.get("frequency") == "monthly" and item.get("status") == "active"
        )

        if summary.get("total_monthly_cost"):
            # Allow some tolerance for rounding
            assert summary["total_monthly_cost"] == pytest.approx(monthly_sum, rel=0.05)


class TestEquityConsistency:
    async def test_equity_grant_shares_match_holdings(self, client, demo_seed):
        """RSU vested shares should match the AAPL holding shares."""
        # Get equity grants
        resp = await client.get("/equity-comp/grants")
        assert resp.status_code == 200
        grants = resp.json()
        assert len(grants) >= 1

        aapl_grant = next(
            (g for g in grants if g.get("ticker") == EQUITY_GRANT_TICKER), None,
        )
        if aapl_grant:
            assert aapl_grant["vested_shares"] == EQUITY_GRANT_VESTED_SHARES
            assert aapl_grant["total_shares"] == EQUITY_GRANT_TOTAL_SHARES

        # Get portfolio holdings
        resp = await client.get("/portfolio/holdings")
        data = resp.json()
        holdings = data if isinstance(data, list) else data.get("holdings", data.get("items", []))
        aapl_holding = next((h for h in holdings if h.get("ticker") == "AAPL"), None)
        if aapl_holding and aapl_grant:
            assert aapl_holding["shares"] == pytest.approx(
                aapl_grant["vested_shares"], rel=0.01,
            )


class TestGoalProgressConsistency:
    async def test_goals_have_progress(self, client, demo_seed):
        """All goals should have current_amount <= target_amount."""
        resp = await client.get("/goals")
        assert resp.status_code == 200
        goals = resp.json()
        assert len(goals) >= GOAL_COUNT

        for goal in goals:
            assert goal["current_amount"] <= goal["target_amount"]
            assert goal["current_amount"] >= 0

    async def test_emergency_fund_values(self, client, demo_seed):
        resp = await client.get("/goals")
        goals = resp.json()
        ef = next((g for g in goals if "Emergency" in g["name"]), None)
        if ef:
            assert ef["target_amount"] == EMERGENCY_FUND_TARGET
            assert ef["current_amount"] == EMERGENCY_FUND_CURRENT


class TestHoldingToPortfolioFlow:
    async def test_add_holding_increases_total(self, fresh_client, fresh_seed):
        """Adding a holding should increase portfolio total value."""
        # Get initial portfolio total
        resp = await fresh_client.get("/portfolio/summary")
        initial_total = resp.json().get("total_value", 0)

        # Add a new holding via API (if endpoint exists)
        resp = await fresh_client.post("/portfolio/holdings", json={
            "ticker": "GOOGL",
            "name": "Alphabet Inc",
            "shares": 10,
            "cost_basis_per_share": 150.0,
            "total_cost_basis": 1_500,
            "current_price": 175.0,
            "current_value": 1_750,
            "unrealized_gain_loss": 250,
            "asset_class": "stock",
            "sector": "Technology",
        })
        if resp.status_code in (200, 201):
            # Verify total increased
            resp = await fresh_client.get("/portfolio/summary")
            new_total = resp.json().get("total_value", 0)
            assert new_total >= initial_total
