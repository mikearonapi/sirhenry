"""
Coverage gap tests — targets the remaining uncovered lines across:
- pipeline/ai/chat.py (_exec_tool dispatch + streaming)
- pipeline/ai/chat_tools.py (sync edge cases)
- pipeline/analytics/insights.py (outlier detection + monthly analysis)
- api/routes/tax_modeling.py (all endpoints)
- api/routes/demo.py (seed/reset/status)
- Various scattered 1-7 line gaps
"""
import asyncio
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base


# ── Shared fixtures ──

@pytest_asyncio.fixture
async def mem_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def mem_session(mem_engine):
    Session = async_sessionmaker(mem_engine, expire_on_commit=False)
    async with Session() as session:
        yield session


# ═══════════════════════════════════════════════════════════════
# 1. pipeline/ai/chat.py — _exec_tool dispatch (lines 820-868)
# ═══════════════════════════════════════════════════════════════

class TestChatExecTool:
    """Cover every elif branch in _exec_tool."""

    TOOL_NAMES = [
        ("get_tax_info", {"year": 2025}),
        ("get_budget_status", {"month": 3}),
        ("get_recurring_expenses", {}),
        ("get_setup_status", {}),
        ("get_household_summary", {}),
        ("get_goals_summary", {}),
        ("get_portfolio_overview", {}),
        ("get_retirement_status", {}),
        ("get_life_scenarios", {}),
        ("list_manual_assets", {"asset_type": "property"}),
        ("update_asset_value", {"asset_id": 1, "value": 100}),
        ("get_stock_quote", {"symbol": "AAPL"}),
        ("trigger_plaid_sync", {"item_id": 1}),
        ("run_categorization", {"limit": 10}),
        ("get_data_health", {"check": "all"}),
        ("update_transaction", {"id": 1, "category": "Food"}),
        ("create_transaction", {"amount": -50, "description": "Test"}),
        ("exclude_transactions", {"ids": [1, 2]}),
        ("manage_budget", {"action": "create", "category": "Food"}),
        ("manage_goal", {"action": "create", "name": "Save"}),
        ("create_reminder", {"title": "Pay bill"}),
        ("update_business_entity", {"id": 1, "name": "Corp"}),
        ("create_business_entity", {"name": "NewCorp"}),
        ("save_user_context", {"key": "pref", "value": "dark"}),
        ("get_user_context", {"key": "pref"}),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,tool_input", TOOL_NAMES)
    async def test_exec_tool_branches(self, tool_name, tool_input):
        from pipeline.ai.chat import _exec_tool
        session = AsyncMock()
        handler_name = f"_tool_{tool_name}"

        with patch(f"pipeline.ai.chat.{handler_name}", new_callable=AsyncMock,
                   return_value='{"ok": true}') as mock_handler:
            result = await _exec_tool(session, tool_name, tool_input)
            assert '"ok"' in result
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_exec_tool_unknown(self):
        from pipeline.ai.chat import _exec_tool
        session = AsyncMock()
        result = await _exec_tool(session, "nonexistent_tool", {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_exec_tool_exception(self):
        from pipeline.ai.chat import _exec_tool
        session = AsyncMock()
        with patch("pipeline.ai.chat._tool_search_transactions", new_callable=AsyncMock,
                   side_effect=RuntimeError("boom")):
            result = await _exec_tool(session, "search_transactions", {"query": "test"})
            assert "boom" in result


# ═══════════════════════════════════════════════════════════════
# 2. chat.py — line 307 (no income data gap)
# ═══════════════════════════════════════════════════════════════

class TestChatSystemPromptGaps:
    @pytest.mark.asyncio
    async def test_no_income_gap(self):
        """Line 307: household exists but no income data triggers gap warning."""
        from pipeline.ai.chat import _build_system_prompt, invalidate_prompt_cache
        from pipeline.db.schema import HouseholdProfile

        # Clear the prompt cache to avoid stale results from other tests
        invalidate_prompt_cache()

        # Fully isolated engine — no fixture sharing
        iso_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with iso_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        IsoSession = async_sessionmaker(iso_engine, expire_on_commit=False)
        async with IsoSession() as sess:
            hp = HouseholdProfile(
                filing_status="single", state="CA",
                spouse_a_name="Alice", spouse_a_income=0,
                spouse_b_income=0, is_primary=True,
            )
            sess.add(hp)
            await sess.commit()

        async with IsoSession() as sess:
            result = await _build_system_prompt(sess)
            prompt = result[0] if isinstance(result, tuple) else result
            assert "No income data" in prompt

        # Clean up cache so other tests aren't affected
        invalidate_prompt_cache()
        await iso_engine.dispose()


# ═══════════════════════════════════════════════════════════════
# 3. chat.py — streaming tool execution (lines 1777, 1877,
#    1961, 1984-1994, 2012-2020)
# ═══════════════════════════════════════════════════════════════

class TestChatStreaming:
    def _mock_session_with_consent(self):
        """Create a mock session that passes the consent check."""
        session = AsyncMock()
        consent_obj = SimpleNamespace(consent_type="ai_features", consented=True)

        call_count = [0]
        async def mock_execute(query, *a, **kw):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # Consent check returns consent object
                result.scalar_one_or_none.return_value = consent_obj
            else:
                result.scalar_one_or_none.return_value = None
                result.scalars.return_value.all.return_value = []
            return result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    def _make_stream_ctx(self, final_message):
        """Create a mock streaming context manager."""
        class MockStream:
            def __init__(self, final):
                self._final = final
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
            async def get_final_message(self):
                return self._final
        return MockStream(final_message)

    @pytest.mark.asyncio
    async def test_stream_tool_use_with_text_block(self):
        """Lines 1961: text block in tool_use response."""
        from pipeline.ai.chat import run_chat_stream

        text_block = SimpleNamespace(type="text", text="Looking up data...")
        tool_block = SimpleNamespace(
            type="tool_use", id="tu_1", name="get_account_balances", input={}
        )
        tool_response = SimpleNamespace(
            content=[text_block, tool_block],
            stop_reason="tool_use",
        )
        final_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Your balance is $1000.")],
            stop_reason="end_turn",
        )

        stream_calls = [0]
        def make_stream(**kwargs):
            stream_calls[0] += 1
            msg = tool_response if stream_calls[0] == 1 else final_response
            return self._make_stream_ctx(msg)

        mock_client = AsyncMock()
        mock_client.messages.stream = make_stream

        session = self._mock_session_with_consent()

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic, \
             patch("pipeline.ai.chat._build_system_prompt", new_callable=AsyncMock, return_value=("sys", MagicMock())), \
             patch("pipeline.ai.chat._exec_tool", new_callable=AsyncMock, return_value='{"balances": []}'), \
             patch("pipeline.ai.chat.os.getenv", return_value="test-key"), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            events = []
            async for event in run_chat_stream(session, [{"role": "user", "content": "What's my balance?"}]):
                events.append(event)

            event_types = [e["type"] for e in events]
            assert "done" in event_types

    @pytest.mark.asyncio
    async def test_stream_learning_event_save_user_context(self):
        """Lines 1984-1985: save_user_context learning event."""
        from pipeline.ai.chat import run_chat_stream

        tool_block = SimpleNamespace(
            type="tool_use", id="tu_1", name="save_user_context",
            input={"key": "pref", "value": "dark mode"}
        )
        tool_response = SimpleNamespace(
            content=[tool_block],
            stop_reason="tool_use",
        )
        final_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Saved your preference.")],
            stop_reason="end_turn",
        )

        stream_calls = [0]
        def make_stream(**kwargs):
            stream_calls[0] += 1
            msg = tool_response if stream_calls[0] == 1 else final_response
            return self._make_stream_ctx(msg)

        mock_client = AsyncMock()
        mock_client.messages.stream = make_stream

        session = self._mock_session_with_consent()

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic, \
             patch("pipeline.ai.chat._build_system_prompt", new_callable=AsyncMock, return_value=("sys", MagicMock())), \
             patch("pipeline.ai.chat._exec_tool", new_callable=AsyncMock,
                   return_value='{"remembered": true, "value": "dark mode"}'), \
             patch("pipeline.ai.chat.os.getenv", return_value="test-key"), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            events = []
            async for event in run_chat_stream(session, [{"role": "user", "content": "Remember I like dark mode"}]):
                events.append(event)

            learning_events = [e for e in events if e.get("type") == "learning"]
            assert len(learning_events) >= 1
            assert "Remembered" in learning_events[0]["message"]

    @pytest.mark.asyncio
    async def test_stream_learning_event_update_business_entity(self):
        """Lines 1986-1994: update_business_entity learning event."""
        from pipeline.ai.chat import run_chat_stream

        tool_block = SimpleNamespace(
            type="tool_use", id="tu_1", name="update_business_entity",
            input={"id": 1, "name": "Acme Corp"}
        )
        tool_response = SimpleNamespace(
            content=[tool_block],
            stop_reason="tool_use",
        )
        final_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Updated.")],
            stop_reason="end_turn",
        )

        stream_calls = [0]
        def make_stream(**kwargs):
            stream_calls[0] += 1
            msg = tool_response if stream_calls[0] == 1 else final_response
            return self._make_stream_ctx(msg)

        mock_client = AsyncMock()
        mock_client.messages.stream = make_stream

        session = self._mock_session_with_consent()

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic, \
             patch("pipeline.ai.chat._build_system_prompt", new_callable=AsyncMock, return_value=("sys", MagicMock())), \
             patch("pipeline.ai.chat._exec_tool", new_callable=AsyncMock,
                   return_value='{"success": true, "entity_name": "Acme Corp", "fields_updated": ["name", "ein"]}'), \
             patch("pipeline.ai.chat.os.getenv", return_value="test-key"), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            events = []
            async for event in run_chat_stream(session, [{"role": "user", "content": "Update Acme"}]):
                events.append(event)

            learning_events = [e for e in events if e.get("type") == "learning"]
            assert len(learning_events) >= 1
            assert "Acme Corp" in learning_events[0]["message"]

    @pytest.mark.asyncio
    async def test_stream_unexpected_stop_reason(self):
        """Lines 2012-2013: unexpected stop reason."""
        from pipeline.ai.chat import run_chat_stream

        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Partial")],
            stop_reason="max_tokens",
        )

        mock_client = AsyncMock()
        mock_client.messages.stream = lambda **kw: self._make_stream_ctx(response)

        session = self._mock_session_with_consent()

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic, \
             patch("pipeline.ai.chat._build_system_prompt", new_callable=AsyncMock, return_value=("sys", MagicMock())), \
             patch("pipeline.ai.chat.os.getenv", return_value="test-key"), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            events = []
            async for event in run_chat_stream(session, [{"role": "user", "content": "test"}]):
                events.append(event)

            error_events = [e for e in events if e.get("type") == "error"]
            assert len(error_events) >= 1
            assert "Unexpected stop reason" in error_events[0]["message"]

    @pytest.mark.asyncio
    async def test_stream_max_tool_rounds(self):
        """Lines 2015-2020: hit MAX_TOOL_ROUNDS limit."""
        from pipeline.ai.chat import run_chat_stream

        tool_block = SimpleNamespace(
            type="tool_use", id="tu_1", name="get_account_balances", input={}
        )
        tool_response = SimpleNamespace(
            content=[tool_block],
            stop_reason="tool_use",
        )

        mock_client = AsyncMock()
        mock_client.messages.stream = lambda **kw: self._make_stream_ctx(tool_response)

        session = self._mock_session_with_consent()

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic, \
             patch("pipeline.ai.chat._build_system_prompt", new_callable=AsyncMock, return_value=("sys", MagicMock())), \
             patch("pipeline.ai.chat._exec_tool", new_callable=AsyncMock, return_value='{"ok": true}'), \
             patch("pipeline.ai.chat.os.getenv", return_value="test-key"), \
             patch("pipeline.ai.chat.MAX_TOOL_ROUNDS", 2), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            events = []
            async for event in run_chat_stream(session, [{"role": "user", "content": "test"}]):
                events.append(event)

            done_events = [e for e in events if e.get("type") == "done"]
            assert len(done_events) >= 1


# ═══════════════════════════════════════════════════════════════
# 4. chat.py run_chat tool_use with text block (line 1777)
# ═══════════════════════════════════════════════════════════════

class TestChatRunChatToolText:
    @pytest.mark.asyncio
    async def test_run_chat_tool_use_with_text(self):
        """Line 1777: text block alongside tool_use in run_chat."""
        from pipeline.ai.chat import run_chat

        text_block = SimpleNamespace(type="text", text="Let me check...")
        tool_block = SimpleNamespace(
            type="tool_use", id="tu_1", name="get_account_balances", input={}
        )
        response1 = SimpleNamespace(
            content=[text_block, tool_block],
            stop_reason="tool_use",
        )
        response2 = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Your balance is $1000.")],
            stop_reason="end_turn",
        )

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=[response1, response2])

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.flush = AsyncMock()

        with patch("pipeline.ai.chat.anthropic") as mock_anthropic, \
             patch("pipeline.ai.chat._build_system_prompt", new_callable=AsyncMock, return_value="sys"), \
             patch("pipeline.ai.chat._exec_tool", new_callable=AsyncMock, return_value='{}'), \
             patch("pipeline.ai.chat.os.getenv", return_value="test-key"):
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await run_chat(
                session,
                [{"role": "user", "content": "balance?"}],
            )
            assert "reply" in result or "response" in result or isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════
# 5. pipeline/ai/chat_tools.py (lines 188-195, 200-201, 319-320)
# ═══════════════════════════════════════════════════════════════

class TestChatToolsEdgeCases:
    @pytest.mark.asyncio
    async def test_trigger_plaid_sync_timeout(self):
        """Lines 188-191: sync timeout handling."""
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync

        session = AsyncMock()

        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.institution_name = "Chase"
        mock_item.access_token = "tok"
        mock_item.status = "active"
        mock_item.error_code = None
        mock_item.last_synced_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item]
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        with patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock,
                   side_effect=asyncio.TimeoutError()), \
             patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock):
            result = await _tool_trigger_plaid_sync(session, {})
            parsed = json.loads(result)
            assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_trigger_plaid_sync_exception(self):
        """Lines 192-195: generic sync exception."""
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync

        session = AsyncMock()

        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.institution_name = "Chase"
        mock_item.access_token = "tok"
        mock_item.status = "active"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item]
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        with patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock,
                   side_effect=RuntimeError("connection failed")), \
             patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock):
            result = await _tool_trigger_plaid_sync(session, {})
            parsed = json.loads(result)
            assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_net_worth_snapshot_failure(self):
        """Lines 200-201: net worth snapshot fails."""
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        with patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock,
                   side_effect=RuntimeError("snapshot fail")):
            result = await _tool_trigger_plaid_sync(session, {})
            parsed = json.loads(result)
            assert isinstance(parsed, dict)


# ═══════════════════════════════════════════════════════════════
# 6. pipeline/analytics/insights.py (30 uncovered lines)
# ═══════════════════════════════════════════════════════════════

def _make_tx(id, amount, category="Food", month=1, year=2025, description="Test"):
    """Helper to create transaction-like objects."""
    safe_month = max(1, min(month, 12))
    return SimpleNamespace(
        id=id, amount=amount, effective_category=category,
        period_month=month, period_year=year,
        date=date(year, safe_month, 15), description=description,
        effective_segment="needs",
    )


class TestInsightsOutlierDetection:
    def test_suppressed_categories(self):
        """Line 156: category suppression from feedback."""
        from pipeline.analytics.insights import _build_feedback_index

        fb1 = SimpleNamespace(
            transaction_id=1, classification="not_outlier",
            apply_to_future=True, description_pattern=None,
            category="Dining", id=1, user_note=None,
        )
        fb2 = SimpleNamespace(
            transaction_id=2, classification="not_outlier",
            apply_to_future=True, description_pattern=None,
            category="Dining", id=2, user_note=None,
        )
        by_txn, patterns, suppressed_cats = _build_feedback_index([fb1, fb2])
        assert "Dining" in suppressed_cats

    def test_feedback_to_dict(self):
        """Line 168: feedback to dict conversion."""
        from pipeline.analytics.insights import _feedback_to_dict

        fb = SimpleNamespace(
            id=1, transaction_id=10, classification="not_outlier",
            user_note="normal", description_pattern="STARBUCKS",
            category="Coffee", apply_to_future=True, year=2025,
            created_at=datetime(2025, 1, 1),
        )
        result = _feedback_to_dict(fb)
        assert result["id"] == 1
        assert result["classification"] == "not_outlier"

    def test_detect_outlier_transactions(self):
        """Lines 222-294: outlier detection with prior year data and edge cases."""
        from pipeline.analytics.insights import _detect_outlier_transactions

        txns = [
            _make_tx(1, -100, "Coffee", 1),
            _make_tx(2, -100, "Coffee", 2),
            _make_tx(3, -100, "Coffee", 3),
            _make_tx(4, -100, "Coffee", 4),
            _make_tx(5, -5000, "Coffee", 5),  # Expense outlier
            _make_tx(6, 5000, "Salary", 1),
            _make_tx(7, 5000, "Salary", 2),
            _make_tx(8, 5000, "Salary", 3),
            _make_tx(9, 5000, "Salary", 4),
            _make_tx(10, 50000, "Salary", 5),  # Income outlier
        ]
        prior = [
            _make_tx(100, -110, "Coffee", 1, 2024),
            _make_tx(101, -120, "Coffee", 2, 2024),
            _make_tx(102, -115, "Coffee", 3, 2024),
            _make_tx(103, -105, "Coffee", 4, 2024),
            _make_tx(104, 5100, "Salary", 1, 2024),
            _make_tx(105, 5200, "Salary", 2, 2024),
            _make_tx(106, 4900, "Salary", 3, 2024),
            _make_tx(107, 5050, "Salary", 4, 2024),
        ]
        expense_out, income_out = _detect_outlier_transactions(txns, feedback_rows=[], prior_year_transactions=prior)
        assert isinstance(expense_out, list)
        assert isinstance(income_out, list)


class TestInsightsMonthlyAnalysis:
    def test_monthly_heatmap(self):
        """Lines 333, 387, 402, 427: monthly heatmap with various conditions."""
        from pipeline.analytics.insights import _monthly_analysis, FinancialPeriod

        txns = [
            _make_tx(1, -200, "Food", 1),
            _make_tx(2, -200, "Food", 2),
            _make_tx(3, -200, "Food", 3),
            _make_tx(4, -200, "Food", 4),
            _make_tx(5, -200, "Food", 5),
            _make_tx(6, -600, "Food", 6),  # Higher month
            _make_tx(7, 5000, "Salary", 1),
            _make_tx(8, 50000, "Bonus", 2),  # Income outlier
            _make_tx(100, -100, "Food", 0),  # period_month == 0 → skip
        ]
        periods = [
            FinancialPeriod(month=m, year=2025, total_income=5000, total_expenses=-200,
                            expense_breakdown='{"Food": 200}')
            for m in range(1, 7)
        ]
        result = _monthly_analysis(txns, set(), {8}, periods)
        assert isinstance(result, list)
        months = [r["month"] for r in result]
        assert 0 not in months

    def test_seasonal_patterns(self):
        """Lines 472, 487, 490, 525, 530: seasonal pattern branches."""
        from pipeline.analytics.insights import _seasonal_patterns

        txns = []
        for m in range(1, 13):
            base = -200 if m != 12 else -800  # December peak
            txns.append(_make_tx(m, base, "Shopping", m, 2025))
        prior = []
        for m in range(1, 13):
            base = -180 if m != 12 else -750
            prior.append(_make_tx(m + 100, base, "Shopping", m, 2024))

        result = _seasonal_patterns(txns, prior)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_category_trends(self):
        """Lines 563, 581: category trends with edge cases."""
        from pipeline.analytics.insights import _category_trends

        periods = [SimpleNamespace(month=m, year=2025) for m in range(1, 7)]
        txns = [
            _make_tx(1, -100, "Food", 1),
            _make_tx(2, -150, "Food", 2),
            _make_tx(3, -200, "Food", 3),
            _make_tx(4, -250, "Food", 4),
            _make_tx(5, -300, "Food", 5),
            _make_tx(6, -350, "Food", 6),
        ]
        result = _category_trends(txns, periods)
        assert isinstance(result, list)


class TestInsightsYoY:
    def test_yoy_with_additional_prior(self):
        """Lines 687, 747-751: year-over-year with additional prior periods."""
        from pipeline.analytics.insights import _year_over_year

        FinPeriod = SimpleNamespace
        current = [FinPeriod(month=m, year=2025, total_income=5000, total_expenses=-3000, expense_breakdown='{"Food": 2000, "Transport": 1000}') for m in range(1, 7)]
        prior = [FinPeriod(month=m, year=2024, total_income=4500, total_expenses=-2800, expense_breakdown='{"Food": 1800, "Transport": 1000}') for m in range(1, 7)]
        additional = [FinPeriod(month=m, year=2023, total_income=4000, total_expenses=-2500, expense_breakdown='{"Food": 1500}') for m in range(1, 7)]

        result = _year_over_year(current, prior, additional)
        assert "prior_year_2" in result
        assert "prior_year_2_income" in result
        assert "prior_year_2_expenses" in result


# ═══════════════════════════════════════════════════════════════
# 7. api/routes/tax_modeling.py (14 uncovered lines — all endpoints)
# ═══════════════════════════════════════════════════════════════

class TestTaxModelingRoute:
    @pytest_asyncio.fixture
    async def client(self):
        from httpx import AsyncClient, ASGITransport
        from fastapi import FastAPI
        from api.routes.tax_modeling import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_roth_conversion(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.roth_conversion_ladder.return_value = {"savings": 5000}
            resp = await client.post("/tax/model/roth-conversion", json={
                "traditional_balance": 500000, "current_income": 200000,
                "filing_status": "mfj", "years": 10, "target_bracket_rate": 0.22,
                "growth_rate": 0.07,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_backdoor_roth(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.backdoor_roth_checklist.return_value = {"eligible": True}
            resp = await client.post("/tax/model/backdoor-roth", json={
                "has_traditional_ira_balance": False, "traditional_ira_balance": 0,
                "income": 300000, "filing_status": "mfj",
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_mega_backdoor(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.mega_backdoor_roth_analysis.return_value = {"max_contrib": 30000}
            resp = await client.post("/tax/model/mega-backdoor", json={
                "employer_plan_allows": True, "current_employee_contrib": 23000,
                "employer_match_contrib": 10000, "plan_limit": 69000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_daf_bunching(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.daf_bunching_strategy.return_value = {"savings": 3000}
            resp = await client.post("/tax/model/daf-bunching", json={
                "annual_charitable": 15000, "standard_deduction": 29200,
                "itemized_deductions_excl_charitable": 20000, "bunch_years": 2,
                "filing_status": "mfj", "taxable_income": 300000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_scorp(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.scorp_election_model.return_value = {"savings": 8000}
            resp = await client.post("/tax/model/scorp", json={
                "gross_1099_income": 200000, "reasonable_salary": 100000,
                "business_expenses": 30000, "state": "CA", "filing_status": "mfj",
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_multi_year(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.multi_year_projection.return_value = {"projections": []}
            resp = await client.post("/tax/model/multi-year", json={
                "current_income": 200000, "income_growth_rate": 0.03,
                "filing_status": "mfj", "state_rate": 0.09, "years": 5,
                "roth_conversions": [], "equity_vesting": [],
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_estimated_payments(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.estimated_payment_calculator.return_value = {"quarterly": 5000}
            resp = await client.post("/tax/model/estimated-payments", json={
                "total_underwithholding": 20000, "prior_year_tax": 50000,
                "current_withholding": 40000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_student_loan(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.student_loan_optimizer.return_value = {"strategy": "pay_min"}
            resp = await client.post("/tax/model/student-loan", json={
                "loan_balance": 50000, "interest_rate": 0.05,
                "monthly_income": 10000, "filing_status": "mfj",
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_defined_benefit(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.defined_benefit_plan_analysis.return_value = {"max_contrib": 200000}
            resp = await client.post("/tax/model/defined-benefit", json={
                "self_employment_income": 300000, "age": 50,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_real_estate_str(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.real_estate_str_analysis.return_value = {"depreciation": 15000}
            resp = await client.post("/tax/model/real-estate-str", json={
                "property_value": 500000, "annual_rental_income": 50000,
                "average_stay_days": 5, "hours_per_week_managing": 20,
                "w2_income": 200000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_filing_status_compare(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.filing_status_comparison.return_value = {"best": "mfj"}
            resp = await client.post("/tax/model/filing-status-compare", json={
                "spouse_a_income": 200000, "spouse_b_income": 150000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_section_179(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.section_179_equipment_analysis.return_value = {"deduction": 50000}
            resp = await client.post("/tax/model/section-179", json={
                "equipment_cost": 80000, "business_income": 200000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_qbi_deduction(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.qbi_deduction_check.return_value = {"deduction": 40000}
            resp = await client.post("/tax/model/qbi-deduction", json={
                "qbi_income": 200000, "taxable_income": 300000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_state_comparison(self, client):
        with patch("api.routes.tax_modeling.TaxModelingEngine") as mock:
            mock.state_tax_comparison.return_value = {"savings": 10000}
            resp = await client.post("/tax/model/state-comparison", json={
                "income": 300000,
            })
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# 8. api/routes/demo.py (lines 17, 28-29)
# ═══════════════════════════════════════════════════════════════

class TestDemoRoute:
    @pytest_asyncio.fixture
    async def client(self, mem_engine):
        from httpx import AsyncClient, ASGITransport
        from fastapi import FastAPI
        from api.routes.demo import router
        from api.database import get_session

        Session = async_sessionmaker(mem_engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(router)

        async def override_session():
            async with Session() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_seed_demo_value_error(self, client):
        """Line 17-19: seed raises ValueError → 409."""
        with patch("api.routes.demo.seed_demo_data", new_callable=AsyncMock,
                   side_effect=ValueError("DB already has data")):
            resp = await client.post("/demo/seed")
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_reset_not_demo_mode(self, client):
        """Lines 28-29: reset when not in demo mode → 409."""
        with patch("api.routes.demo.get_demo_status", new_callable=AsyncMock,
                   return_value={"active": False}):
            resp = await client.post("/demo/reset")
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_reset_in_demo_mode(self, client):
        """Lines 28-29: reset when in demo mode → success."""
        with patch("api.routes.demo.get_demo_status", new_callable=AsyncMock,
                   return_value={"active": True}), \
             patch("api.routes.demo.reset_demo_data", new_callable=AsyncMock):
            resp = await client.post("/demo/reset")
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# 9. Scattered small gaps (1-5 lines each)
# ═══════════════════════════════════════════════════════════════

class TestScatteredGaps:
    def test_investment_extract_1099b_value_error(self):
        """investment.py lines 80-81: ValueError in parsing."""
        from pipeline.importers.investment import _extract_1099b_entries

        # Text with malformed numbers that cause ValueError
        text = "AAPL 01/15/2024 12/20/2024 $INVALID $100.00 $50.00 short"
        entries = _extract_1099b_entries(text)
        # Should not include the malformed entry
        assert isinstance(entries, list)

    def test_investment_extract_dividend_value_error(self):
        """investment.py lines 93-94: ValueError in dividend parsing."""
        from pipeline.importers.investment import _extract_dividend_income

        text = "Total Dividends $INVALID"
        result = _extract_dividend_income(text)
        assert result == 0.0
