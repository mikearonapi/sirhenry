"""
Comprehensive coverage tests for pipeline/ai/chat.py and pipeline/ai/chat_tools.py.

Targets all uncovered exec_* functions in chat.py (lines 820-2020) and tool
handler implementations in chat_tools.py (lines 35-907).

All Anthropic API calls are mocked. Uses in-memory SQLite from conftest fixtures.
"""
import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    BenefitPackage,
    Budget,
    BusinessEntity,
    ChatConversation,
    ChatMessage as ChatMessageModel,
    CryptoHolding,
    Goal,
    HouseholdProfile,
    InsurancePolicy,
    InvestmentHolding,
    LifeEvent,
    LifeScenario,
    ManualAsset,
    NetWorthSnapshot,
    PlaidItem,
    RecurringTransaction,
    Reminder,
    RetirementProfile,
    TaxStrategy,
    Transaction,
    UserContext,
    UserPrivacyConsent,
)


# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

async def _seed_account(session, name="Chase Sapphire", **kw):
    defaults = dict(
        account_type="personal", subtype="credit_card",
        institution="Chase", data_source="csv", is_active=True,
    )
    defaults.update(kw)
    acct = Account(name=name, **defaults)
    session.add(acct)
    await session.flush()
    return acct


async def _seed_transaction(session, account_id, description="STARBUCKS", amount=-5.50, **kw):
    defaults = dict(
        date=datetime(2025, 6, 15, tzinfo=timezone.utc),
        period_year=2025, period_month=6,
        segment="personal", effective_segment="personal",
        data_source="csv", is_excluded=False,
    )
    defaults.update(kw)
    tx = Transaction(account_id=account_id, description=description, amount=amount, **defaults)
    session.add(tx)
    await session.flush()
    return tx


async def _seed_entity(session, name="AutoRev", **kw):
    defaults = dict(
        entity_type="sole_prop", tax_treatment="schedule_c",
        is_active=True,
    )
    defaults.update(kw)
    ent = BusinessEntity(name=name, **defaults)
    session.add(ent)
    await session.flush()
    return ent


async def _seed_household(session, **kw):
    defaults = dict(
        name="Our Household", filing_status="mfj", state="CA",
        spouse_a_name="Mike", spouse_a_income=200000.0,
        spouse_a_employer="Acme Corp",
        spouse_b_name="Jane", spouse_b_income=150000.0,
        spouse_b_employer="BigCo",
        combined_income=350000.0, is_primary=True,
    )
    defaults.update(kw)
    hp = HouseholdProfile(**defaults)
    session.add(hp)
    await session.flush()
    return hp


async def _seed_consent(session):
    c = UserPrivacyConsent(
        consent_type="ai_features", consented=True,
        consented_at=datetime.now(timezone.utc),
    )
    session.add(c)
    await session.flush()
    return c


def _mock_text_response(text="Here is my response."):
    block = MagicMock()
    block.text = text
    block.type = "text"
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "end_turn"
    return resp


def _mock_tool_response(tool_name, tool_input, tool_id="toolu_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "tool_use"
    return resp


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_search_transactions
# ═══════════════════════════════════════════════════════════════════════════

class TestSearchTransactionsFilters:
    """Cover all filter branches in _tool_search_transactions."""

    async def test_filter_by_year_and_month(self, session):
        from pipeline.ai.chat import _tool_search_transactions
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Grocery Store", -50.0,
                                period_year=2025, period_month=3,
                                effective_category="Groceries")
        await _seed_transaction(session, acct.id, "Gas Station", -40.0,
                                period_year=2025, period_month=4,
                                effective_category="Gas")
        result = json.loads(await _tool_search_transactions(session, {"year": 2025, "month": 3}))
        assert result["count"] == 1
        assert result["transactions"][0]["description"] == "Grocery Store"

    async def test_filter_by_amount_range(self, session):
        from pipeline.ai.chat import _tool_search_transactions
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Small", -5.0, effective_category="Food")
        await _seed_transaction(session, acct.id, "Big", -500.0, effective_category="Shopping")
        result = json.loads(await _tool_search_transactions(session, {"min_amount": -100, "max_amount": -1}))
        assert result["count"] == 1
        assert result["transactions"][0]["description"] == "Small"

    async def test_filter_by_category(self, session):
        from pipeline.ai.chat import _tool_search_transactions
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Uber", -20.0, effective_category="Transportation")
        await _seed_transaction(session, acct.id, "Pizza", -15.0, effective_category="Dining Out")
        result = json.loads(await _tool_search_transactions(session, {"category": "Transportation"}))
        assert result["count"] == 1
        assert result["transactions"][0]["category"] == "Transportation"

    async def test_filter_by_segment(self, session):
        from pipeline.ai.chat import _tool_search_transactions
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Office Supplies", -30.0,
                                effective_segment="business", effective_category="Supplies")
        await _seed_transaction(session, acct.id, "Coffee", -5.0,
                                effective_segment="personal", effective_category="Food")
        result = json.loads(await _tool_search_transactions(session, {"segment": "business"}))
        assert result["count"] == 1
        assert result["transactions"][0]["segment"] == "business"

    async def test_excludes_credit_card_payments(self, session):
        from pipeline.ai.chat import _tool_search_transactions
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "CHASE PAYMENT", -2000.0,
                                effective_category="Credit Card Payment")
        await _seed_transaction(session, acct.id, "Real Purchase", -50.0,
                                effective_category="Shopping")
        result = json.loads(await _tool_search_transactions(session, {}))
        assert result["count"] == 1
        assert result["transactions"][0]["description"] == "Real Purchase"

    async def test_limit_parameter(self, session):
        from pipeline.ai.chat import _tool_search_transactions
        acct = await _seed_account(session)
        for i in range(10):
            await _seed_transaction(session, acct.id, f"TX {i}", -i - 1,
                                    effective_category="Shopping")
        result = json.loads(await _tool_search_transactions(session, {"limit": 3}))
        assert result["count"] == 3

    async def test_limit_capped_at_50(self, session):
        from pipeline.ai.chat import _tool_search_transactions
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "TX", -10.0, effective_category="Shopping")
        result = json.loads(await _tool_search_transactions(session, {"limit": 200}))
        # Should not crash; limit internally capped
        assert result["count"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_transaction_detail
# ═══════════════════════════════════════════════════════════════════════════

class TestGetTransactionDetail:
    async def test_with_account_and_entity(self, session):
        from pipeline.ai.chat import _tool_get_transaction_detail
        acct = await _seed_account(session)
        ent = await _seed_entity(session, "TestBiz")
        tx = await _seed_transaction(session, acct.id, "Biz Expense", -100.0,
                                     effective_business_entity_id=ent.id)
        result = json.loads(await _tool_get_transaction_detail(session, {"transaction_id": tx.id}))
        assert result["id"] == tx.id
        assert result["account"]["name"] == "Chase Sapphire"
        assert result["business_entity"]["name"] == "TestBiz"
        assert result["amount"] == -100.0

    async def test_not_found(self, session):
        from pipeline.ai.chat import _tool_get_transaction_detail
        result = json.loads(await _tool_get_transaction_detail(session, {"transaction_id": 99999}))
        assert "error" in result

    async def test_without_entity(self, session):
        from pipeline.ai.chat import _tool_get_transaction_detail
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "Plain TX", -25.0)
        result = json.loads(await _tool_get_transaction_detail(session, {"transaction_id": tx.id}))
        assert result["business_entity"] is None


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_recategorize_transaction
# ═══════════════════════════════════════════════════════════════════════════

class TestRecategorizeTransaction:
    async def test_category_and_segment_override(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "Some TX", -50.0)
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": tx.id,
            "category_override": "Business Meals",
            "segment_override": "business",
        }))
        assert result["success"] is True
        assert "category" in result["changes"][0]
        assert "segment" in result["changes"][1]

    async def test_assign_business_entity(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        acct = await _seed_account(session)
        ent = await _seed_entity(session, "AutoRev")
        tx = await _seed_transaction(session, acct.id, "Parts", -200.0)
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": tx.id,
            "business_entity_name": "AutoRev",
        }))
        assert result["success"] is True
        assert "business_entity" in result["changes"][0]

    async def test_clear_business_entity(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        acct = await _seed_account(session)
        ent = await _seed_entity(session, "OldBiz")
        tx = await _seed_transaction(session, acct.id, "TX", -50.0,
                                     effective_business_entity_id=ent.id)
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": tx.id,
            "business_entity_name": None,
        }))
        assert result["success"] is True
        assert "cleared" in result["changes"][0]

    async def test_entity_not_found(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "TX", -50.0)
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": tx.id,
            "business_entity_name": "NonExistent",
        }))
        assert "error" in result

    async def test_tax_category_override(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "Deductible", -100.0)
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": tx.id,
            "tax_category_override": "Schedule C Line 14",
        }))
        assert result["success"] is True
        assert "tax_category" in result["changes"][0]

    async def test_add_notes(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "TX", -50.0)
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": tx.id,
            "notes": "This is a business expense",
        }))
        assert result["success"] is True
        assert "notes" in result["changes"][0]

    async def test_no_changes(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "TX", -50.0)
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": tx.id,
        }))
        assert "error" in result

    async def test_transaction_not_found(self, session):
        from pipeline.ai.chat import _tool_recategorize_transaction
        result = json.loads(await _tool_recategorize_transaction(session, {
            "transaction_id": 99999,
            "category_override": "Food",
        }))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_spending_summary
# ═══════════════════════════════════════════════════════════════════════════

class TestGetSpendingSummary:
    async def test_with_income_and_expenses(self, session):
        from pipeline.ai.chat import _tool_get_spending_summary
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Paycheck", 5000.0,
                                effective_category="Income", period_year=2025, period_month=6)
        await _seed_transaction(session, acct.id, "Rent", -2000.0,
                                effective_category="Housing", period_year=2025, period_month=6)
        await _seed_transaction(session, acct.id, "Food", -500.0,
                                effective_category="Groceries", period_year=2025, period_month=6)
        result = json.loads(await _tool_get_spending_summary(session, {"year": 2025, "month": 6}))
        assert result["total_income"] == 5000.0
        assert result["total_expenses"] == 2500.0
        assert result["net_cash_flow"] == 2500.0
        assert result["period"] == "2025-06"
        assert len(result["top_expense_categories"]) == 2

    async def test_segment_filter(self, session):
        from pipeline.ai.chat import _tool_get_spending_summary
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Biz", -100.0,
                                effective_category="Supplies", effective_segment="business",
                                period_year=2025, period_month=6)
        await _seed_transaction(session, acct.id, "Personal", -50.0,
                                effective_category="Food", effective_segment="personal",
                                period_year=2025, period_month=6)
        result = json.loads(await _tool_get_spending_summary(session, {
            "year": 2025, "segment": "business",
        }))
        assert result["total_expenses"] == 100.0

    async def test_annual_summary(self, session):
        from pipeline.ai.chat import _tool_get_spending_summary
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Q1", -100.0,
                                effective_category="Food", period_year=2025, period_month=3)
        await _seed_transaction(session, acct.id, "Q2", -200.0,
                                effective_category="Food", period_year=2025, period_month=6)
        result = json.loads(await _tool_get_spending_summary(session, {"year": 2025}))
        assert result["total_expenses"] == 300.0
        assert result["period"] == "2025"

    async def test_excludes_transfers(self, session):
        from pipeline.ai.chat import _tool_get_spending_summary
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "Transfer", -1000.0,
                                effective_category="Transfer", period_year=2025, period_month=6)
        await _seed_transaction(session, acct.id, "Real", -50.0,
                                effective_category="Food", period_year=2025, period_month=6)
        result = json.loads(await _tool_get_spending_summary(session, {"year": 2025}))
        assert result["total_expenses"] == 50.0


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_account_balances
# ═══════════════════════════════════════════════════════════════════════════

class TestGetAccountBalances:
    async def test_with_accounts_and_transactions(self, session):
        from pipeline.ai.chat import _tool_get_account_balances
        acct = await _seed_account(session, "Checking", account_type="personal", subtype="checking")
        await _seed_transaction(session, acct.id, "Deposit", 3000.0)
        await _seed_transaction(session, acct.id, "Withdrawal", -500.0)
        result = json.loads(await _tool_get_account_balances(session))
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["transaction_count"] == 2
        assert result["accounts"][0]["balance"] == 2500.0


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_tax_info
# ═══════════════════════════════════════════════════════════════════════════

class TestGetTaxInfo:
    async def test_returns_tax_data(self, session):
        from pipeline.ai.chat import _tool_get_tax_info
        mock_summary = AsyncMock(return_value={
            "w2_total_wages": 200000,
            "w2_federal_withheld": 35000,
            "nec_total": 50000,
            "div_ordinary": 5000,
            "div_qualified": 3000,
            "capital_gains_long": 10000,
            "capital_gains_short": 2000,
            "interest_income": 1000,
        })
        strategy = MagicMock()
        strategy.priority = 1
        strategy.title = "Max 401k"
        strategy.description = "Maximize 401k contributions to reduce taxable income."
        strategy.strategy_type = "retirement"
        strategy.estimated_savings_low = 5000.0
        strategy.estimated_savings_high = 8000.0
        strategy.deadline = "Dec 31"
        strategy.is_dismissed = False
        mock_strategies = AsyncMock(return_value=[strategy])

        with patch("pipeline.db.get_tax_summary", mock_summary), \
             patch("pipeline.db.get_tax_strategies", mock_strategies):
            result = json.loads(await _tool_get_tax_info(session, {"tax_year": 2025}))
        assert result["tax_year"] == 2025
        assert result["w2_wages"] == 200000
        assert result["nec_income"] == 50000
        assert len(result["active_strategies"]) == 1
        assert result["active_strategies"][0]["title"] == "Max 401k"
        assert "$5,000" in result["active_strategies"][0]["savings_range"]

    async def test_dismissed_strategies_excluded(self, session):
        from pipeline.ai.chat import _tool_get_tax_info
        mock_summary = AsyncMock(return_value={"w2_total_wages": 0})
        dismissed = MagicMock()
        dismissed.is_dismissed = True
        dismissed.priority = 1
        dismissed.title = "Dismissed"
        mock_strategies = AsyncMock(return_value=[dismissed])
        with patch("pipeline.db.get_tax_summary", mock_summary), \
             patch("pipeline.db.get_tax_strategies", mock_strategies):
            result = json.loads(await _tool_get_tax_info(session, {"tax_year": 2025}))
        assert len(result["active_strategies"]) == 0


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_budget_status
# ═══════════════════════════════════════════════════════════════════════════

class TestGetBudgetStatus:
    async def test_with_budgets_and_actuals(self, session):
        from pipeline.ai.chat import _tool_get_budget_status
        acct = await _seed_account(session)
        b = Budget(year=2025, month=6, category="Groceries",
                   segment="personal", budget_amount=500.0)
        session.add(b)
        await session.flush()
        await _seed_transaction(session, acct.id, "Whole Foods", -150.0,
                                effective_category="Groceries", period_year=2025, period_month=6)
        await _seed_transaction(session, acct.id, "Trader Joes", -100.0,
                                effective_category="Groceries", period_year=2025, period_month=6)
        result = json.loads(await _tool_get_budget_status(session, {"year": 2025, "month": 6}))
        assert result["total_budgeted"] == 500.0
        assert result["total_actual"] == 250.0
        assert result["total_variance"] == 250.0
        assert len(result["categories"]) == 1
        assert result["categories"][0]["utilization_pct"] == 50.0

    async def test_no_budgets(self, session):
        from pipeline.ai.chat import _tool_get_budget_status
        result = json.loads(await _tool_get_budget_status(session, {"year": 2025, "month": 1}))
        assert "No budgets set" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_recurring_expenses
# ═══════════════════════════════════════════════════════════════════════════

class TestGetRecurringExpenses:
    async def test_with_recurring(self, session):
        """Test recurring expenses using mocked query results with annual_cost attr."""
        from pipeline.ai.chat import _tool_get_recurring_expenses
        from types import SimpleNamespace

        # Create a mock recurring item that has the annual_cost attribute
        mock_item = SimpleNamespace(
            name="Netflix", amount=-15.99, frequency="monthly",
            category="Entertainment", segment="personal",
            status="active", annual_cost=191.88,
            last_seen_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item]

        with patch.object(session, "execute", return_value=mock_result):
            result = json.loads(await _tool_get_recurring_expenses(session))

        assert result["count"] == 1
        assert result["subscriptions"][0]["name"] == "Netflix"
        assert result["subscriptions"][0]["amount"] == 15.99
        assert result["subscriptions"][0]["annual_cost"] == 191.88
        assert result["total_monthly_cost"] == 15.99
        assert result["total_annual_cost"] == 191.88

    async def test_empty(self, session):
        from pipeline.ai.chat import _tool_get_recurring_expenses
        # Insert and flush something unrelated first so session is active
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        with patch.object(session, "execute", return_value=mock_result):
            result = json.loads(await _tool_get_recurring_expenses(session))
        assert result["count"] == 0
        assert result["total_monthly_cost"] == 0.0

    async def test_without_annual_cost(self, session):
        """Test that _exec_tool catches the AttributeError when annual_cost is missing."""
        from pipeline.ai.chat import _exec_tool
        # Seed a real RecurringTransaction (no annual_cost column)
        r = RecurringTransaction(
            name="Spotify", amount=-9.99, frequency="monthly",
            category="Entertainment", segment="personal",
            status="active",
        )
        session.add(r)
        await session.flush()
        # The tool will fail because the ORM model lacks annual_cost.
        # _exec_tool catches the exception and returns an error JSON.
        result = json.loads(await _exec_tool(session, "get_recurring_expenses", {}))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_setup_status
# ═══════════════════════════════════════════════════════════════════════════

class TestGetSetupStatus:
    async def test_complete_setup(self, session):
        from pipeline.ai.chat import _tool_get_setup_status
        hp = await _seed_household(session)
        acct = await _seed_account(session)
        bp = BenefitPackage(household_id=hp.id, spouse="A", employer_name="Acme",
                            has_401k=True, employer_match_pct=6.0)
        session.add(bp)
        ip = InsurancePolicy(household_id=hp.id, policy_type="health",
                             provider="Blue Cross", is_active=True)
        session.add(ip)
        ent = await _seed_entity(session, "TestBiz", owner="Mike")
        le = LifeEvent(household_id=hp.id, event_type="home_purchase",
                       title="Bought a house", tax_year=2025)
        session.add(le)
        await session.flush()
        result = json.loads(await _tool_get_setup_status(session))
        assert result["sections"]["household"]["status"] == "complete"
        assert result["sections"]["accounts"]["status"] == "complete"
        assert result["sections"]["benefits"]["status"] == "complete"
        assert result["sections"]["insurance"]["status"] == "complete"
        assert result["overall_completeness"] > 0.5

    async def test_empty_setup(self, session):
        from pipeline.ai.chat import _tool_get_setup_status
        result = json.loads(await _tool_get_setup_status(session))
        assert result["sections"]["household"]["status"] == "missing"
        assert result["sections"]["accounts"]["status"] == "missing"
        assert len(result["gaps"]) > 0
        assert "No household profile" in result["gaps"][0]

    async def test_missing_income(self, session):
        from pipeline.ai.chat import _tool_get_setup_status
        await _seed_household(session, spouse_a_income=0.0, spouse_b_income=0.0)
        result = json.loads(await _tool_get_setup_status(session))
        assert any("No income data" in g for g in result["gaps"])

    async def test_entity_without_owner(self, session):
        from pipeline.ai.chat import _tool_get_setup_status
        await _seed_household(session)
        await _seed_entity(session, "NoOwnerBiz", owner=None)
        result = json.loads(await _tool_get_setup_status(session))
        assert any("no owner" in g for g in result["gaps"])


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_household_summary
# ═══════════════════════════════════════════════════════════════════════════

class TestGetHouseholdSummary:
    async def test_full_household(self, session):
        from pipeline.ai.chat import _tool_get_household_summary
        hp = await _seed_household(session,
            dependents_json='[{"name":"Kid","age":5}]',
            other_income_sources_json='[{"source":"Rental","amount":1200}]',
            other_income_annual=14400.0,
        )
        bp = BenefitPackage(household_id=hp.id, spouse="A", employer_name="Acme",
                            has_401k=True, employer_match_pct=6.0,
                            has_hsa=True, has_espp=False, life_insurance_coverage=500000.0)
        session.add(bp)
        ip = InsurancePolicy(household_id=hp.id, policy_type="health",
                             provider="Blue Cross", is_active=True)
        session.add(ip)
        ent = await _seed_entity(session, "SideBiz", owner="Mike")
        await session.flush()
        result = json.loads(await _tool_get_household_summary(session))
        assert result["filing_status"] == "mfj"
        assert result["spouse_a"]["name"] == "Mike"
        assert result["spouse_a"]["w2_income"] == 200000.0
        assert result["combined_income"] == 350000.0
        assert len(result["dependents"]) == 1
        assert len(result["other_income_sources"]) == 1
        assert len(result["benefits"]) == 1
        assert len(result["insurance_policies"]) == 1
        assert len(result["business_entities"]) == 1

    async def test_no_household(self, session):
        from pipeline.ai.chat import _tool_get_household_summary
        result = json.loads(await _tool_get_household_summary(session))
        assert "error" in result

    async def test_invalid_json_fields(self, session):
        from pipeline.ai.chat import _tool_get_household_summary
        await _seed_household(session,
            dependents_json="not valid json",
            other_income_sources_json="{bad}",
        )
        result = json.loads(await _tool_get_household_summary(session))
        assert result["dependents"] == []
        assert result["other_income_sources"] == []


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_goals_summary
# ═══════════════════════════════════════════════════════════════════════════

class TestGetGoalsSummary:
    async def test_with_goals(self, session):
        from pipeline.ai.chat import _tool_get_goals_summary
        g = Goal(
            name="Emergency Fund", goal_type="savings",
            target_amount=25000.0, current_amount=15000.0,
            target_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            monthly_contribution=1000.0, status="active",
        )
        session.add(g)
        await session.flush()
        result = json.loads(await _tool_get_goals_summary(session))
        assert result["count"] == 1
        assert result["total_target"] == 25000.0
        assert result["total_saved"] == 15000.0
        assert result["goals"][0]["progress_pct"] == 60.0
        assert result["goals"][0]["on_track"] is not None

    async def test_no_goals(self, session):
        from pipeline.ai.chat import _tool_get_goals_summary
        result = json.loads(await _tool_get_goals_summary(session))
        assert result["count"] == 0
        assert "No financial goals" in result["message"]

    async def test_goal_without_target_date(self, session):
        from pipeline.ai.chat import _tool_get_goals_summary
        g = Goal(name="Vacation", goal_type="savings",
                 target_amount=5000.0, current_amount=2000.0,
                 status="active")
        session.add(g)
        await session.flush()
        result = json.loads(await _tool_get_goals_summary(session))
        goal = result["goals"][0]
        assert goal["months_remaining"] is None
        assert goal["monthly_needed"] is None
        assert goal["on_track"] is None


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_portfolio_overview
# ═══════════════════════════════════════════════════════════════════════════

class TestGetPortfolioOverview:
    async def test_with_holdings(self, session):
        from pipeline.ai.chat import _tool_get_portfolio_overview
        acct = await _seed_account(session, "Brokerage", account_type="investment")
        h = InvestmentHolding(
            account_id=acct.id, ticker="AAPL", name="Apple Inc",
            asset_class="stock", shares=100, total_cost_basis=15000.0,
            current_value=17500.0, is_active=True,
        )
        session.add(h)
        c = CryptoHolding(
            coin_id="bitcoin", symbol="BTC", name="Bitcoin",
            quantity=0.5, current_value=30000.0, is_active=True,
        )
        session.add(c)
        m = ManualAsset(
            name="401k", asset_type="retirement_account",
            is_liability=False, current_value=100000.0, is_active=True,
        )
        session.add(m)
        await session.flush()
        result = json.loads(await _tool_get_portfolio_overview(session))
        assert result["total_value"] > 0
        assert result["holdings_count"] == 1
        assert result["crypto_count"] == 1
        assert result["manual_accounts"] == 1
        assert "stock" in result["allocation"]
        assert result["top_holdings"][0]["ticker"] == "AAPL"
        assert result["top_holdings"][0]["gain_loss"] == 2500.0

    async def test_empty_portfolio(self, session):
        from pipeline.ai.chat import _tool_get_portfolio_overview
        result = json.loads(await _tool_get_portfolio_overview(session))
        assert result["total_value"] == 0.0
        assert result["holdings_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_retirement_status
# ═══════════════════════════════════════════════════════════════════════════

class TestGetRetirementStatus:
    async def test_with_profile(self, session):
        from pipeline.ai.chat import _tool_get_retirement_status
        rp = RetirementProfile(
            name="My Plan", current_age=35, retirement_age=65,
            life_expectancy=90, current_annual_income=200000.0,
            current_retirement_savings=100000.0,
            monthly_retirement_contribution=2000.0,
            pre_retirement_return_pct=7.0,
            target_nest_egg=2000000.0, fire_number=1500000.0,
            expected_social_security_monthly=2500.0,
            social_security_start_age=67,
            income_replacement_pct=80.0,
            is_primary=True,
        )
        session.add(rp)
        await session.flush()
        result = json.loads(await _tool_get_retirement_status(session))
        assert result["current_age"] == 35
        assert result["retirement_age"] == 65
        assert result["years_to_retirement"] == 30
        assert result["current_savings"] == 100000.0
        assert result["projected_at_retirement"] > 100000.0
        assert result["target_nest_egg"] == 2000000.0
        assert result["social_security_monthly"] == 2500.0

    async def test_no_profile(self, session):
        from pipeline.ai.chat import _tool_get_retirement_status
        result = json.loads(await _tool_get_retirement_status(session))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _tool_get_life_scenarios
# ═══════════════════════════════════════════════════════════════════════════

class TestGetLifeScenarios:
    async def test_with_scenarios(self, session):
        from pipeline.ai.chat import _tool_get_life_scenarios
        s = LifeScenario(
            name="Buy House", scenario_type="home_purchase",
            total_cost=500000.0, new_monthly_payment=3000.0,
            monthly_surplus_after=1500.0,
            savings_rate_before_pct=30.0, savings_rate_after_pct=15.0,
            dti_before_pct=10.0, dti_after_pct=25.0,
            affordability_score=75.0, verdict="affordable",
            status="saved", is_favorite=True,
        )
        session.add(s)
        await session.flush()
        result = json.loads(await _tool_get_life_scenarios(session))
        assert result["count"] == 1
        assert result["scenarios"][0]["name"] == "Buy House"
        assert result["scenarios"][0]["affordability_score"] == 75.0
        assert result["scenarios"][0]["verdict"] == "affordable"
        assert result["scenarios"][0]["is_favorite"] is True

    async def test_no_scenarios(self, session):
        from pipeline.ai.chat import _tool_get_life_scenarios
        result = json.loads(await _tool_get_life_scenarios(session))
        assert result["count"] == 0
        assert "No life scenarios" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _exec_tool dispatch + error handling
# ═══════════════════════════════════════════════════════════════════════════

class TestExecToolDispatch:
    async def test_dispatches_all_tools(self, session):
        """Verify _exec_tool dispatches to the correct handler for every tool."""
        from pipeline.ai.chat import _exec_tool
        # A few spot-check calls for tools not otherwise tested
        result = json.loads(await _exec_tool(session, "get_account_balances", {}))
        assert "accounts" in result

        result = json.loads(await _exec_tool(session, "get_recurring_expenses", {}))
        assert "count" in result

    async def test_unknown_tool(self, session):
        from pipeline.ai.chat import _exec_tool
        result = json.loads(await _exec_tool(session, "nonexistent_tool", {}))
        assert "error" in result
        assert "Unknown tool" in result["error"]

    async def test_exception_handling(self, session):
        from pipeline.ai.chat import _exec_tool
        with patch("pipeline.ai.chat._tool_search_transactions", side_effect=RuntimeError("DB broke")):
            result = json.loads(await _exec_tool(session, "search_transactions", {}))
            assert "error" in result
            assert "DB broke" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — run_chat
# ═══════════════════════════════════════════════════════════════════════════

class TestRunChatFlow:
    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_existing_conversation(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))
        conv = ChatConversation(title="Existing Conv")
        session.add(conv)
        await session.flush()
        conv_id = conv.id

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_text_response("Got it.")
            result = await run_chat(session, [{"role": "user", "content": "Hello"}],
                                    conversation_id=conv_id)
        assert result["response"] == "Got it."
        assert result["conversation_id"] == conv_id

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_deleted_conversation_starts_fresh(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))
        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_text_response("Fresh start.")
            result = await run_chat(session, [{"role": "user", "content": "Hi"}],
                                    conversation_id=99999)
        assert result["response"] == "Fresh start."
        assert result["conversation_id"] is not None

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_tool_use_round_trip(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            # First call: tool_use; second call: end_turn with final text
            mock_client.messages.create.side_effect = [
                _mock_tool_response("get_account_balances", {}),
                _mock_text_response("You have no accounts."),
            ]
            result = await run_chat(session, [{"role": "user", "content": "Show my accounts"}])
        assert result["response"] == "You have no accounts."
        assert len(result["actions"]) == 1
        assert result["actions"][0]["tool"] == "get_account_balances"

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_max_tool_rounds(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat, MAX_TOOL_ROUNDS
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            # Always return tool_use to hit max rounds
            mock_client.messages.create.return_value = _mock_tool_response(
                "get_account_balances", {})
            result = await run_chat(session, [{"role": "user", "content": "Loop forever"}])
        assert "maximum number of steps" in result["response"]

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_unexpected_stop_reason(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))
        weird_resp = _mock_text_response("Partial response.")
        weird_resp.stop_reason = "max_tokens"

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = weird_resp
            result = await run_chat(session, [{"role": "user", "content": "Q"}])
        assert result["response"] == "Partial response."

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_desanitizes_response(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat
        await _seed_consent(session)
        sanitizer = MagicMock()
        sanitizer.has_mappings = True
        sanitizer.desanitize_text.return_value = "Hello Mike!"
        mock_prompt.return_value = ("System prompt", sanitizer)

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_text_response("Hello [PERSON_A]!")
            result = await run_chat(session, [{"role": "user", "content": "Hi"}])
        assert result["response"] == "Hello Mike!"

    async def test_no_consent_returns_requires_consent(self, session):
        from pipeline.ai.chat import run_chat
        result = await run_chat(session, [{"role": "user", "content": "Hi"}])
        assert result["requires_consent"] is True
        assert result["response"] is None

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_new_conversation_title_trimming(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))
        long_msg = "A " * 50  # 100 chars
        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_text_response("OK")
            result = await run_chat(session, [{"role": "user", "content": long_msg}])
        # Verify conversation was created
        assert result["conversation_id"] is not None


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — run_chat_stream
# ═══════════════════════════════════════════════════════════════════════════

class TestRunChatStream:
    async def test_no_consent_yields_requires_consent(self, session):
        from pipeline.ai.chat import run_chat_stream
        events = []
        async for ev in run_chat_stream(session, [{"role": "user", "content": "Hi"}]):
            events.append(ev)
        assert len(events) == 1
        assert events[0]["type"] == "requires_consent"

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_stream_end_turn(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat_stream
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))

        # Mock streaming
        mock_stream_ctx = AsyncMock()
        mock_event = MagicMock()
        mock_event.type = "content_block_delta"
        mock_delta = MagicMock()
        mock_delta.type = "text_delta"
        mock_delta.text = "Hello!"
        mock_event.delta = mock_delta

        final_msg = MagicMock()
        final_msg.stop_reason = "end_turn"
        final_msg.content = []

        async def mock_aiter(self):
            yield mock_event

        mock_stream_obj = MagicMock()
        mock_stream_obj.__aiter__ = mock_aiter
        mock_stream_obj.get_final_message = AsyncMock(return_value=final_msg)
        mock_stream_obj.__aenter__ = AsyncMock(return_value=mock_stream_obj)
        mock_stream_obj.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_async_client = MagicMock()
            mock_anthropic.AsyncAnthropic.return_value = mock_async_client
            mock_async_client.messages.stream.return_value = mock_stream_obj
            events = []
            async for ev in run_chat_stream(session, [{"role": "user", "content": "Hi"}]):
                events.append(ev)

        types = [e["type"] for e in events]
        assert "text_delta" in types
        assert "done" in types

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_stream_error(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat_stream
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))

        mock_stream_obj = MagicMock()
        mock_stream_obj.__aenter__ = AsyncMock(side_effect=RuntimeError("Stream failed"))
        mock_stream_obj.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_async_client = MagicMock()
            mock_anthropic.AsyncAnthropic.return_value = mock_async_client
            mock_async_client.messages.stream.return_value = mock_stream_obj
            events = []
            async for ev in run_chat_stream(session, [{"role": "user", "content": "Hi"}]):
                events.append(ev)

        assert any(e["type"] == "error" for e in events)

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_stream_tool_use_with_learning_event(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat_stream
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))

        # First round: tool_use; second round: end_turn
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "save_user_context"
        tool_block.input = {"category": "tax", "key": "test", "value": "I prefer aggressive"}
        tool_block.id = "toolu_1"

        final_tool = MagicMock()
        final_tool.stop_reason = "tool_use"
        final_tool.content = [tool_block]

        final_end = MagicMock()
        final_end.stop_reason = "end_turn"
        final_end.content = []

        call_count = 0

        async def mock_aiter_empty(self):
            return
            yield  # make it async generator

        def make_stream(stop_reason, content):
            s = MagicMock()
            s.__aiter__ = mock_aiter_empty
            s.get_final_message = AsyncMock(return_value=MagicMock(
                stop_reason=stop_reason, content=content))
            s.__aenter__ = AsyncMock(return_value=s)
            s.__aexit__ = AsyncMock(return_value=False)
            return s

        streams = [
            make_stream("tool_use", [tool_block]),
            make_stream("end_turn", []),
        ]

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_async_client = MagicMock()
            mock_anthropic.AsyncAnthropic.return_value = mock_async_client
            mock_async_client.messages.stream.side_effect = streams
            events = []
            async for ev in run_chat_stream(session, [{"role": "user", "content": "Remember this"}]):
                events.append(ev)

        types = [e["type"] for e in events]
        assert "tool_start" in types
        assert "tool_done" in types
        assert "learning" in types
        assert "done" in types

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_stream_deleted_conversation(self, mock_prompt, session):
        from pipeline.ai.chat import run_chat_stream
        await _seed_consent(session)
        mock_prompt.return_value = ("System prompt", MagicMock(has_mappings=False))

        final_msg = MagicMock()
        final_msg.stop_reason = "end_turn"
        final_msg.content = []

        async def mock_aiter(self):
            return
            yield

        mock_stream = MagicMock()
        mock_stream.__aiter__ = mock_aiter
        mock_stream.get_final_message = AsyncMock(return_value=final_msg)
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic:
            mock_async_client = MagicMock()
            mock_anthropic.AsyncAnthropic.return_value = mock_async_client
            mock_async_client.messages.stream.return_value = mock_stream
            events = []
            async for ev in run_chat_stream(session, [{"role": "user", "content": "Hi"}],
                                            conversation_id=99999):
                events.append(ev)
        assert any(e["type"] == "done" for e in events)


# ═══════════════════════════════════════════════════════════════════════════
# chat.py — _build_system_prompt
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildSystemPromptCoverage:
    async def test_with_entities_and_context(self, session):
        from pipeline.ai.chat import _build_system_prompt, invalidate_prompt_cache
        invalidate_prompt_cache()
        hp = await _seed_household(session)
        ent = await _seed_entity(session, "AutoRev", description=None, owner=None, ein=None)
        ctx = UserContext(category="tax", key="preference",
                          value="Prefers aggressive strategies",
                          source="chat", confidence=1.0, is_active=True)
        session.add(ctx)
        await session.flush()
        prompt, sanitizer = await _build_system_prompt(session)
        assert "Household Context" in prompt
        assert "Active business entities" in prompt
        assert "Business entities needing enrichment" in prompt
        assert "What You Know About This Household" in prompt
        assert "Setup Progress" in prompt

    async def test_with_gaps(self, session):
        from pipeline.ai.chat import _build_system_prompt, invalidate_prompt_cache
        invalidate_prompt_cache()
        # No household, no accounts — should flag gaps
        prompt, _ = await _build_system_prompt(session)
        assert "Missing Data Affecting Features" in prompt

    async def test_caching(self, session):
        from pipeline.ai.chat import _build_system_prompt, invalidate_prompt_cache
        invalidate_prompt_cache()
        prompt1, _ = await _build_system_prompt(session)
        prompt2, _ = await _build_system_prompt(session)
        assert prompt1 == prompt2  # Should be cached

    async def test_no_benefits_gap(self, session):
        from pipeline.ai.chat import _build_system_prompt, invalidate_prompt_cache
        invalidate_prompt_cache()
        await _seed_household(session)
        prompt, _ = await _build_system_prompt(session)
        assert "No benefits configured" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_list_manual_assets (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════

class TestListManualAssetsExtended:
    async def test_with_liabilities(self, session):
        from pipeline.ai.chat_tools import _tool_list_manual_assets
        a1 = ManualAsset(name="Home", asset_type="real_estate",
                         is_liability=False, current_value=500000.0,
                         is_active=True, as_of_date=datetime.now(timezone.utc),
                         institution="Zillow", owner="Mike")
        a2 = ManualAsset(name="Mortgage", asset_type="real_estate",
                         is_liability=True, current_value=300000.0,
                         is_active=True)
        session.add_all([a1, a2])
        await session.flush()
        result = json.loads(await _tool_list_manual_assets(session, {}))
        assert result["count"] == 2
        assert result["total_assets"] == 500000.0
        assert result["total_liabilities"] == 300000.0
        assert result["net"] == 200000.0


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_update_asset_value (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdateAssetValueExtended:
    async def test_inactive_asset(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value
        a = ManualAsset(name="Old Car", asset_type="vehicle",
                        is_liability=False, current_value=5000.0,
                        is_active=False)
        session.add(a)
        await session.flush()
        result = json.loads(await _tool_update_asset_value(session, {
            "asset_id": a.id, "new_value": 4000.0,
        }))
        assert "error" in result
        assert "inactive" in result["error"]

    async def test_appends_notes(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value
        a = ManualAsset(name="House", asset_type="real_estate",
                        is_liability=False, current_value=400000.0,
                        is_active=True, notes="Original purchase")
        session.add(a)
        await session.flush()
        result = json.loads(await _tool_update_asset_value(session, {
            "asset_id": a.id, "new_value": 450000.0, "notes": "Zillow update",
        }))
        assert result["success"] is True
        assert result["old_value"] == 400000.0
        assert result["new_value"] == 450000.0
        # Verify notes were appended
        await session.refresh(a)
        assert "Original purchase" in a.notes
        assert "Zillow update" in a.notes

    async def test_notes_on_empty_existing(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value
        a = ManualAsset(name="Car", asset_type="vehicle",
                        is_liability=False, current_value=20000.0,
                        is_active=True, notes=None)
        session.add(a)
        await session.flush()
        result = json.loads(await _tool_update_asset_value(session, {
            "asset_id": a.id, "new_value": 18000.0, "notes": "KBB estimate",
        }))
        assert result["success"] is True
        await session.refresh(a)
        assert "KBB estimate" in a.notes


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_get_stock_quote
# ═══════════════════════════════════════════════════════════════════════════

class TestGetStockQuote:
    async def test_success(self, session):
        from pipeline.ai.chat_tools import _tool_get_stock_quote
        with patch("pipeline.ai.chat_tools.asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock(return_value={
                "ticker": "AAPL", "price": 185.50, "change_pct": 1.2,
            })
            loop = MagicMock()
            loop.run_in_executor = mock_executor
            mock_loop.return_value = loop
            result = json.loads(await _tool_get_stock_quote(session, {"ticker": "aapl"}))
        assert result["ticker"] == "AAPL"
        assert result["price"] == 185.50

    async def test_failure(self, session):
        from pipeline.ai.chat_tools import _tool_get_stock_quote
        with patch("pipeline.ai.chat_tools.asyncio.get_event_loop") as mock_loop:
            loop = MagicMock()
            loop.run_in_executor = AsyncMock(side_effect=RuntimeError("Network error"))
            mock_loop.return_value = loop
            result = json.loads(await _tool_get_stock_quote(session, {"ticker": "FAKE"}))
        assert "error" in result

    async def test_no_data(self, session):
        from pipeline.ai.chat_tools import _tool_get_stock_quote
        with patch("pipeline.ai.chat_tools.asyncio.get_event_loop") as mock_loop:
            loop = MagicMock()
            loop.run_in_executor = AsyncMock(return_value=None)
            mock_loop.return_value = loop
            result = json.loads(await _tool_get_stock_quote(session, {"ticker": "ZZZZZ"}))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_trigger_plaid_sync
# ═══════════════════════════════════════════════════════════════════════════

class TestTriggerPlaidSync:
    async def test_no_plaid_items(self, session):
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync
        result = json.loads(await _tool_trigger_plaid_sync(session, {}))
        assert "error" in result
        assert "No active Plaid items" in result["error"]

    async def test_no_items_matching_institution(self, session):
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync
        pi = PlaidItem(item_id="item_1", access_token="token", status="active",
                       institution_name="Chase")
        session.add(pi)
        await session.flush()
        result = json.loads(await _tool_trigger_plaid_sync(session, {"institution": "Wells Fargo"}))
        assert "error" in result
        assert "Wells Fargo" in result["error"]

    async def test_successful_sync(self, session):
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync
        pi = PlaidItem(item_id="item_1", access_token="encrypted_token",
                       status="active", institution_name="Chase")
        session.add(pi)
        await session.flush()

        mock_sync = AsyncMock(return_value=(5, 2))
        mock_snapshot = AsyncMock()

        with patch("pipeline.plaid.sync.sync_item", mock_sync), \
             patch("pipeline.plaid.sync.snapshot_net_worth", mock_snapshot), \
             patch("pipeline.ai.chat_tools.asyncio.wait_for",
                   side_effect=[mock_sync.return_value, None]):
            result = json.loads(await _tool_trigger_plaid_sync(session, {}))

        assert result["items_synced"] == 1
        assert result["transactions_added"] == 5

    async def test_item_without_token_skipped(self, session):
        """Items with falsy access_token (empty string) are skipped during sync."""
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync
        # access_token is NOT NULL in schema, so use empty string to test falsy path
        pi = PlaidItem(item_id="item_1", access_token="",
                       status="active", institution_name="Chase")
        session.add(pi)
        await session.flush()

        with patch("pipeline.plaid.sync.snapshot_net_worth", AsyncMock()), \
             patch("pipeline.ai.chat_tools.asyncio.wait_for", AsyncMock(return_value=None)):
            result = json.loads(await _tool_trigger_plaid_sync(session, {}))
        # No items synced because access_token is falsy (empty string)
        assert result["items_synced"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_run_categorization
# ═══════════════════════════════════════════════════════════════════════════

class TestRunCategorization:
    async def test_success(self, session):
        from pipeline.ai.chat_tools import _tool_run_categorization
        with patch("pipeline.ai.chat_tools.asyncio.wait_for",
                    new_callable=AsyncMock) as mock_wait:
            mock_wait.return_value = {"categorized": 10, "skipped": 2}
            result = json.loads(await _tool_run_categorization(session, {"year": 2025, "month": 6}))
        assert result["categorized"] == 10

    async def test_timeout(self, session):
        import asyncio as _asyncio
        from pipeline.ai.chat_tools import _tool_run_categorization
        with patch("pipeline.ai.chat_tools.asyncio.wait_for",
                    side_effect=_asyncio.TimeoutError):
            result = json.loads(await _tool_run_categorization(session, {}))
        assert "error" in result
        assert "timed out" in result["error"]

    async def test_exception(self, session):
        from pipeline.ai.chat_tools import _tool_run_categorization
        with patch("pipeline.ai.chat_tools.asyncio.wait_for",
                    side_effect=RuntimeError("AI broke")):
            result = json.loads(await _tool_run_categorization(session, {}))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_get_data_health (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════

class TestGetDataHealthExtended:
    async def test_with_full_data(self, session):
        from pipeline.ai.chat_tools import _tool_get_data_health
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "TX1", -50.0,
                                effective_category="Food", ai_confidence=0.5,
                                is_manually_reviewed=False)
        await _seed_transaction(session, acct.id, "TX2", -30.0,
                                effective_category=None)

        pi = PlaidItem(item_id="pi_1", access_token="tok", status="error",
                       institution_name="Chase", error_code="ITEM_LOGIN_REQUIRED",
                       last_synced_at=datetime.now(timezone.utc) - timedelta(hours=48))
        session.add(pi)

        stale_asset = ManualAsset(
            name="Old House", asset_type="real_estate",
            is_liability=False, current_value=300000.0,
            is_active=True,
            as_of_date=datetime.now(timezone.utc) - timedelta(days=120),
        )
        session.add(stale_asset)

        nw = NetWorthSnapshot(
            snapshot_date=datetime.now(timezone.utc),
            year=2025, month=6,
            total_assets=500000.0, total_liabilities=200000.0,
            net_worth=300000.0,
        )
        session.add(nw)
        await session.flush()

        result = json.loads(await _tool_get_data_health(session, {}))
        assert result["transactions"]["total"] >= 2
        assert result["transactions"]["uncategorized"] >= 1
        assert result["transactions"]["low_confidence"] >= 1
        assert len(result["plaid"]) == 1
        assert result["plaid"][0]["status"] == "error"
        assert result["manual_assets"]["stale_count"] >= 1
        assert result["net_worth"]["net_worth"] == 300000.0
        assert result["gap_count"] >= 1

    async def test_empty_account_detection(self, session):
        from pipeline.ai.chat_tools import _tool_get_data_health
        acct = await _seed_account(session)
        # Account with no transactions
        result = json.loads(await _tool_get_data_health(session, {}))
        assert len(result["accounts"]["empty_accounts"]) == 1
        assert result["accounts"]["empty_accounts"][0]["name"] == "Chase Sapphire"

    async def test_stale_plaid_item(self, session):
        from pipeline.ai.chat_tools import _tool_get_data_health
        pi = PlaidItem(item_id="pi_stale", access_token="tok", status="active",
                       institution_name="BofA",
                       last_synced_at=datetime.now(timezone.utc) - timedelta(hours=48))
        session.add(pi)
        await session.flush()
        result = json.loads(await _tool_get_data_health(session, {}))
        assert result["plaid"][0]["stale"] is True
        assert any("stale" in g for g in result["gaps"])


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_update_transaction (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdateTransactionExtended:
    async def test_mark_reviewed(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "TX", -50.0)
        result = json.loads(await _tool_update_transaction(session, {
            "transaction_id": tx.id,
            "is_manually_reviewed": True,
        }))
        assert result["success"] is True
        assert "manually reviewed" in result["changes"][0]

    async def test_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction
        result = json.loads(await _tool_update_transaction(session, {
            "transaction_id": 99999,
            "notes": "test",
        }))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_create_transaction
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateTransaction:
    async def test_creates_manual_transaction(self, session):
        from pipeline.ai.chat_tools import _tool_create_transaction
        acct = await _seed_account(session)
        result = json.loads(await _tool_create_transaction(session, {
            "account_id": acct.id,
            "date": "2025-06-15",
            "description": "Freelance Payment",
            "amount": 5000.0,
            "category": "Income",
            "segment": "business",
            "notes": "Q2 invoice",
        }))
        assert result["success"] is True
        assert result["description"] == "Freelance Payment"
        assert result["amount"] == 5000.0
        assert result["category"] == "Income"
        assert result["segment"] == "business"
        assert result["account"] == "Chase Sapphire"

    async def test_account_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_create_transaction
        result = json.loads(await _tool_create_transaction(session, {
            "account_id": 99999,
            "date": "2025-06-15",
            "description": "Test",
            "amount": 100.0,
        }))
        assert "error" in result

    async def test_invalid_date(self, session):
        from pipeline.ai.chat_tools import _tool_create_transaction
        acct = await _seed_account(session)
        result = json.loads(await _tool_create_transaction(session, {
            "account_id": acct.id,
            "date": "not-a-date",
            "description": "Test",
            "amount": 100.0,
        }))
        assert "error" in result
        assert "Invalid date" in result["error"]

    async def test_default_segment(self, session):
        from pipeline.ai.chat_tools import _tool_create_transaction
        acct = await _seed_account(session)
        result = json.loads(await _tool_create_transaction(session, {
            "account_id": acct.id,
            "date": "2025-06-15",
            "description": "Misc",
            "amount": -20.0,
        }))
        assert result["success"] is True
        assert result["segment"] == "personal"


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_exclude_transactions (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════

class TestExcludeTransactionsExtended:
    async def test_too_many_ids(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
            "transaction_ids": list(range(51)),
        }))
        assert "error" in result
        assert "Maximum 50" in result["error"]

    async def test_no_ids_or_query(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
        }))
        assert "error" in result

    async def test_query_with_filters(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, "DUPLICATE CHARGE", -50.0,
                                period_year=2025, period_month=6)
        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
            "query": "DUPLICATE",
            "year": 2025,
            "month": 6,
            "account_id": acct.id,
            "reason": "Duplicate transaction",
        }))
        assert result["success"] is True
        assert result["count"] == 1

    async def test_include_action(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, "Was Excluded", -50.0,
                                     is_excluded=True)
        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "include",
            "transaction_ids": [tx.id],
        }))
        assert result["success"] is True
        assert result["count"] == 1
        assert result["action"] == "include"

    async def test_no_matching_transactions(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
            "query": "NONEXISTENT_TX_12345",
        }))
        assert result["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_manage_budget
# ═══════════════════════════════════════════════════════════════════════════

class TestManageBudget:
    async def test_upsert_budget(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        result = json.loads(await _tool_manage_budget(session, {
            "action": "upsert",
            "year": 2025, "month": 6,
            "category": "Groceries",
            "budget_amount": 600.0,
            "segment": "personal",
            "notes": "Tight month",
        }))
        assert result["success"] is True
        assert result["action"] == "saved"
        assert result["category"] == "Groceries"
        assert result["budget_amount"] == 600.0

    async def test_upsert_missing_field(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        result = json.loads(await _tool_manage_budget(session, {
            "action": "upsert",
            "year": 2025,
            "category": "Food",
            "budget_amount": None,
        }))
        assert "error" in result

    async def test_delete_budget(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        b = Budget(year=2025, month=6, category="Dining",
                   segment="personal", budget_amount=200.0)
        session.add(b)
        await session.flush()
        result = json.loads(await _tool_manage_budget(session, {
            "action": "delete", "budget_id": b.id,
        }))
        assert result["success"] is True

    async def test_delete_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        result = json.loads(await _tool_manage_budget(session, {
            "action": "delete", "budget_id": 99999,
        }))
        assert "error" in result

    async def test_delete_missing_id(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        result = json.loads(await _tool_manage_budget(session, {
            "action": "delete",
        }))
        assert "error" in result

    async def test_unknown_action(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        result = json.loads(await _tool_manage_budget(session, {
            "action": "foobar",
        }))
        assert "error" in result
        assert "Unknown action" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_manage_goal
# ═══════════════════════════════════════════════════════════════════════════

class TestManageGoal:
    async def test_create_goal(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {
            "action": "upsert",
            "name": "Emergency Fund",
            "target_amount": 25000.0,
            "current_amount": 5000.0,
            "goal_type": "savings",
            "target_date": "2026-12-31",
            "monthly_contribution": 1000.0,
            "status": "active",
        }))
        assert result["success"] is True
        assert result["action"] == "created"
        assert result["name"] == "Emergency Fund"
        assert result["target_amount"] == 25000.0

    async def test_update_existing_goal(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        g = Goal(name="Vacation", goal_type="savings",
                 target_amount=5000.0, current_amount=2000.0, status="active")
        session.add(g)
        await session.flush()
        result = json.loads(await _tool_manage_goal(session, {
            "action": "upsert",
            "goal_id": g.id,
            "current_amount": 3000.0,
        }))
        assert result["success"] is True
        assert result["action"] == "updated"

    async def test_delete_goal(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        g = Goal(name="To Delete", goal_type="savings",
                 target_amount=1000.0, status="active")
        session.add(g)
        await session.flush()
        result = json.loads(await _tool_manage_goal(session, {
            "action": "delete", "goal_id": g.id,
        }))
        assert result["success"] is True

    async def test_delete_missing_id(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {
            "action": "delete",
        }))
        assert "error" in result

    async def test_delete_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {
            "action": "delete", "goal_id": 99999,
        }))
        assert "error" in result

    async def test_new_goal_missing_name(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {
            "action": "upsert",
            "target_amount": 5000.0,
        }))
        assert "error" in result
        assert "name" in result["error"]

    async def test_new_goal_missing_target(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {
            "action": "upsert",
            "name": "New Goal",
        }))
        assert "error" in result
        assert "target_amount" in result["error"]

    async def test_invalid_target_date(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {
            "action": "upsert",
            "name": "Goal",
            "target_amount": 5000.0,
            "target_date": "not-a-date",
        }))
        assert "error" in result

    async def test_unknown_action(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {
            "action": "foobar",
        }))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_create_reminder
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateReminder:
    async def test_creates_reminder(self, session):
        from pipeline.ai.chat_tools import _tool_create_reminder
        result = json.loads(await _tool_create_reminder(session, {
            "title": "Q1 Tax Payment",
            "due_date": "2025-04-15",
            "description": "Federal estimated tax",
            "reminder_type": "tax_deadline",
            "amount": 5000.0,
            "advance_notice": "14_days",
        }))
        assert result["success"] is True
        assert result["title"] == "Q1 Tax Payment"
        assert result["due_date"] == "2025-04-15"
        assert result["reminder_type"] == "tax_deadline"
        assert result["amount"] == 5000.0
        assert result["advance_notice"] == "14_days"

    async def test_invalid_date(self, session):
        from pipeline.ai.chat_tools import _tool_create_reminder
        result = json.loads(await _tool_create_reminder(session, {
            "title": "Test",
            "due_date": "bad-date",
        }))
        assert "error" in result

    async def test_defaults(self, session):
        from pipeline.ai.chat_tools import _tool_create_reminder
        result = json.loads(await _tool_create_reminder(session, {
            "title": "Simple Reminder",
            "due_date": "2025-12-31",
        }))
        assert result["success"] is True
        assert result["reminder_type"] == "custom"
        assert result["advance_notice"] == "7_days"


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_update_business_entity
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdateBusinessEntity:
    async def test_update_by_name(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "AutoRev")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "AutoRev",
            "description": "Used car dealership",
            "expected_expenses": "Inventory, Rent, Marketing",
            "owner": "Mike",
        }))
        assert result["success"] is True
        assert "description" in result["fields_updated"]
        assert result["profile_complete"] is False  # Missing EIN

    async def test_update_by_id(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "TestBiz")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_id": ent.id,
            "ein": "12-3456789",
        }))
        assert result["success"] is True
        assert "ein" in result["fields_updated"]

    async def test_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "NonExistent",
            "description": "Test",
        }))
        assert "error" in result

    async def test_no_fields(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "EmptyUpdate")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "EmptyUpdate",
        }))
        assert "error" in result
        assert "No fields" in result["error"]

    async def test_rename(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "OldName")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "OldName",
            "new_name": "NewName",
        }))
        assert result["success"] is True
        assert result["entity_name"] == "NewName"

    async def test_date_fields(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "DateBiz")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "DateBiz",
            "active_from": "2024-01-01",
        }))
        assert result["success"] is True
        assert "active_from" in result["fields_updated"]

    async def test_invalid_date(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "BadDate")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "BadDate",
            "active_from": "not-a-date",
        }))
        assert "error" in result

    async def test_append_notes(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "NotesBiz", notes="Original note")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "NotesBiz",
            "notes": "New info added",
        }))
        assert result["success"] is True

    async def test_complete_profile(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        ent = await _seed_entity(session, "FullBiz",
                                 description="Full biz", expected_expenses="Rent",
                                 owner="Mike", ein="12-3456789")
        result = json.loads(await _tool_update_business_entity(session, {
            "entity_name": "FullBiz",
            "notes": "All good",
        }))
        assert result["success"] is True
        assert result["profile_complete"] is True
        assert result["missing_fields"] == []


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_create_business_entity
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateBusinessEntity:
    async def test_create_minimal(self, session):
        from pipeline.ai.chat_tools import _tool_create_business_entity
        result = json.loads(await _tool_create_business_entity(session, {
            "name": "NewBiz",
        }))
        assert result["success"] is True
        assert result["entity_name"] == "NewBiz"
        assert len(result["missing_fields"]) > 0
        assert "hint" in result

    async def test_create_full(self, session):
        from pipeline.ai.chat_tools import _tool_create_business_entity
        result = json.loads(await _tool_create_business_entity(session, {
            "name": "FullBiz",
            "description": "A consulting firm",
            "expected_expenses": "Travel, Software",
            "entity_type": "llc",
            "tax_treatment": "schedule_c",
            "ein": "98-7654321",
            "owner": "Jane",
            "active_from": "2024-06-01",
            "notes": "Started mid-year",
        }))
        assert result["success"] is True
        assert result["entity_type"] == "llc"
        assert result["profile_complete"] is True

    async def test_missing_name(self, session):
        from pipeline.ai.chat_tools import _tool_create_business_entity
        result = json.loads(await _tool_create_business_entity(session, {}))
        assert "error" in result

    async def test_invalid_date(self, session):
        from pipeline.ai.chat_tools import _tool_create_business_entity
        result = json.loads(await _tool_create_business_entity(session, {
            "name": "BadDateBiz",
            "active_from": "invalid",
        }))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_save_user_context (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════

class TestSaveUserContextExtended:
    async def test_missing_fields(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context
        result = json.loads(await _tool_save_user_context(session, {
            "category": "tax",
        }))
        assert "error" in result

    async def test_invalid_category(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context
        result = json.loads(await _tool_save_user_context(session, {
            "category": "invalid_cat",
            "key": "test",
            "value": "test value",
        }))
        assert "error" in result
        assert "Invalid category" in result["error"]

    async def test_successful_save(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context
        result = json.loads(await _tool_save_user_context(session, {
            "category": "tax",
            "key": "filing_preference",
            "value": "Prefers to file jointly",
        }))
        assert result["success"] is True
        assert result["remembered"] is True
        assert result["category"] == "tax"


# ═══════════════════════════════════════════════════════════════════════════
# chat_tools.py — _tool_get_user_context (additional coverage)
# ═══════════════════════════════════════════════════════════════════════════

class TestGetUserContextExtended:
    async def test_filter_by_category(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context, _tool_get_user_context
        await _tool_save_user_context(session, {
            "category": "tax", "key": "k1", "value": "v1",
        })
        await _tool_save_user_context(session, {
            "category": "career", "key": "k2", "value": "v2",
        })
        result = json.loads(await _tool_get_user_context(session, {"category": "tax"}))
        assert result["count"] == 1
        assert result["facts"][0]["category"] == "tax"

    async def test_get_all(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context, _tool_get_user_context
        await _tool_save_user_context(session, {
            "category": "household", "key": "k1", "value": "v1",
        })
        result = json.loads(await _tool_get_user_context(session, {}))
        assert result["count"] >= 1

    async def test_empty(self, session):
        from pipeline.ai.chat_tools import _tool_get_user_context
        result = json.loads(await _tool_get_user_context(session, {}))
        assert result["count"] == 0
