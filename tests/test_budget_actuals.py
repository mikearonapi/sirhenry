"""Tests for pipeline/planning/budget_actuals.py — budget vs actuals."""
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from pipeline.planning.budget_actuals import (
    INTERNAL_TRANSFER_CATEGORIES,
    _BASE_INCOME_CATEGORIES,
    get_income_categories,
    fetch_actuals,
)
from pipeline.db.schema import Account, Transaction, HouseholdProfile


class TestConstants:
    def test_transfer_categories_exist(self):
        assert "Transfer" in INTERNAL_TRANSFER_CATEGORIES
        assert "Credit Card Payment" in INTERNAL_TRANSFER_CATEGORIES

    def test_base_income_categories(self):
        assert "W-2 Wages" in _BASE_INCOME_CATEGORIES
        assert "Dividend Income" in _BASE_INCOME_CATEGORIES
        assert "K-1 / Partnership Income" in _BASE_INCOME_CATEGORIES


class TestGetIncomeCategories:
    async def test_base_only(self, session):
        """Without a household profile, returns base categories."""
        categories = await get_income_categories(session)
        assert "W-2 Wages" in categories

    async def test_employer_specific(self, session):
        """With an employer set, adds employer-specific categories."""
        hp = HouseholdProfile(
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            spouse_b_income=100000,
            combined_income=300000,
            spouse_a_employer="Google",
            is_primary=True,
        )
        session.add(hp)
        await session.flush()

        categories = await get_income_categories(session)
        assert "Google Paycheck" in categories
        assert "Google Bonus" in categories
        assert "Google Expenses" in categories


class TestFetchActuals:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_data(self, session):
        """Create an account and sample transactions for Jan 2025."""
        acct = Account(name="Test Checking", institution="Test Bank", account_type="depository")
        session.add(acct)
        await session.flush()
        self.account_id = acct.id

        txns = [
            Transaction(
                account_id=acct.id,
                date=datetime(2025, 1, 5, tzinfo=timezone.utc),
                description="Grocery Store",
                amount=-200.0,
                effective_category="Groceries",
                period_year=2025,
                period_month=1,
                is_excluded=False,
            ),
            Transaction(
                account_id=acct.id,
                date=datetime(2025, 1, 10, tzinfo=timezone.utc),
                description="Gas Station",
                amount=-50.0,
                effective_category="Gas & Fuel",
                period_year=2025,
                period_month=1,
                is_excluded=False,
            ),
            Transaction(
                account_id=acct.id,
                date=datetime(2025, 1, 15, tzinfo=timezone.utc),
                description="Paycheck",
                amount=5000.0,
                effective_category="W-2 Wages",
                period_year=2025,
                period_month=1,
                is_excluded=False,
            ),
            # Internal transfer — should be excluded
            Transaction(
                account_id=acct.id,
                date=datetime(2025, 1, 20, tzinfo=timezone.utc),
                description="Transfer to Savings",
                amount=-1000.0,
                effective_category="Transfer",
                period_year=2025,
                period_month=1,
                is_excluded=False,
            ),
            # Excluded transaction — should not appear
            Transaction(
                account_id=acct.id,
                date=datetime(2025, 1, 25, tzinfo=timezone.utc),
                description="Excluded Purchase",
                amount=-100.0,
                effective_category="Shopping",
                period_year=2025,
                period_month=1,
                is_excluded=True,
            ),
        ]
        for t in txns:
            session.add(t)
        await session.flush()

    async def test_expense_totals(self, session):
        actuals = await fetch_actuals(session, 2025, 1)
        assert actuals["Groceries"] == 200.0  # abs(-200)
        assert actuals["Gas & Fuel"] == 50.0  # abs(-50)

    async def test_transfer_excluded(self, session):
        actuals = await fetch_actuals(session, 2025, 1)
        assert "Transfer" not in actuals

    async def test_excluded_transactions_skipped(self, session):
        actuals = await fetch_actuals(session, 2025, 1)
        assert "Shopping" not in actuals

    async def test_income_included(self, session):
        actuals = await fetch_actuals(session, 2025, 1)
        assert "W-2 Wages" in actuals
        assert actuals["W-2 Wages"] == 5000.0

    async def test_empty_month(self, session):
        actuals = await fetch_actuals(session, 2025, 6)  # No data for June
        assert len(actuals) == 0

    async def test_category_grouping(self, session):
        """Multiple transactions in same category should sum."""
        session.add(Transaction(
            account_id=self.account_id,
            date=datetime(2025, 1, 28, tzinfo=timezone.utc),
            description="Another Grocery",
            amount=-75.0,
            effective_category="Groceries",
            period_year=2025,
            period_month=1,
            is_excluded=False,
        ))
        await session.flush()

        actuals = await fetch_actuals(session, 2025, 1)
        assert actuals["Groceries"] == 275.0  # 200 + 75
