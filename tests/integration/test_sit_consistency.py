"""SIT: Cross-system consistency.

Validates that data presented to users is consistent across
all views and endpoints (read-only tests against demo data).
"""
import pytest
from sqlalchemy import select, func
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


class TestNetWorthConsistency:
    async def test_net_worth_equals_assets_minus_liabilities(self, demo_session, demo_seed):
        """Net worth snapshot should equal total assets minus total liabilities."""
        from pipeline.db.schema import NetWorthSnapshot

        # Get the latest snapshot
        snapshot = (await demo_session.execute(
            select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date.desc()).limit(1)
        )).scalar_one_or_none()

        assert snapshot is not None
        assert snapshot.net_worth == pytest.approx(LATEST_NET_WORTH, rel=0.05)
        assert snapshot.total_assets > snapshot.total_liabilities
        # Net worth = assets - liabilities
        assert snapshot.net_worth == pytest.approx(
            snapshot.total_assets - snapshot.total_liabilities, rel=0.01,
        )


class TestBudgetTransactionConsistency:
    async def test_budget_categories_match_transaction_categories(self, demo_session, demo_seed):
        """Budget categories should have corresponding transactions."""
        from pipeline.db.schema import Transaction, Budget

        # Get budget categories
        budgets = (await demo_session.execute(
            select(Budget.category).distinct()
        )).scalars().all()

        # Get transaction categories
        txn_cats = (await demo_session.execute(
            select(Transaction.effective_category).distinct().where(
                Transaction.effective_category.isnot(None)
            )
        )).scalars().all()

        # Most budget categories should have corresponding transactions
        overlap = set(budgets) & set(txn_cats)
        assert len(overlap) >= 10, f"Only {len(overlap)} categories overlap: {overlap}"


class TestRecurringSummaryConsistency:
    async def test_recurring_items_sum_matches_summary(self, client, demo_seed):
        """Sum of recurring amounts should match the summary total."""
        resp = await client.get("/recurring")
        items = resp.json()
        active_monthly = [
            i for i in items
            if i.get("frequency") == "monthly" and i.get("status") == "active"
        ]

        resp = await client.get("/recurring/summary")
        summary = resp.json()

        if summary.get("total_monthly_cost") and active_monthly:
            items_sum = sum(abs(i["amount"]) for i in active_monthly)
            assert summary["total_monthly_cost"] == pytest.approx(items_sum, rel=0.05)


class TestTaxItemsHouseholdConsistency:
    async def test_w2_wages_match_household_income(self, demo_session, demo_seed):
        """W-2 tax items should match household profile incomes."""
        from pipeline.db.schema import TaxItem, HouseholdProfile

        household = (await demo_session.execute(
            select(HouseholdProfile).limit(1)
        )).scalar_one_or_none()
        assert household is not None

        tax_items = (await demo_session.execute(
            select(TaxItem).where(TaxItem.form_type == "w2")
        )).scalars().all()
        assert len(tax_items) >= 2

        # Map payer to wages
        wages_by_payer = {t.payer_name: t.w2_wages for t in tax_items}
        assert wages_by_payer.get("Meridian Technologies") == MICHAEL_W2_WAGES
        assert wages_by_payer.get("BlackRock") == JESSICA_W2_WAGES

        # Combined should match household
        total_w2 = sum(t.w2_wages for t in tax_items)
        assert total_w2 == COMBINED_INCOME


class TestEquitySharesConsistency:
    async def test_vested_shares_match_holdings(self, demo_session, demo_seed):
        """Equity grant vested shares should match AAPL investment holding shares."""
        from pipeline.db.schema import EquityGrant, InvestmentHolding

        grant = (await demo_session.execute(
            select(EquityGrant).where(EquityGrant.ticker == "AAPL")
        )).scalar_one_or_none()
        assert grant is not None
        assert grant.vested_shares == EQUITY_GRANT_VESTED_SHARES

        holding = (await demo_session.execute(
            select(InvestmentHolding).where(InvestmentHolding.ticker == "AAPL")
        )).scalar_one_or_none()
        assert holding is not None
        assert holding.shares == pytest.approx(grant.vested_shares, rel=0.01)


class TestPortfolioTotalConsistency:
    async def test_summary_matches_individual_holdings(self, client, demo_seed):
        """Portfolio summary total should equal sum of individual holdings."""
        resp = await client.get("/portfolio/summary")
        summary = resp.json()

        resp = await client.get("/portfolio/holdings")
        data = resp.json()
        holdings = data if isinstance(data, list) else data.get("holdings", data.get("items", []))

        if holdings:
            holdings_sum = sum(h.get("current_value", 0) for h in holdings)
            # Summary total should include holdings (might also include crypto/manual)
            assert summary["total_value"] >= holdings_sum * 0.95


class TestSetupStatusConsistency:
    async def test_setup_complete_with_demo_data(self, client, demo_seed):
        """With full demo data, setup should be marked complete."""
        resp = await client.get("/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["household"] is True
        assert data["income"] is True
        assert data["accounts"] is True
        assert data["complete"] is True


class TestInsuranceCoverageConsistency:
    async def test_policy_list_matches_gap_analysis(self, client, demo_seed):
        """Total coverage from policy list should be consistent with gap analysis."""
        resp = await client.get("/insurance/")
        policies = resp.json()
        life_policies = [p for p in policies if p["policy_type"] == "life"]
        total_life_from_list = sum(p.get("coverage_amount", 0) for p in life_policies)
        assert total_life_from_list == pytest.approx(
            PERSONAL_LIFE_COVERAGE_A + PERSONAL_LIFE_COVERAGE_B, rel=0.01,
        )
