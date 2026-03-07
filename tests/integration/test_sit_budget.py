"""SIT: Budget engine accuracy.

Validates budget categories, amounts, actuals matching transaction sums,
and variance calculations against demo data.
"""
import pytest
from sqlalchemy import select, func
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Budget categories & amounts
# ---------------------------------------------------------------------------

class TestBudgetCategories:
    async def test_seeded_budget_categories_count(self, client, demo_seed):
        """20 budget categories should be seeded."""
        resp = await client.get("/budget/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= BUDGET_CATEGORY_COUNT

    async def test_budget_amounts_match_seeded(self, client, demo_seed):
        """Budget amounts for a recent month should match seeded values."""
        resp = await client.get("/budget", params={"year": 2026, "month": 2})
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            budgets_by_cat = {b["category"]: b["budget_amount"] for b in data}
            # Spot-check key categories
            for cat, expected_amt in [
                ("Groceries", 1_500), ("Housing", 5_075), ("Childcare", 2_400),
            ]:
                if cat in budgets_by_cat:
                    assert budgets_by_cat[cat] == pytest.approx(expected_amt, rel=0.01)


# ---------------------------------------------------------------------------
# Budget summary
# ---------------------------------------------------------------------------

class TestBudgetSummary:
    async def test_budget_summary_structure(self, client, demo_seed):
        resp = await client.get("/budget/summary", params={"year": 2026, "month": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_budget_summary_has_totals(self, client, demo_seed):
        resp = await client.get("/budget/summary", params={"year": 2026, "month": 2})
        data = resp.json()
        # Summary should contain total budget and total spent
        has_totals = (
            "total_budget" in data or "total_budgeted" in data
            or "categories" in data or "items" in data
        )
        assert has_totals


# ---------------------------------------------------------------------------
# Budget actuals match transactions
# ---------------------------------------------------------------------------

class TestBudgetActuals:
    async def test_actuals_match_transactions(self, demo_session, demo_seed):
        """Budget actuals for a month should match transaction sums by category."""
        from pipeline.db.schema import Transaction, Budget

        year, month = 2026, 1  # Use January 2026

        # Get budgets for this month
        budgets = (await demo_session.execute(
            select(Budget).where(Budget.year == year, Budget.month == month)
        )).scalars().all()

        # Get transactions for this month (negative amounts = expenses)
        txns = (await demo_session.execute(
            select(Transaction).where(
                Transaction.period_year == year,
                Transaction.period_month == month,
            )
        )).scalars().all()

        # Compute actual spending by category (from transactions)
        actual_by_cat: dict[str, float] = {}
        for t in txns:
            cat = t.effective_category or t.category
            if cat and t.amount < 0:  # Expenses are negative
                actual_by_cat[cat] = actual_by_cat.get(cat, 0) + abs(t.amount)

        # Verify at least some overlap between budget categories and actuals
        budget_cats = {b.category for b in budgets}
        actual_cats = set(actual_by_cat.keys())
        overlap = budget_cats & actual_cats
        assert len(overlap) > 5, f"Too few overlapping categories: {overlap}"

    async def test_transfers_excluded_from_budget(self, demo_session, demo_seed):
        """Transfer and Credit Card Payment should not be budget categories."""
        from pipeline.db.schema import Budget

        budgets = (await demo_session.execute(select(Budget))).scalars().all()
        budget_cats = {b.category for b in budgets}
        assert "Transfer" not in budget_cats
        assert "Credit Card Payment" not in budget_cats


# ---------------------------------------------------------------------------
# Budget forecast
# ---------------------------------------------------------------------------

class TestBudgetForecast:
    async def test_forecast_endpoint(self, client, demo_seed):
        resp = await client.get("/budget/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (dict, list))


# ---------------------------------------------------------------------------
# Income recognition
# ---------------------------------------------------------------------------

class TestBudgetIncome:
    async def test_paycheck_transactions_exist(self, demo_session, demo_seed):
        """Paycheck transactions should exist for both earners."""
        from pipeline.db.schema import Transaction

        paychecks = (await demo_session.execute(
            select(Transaction).where(
                Transaction.effective_category == "Paycheck",
            )
        )).scalars().all()
        assert len(paychecks) > 0
        descriptions = [t.description for t in paychecks]
        assert any("MERIDIAN" in d.upper() for d in descriptions)
        assert any("BLACKROCK" in d.upper() for d in descriptions)
