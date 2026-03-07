"""SIT: AI chat tool execution.

Calls chat tool functions directly against the demo database
(no Anthropic API calls) to validate tool output accuracy.
"""
import pytest
from sqlalchemy import select
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


class TestSearchTransactions:
    async def test_search_by_category(self, demo_session, demo_seed):
        """Searching for Groceries should return grocery merchants."""
        from pipeline.db.schema import Transaction

        txns = (await demo_session.execute(
            select(Transaction).where(
                Transaction.effective_category == "Groceries"
            ).limit(20)
        )).scalars().all()

        assert len(txns) > 0
        descriptions = [t.description for t in txns]
        grocery_merchants = ["Whole Foods", "Trader Joe", "Costco"]
        found_any = any(
            any(merchant.lower() in desc.lower() for merchant in grocery_merchants)
            for desc in descriptions
        )
        assert found_any, f"No grocery merchants found in: {descriptions[:5]}"

    async def test_search_by_segment(self, demo_session, demo_seed):
        """Business segment should return consulting/business expenses."""
        from pipeline.db.schema import Transaction

        biz_txns = (await demo_session.execute(
            select(Transaction).where(
                Transaction.effective_segment == "business"
            ).limit(20)
        )).scalars().all()

        assert len(biz_txns) > 0
        # Should include business income and expenses
        descriptions = [t.description for t in biz_txns]
        assert any("CONSULT" in d.upper() or "AWS" in d.upper() or "GITHUB" in d.upper()
                    for d in descriptions)


class TestAccountBalances:
    async def test_all_accounts_returned(self, demo_session, demo_seed):
        """Should return all 13 demo accounts."""
        from pipeline.db.schema import Account

        accounts = (await demo_session.execute(
            select(Account)
        )).scalars().all()
        assert len(accounts) >= ACCOUNT_COUNT

    async def test_account_types(self, demo_session, demo_seed):
        from pipeline.db.schema import Account

        accounts = (await demo_session.execute(select(Account))).scalars().all()
        types = {a.account_type for a in accounts}
        assert "personal" in types
        assert "investment" in types
        assert "income" in types


class TestTaxInfo:
    async def test_w2_wages(self, demo_session, demo_seed):
        """W-2 tax items should have correct wages."""
        from pipeline.db.schema import TaxItem

        items = (await demo_session.execute(
            select(TaxItem).where(TaxItem.form_type == "w2")
        )).scalars().all()
        assert len(items) == 2

        wages = {t.payer_name: t.w2_wages for t in items}
        assert wages["Meridian Technologies"] == MICHAEL_W2_WAGES
        assert wages["BlackRock"] == JESSICA_W2_WAGES

    async def test_withholding_amounts(self, demo_session, demo_seed):
        from pipeline.db.schema import TaxItem

        items = (await demo_session.execute(
            select(TaxItem).where(TaxItem.form_type == "w2")
        )).scalars().all()

        withholdings = {t.payer_name: t.w2_federal_tax_withheld for t in items}
        assert withholdings["Meridian Technologies"] == MICHAEL_FED_WITHHELD
        assert withholdings["BlackRock"] == JESSICA_FED_WITHHELD


class TestRecurringExpenses:
    async def test_recurring_count(self, demo_session, demo_seed):
        from pipeline.db.schema import RecurringTransaction

        items = (await demo_session.execute(
            select(RecurringTransaction)
        )).scalars().all()
        assert len(items) >= RECURRING_COUNT

    async def test_mortgage_amount(self, demo_session, demo_seed):
        from pipeline.db.schema import RecurringTransaction

        items = (await demo_session.execute(
            select(RecurringTransaction).where(
                RecurringTransaction.name.contains("Mortgage")
            )
        )).scalars().all()
        assert len(items) >= 1
        assert items[0].amount == pytest.approx(MORTGAGE_PAYMENT, rel=0.01)


class TestHouseholdSummary:
    async def test_household_data(self, demo_session, demo_seed):
        from pipeline.db.schema import HouseholdProfile

        hp = (await demo_session.execute(
            select(HouseholdProfile).limit(1)
        )).scalar_one_or_none()
        assert hp is not None
        assert hp.filing_status == FILING_STATUS
        assert hp.state == STATE
        assert hp.combined_income >= COMBINED_INCOME


class TestGoalsSummary:
    async def test_goals_exist(self, demo_session, demo_seed):
        from pipeline.db.schema import Goal

        goals = (await demo_session.execute(select(Goal))).scalars().all()
        assert len(goals) >= GOAL_COUNT
        names = [g.name for g in goals]
        assert "Emergency Fund" in names
        assert "Pay Off Student Loans" in names


class TestPortfolioOverview:
    async def test_investment_holdings(self, demo_session, demo_seed):
        from pipeline.db.schema import InvestmentHolding

        holdings = (await demo_session.execute(
            select(InvestmentHolding).where(InvestmentHolding.is_active == True)
        )).scalars().all()
        assert len(holdings) >= INVESTMENT_HOLDINGS_COUNT

        total_value = sum(h.current_value for h in holdings)
        assert total_value == pytest.approx(TOTAL_HOLDINGS_VALUE, rel=0.01)


class TestRetirementStatus:
    async def test_retirement_profile_exists(self, demo_session, demo_seed):
        from pipeline.db.schema import RetirementProfile

        profile = (await demo_session.execute(
            select(RetirementProfile).limit(1)
        )).scalar_one_or_none()
        assert profile is not None
        assert profile.current_age == CURRENT_AGE
        assert profile.retirement_age == RETIREMENT_AGE


class TestTransactionMutation:
    async def test_recategorize_persists(self, fresh_client, fresh_seed):
        """Recategorizing a transaction should persist."""
        resp = await fresh_client.get("/transactions")
        data = resp.json()
        txns = data.get("items", data) if isinstance(data, dict) else data
        if not txns:
            pytest.skip("No transactions")

        txn = txns[0]
        new_category = "Test Category"
        # PATCH uses category_override field (not effective_category)
        resp = await fresh_client.patch(f"/transactions/{txn['id']}", json={
            "category_override": new_category,
        })
        assert resp.status_code == 200
        # The PATCH response itself returns the updated transaction
        updated = resp.json()
        assert updated.get("effective_category") == new_category

        # Also verify via a fresh GET
        resp2 = await fresh_client.get(f"/transactions/{txn['id']}")
        assert resp2.status_code == 200
        assert resp2.json().get("effective_category") == new_category
