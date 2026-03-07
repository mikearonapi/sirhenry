"""
Comprehensive tests for all AI modules in pipeline/ai/.

Covers:
  - privacy.py: PIISanitizer, build_sanitized_household_context, sanitize_entity_list
  - category_rules.py: normalize_merchant, _matches_merchant, rule CRUD, apply_rules
  - scenario_analyzer.py: _build_scenario_prompt, analyze_scenario_with_ai
  - categorizer.py: _build_categorization_prompt, detect_document_type, extract_tax_fields_with_claude
  - rule_generator.py: generate_rules_from_patterns, create_rules_from_proposals
  - report_gen.py: compute_period_summary, generate_monthly_insights
  - tax_analyzer.py: _build_strategy_prompt, run_tax_analysis
  - chat.py: TOOLS schema, _exec_tool dispatch, _build_system_prompt, run_chat
  - chat_tools.py: individual tool functions

All Anthropic API calls are mocked.
"""
import json
import logging
import pytest
import pytest_asyncio
from datetime import datetime, timezone, date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    BusinessEntity,
    CategoryRule,
    ChatConversation,
    ChatMessage as ChatMessageModel,
    FinancialPeriod,
    HouseholdProfile,
    Transaction,
    UserContext,
    UserPrivacyConsent,
    ManualAsset,
    NetWorthSnapshot,
    PlaidItem,
    InsurancePolicy,
    BenefitPackage,
)

# Reuse conftest fixtures (engine, session) via pytest discovery.


# ═══════════════════════════════════════════════════════════════════════════
# Helper: build a mock Claude API response
# ═══════════════════════════════════════════════════════════════════════════

def _mock_claude_response(text: str):
    """Build a mock object mimicking anthropic.types.Message."""
    content_block = MagicMock()
    content_block.text = text
    content_block.type = "text"
    response = MagicMock()
    response.content = [content_block]
    response.stop_reason = "end_turn"
    response.model = "claude-sonnet-4-20250514"
    return response


def _mock_tool_use_response(tool_name: str, tool_input: dict, tool_use_id: str = "toolu_123"):
    """Build a mock Claude response that requests a tool call."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_use_id
    response = MagicMock()
    response.content = [tool_block]
    response.stop_reason = "tool_use"
    return response


async def _seed_account(session: AsyncSession, name: str = "Chase Sapphire") -> Account:
    acct = Account(name=name, account_type="personal", subtype="credit_card", institution="Chase", data_source="csv")
    session.add(acct)
    await session.flush()
    return acct


async def _seed_transaction(
    session: AsyncSession,
    account_id: int,
    description: str = "STARBUCKS #1234 SEATTLE WA",
    amount: float = -5.50,
    **kwargs,
) -> Transaction:
    defaults = dict(
        date=datetime(2025, 6, 15, tzinfo=timezone.utc),
        period_year=2025,
        period_month=6,
        segment="personal",
        data_source="csv",
    )
    defaults.update(kwargs)
    tx = Transaction(account_id=account_id, description=description, amount=amount, **defaults)
    session.add(tx)
    await session.flush()
    return tx


async def _seed_household(session: AsyncSession, **overrides) -> HouseholdProfile:
    defaults = dict(
        name="Test Household",
        filing_status="mfj",
        state="CA",
        spouse_a_name="John Smith",
        spouse_a_preferred_name="John",
        spouse_a_income=250000.0,
        spouse_a_employer="Accenture",
        spouse_b_name="Jane Smith",
        spouse_b_income=150000.0,
        spouse_b_employer="Google",
        is_primary=True,
    )
    defaults.update(overrides)
    hh = HouseholdProfile(**defaults)
    session.add(hh)
    await session.flush()
    return hh


async def _seed_entity(session: AsyncSession, name: str = "AutoRev", **overrides) -> BusinessEntity:
    defaults = dict(
        entity_type="llc",
        tax_treatment="schedule_c",
        is_active=True,
        is_provisional=False,
    )
    defaults.update(overrides)
    entity = BusinessEntity(name=name, **defaults)
    session.add(entity)
    await session.flush()
    return entity


# ═══════════════════════════════════════════════════════════════════════════
# 1. PRIVACY MODULE (pipeline/ai/privacy.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestPIISanitizer:
    """Test PII scrubbing with realistic financial data."""

    def test_sanitize_names(self):
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        hh = SimpleNamespace(
            spouse_a_name="John Smith",
            spouse_a_preferred_name="John",
            spouse_b_name="Jane Smith",
            spouse_a_employer="Accenture",
            spouse_b_employer="Google",
        )
        sanitizer.register_household(hh)

        text = "John Smith earns $250k at Accenture and Jane Smith earns $150k at Google."
        sanitized = sanitizer.sanitize_text(text)

        # Real names and employers must be removed
        assert "John Smith" not in sanitized
        assert "Jane Smith" not in sanitized
        assert "Accenture" not in sanitized
        assert "Google" not in sanitized

        # Labels must be present
        assert "Primary Earner" in sanitized
        assert "Secondary Earner" in sanitized
        assert "Employer A" in sanitized
        assert "Employer B" in sanitized

    def test_desanitize_restores_names(self):
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        hh = SimpleNamespace(
            spouse_a_name="Mike Aron",
            spouse_a_preferred_name=None,
            spouse_b_name="Sarah Aron",
            spouse_a_employer="TechCorp",
            spouse_b_employer=None,
        )
        sanitizer.register_household(hh)

        original = "Mike Aron works at TechCorp with Sarah Aron."
        sanitized = sanitizer.sanitize_text(original)
        restored = sanitizer.desanitize_text(sanitized)

        assert "Mike Aron" in restored
        assert "Sarah Aron" in restored
        assert "TechCorp" in restored

    def test_sanitize_case_insensitive(self):
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        hh = SimpleNamespace(
            spouse_a_name="Robert Chen",
            spouse_a_preferred_name=None,
            spouse_b_name=None,
            spouse_a_employer="META",
            spouse_b_employer=None,
        )
        sanitizer.register_household(hh)

        text = "ROBERT CHEN at meta gets paid well."
        sanitized = sanitizer.sanitize_text(text)

        assert "ROBERT CHEN" not in sanitized
        assert "meta" not in sanitized
        assert "Primary Earner" in sanitized
        assert "Employer A" in sanitized

    def test_sanitize_entities(self):
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        entities = [
            SimpleNamespace(name="AutoRev LLC"),
            SimpleNamespace(name="SkyBridge Consulting"),
        ]
        sanitizer.register_household(SimpleNamespace(
            spouse_a_name=None, spouse_a_preferred_name=None,
            spouse_b_name=None, spouse_a_employer=None, spouse_b_employer=None,
        ), entities)

        text = "AutoRev LLC has $50k in expenses. SkyBridge Consulting earned $100k."
        sanitized = sanitizer.sanitize_text(text)

        assert "AutoRev LLC" not in sanitized
        assert "SkyBridge Consulting" not in sanitized
        assert "Entity A" in sanitized
        assert "Entity B" in sanitized

    def test_longer_matches_replaced_first(self):
        """'John Smith' should be replaced before 'John' to avoid partial replacement."""
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        hh = SimpleNamespace(
            spouse_a_name="John Smith",
            spouse_a_preferred_name="John",
            spouse_b_name=None,
            spouse_a_employer=None,
            spouse_b_employer=None,
        )
        sanitizer.register_household(hh)

        text = "John Smith went to the store. John paid with cash."
        sanitized = sanitizer.sanitize_text(text)

        # "John Smith" should become "Primary Earner", not "Primary Earner Smith"
        assert "Smith" not in sanitized
        # Count: "John Smith" -> "Primary Earner", then "John" -> "Primary Earner"
        assert sanitized.count("Primary Earner") >= 2

    def test_sanitize_dict_recursive(self):
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        hh = SimpleNamespace(
            spouse_a_name="Alice",
            spouse_a_preferred_name=None,
            spouse_b_name=None,
            spouse_a_employer="BigCo",
            spouse_b_employer=None,
        )
        sanitizer.register_household(hh)

        data = {
            "name": "Alice",
            "nested": {"employer": "BigCo", "amount": 100000},
            "list_field": ["Alice earns", "from BigCo"],
        }
        result = sanitizer.sanitize_dict(data)

        assert result["name"] == "Primary Earner"
        assert result["nested"]["employer"] == "Employer A"
        assert result["nested"]["amount"] == 100000  # Non-string preserved
        assert "Primary Earner" in result["list_field"][0]
        assert "Employer A" in result["list_field"][1]

    def test_has_mappings_property(self):
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        assert sanitizer.has_mappings is False

        hh = SimpleNamespace(
            spouse_a_name="Test",
            spouse_a_preferred_name=None,
            spouse_b_name=None,
            spouse_a_employer=None,
            spouse_b_employer=None,
        )
        sanitizer.register_household(hh)
        assert sanitizer.has_mappings is True

    def test_empty_and_whitespace_values_skipped(self):
        from pipeline.ai.privacy import PIISanitizer

        sanitizer = PIISanitizer()
        hh = SimpleNamespace(
            spouse_a_name="",
            spouse_a_preferred_name="  ",
            spouse_b_name=None,
            spouse_a_employer="",
            spouse_b_employer=None,
        )
        sanitizer.register_household(hh)
        assert sanitizer.has_mappings is False


class TestBuildSanitizedHouseholdContext:
    def test_with_full_household(self):
        from pipeline.ai.privacy import PIISanitizer, build_sanitized_household_context

        hh = SimpleNamespace(
            filing_status="mfj",
            state="CA",
            spouse_a_name="John Smith",
            spouse_a_preferred_name=None,
            spouse_a_income=250000.0,
            spouse_a_employer="Accenture",
            spouse_b_name="Jane Smith",
            spouse_b_income=150000.0,
            spouse_b_employer="Google",
            other_income_sources_json=json.dumps([
                {"label": "Rental Income", "amount": 24000, "type": "rental"}
            ]),
            dependents_json=json.dumps([{"name": "Kid", "age": 5}]),
        )
        sanitizer = PIISanitizer()
        sanitizer.register_household(hh)

        ctx = build_sanitized_household_context(hh, sanitizer)

        assert "MFJ" in ctx
        assert "CA" in ctx
        assert "250,000" in ctx
        assert "150,000" in ctx
        assert "John Smith" not in ctx
        assert "Jane Smith" not in ctx
        assert "Accenture" not in ctx
        assert "Google" not in ctx
        assert "Primary Earner" in ctx
        assert "Dependents: 1" in ctx
        assert "24,000" in ctx

    def test_no_household(self):
        from pipeline.ai.privacy import PIISanitizer, build_sanitized_household_context

        sanitizer = PIISanitizer()
        ctx = build_sanitized_household_context(None, sanitizer)
        assert "No household profile configured" in ctx


class TestSanitizeEntityList:
    def test_entity_names_sanitized(self):
        from pipeline.ai.privacy import PIISanitizer, sanitize_entity_list

        entities = [
            SimpleNamespace(
                id=1, name="AutoRev LLC", entity_type="llc",
                tax_treatment="schedule_c", owner="John Smith",
                is_active=True, is_provisional=False,
                description="Car dealership", expected_expenses="inventory, rent",
            ),
        ]
        sanitizer = PIISanitizer()
        hh = SimpleNamespace(
            spouse_a_name="John Smith", spouse_a_preferred_name=None,
            spouse_b_name=None, spouse_a_employer=None, spouse_b_employer=None,
        )
        sanitizer.register_household(hh, entities)

        result = sanitize_entity_list(entities, sanitizer)

        assert len(result) == 1
        assert "AutoRev LLC" not in result[0]["name"]
        assert result[0]["entity_type"] == "llc"
        assert result[0]["tax_treatment"] == "schedule_c"
        assert "John Smith" not in result[0]["owner"]
        assert result[0]["description"] == "Car dealership"

    def test_enrichment_maps(self):
        from pipeline.ai.privacy import PIISanitizer, sanitize_entity_list

        entities = [
            SimpleNamespace(
                id=1, name="BizCo", entity_type="sole_prop",
                tax_treatment="schedule_c", owner="", is_active=True,
                is_provisional=False, description=None, expected_expenses=None,
            ),
        ]
        sanitizer = PIISanitizer()
        sanitizer.register_household(SimpleNamespace(
            spouse_a_name=None, spouse_a_preferred_name=None,
            spouse_b_name=None, spouse_a_employer=None, spouse_b_employer=None,
        ), entities)

        accounts_map = {1: ["Chase Business Card"]}
        rules_map = {1: ["amazon", "stripe"]}

        result = sanitize_entity_list(entities, sanitizer, accounts_map=accounts_map, rules_map=rules_map)

        assert result[0]["assigned_accounts"] == ["Chase Business Card"]
        assert result[0]["vendor_patterns"] == ["amazon", "stripe"]


class TestLogAiPrivacyAudit:
    def test_logs_audit(self, caplog):
        from pipeline.ai.privacy import log_ai_privacy_audit

        with caplog.at_level(logging.INFO, logger="pipeline.ai.privacy"):
            log_ai_privacy_audit("categorize", ["transactions", "entities"], sanitized=True)

        assert "AI privacy audit" in caplog.text
        assert "categorize" in caplog.text
        assert "sanitized" in caplog.text


# ═══════════════════════════════════════════════════════════════════════════
# 2. CATEGORY RULES ENGINE (pipeline/ai/category_rules.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestNormalizeMerchant:
    def test_strips_store_number(self):
        from pipeline.ai.category_rules import normalize_merchant

        assert normalize_merchant("STARBUCKS #1234 SEATTLE WA") == "starbucks"

    def test_strips_date_suffix(self):
        from pipeline.ai.category_rules import normalize_merchant

        assert normalize_merchant("TARGET 06/15 PURCHASE") == "target"

    def test_strips_reference_numbers(self):
        from pipeline.ai.category_rules import normalize_merchant

        assert normalize_merchant("AMAZON.COM 123456789") == "amazon.com"

    def test_strips_trailing_state(self):
        from pipeline.ai.category_rules import normalize_merchant

        assert normalize_merchant("TRADER JOE'S CA") == "trader joe's"

    def test_strips_trailing_amount(self):
        from pipeline.ai.category_rules import normalize_merchant

        assert normalize_merchant("UBER TRIP 12.50") == "uber trip"

    def test_empty_string(self):
        from pipeline.ai.category_rules import normalize_merchant

        assert normalize_merchant("") == ""
        assert normalize_merchant(None) == ""

    def test_collapses_whitespace(self):
        from pipeline.ai.category_rules import normalize_merchant

        result = normalize_merchant("WHOLE   FOODS   MARKET")
        assert "  " not in result
        assert result == "whole foods market"


class TestMatchesMerchant:
    def test_exact_match(self):
        from pipeline.ai.category_rules import _matches_merchant

        assert _matches_merchant("starbucks", "starbucks") is True

    def test_prefix_match(self):
        from pipeline.ai.category_rules import _matches_merchant

        assert _matches_merchant("starbucks", "starbucks coffee") is True

    def test_word_boundary_match(self):
        from pipeline.ai.category_rules import _matches_merchant

        assert _matches_merchant("starbucks", "the starbucks store") is True

    def test_no_substring_match(self):
        from pipeline.ai.category_rules import _matches_merchant

        # "at" should NOT match "national"
        assert _matches_merchant("at", "national") is False

    def test_empty_values(self):
        from pipeline.ai.category_rules import _matches_merchant

        assert _matches_merchant("", "starbucks") is False
        assert _matches_merchant("starbucks", "") is False
        assert _matches_merchant("", "") is False


class TestSortRulesBySpecificity:
    def test_longer_patterns_first(self):
        from pipeline.ai.category_rules import _sort_rules_by_specificity

        r1 = MagicMock(merchant_pattern="target")
        r2 = MagicMock(merchant_pattern="target supercenter")
        result = _sort_rules_by_specificity([r1, r2])
        assert result[0].merchant_pattern == "target supercenter"
        assert result[1].merchant_pattern == "target"


class TestApplyRuleToTransaction:
    def test_applies_all_fields(self):
        from pipeline.ai.category_rules import _apply_rule_to_transaction

        txn = MagicMock()
        rule = MagicMock(
            category="Groceries & Food",
            tax_category="Not Deductible",
            segment="personal",
            business_entity_id=None,
        )
        _apply_rule_to_transaction(txn, rule)

        assert txn.effective_category == "Groceries & Food"
        assert txn.category == "Groceries & Food"
        assert txn.effective_tax_category == "Not Deductible"
        assert txn.effective_segment == "personal"
        assert txn.ai_confidence == 0.95

    def test_skips_none_fields(self):
        from pipeline.ai.category_rules import _apply_rule_to_transaction

        txn = MagicMock(effective_category="Old Category")
        rule = MagicMock(
            category="New Category",
            tax_category=None,
            segment=None,
            business_entity_id=None,
        )
        _apply_rule_to_transaction(txn, rule)

        assert txn.effective_category == "New Category"
        # tax_category and segment should not be changed when rule value is None


class TestRuleDateMatching:
    def test_no_date_constraints(self):
        from pipeline.ai.category_rules import _rule_matches_date

        rule = MagicMock(effective_from=None, effective_to=None)
        assert _rule_matches_date(rule, date(2025, 6, 15)) is True

    def test_within_range(self):
        from pipeline.ai.category_rules import _rule_matches_date

        rule = MagicMock(effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31))
        assert _rule_matches_date(rule, date(2025, 6, 15)) is True

    def test_before_range(self):
        from pipeline.ai.category_rules import _rule_matches_date

        rule = MagicMock(effective_from=date(2025, 1, 1), effective_to=None)
        assert _rule_matches_date(rule, date(2024, 12, 31)) is False

    def test_after_range(self):
        from pipeline.ai.category_rules import _rule_matches_date

        rule = MagicMock(effective_from=None, effective_to=date(2025, 6, 1))
        assert _rule_matches_date(rule, date(2025, 6, 15)) is False


@pytest.mark.asyncio
class TestLearnFromOverride:
    async def test_creates_rule_from_transaction(self, session):
        from pipeline.ai.category_rules import learn_from_override

        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, description="STARBUCKS #1234 SEATTLE WA")

        result = await learn_from_override(
            session, tx.id, new_category="Coffee & Beverages"
        )

        assert result["rule_created"] is True
        assert result["merchant"] == "starbucks"
        assert result["category"] == "Coffee & Beverages"

        # Verify rule exists in DB
        rule_result = await session.execute(
            select(CategoryRule).where(CategoryRule.merchant_pattern == "starbucks")
        )
        rule = rule_result.scalar_one()
        assert rule.category == "Coffee & Beverages"
        assert rule.source == "user_override"

    async def test_updates_existing_rule(self, session):
        from pipeline.ai.category_rules import learn_from_override

        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, description="STARBUCKS #5678")

        # Create first rule
        await learn_from_override(session, tx.id, new_category="Coffee & Beverages")

        # Update with different category
        result = await learn_from_override(session, tx.id, new_category="Restaurants & Dining")

        assert result["rule_created"] is True
        rule_result = await session.execute(
            select(CategoryRule).where(CategoryRule.merchant_pattern == "starbucks")
        )
        rule = rule_result.scalar_one()
        assert rule.category == "Restaurants & Dining"
        assert rule.match_count >= 2

    async def test_short_merchant_skipped(self, session):
        from pipeline.ai.category_rules import learn_from_override

        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, description="AT")

        result = await learn_from_override(session, tx.id, new_category="Coffee & Beverages")
        assert result["rule_created"] is False

    async def test_transaction_not_found(self, session):
        from pipeline.ai.category_rules import learn_from_override

        result = await learn_from_override(session, 99999, new_category="Coffee & Beverages")
        assert result["rule_created"] is False
        assert "not found" in result.get("error", "").lower()


@pytest.mark.asyncio
class TestApplyRules:
    async def test_applies_rules_to_uncategorized(self, session):
        from pipeline.ai.category_rules import apply_rules

        acct = await _seed_account(session)

        # Create two uncategorized starbucks transactions
        await _seed_transaction(session, acct.id, description="STARBUCKS #111 SEATTLE")
        await _seed_transaction(session, acct.id, description="STARBUCKS #222 PORTLAND")

        # Create a rule
        rule = CategoryRule(
            merchant_pattern="starbucks",
            category="Coffee & Beverages",
            segment="personal",
            source="user_override",
            match_count=0,
            is_active=True,
        )
        session.add(rule)
        await session.flush()

        result = await apply_rules(session)

        assert result["applied"] >= 2

    async def test_no_rules_returns_zero(self, session):
        from pipeline.ai.category_rules import apply_rules

        result = await apply_rules(session)
        assert result["applied"] == 0


@pytest.mark.asyncio
class TestUpdateAndDeactivateRule:
    async def test_update_rule_fields(self, session):
        from pipeline.ai.category_rules import update_rule

        rule = CategoryRule(
            merchant_pattern="starbucks",
            category="Coffee & Beverages",
            source="user_override",
            match_count=0,
            is_active=True,
        )
        session.add(rule)
        await session.flush()

        result = await update_rule(session, rule.id, {"category": "Restaurants & Dining", "segment": "business"})

        assert result["success"] is True
        assert "category" in result["changes"]
        assert "segment" in result["changes"]

    async def test_update_nonexistent_rule(self, session):
        from pipeline.ai.category_rules import update_rule

        result = await update_rule(session, 99999, {"category": "test"})
        assert "error" in result

    async def test_deactivate_rule(self, session):
        from pipeline.ai.category_rules import deactivate_rule

        rule = CategoryRule(
            merchant_pattern="starbucks",
            category="Coffee & Beverages",
            source="user_override",
            match_count=0,
            is_active=True,
        )
        session.add(rule)
        await session.flush()

        result = await deactivate_rule(session, rule.id)

        assert result["success"] is True
        # Verify in DB
        r = await session.execute(select(CategoryRule).where(CategoryRule.id == rule.id))
        assert r.scalar_one().is_active is False


@pytest.mark.asyncio
class TestListRules:
    async def test_lists_rules_ordered_by_match_count(self, session):
        from pipeline.ai.category_rules import list_rules

        session.add(CategoryRule(
            merchant_pattern="starbucks", category="Coffee",
            source="user_override", match_count=5, is_active=True,
        ))
        session.add(CategoryRule(
            merchant_pattern="target", category="Shopping",
            source="user_override", match_count=10, is_active=True,
        ))
        await session.flush()

        rules = await list_rules(session)

        assert len(rules) >= 2
        assert rules[0]["match_count"] >= rules[1]["match_count"]
        assert rules[0]["merchant_pattern"] == "target"


# ═══════════════════════════════════════════════════════════════════════════
# 3. SCENARIO ANALYZER (pipeline/ai/scenario_analyzer.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildScenarioPrompt:
    def test_includes_scenario_fields(self):
        from pipeline.ai.scenario_analyzer import _build_scenario_prompt

        scenario = {
            "name": "Buy a House",
            "scenario_type": "home_purchase",
            "total_cost": 800000,
            "new_monthly_payment": 4500,
            "monthly_surplus_after": 3000,
            "savings_rate_before_pct": 25.0,
            "savings_rate_after_pct": 15.0,
            "dti_before_pct": 10.0,
            "dti_after_pct": 32.0,
            "affordability_score": 72,
            "verdict": "stretch",
            "parameters": {"down_payment_pct": 20, "rate": 6.5},
        }
        household = {"income": 400000, "filing_status": "mfj", "state": "CA"}

        prompt = _build_scenario_prompt(scenario, household)

        assert "Buy a House" in prompt
        assert "home_purchase" in prompt
        assert "$800,000" in prompt
        assert "$4,500" in prompt
        assert "25.0%" in prompt
        assert "72" in prompt
        assert "stretch" in prompt
        assert "400,000" in prompt
        assert "MFJ" in prompt.upper()

    def test_empty_household_context(self):
        from pipeline.ai.scenario_analyzer import _build_scenario_prompt

        scenario = {"name": "Test", "scenario_type": "test", "total_cost": 0,
                     "new_monthly_payment": 0, "monthly_surplus_after": 0,
                     "savings_rate_before_pct": 0, "savings_rate_after_pct": 0,
                     "dti_before_pct": 0, "dti_after_pct": 0,
                     "affordability_score": 0, "verdict": "unknown",
                     "parameters": {}}

        prompt = _build_scenario_prompt(scenario, {})
        assert "HENRY" in prompt  # Still contains the instruction


class TestAnalyzeScenarioWithAI:
    @patch("pipeline.ai.scenario_analyzer.get_claude_client")
    @patch("pipeline.ai.scenario_analyzer.call_claude_with_retry")
    def test_returns_analysis_text(self, mock_call, mock_client):
        from pipeline.ai.scenario_analyzer import analyze_scenario_with_ai

        mock_client.return_value = MagicMock()
        mock_call.return_value = _mock_claude_response(
            "This is a solid financial decision. The 20% down payment keeps you under the 32% DTI threshold..."
        )

        result = analyze_scenario_with_ai(
            {"name": "Buy House", "scenario_type": "home_purchase", "total_cost": 500000,
             "new_monthly_payment": 3000, "monthly_surplus_after": 2000,
             "savings_rate_before_pct": 30, "savings_rate_after_pct": 20,
             "dti_before_pct": 5, "dti_after_pct": 28,
             "affordability_score": 80, "verdict": "comfortable",
             "parameters": {}},
            {"income": 300000, "filing_status": "mfj", "state": "TX"},
        )

        assert "analysis" in result
        assert len(result["analysis"]) > 0
        mock_call.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# 4. CATEGORIZER (pipeline/ai/categorizer.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildCategorizationPrompt:
    def test_includes_transactions_and_categories(self):
        from pipeline.ai.categorizer import _build_categorization_prompt

        txns = [
            {"id": 1, "date": "2025-06-15", "description": "STARBUCKS", "amount": -5.50, "segment": "personal"},
            {"id": 2, "date": "2025-06-16", "description": "AMAZON WEB SERVICES", "amount": -99.00, "segment": "business"},
        ]
        prompt = _build_categorization_prompt(txns)

        assert "STARBUCKS" in prompt
        assert "AMAZON WEB SERVICES" in prompt
        assert "-5.5" in prompt
        assert "-99.0" in prompt
        assert "Groceries & Food" in prompt  # From EXPENSE_CATEGORIES
        assert "Schedule C" in prompt  # From TAX_CATEGORIES

    def test_includes_entity_context(self):
        from pipeline.ai.categorizer import _build_categorization_prompt

        txns = [{"id": 1, "date": "2025-06-15", "description": "TEST", "amount": -10}]
        entities = [
            {"name": "Entity A", "entity_type": "llc", "tax_treatment": "schedule_c",
             "owner": "Primary Earner", "is_active": True, "is_provisional": False,
             "description": "Software consulting", "expected_expenses": "cloud hosting, software",
             "assigned_accounts": ["Chase Business"], "vendor_patterns": ["aws", "google cloud"]},
        ]
        prompt = _build_categorization_prompt(txns, entities=entities)

        assert "Entity A" in prompt
        assert "llc" in prompt
        assert "Software consulting" in prompt
        assert "cloud hosting, software" in prompt
        assert "Chase Business" in prompt
        assert "aws" in prompt

    def test_includes_household_context(self):
        from pipeline.ai.categorizer import _build_categorization_prompt

        txns = [{"id": 1, "date": "2025-06-15", "description": "TEST", "amount": -10}]
        prompt = _build_categorization_prompt(txns, household_context="- Filing status: MFJ\n- Primary earner: W-2 employee")

        assert "MFJ" in prompt
        assert "W-2 employee" in prompt


class TestDetectDocumentType:
    """Test rule-based document type detection (no AI call)."""

    def test_w2_from_content(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("Wage and Tax Statement W-2 2025", "doc.pdf")
        assert result["detected_type"] == "tax_document"
        assert result["suggested_fields"]["form_type"] == "w2"
        assert result["confidence"] >= 0.9

    def test_1099_nec(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("Form 1099-NEC Nonemployee Compensation", "1099.pdf")
        assert result["detected_type"] == "tax_document"
        assert result["suggested_fields"]["form_type"] == "1099_nec"

    def test_amazon_csv(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("Order ID,Order Date,Items Ordered,Shipping Address", "orders.csv")
        assert result["detected_type"] == "amazon"
        assert result["confidence"] >= 0.9

    def test_credit_card_csv(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("Transaction Date,Description,Amount,Debit", "statement.csv")
        assert result["detected_type"] == "credit_card"

    def test_pay_stub_pdf(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("Pay Stub Earnings Statement Pay Period Gross Pay Net Pay", "pay.pdf")
        assert result["detected_type"] == "pay_stub"

    def test_insurance_pdf(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("Home Insurance Policy Number Premium Coverage Deductible Underwritten By", "policy.pdf")
        assert result["detected_type"] == "insurance"

    def test_k1_from_content(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("Schedule K-1 Partner's Share of Income", "k1.pdf")
        assert result["detected_type"] == "tax_document"
        assert result["suggested_fields"]["form_type"] == "k1"

    def test_filename_fallback_w2(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("", "my-w2-2025.pdf")
        assert result["detected_type"] == "tax_document"

    def test_unknown_defaults_to_credit_card(self):
        from pipeline.ai.categorizer import detect_document_type

        result = detect_document_type("random stuff", "mystery.txt")
        assert result["detected_type"] == "credit_card"
        assert result["confidence"] == 0.50


class TestExtractTaxFieldsWithClaude:
    @pytest.mark.asyncio
    @patch("pipeline.ai.categorizer.get_claude_client")
    @patch("pipeline.ai.categorizer.call_claude_with_retry")
    async def test_extracts_w2_fields(self, mock_call, mock_client):
        mock_client.return_value = MagicMock()
        mock_call.return_value = _mock_claude_response(json.dumps({
            "_form_type": "w2",
            "payer_name": "Accenture LLP",
            "payer_ein": "36-0000000",
            "w2_wages": 250000,
            "w2_federal_tax_withheld": 50000,
            "w2_ss_wages": 168600,
            "w2_ss_tax_withheld": 10453,
            "w2_medicare_wages": 250000,
            "w2_medicare_tax_withheld": 3625,
        }))

        from pipeline.ai.categorizer import extract_tax_fields_with_claude

        result = await extract_tax_fields_with_claude("Wage and Tax Statement...", 2025)

        assert result["_form_type"] == "w2"
        assert result["w2_wages"] == 250000
        assert result["w2_federal_tax_withheld"] == 50000
        mock_call.assert_called_once()

    @pytest.mark.asyncio
    @patch("pipeline.ai.categorizer.get_claude_client")
    @patch("pipeline.ai.categorizer.call_claude_with_retry")
    async def test_handles_images(self, mock_call, mock_client):
        mock_client.return_value = MagicMock()
        mock_call.return_value = _mock_claude_response(json.dumps({
            "_form_type": "1099_int",
            "payer_name": "Chase",
            "int_interest": 1500.0,
        }))

        from pipeline.ai.categorizer import extract_tax_fields_with_claude

        result = await extract_tax_fields_with_claude(
            "Interest income...",
            2025,
            images=[b"fake_png_data"],
        )

        assert result["_form_type"] == "1099_int"
        # Verify images were included in the call
        call_args = mock_call.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
        content = messages[0]["content"]
        assert any(c.get("type") == "image" for c in content)


# ═══════════════════════════════════════════════════════════════════════════
# 5. RULE GENERATOR (pipeline/ai/rule_generator.py)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGenerateRulesFromPatterns:
    async def test_finds_consistent_merchants(self, session):
        from pipeline.ai.rule_generator import generate_rules_from_patterns

        acct = await _seed_account(session)

        # Create 3 transactions with same merchant and same category
        for i in range(3):
            await _seed_transaction(
                session, acct.id,
                description=f"WHOLE FOODS #{i}",
                amount=-50.0 - i,
                effective_category="Groceries & Food",
                effective_segment="personal",
                is_excluded=False,
                is_manually_reviewed=False,
            )

        proposals = await generate_rules_from_patterns(session)

        assert len(proposals) >= 1
        wf = [p for p in proposals if p["merchant"] == "whole foods"]
        assert len(wf) == 1
        assert wf[0]["category"] == "Groceries & Food"
        assert wf[0]["confidence"] >= 0.8
        assert wf[0]["source"] == "pattern"

    async def test_skips_low_consistency(self, session):
        from pipeline.ai.rule_generator import generate_rules_from_patterns

        acct = await _seed_account(session)

        # Two starbucks transactions with different categories
        await _seed_transaction(session, acct.id, description="STARBUCKS #111",
                                effective_category="Coffee & Beverages", effective_segment="personal",
                                is_excluded=False, is_manually_reviewed=False)
        await _seed_transaction(session, acct.id, description="STARBUCKS #222",
                                effective_category="Business — Meals (50% deductible)", effective_segment="business",
                                is_excluded=False, is_manually_reviewed=False)

        proposals = await generate_rules_from_patterns(session)

        starbucks_proposals = [p for p in proposals if p["merchant"] == "starbucks"]
        # 50% consistency is below 80% threshold
        assert len(starbucks_proposals) == 0


@pytest.mark.asyncio
class TestCreateRulesFromProposals:
    async def test_creates_new_rules(self, session):
        from pipeline.ai.rule_generator import create_rules_from_proposals

        proposals = [
            {"merchant": "whole foods", "category": "Groceries & Food",
             "tax_category": None, "segment": "personal", "entity_id": None},
            {"merchant": "aws", "category": "Business — Software & Subscriptions",
             "tax_category": "Schedule C — Supplies", "segment": "business", "entity_id": None},
        ]

        result = await create_rules_from_proposals(session, proposals)

        assert result["rules_created"] == 2
        assert result["duplicates_skipped"] == 0

    async def test_skips_existing_active_rules(self, session):
        from pipeline.ai.rule_generator import create_rules_from_proposals

        # Seed existing active rule
        session.add(CategoryRule(
            merchant_pattern="whole foods", category="Groceries & Food",
            source="user_override", match_count=5, is_active=True,
        ))
        await session.flush()

        proposals = [
            {"merchant": "whole foods", "category": "Groceries & Food",
             "segment": "personal", "entity_id": None},
        ]

        result = await create_rules_from_proposals(session, proposals)

        assert result["duplicates_skipped"] == 1
        assert result["rules_created"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 6. REPORT GENERATOR (pipeline/ai/report_gen.py)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestComputePeriodSummary:
    async def test_computes_income_and_expenses(self, session):
        from pipeline.ai.report_gen import compute_period_summary

        acct = await _seed_account(session)

        # Income transaction
        await _seed_transaction(session, acct.id, description="PAYROLL",
                                amount=10000.0, effective_category="W-2 Wages",
                                effective_segment="personal")
        # Expense transaction
        await _seed_transaction(session, acct.id, description="GROCERIES",
                                amount=-500.0, effective_category="Groceries & Food",
                                effective_segment="personal")
        # Transfer (should be excluded from totals)
        await _seed_transaction(session, acct.id, description="CREDIT CARD PAYMENT",
                                amount=-3000.0, effective_category="Credit Card Payment",
                                effective_segment="personal")

        result = await compute_period_summary(session, 2025, month=6)

        assert result["total_income"] == 10000.0
        assert result["total_expenses"] == 500.0  # Transfer excluded
        assert result["net_cash_flow"] == 9500.0
        assert result["w2_income"] == 10000.0

    async def test_excludes_transfers(self, session):
        from pipeline.ai.report_gen import compute_period_summary

        acct = await _seed_account(session)

        # Only a transfer
        await _seed_transaction(session, acct.id, description="TRANSFER",
                                amount=-1000.0, effective_category="Transfer",
                                effective_segment="personal")

        result = await compute_period_summary(session, 2025, month=6)

        assert result["total_income"] == 0.0
        assert result["total_expenses"] == 0.0


@pytest.mark.asyncio
class TestGenerateMonthlyInsights:
    @patch("pipeline.ai.report_gen.get_claude_client")
    @patch("pipeline.ai.report_gen.call_claude_with_retry")
    async def test_generates_insights(self, mock_call, mock_client, session):
        mock_client.return_value = MagicMock()
        mock_call.return_value = _mock_claude_response(
            "## June 2025 Financial Review\n\nYour net cash flow was positive at **$9,500**..."
        )

        from pipeline.ai.report_gen import generate_monthly_insights

        period_data = {
            "total_income": 10000.0,
            "total_expenses": 500.0,
            "net_cash_flow": 9500.0,
            "business_expenses": 0.0,
            "w2_income": 10000.0,
            "investment_income": 0.0,
            "board_income": 0.0,
            "expense_breakdown": json.dumps({"Groceries & Food": 500.0}),
            "income_breakdown": json.dumps({"W-2 Wages": 10000.0}),
        }

        result = await generate_monthly_insights(session, 2025, 6, period_data)

        assert "Financial Review" in result
        assert len(result) > 0
        mock_call.assert_called_once()

    @patch("pipeline.ai.report_gen.get_claude_client")
    @patch("pipeline.ai.report_gen.call_claude_with_retry")
    async def test_includes_prior_month_comparison(self, mock_call, mock_client, session):
        mock_client.return_value = MagicMock()
        mock_call.return_value = _mock_claude_response("Insights with comparison...")

        from pipeline.ai.report_gen import generate_monthly_insights

        period_data = {
            "total_income": 12000, "total_expenses": 3000, "net_cash_flow": 9000,
            "business_expenses": 500, "w2_income": 12000, "investment_income": 0,
            "board_income": 0, "expense_breakdown": "{}", "income_breakdown": "{}",
        }
        prior = {
            "total_income": 10000, "total_expenses": 2500, "net_cash_flow": 7500,
        }

        await generate_monthly_insights(session, 2025, 6, period_data, prior_month_data=prior)

        # Verify prior month data was included in the prompt
        call_args = mock_call.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
        prompt_text = messages[0]["content"]
        assert "$10,000" in prompt_text  # Prior month income
        assert "$12,000" in prompt_text  # Current month income


# ═══════════════════════════════════════════════════════════════════════════
# 7. TAX ANALYZER (pipeline/ai/tax_analyzer.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildStrategyPrompt:
    def test_includes_tax_brackets(self):
        from pipeline.ai.tax_analyzer import _build_strategy_prompt

        snapshot = {
            "tax_year": 2025,
            "w2_wages": 250000,
            "estimated_total_income": 400000,
        }
        prompt = _build_strategy_prompt(snapshot, household_context="- Filing status: MFJ")

        assert "2025 Federal Tax Brackets" in prompt
        assert "$23,850" in prompt or "23,850" in prompt
        assert "MFJ" in prompt
        assert "250000" in prompt or "250,000" in prompt
        assert "SALT deduction cap" in prompt
        assert "401(k)" in prompt

    def test_no_household_context_fallback(self):
        from pipeline.ai.tax_analyzer import _build_strategy_prompt

        prompt = _build_strategy_prompt({"tax_year": 2025}, household_context="")
        assert "No household profile configured" in prompt


@pytest.mark.asyncio
class TestRunTaxAnalysis:
    @patch("pipeline.ai.tax_analyzer.get_claude_client")
    @patch("pipeline.ai.tax_analyzer.call_claude_with_retry")
    @patch("pipeline.ai.tax_analyzer.get_tax_summary")
    @patch("pipeline.ai.tax_analyzer.get_all_business_entities")
    @patch("pipeline.ai.tax_analyzer.replace_tax_strategies")
    async def test_generates_strategies(self, mock_replace, mock_entities,
                                        mock_tax_summary, mock_call, mock_client, session):
        mock_client.return_value = MagicMock()

        strategies = [
            {
                "priority": 1,
                "title": "Maximize 401(k) Contributions",
                "description": "You can save $5,000+ by maxing contributions.",
                "strategy_type": "retirement",
                "estimated_savings_low": 5000,
                "estimated_savings_high": 8000,
                "action_required": "Increase payroll contribution to $23,500",
                "deadline": "December 31",
                "confidence": 0.95,
                "confidence_reasoning": "Standard retirement optimization",
                "category": "quick_win",
                "complexity": "low",
                "prerequisites_json": "[]",
                "who_its_for": "W-2 employees",
                "related_simulator": None,
            },
        ]
        mock_call.return_value = _mock_claude_response(json.dumps(strategies))
        mock_tax_summary.return_value = {
            "w2_total_wages": 250000, "w2_federal_withheld": 50000,
            "nec_total": 0, "div_ordinary": 5000, "div_qualified": 3000,
            "capital_gains_long": 2000, "capital_gains_short": 0,
            "interest_income": 1000, "w2_state_allocations": [],
        }
        mock_entities.return_value = []
        mock_replace.return_value = None

        from pipeline.ai.tax_analyzer import run_tax_analysis

        result = await run_tax_analysis(session, tax_year=2025)

        assert len(result) == 1
        assert result[0]["title"] == "Maximize 401(k) Contributions"
        assert result[0]["estimated_savings_low"] == 5000
        mock_replace.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# 8. CHAT MODULE (pipeline/ai/chat.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestChatToolDefinitions:
    """Verify the TOOLS list has correct schemas."""

    def test_all_tools_have_required_fields(self):
        from pipeline.ai.chat import TOOLS

        for tool in TOOLS:
            assert "name" in tool, f"Tool missing 'name'"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"
            assert tool["input_schema"]["type"] == "object", f"Tool {tool['name']} schema not object"
            assert "properties" in tool["input_schema"], f"Tool {tool['name']} missing 'properties'"

    def test_tool_count(self):
        from pipeline.ai.chat import TOOLS

        # There should be at least 25 tools
        assert len(TOOLS) >= 25

    def test_search_transactions_schema(self):
        from pipeline.ai.chat import TOOLS

        search = next(t for t in TOOLS if t["name"] == "search_transactions")
        props = search["input_schema"]["properties"]
        assert "query" in props
        assert "year" in props
        assert "month" in props
        assert "min_amount" in props
        assert "category" in props
        assert "segment" in props

    def test_recategorize_transaction_schema(self):
        from pipeline.ai.chat import TOOLS

        recat = next(t for t in TOOLS if t["name"] == "recategorize_transaction")
        assert "transaction_id" in recat["input_schema"]["required"]
        props = recat["input_schema"]["properties"]
        assert "category_override" in props
        assert "tax_category_override" in props
        assert "segment_override" in props
        assert "business_entity_name" in props

    def test_manage_budget_schema(self):
        from pipeline.ai.chat import TOOLS

        budget = next(t for t in TOOLS if t["name"] == "manage_budget")
        assert "action" in budget["input_schema"]["required"]
        props = budget["input_schema"]["properties"]
        assert props["action"]["enum"] == ["upsert", "delete"]

    def test_create_business_entity_schema(self):
        from pipeline.ai.chat import TOOLS

        create = next(t for t in TOOLS if t["name"] == "create_business_entity")
        assert "name" in create["input_schema"]["required"]
        props = create["input_schema"]["properties"]
        assert "entity_type" in props
        assert "tax_treatment" in props
        assert props["entity_type"]["enum"] == ["sole_prop", "llc", "s_corp", "c_corp", "partnership", "employer"]


class TestToolLabels:
    def test_every_tool_has_labels(self):
        from pipeline.ai.chat import TOOLS, TOOL_LABELS, TOOL_DONE_LABELS

        tool_names = {t["name"] for t in TOOLS}
        for name in tool_names:
            assert name in TOOL_LABELS, f"Tool '{name}' missing from TOOL_LABELS"
            assert name in TOOL_DONE_LABELS, f"Tool '{name}' missing from TOOL_DONE_LABELS"


@pytest.mark.asyncio
class TestExecTool:
    """Test the _exec_tool dispatcher routes to the correct handler."""

    async def test_search_transactions_empty(self, session):
        from pipeline.ai.chat import _exec_tool

        result = await _exec_tool(session, "search_transactions", {})
        data = json.loads(result)
        assert "transactions" in data or "count" in data

    async def test_get_account_balances_empty(self, session):
        from pipeline.ai.chat import _exec_tool

        result = await _exec_tool(session, "get_account_balances", {})
        data = json.loads(result)
        assert "accounts" in data or "total_count" in data or isinstance(data, dict)

    async def test_unknown_tool_returns_error(self, session):
        from pipeline.ai.chat import _exec_tool

        result = await _exec_tool(session, "nonexistent_tool_xyz", {})
        data = json.loads(result)
        assert "error" in data

    async def test_search_transactions_with_query(self, session):
        from pipeline.ai.chat import _exec_tool

        acct = await _seed_account(session)
        # Must set effective_category to a non-excluded value; search auto-excludes
        # NULL effective_category via not_ilike on SQLite (NULL LIKE anything = NULL).
        await _seed_transaction(session, acct.id, description="STARBUCKS COFFEE SEATTLE",
                                effective_category="Coffee & Beverages",
                                effective_segment="personal")

        result = await _exec_tool(session, "search_transactions", {"query": "STARBUCKS"})
        data = json.loads(result)
        assert data.get("count", 0) >= 1

    async def test_get_transaction_detail(self, session):
        from pipeline.ai.chat import _exec_tool

        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, description="TEST TRANSACTION", amount=-42.50)

        result = await _exec_tool(session, "get_transaction_detail", {"transaction_id": tx.id})
        data = json.loads(result)
        assert data["description"] == "TEST TRANSACTION"
        assert data["amount"] == -42.50

    async def test_get_spending_summary(self, session):
        from pipeline.ai.chat import _exec_tool

        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, description="GROCERIES",
                                amount=-100.0, effective_category="Groceries & Food",
                                effective_segment="personal")

        result = await _exec_tool(session, "get_spending_summary", {"year": 2025, "month": 6})
        data = json.loads(result)
        assert "categories" in data or "total_expenses" in data or isinstance(data, dict)

    async def test_recategorize_transaction(self, session):
        from pipeline.ai.chat import _exec_tool

        acct = await _seed_account(session)
        entity = await _seed_entity(session, name="TestBiz")
        tx = await _seed_transaction(session, acct.id, description="UBER RIDE",
                                     amount=-25.0, effective_segment="personal")

        result = await _exec_tool(session, "recategorize_transaction", {
            "transaction_id": tx.id,
            "category_override": "Business — Travel & Transportation",
            "segment_override": "business",
            "business_entity_name": "TestBiz",
        })
        data = json.loads(result)
        assert data.get("success") is True


@pytest.mark.asyncio
class TestBuildSystemPrompt:
    async def test_builds_prompt_with_household(self, session):
        from pipeline.ai.chat import _build_system_prompt, invalidate_prompt_cache

        invalidate_prompt_cache()
        await _seed_household(session)
        await _seed_entity(session, name="TestBusiness")

        prompt, sanitizer = await _build_system_prompt(session)

        assert "Sir Henry" in prompt
        assert "John Smith" not in prompt  # Should be sanitized
        assert "Accenture" not in prompt  # Should be sanitized
        assert "Primary Earner" in prompt
        assert "Employer A" in prompt
        assert sanitizer.has_mappings is True

    async def test_builds_prompt_without_household(self, session):
        from pipeline.ai.chat import _build_system_prompt, invalidate_prompt_cache

        invalidate_prompt_cache()

        prompt, sanitizer = await _build_system_prompt(session)

        assert "Sir Henry" in prompt
        assert "NOT SET UP" in prompt
        assert sanitizer.has_mappings is False


async def _seed_ai_consent(session: AsyncSession) -> None:
    """Seed the required AI privacy consent so run_chat proceeds."""
    consent = UserPrivacyConsent(
        consent_type="ai_features",
        consented=True,
        consent_version="1.0",
        consented_at=datetime.now(timezone.utc),
    )
    session.add(consent)
    await session.flush()


@pytest.mark.asyncio
class TestRunChat:
    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_simple_text_response(self, mock_build_prompt, session):
        from pipeline.ai.chat import run_chat
        from pipeline.ai.privacy import PIISanitizer

        await _seed_ai_consent(session)

        sanitizer = PIISanitizer()
        mock_build_prompt.return_value = ("System prompt", sanitizer)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(
            "Your spending looks healthy this month!"
        )

        with patch("pipeline.ai.chat.anthropic.Anthropic", return_value=mock_client):
            result = await run_chat(
                session,
                messages=[{"role": "user", "content": "How is my spending this month?"}],
            )

        assert "spending" in result["response"].lower()

    @patch("pipeline.ai.chat._build_system_prompt")
    async def test_tool_use_flow(self, mock_build_prompt, session):
        """Test that run_chat handles a tool_use response followed by a final text response."""
        from pipeline.ai.chat import run_chat
        from pipeline.ai.privacy import PIISanitizer

        await _seed_ai_consent(session)

        sanitizer = PIISanitizer()
        mock_build_prompt.return_value = ("System prompt", sanitizer)

        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, description="STARBUCKS #123", amount=-5.50,
                                effective_category="Coffee & Beverages",
                                effective_segment="personal")

        # First call returns tool_use, second returns text
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _mock_tool_use_response("search_transactions", {"query": "STARBUCKS"}),
            _mock_claude_response("I found 1 Starbucks transaction for **$5.50**."),
        ]

        with patch("pipeline.ai.chat.anthropic.Anthropic", return_value=mock_client):
            result = await run_chat(
                session,
                messages=[{"role": "user", "content": "Find my Starbucks transactions"}],
            )

        assert "starbucks" in result["response"].lower() or "5.50" in result["response"]
        assert mock_client.messages.create.call_count == 2

    async def test_requires_consent(self, session):
        """Without AI consent, run_chat returns requires_consent."""
        from pipeline.ai.chat import run_chat

        result = await run_chat(
            session,
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result["requires_consent"] is True
        assert result["response"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 9. CHAT TOOLS (pipeline/ai/chat_tools.py)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestChatToolListManualAssets:
    async def test_empty_assets(self, session):
        from pipeline.ai.chat_tools import _tool_list_manual_assets

        result = json.loads(await _tool_list_manual_assets(session, {}))
        assert result["count"] == 0
        assert result["total_assets"] == 0.0
        assert result["total_liabilities"] == 0.0

    async def test_with_assets(self, session):
        from pipeline.ai.chat_tools import _tool_list_manual_assets

        home = ManualAsset(
            name="Primary Residence", asset_type="real_estate",
            is_liability=False, current_value=750000.0,
            as_of_date=datetime.now(timezone.utc), is_active=True,
        )
        mortgage = ManualAsset(
            name="Mortgage", asset_type="real_estate",
            is_liability=True, current_value=500000.0,
            as_of_date=datetime.now(timezone.utc), is_active=True,
        )
        session.add_all([home, mortgage])
        await session.flush()

        result = json.loads(await _tool_list_manual_assets(session, {}))
        assert result["count"] == 2
        assert result["total_assets"] == 750000.0
        assert result["total_liabilities"] == 500000.0
        assert result["net"] == 250000.0

    async def test_filter_by_type(self, session):
        from pipeline.ai.chat_tools import _tool_list_manual_assets

        home = ManualAsset(
            name="Primary Residence", asset_type="real_estate",
            is_liability=False, current_value=750000.0,
            as_of_date=datetime.now(timezone.utc), is_active=True,
        )
        car = ManualAsset(
            name="Tesla Model Y", asset_type="vehicle",
            is_liability=False, current_value=45000.0,
            as_of_date=datetime.now(timezone.utc), is_active=True,
        )
        session.add_all([home, car])
        await session.flush()

        result = json.loads(await _tool_list_manual_assets(session, {"asset_type": "vehicle"}))
        assert result["count"] == 1
        assert result["assets"][0]["name"] == "Tesla Model Y"


@pytest.mark.asyncio
class TestChatToolUpdateAssetValue:
    async def test_updates_value(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value

        asset = ManualAsset(
            name="Primary Residence", asset_type="real_estate",
            is_liability=False, current_value=700000.0,
            as_of_date=datetime.now(timezone.utc), is_active=True,
        )
        session.add(asset)
        await session.flush()

        result = json.loads(await _tool_update_asset_value(session, {
            "asset_id": asset.id, "new_value": 750000.0, "notes": "Zillow estimate"
        }))

        assert result["success"] is True
        assert result["old_value"] == 700000.0
        assert result["new_value"] == 750000.0
        assert result["change"] == 50000.0

    async def test_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value

        result = json.loads(await _tool_update_asset_value(session, {
            "asset_id": 99999, "new_value": 100000.0,
        }))
        assert "error" in result


@pytest.mark.asyncio
class TestChatToolUpdateTransaction:
    async def test_exclude_transaction(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction

        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, description="DUPLICATE TXN")

        result = json.loads(await _tool_update_transaction(session, {
            "transaction_id": tx.id, "is_excluded": True,
        }))

        assert result["success"] is True
        assert "excluded from reports" in result["changes"][0]

    async def test_add_notes(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction

        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, description="SOME TXN")

        result = json.loads(await _tool_update_transaction(session, {
            "transaction_id": tx.id, "notes": "This is a test note",
        }))

        assert result["success"] is True
        assert "notes updated" in result["changes"]

    async def test_no_changes_error(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction

        acct = await _seed_account(session)
        tx = await _seed_transaction(session, acct.id, description="SOME TXN")

        result = json.loads(await _tool_update_transaction(session, {
            "transaction_id": tx.id,
        }))

        assert "error" in result


@pytest.mark.asyncio
class TestChatToolExcludeTransactions:
    async def test_batch_exclude_by_ids(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions

        acct = await _seed_account(session)
        tx1 = await _seed_transaction(session, acct.id, description="DUP 1")
        tx2 = await _seed_transaction(session, acct.id, description="DUP 2")

        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
            "transaction_ids": [tx1.id, tx2.id],
            "reason": "Duplicate charges",
        }))

        assert result["success"] is True
        assert result["count"] == 2

    async def test_exclude_by_query(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions

        acct = await _seed_account(session)
        await _seed_transaction(session, acct.id, description="DUPLICATE STARBUCKS #1")
        await _seed_transaction(session, acct.id, description="DUPLICATE STARBUCKS #2")

        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
            "query": "DUPLICATE STARBUCKS",
        }))

        assert result["success"] is True
        assert result["count"] == 2


@pytest.mark.asyncio
class TestChatToolGetDataHealth:
    async def test_health_check_empty_db(self, session):
        from pipeline.ai.chat_tools import _tool_get_data_health

        result = json.loads(await _tool_get_data_health(session, {}))

        assert "accounts" in result
        assert "transactions" in result
        assert "plaid" in result
        assert "manual_assets" in result
        assert "net_worth" in result
        assert "gaps" in result

    async def test_health_check_with_data(self, session):
        from pipeline.ai.chat_tools import _tool_get_data_health

        acct = await _seed_account(session)
        # Uncategorized transaction
        await _seed_transaction(session, acct.id, description="UNKNOWN CHARGE",
                                effective_category=None)

        result = json.loads(await _tool_get_data_health(session, {}))

        assert result["transactions"]["uncategorized"] >= 1
        assert result["gap_count"] >= 1


@pytest.mark.asyncio
class TestChatToolSaveAndGetUserContext:
    async def test_save_and_retrieve(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context, _tool_get_user_context

        save_result = json.loads(await _tool_save_user_context(session, {
            "category": "business",
            "key": "primary_business",
            "value": "Runs a car dealership specializing in imports",
        }))
        assert save_result["success"] is True
        assert save_result["remembered"] is True

        get_result = json.loads(await _tool_get_user_context(session, {"category": "business"}))
        assert get_result["count"] >= 1
        facts = get_result["facts"]
        assert any("car dealership" in f["value"] for f in facts)

    async def test_invalid_category(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context

        result = json.loads(await _tool_save_user_context(session, {
            "category": "invalid_category",
            "key": "test",
            "value": "test value",
        }))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# 10. REPORT GEN — INTERNAL_TRANSFER_CATEGORIES constant
# ═══════════════════════════════════════════════════════════════════════════

class TestInternalTransferCategories:
    def test_transfer_categories_are_excluded(self):
        from pipeline.ai.report_gen import INTERNAL_TRANSFER_CATEGORIES

        assert "Transfer" in INTERNAL_TRANSFER_CATEGORIES
        assert "Credit Card Payment" in INTERNAL_TRANSFER_CATEGORIES
        assert "Savings" in INTERNAL_TRANSFER_CATEGORIES
        # Should NOT contain actual expense categories
        assert "Groceries & Food" not in INTERNAL_TRANSFER_CATEGORIES


# ═══════════════════════════════════════════════════════════════════════════
# 11. UTILS — strip_json_fences, call_claude_with_retry
# ═══════════════════════════════════════════════════════════════════════════

class TestStripJsonFences:
    def test_strips_json_fences(self):
        from pipeline.utils import strip_json_fences

        raw = '```json\n{"key": "value"}\n```'
        assert strip_json_fences(raw) == '{"key": "value"}'

    def test_strips_plain_fences(self):
        from pipeline.utils import strip_json_fences

        raw = '```\n[1, 2, 3]\n```'
        assert strip_json_fences(raw) == '[1, 2, 3]'

    def test_no_fences_passthrough(self):
        from pipeline.utils import strip_json_fences

        raw = '{"key": "value"}'
        assert strip_json_fences(raw) == '{"key": "value"}'

    def test_whitespace_handling(self):
        from pipeline.utils import strip_json_fences

        raw = '  ```json\n  {"a": 1}  \n```  '
        result = strip_json_fences(raw)
        assert '"a"' in result


class TestCallClaudeWithRetry:
    @patch("time.sleep")
    def test_retries_on_rate_limit(self, mock_sleep):
        from pipeline.utils import call_claude_with_retry

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            Exception("rate limit exceeded"),
            _mock_claude_response("Success"),
        ]

        result = call_claude_with_retry(
            mock_client,
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": "test"}],
        )

        assert result.content[0].text == "Success"
        assert mock_client.messages.create.call_count == 2

    def test_raises_on_non_retryable_error(self):
        from pipeline.utils import call_claude_with_retry

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ValueError("Invalid argument")

        with pytest.raises(ValueError, match="Invalid argument"):
            call_claude_with_retry(
                mock_client,
                model="claude-sonnet-4-20250514",
                max_tokens=100,
                messages=[{"role": "user", "content": "test"}],
            )

    @patch("time.sleep")
    def test_exhausts_retries(self, mock_sleep):
        from pipeline.utils import call_claude_with_retry

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("rate limit exceeded")

        with pytest.raises(Exception, match="rate limit"):
            call_claude_with_retry(
                mock_client,
                max_retries=3,
                model="test",
                max_tokens=100,
                messages=[{"role": "user", "content": "test"}],
            )

        assert mock_client.messages.create.call_count == 3


# ═══════════════════════════════════════════════════════════════════════════
# 12. CATEGORIZER — categorize_transactions (mocked API)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCategorizeTransactions:
    @patch("pipeline.ai.categorizer.get_claude_client")
    @patch("pipeline.ai.categorizer.call_claude_with_retry")
    async def test_categorizes_batch(self, mock_call, mock_client, session):
        mock_client.return_value = MagicMock()

        acct = await _seed_account(session)
        tx = await _seed_transaction(
            session, acct.id, description="WHOLE FOODS MARKET", amount=-85.50,
            effective_category=None, is_excluded=False, is_manually_reviewed=False,
        )

        mock_call.return_value = _mock_claude_response(json.dumps([
            {
                "id": tx.id,
                "category": "Groceries & Food",
                "tax_category": "Personal Expense",
                "segment": "personal",
                "business_entity": None,
                "confidence": 0.95,
            }
        ]))

        from pipeline.ai.categorizer import categorize_transactions

        result = await categorize_transactions(session, year=2025, month=6)

        assert result["categorized"] >= 1
        assert result["errors"] == 0

        # Verify the transaction was updated
        updated = await session.execute(
            select(Transaction).where(Transaction.id == tx.id)
        )
        updated_tx = updated.scalar_one()
        assert updated_tx.effective_category == "Groceries & Food"
        assert updated_tx.ai_confidence == 0.95


# ═══════════════════════════════════════════════════════════════════════════
# 13. RULE GENERATOR — generate_rules_from_ai (mocked API)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGenerateRulesFromAI:
    @patch("pipeline.ai.rule_generator.get_claude_client")
    @patch("pipeline.ai.rule_generator.call_claude_with_retry")
    async def test_generates_ai_rules(self, mock_call, mock_client, session):
        mock_client.return_value = MagicMock()

        acct = await _seed_account(session)

        # Create 3 uncategorized transactions with same merchant
        for i in range(3):
            await _seed_transaction(
                session, acct.id, description=f"CHIPOTLE #{i}",
                amount=-12.0 - i, effective_category=None,
                is_excluded=False, is_manually_reviewed=False,
            )

        mock_call.return_value = _mock_claude_response(json.dumps([
            {
                "merchant": "chipotle",
                "category": "Restaurants & Dining",
                "tax_category": None,
                "segment": "personal",
                "business_entity": None,
                "confidence": 0.9,
            }
        ]))

        from pipeline.ai.rule_generator import generate_rules_from_ai

        proposals = await generate_rules_from_ai(session)

        assert len(proposals) >= 1
        assert proposals[0]["category"] == "Restaurants & Dining"
        assert proposals[0]["source"] == "ai"


# ═══════════════════════════════════════════════════════════════════════════
# 14. CHAT — Prompt cache invalidation
# ═══════════════════════════════════════════════════════════════════════════

class TestPromptCache:
    def test_invalidate_clears_cache(self):
        from pipeline.ai.chat import _prompt_cache, invalidate_prompt_cache

        _prompt_cache["system"] = ("cached", None, 0)
        invalidate_prompt_cache()
        assert "system" not in _prompt_cache


# ═══════════════════════════════════════════════════════════════════════════
# 15. CATEGORIZER — _build_household_context (no PII)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestBuildHouseholdContext:
    async def test_with_household(self, session):
        from pipeline.ai.categorizer import _build_household_context

        await _seed_household(session)
        ctx = await _build_household_context(session)

        assert "MFJ" in ctx
        assert "W-2 employee" in ctx
        # Should NOT contain actual names (categorizer strips them)
        assert "John Smith" not in ctx
        assert "Accenture" not in ctx

    async def test_without_household(self, session):
        from pipeline.ai.categorizer import _build_household_context

        ctx = await _build_household_context(session)
        assert "No household profile configured" in ctx
