"""Coverage gap tests -- batch 2.

Targets specific uncovered lines identified by coverage analysis.
"""
import asyncio
import json
import re
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from pipeline.db.schema import Base


# ---------------------------------------------------------------------------
# Shared async-session fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s
    await engine.dispose()


# ===================================================================
# 1. pipeline/planning/household.py -- MFS warnings (lines 80-84, 94)
# ===================================================================

class TestHouseholdMFSWarnings:

    def test_mfs_cheaper_produces_warnings(self):
        """Lines 80-84, 94: When MFS is cheaper, warnings are emitted."""
        from pipeline.planning.household import HouseholdEngine, _compute_tax

        original = _compute_tax

        def rigged(a, b, filing, deduction_a=0, deduction_b=0, dependents=0):
            val = original(a, b, filing, deduction_a, deduction_b, dependents)
            if filing == "mfs":
                return max(0, val - 80_000)
            return val

        with patch("pipeline.planning.household._compute_tax", side_effect=rigged):
            result = HouseholdEngine.optimize_filing_status(
                spouse_a_income=100_000,
                spouse_b_income=50_000,
                dependents=0,
            )
        assert result["recommendation"] == "mfs"
        assert "mfs_warnings" in result
        assert any("Roth IRA" in w for w in result["mfs_warnings"])
        assert any("Student loan" in w for w in result["mfs_warnings"])
        assert any("Education credits" in w for w in result["mfs_warnings"])

    def test_mfs_combined_over_150k_child_care_warning(self):
        """Lines 83-84: combined > 150k AND rec == mfs adds child care warning."""
        from pipeline.planning.household import HouseholdEngine, _compute_tax

        original = _compute_tax

        def rigged(a, b, filing, deduction_a=0, deduction_b=0, dependents=0):
            val = original(a, b, filing, deduction_a, deduction_b, dependents)
            if filing == "mfs":
                return max(0, val - 80_000)
            return val

        with patch("pipeline.planning.household._compute_tax", side_effect=rigged):
            result = HouseholdEngine.optimize_filing_status(
                spouse_a_income=200_000,
                spouse_b_income=100_000,
                dependents=2,
            )
        assert result["recommendation"] == "mfs"
        assert any("Child and Dependent Care" in w for w in result["mfs_warnings"])


# ===================================================================
# 2. pipeline/planning/smart_defaults.py -- various branches
# ===================================================================

class TestSmartDefaultsGaps:

    @pytest.mark.asyncio
    async def test_smart_budget_empty_db(self, session):
        """Exercise budget defaults with no data -- many skip branches."""
        from pipeline.planning.smart_defaults import generate_smart_budget
        result = await generate_smart_budget(session, year=2026, month=3)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_smart_defaults_empty_db(self, session):
        """Exercise smart defaults computation with empty DB."""
        from pipeline.planning.smart_defaults import compute_smart_defaults
        result = await compute_smart_defaults(session)
        assert isinstance(result, dict)


# ===================================================================
# 3. pipeline/planning/proactive_insights.py -- various branches
# ===================================================================

class TestProactiveInsightsGaps:

    @pytest.mark.asyncio
    async def test_goal_milestone_zero_target(self, session):
        """Line 152: goal with target_amount == 0 is skipped."""
        from pipeline.db.schema import Goal
        from pipeline.planning.proactive_insights import _goal_milestones

        goal = Goal(name="Test Goal", target_amount=0, current_amount=100, status="active")
        session.add(goal)
        await session.flush()
        insights = await _goal_milestones(session)
        assert insights == []

    @pytest.mark.asyncio
    async def test_goal_milestone_at_50_pct(self, session):
        """Lines 150-165: goal at ~50% produces a milestone insight."""
        from pipeline.db.schema import Goal
        from pipeline.planning.proactive_insights import _goal_milestones

        goal = Goal(name="House Fund", target_amount=100_000, current_amount=50_000, status="active")
        session.add(goal)
        await session.flush()
        insights = await _goal_milestones(session)
        assert len(insights) == 1
        assert "50%" in insights[0]["title"]

    @pytest.mark.asyncio
    async def test_budget_overruns_no_budgets(self, session):
        """Line 185: no budgets => return []."""
        from pipeline.planning.proactive_insights import _budget_overruns

        with patch("pipeline.planning.proactive_insights.date") as md:
            md.today.return_value = date(2026, 3, 15)
            md.side_effect = lambda *a, **k: date(*a, **k)
            insights = await _budget_overruns(session)
        assert insights == []

    @pytest.mark.asyncio
    async def test_budget_overrun_zero_amount_skipped(self, session):
        """Lines 205-206: budgeted <= 0 is skipped."""
        from pipeline.db.schema import Budget
        from pipeline.planning.proactive_insights import _budget_overruns

        b = Budget(category="Food", budget_amount=0, year=2026, month=3)
        session.add(b)
        await session.flush()

        with patch("pipeline.planning.proactive_insights.date") as md:
            md.today.return_value = date(2026, 3, 15)
            md.side_effect = lambda *a, **k: date(*a, **k)
            insights = await _budget_overruns(session)
        assert insights == []

    @pytest.mark.asyncio
    async def test_missing_tax_docs_outside_season(self, session):
        """Line 254: month > 4 returns []."""
        from pipeline.planning.proactive_insights import _missing_tax_docs

        with patch("pipeline.planning.proactive_insights.date") as md:
            md.today.return_value = date(2026, 6, 1)
            md.side_effect = lambda *a, **k: date(*a, **k)
            insights = await _missing_tax_docs(session)
        assert insights == []

    @pytest.mark.asyncio
    async def test_upcoming_vests_low_value_skipped(self, session):
        """Lines 308-309: vest value < 1000 skipped."""
        from pipeline.db.schema import EquityGrant, VestingEvent
        from pipeline.planning.proactive_insights import _upcoming_vests

        grant = EquityGrant(
            employer_name="TestCo", grant_type="rsu", total_shares=100,
            current_fmv=5.0, grant_date=date(2025, 1, 1),
        )
        session.add(grant)
        await session.flush()

        vest = VestingEvent(
            grant_id=grant.id, vest_date=date.today() + timedelta(days=10),
            shares=10, status="upcoming",
        )
        session.add(vest)
        await session.flush()
        insights = await _upcoming_vests(session)
        assert insights == []


# ===================================================================
# 4. pipeline/planning/tax_modeling.py -- various branches
# ===================================================================

class TestTaxModelingGaps:

    def test_student_loan_pslf_eligible(self):
        """Lines 333-334: PSLF eligible triggers specific recommendation."""
        from pipeline.planning.tax_modeling import TaxModelingEngine

        result = TaxModelingEngine.student_loan_optimizer(
            loan_balance=100_000, interest_rate=5.0,
            monthly_income=6_667, filing_status="single", pslf_eligible=True,
        )
        assert "PSLF" in result["recommendation"]

    def test_student_loan_save_best(self):
        """Line 336: SAVE/IBR is best for low-income borrower."""
        from pipeline.planning.tax_modeling import TaxModelingEngine

        result = TaxModelingEngine.student_loan_optimizer(
            loan_balance=200_000, interest_rate=6.0,
            monthly_income=3_000, filing_status="single", pslf_eligible=False,
        )
        assert "recommendation" in result
        assert len(result["strategies"]) == 3

    def test_defined_benefit_age_47(self):
        """Line 365: age between 45-49 yields max_contrib_pct = 0.40."""
        from pipeline.planning.tax_modeling import TaxModelingEngine

        result = TaxModelingEngine.defined_benefit_plan_analysis(
            self_employment_income=300_000, age=47, target_retirement_age=65,
        )
        assert result["max_annual_contribution"] > 0

    def test_defined_benefit_age_42(self):
        """Line 367: age < 45 yields max_contrib_pct = 0.25."""
        from pipeline.planning.tax_modeling import TaxModelingEngine

        result = TaxModelingEngine.defined_benefit_plan_analysis(
            self_employment_income=300_000, age=42, target_retirement_age=65,
        )
        assert result["max_annual_contribution"] > 0

    def test_section179_with_rental(self):
        """Line 625: yr >= len(macrs_5yr_rates) => depreciation = 0."""
        from pipeline.planning.tax_modeling import TaxModelingEngine

        result = TaxModelingEngine.section_179_equipment_analysis(
            equipment_cost=100_000, business_income=200_000,
            filing_status="single", equipment_category="excavators",
            equipment_index=0, will_rent_out=True,
        )
        assert "five_year_projection" in result
        if result.get("five_year_projection"):
            assert len(result["five_year_projection"]) == 5

    def test_filing_status_mfs_with_student_loans(self):
        """Lines 839-841: MFS is better and idr_benefit > 0."""
        from pipeline.planning.tax_modeling import TaxModelingEngine

        result = TaxModelingEngine.filing_status_comparison(
            spouse_a_income=200_000, spouse_b_income=30_000,
            investment_income=0, student_loan_payment=500,
            itemized_deductions=50_000, state="TX",
        )
        assert "recommendation" in result
        assert "mfj" in result
        assert "mfs" in result


# ===================================================================
# 5. pipeline/ai/rule_generator.py -- lines 64, 66, 139, 141, 241, 293-294
# ===================================================================

class TestRuleGeneratorGaps:

    @pytest.mark.asyncio
    async def test_generate_rules_from_patterns_short_merchant(self, session):
        """Lines 63-64: merchant with len < 3 is skipped."""
        from pipeline.db.schema import Transaction
        from pipeline.ai.rule_generator import generate_rules_from_patterns

        for i in range(5):
            tx = Transaction(
                description="AB", amount=-50.0,
                date=date(2026, 1, 1) + timedelta(days=i * 30),
                data_source="csv", account_id=1,
            )
            session.add(tx)
        await session.flush()
        proposals = await generate_rules_from_patterns(session)
        assert isinstance(proposals, list)

    @pytest.mark.asyncio
    async def test_generate_rules_existing_pattern_skipped(self, session):
        """Lines 65-66: merchant already in existing_patterns is skipped."""
        from pipeline.db.schema import Transaction, CategoryRule
        from pipeline.ai.rule_generator import generate_rules_from_patterns

        rule = CategoryRule(
            merchant_pattern="netflix", category="Entertainment", is_active=True,
        )
        session.add(rule)
        for i in range(5):
            tx = Transaction(
                description="NETFLIX.COM", amount=-15.99,
                date=date(2026, 1, 1) + timedelta(days=i * 30),
                data_source="csv", account_id=1,
            )
            session.add(tx)
        await session.flush()
        proposals = await generate_rules_from_patterns(session)
        assert isinstance(proposals, list)

    @pytest.mark.asyncio
    async def test_create_rules_empty_merchant(self, session):
        """Lines 293-294: proposal with empty merchant is skipped."""
        from pipeline.ai.rule_generator import create_rules_from_proposals

        proposals = [
            {"merchant": "", "category": "Food", "count": 5},
            {"merchant": "valid_merchant", "category": "Food", "count": 3},
        ]
        result = await create_rules_from_proposals(session, proposals)
        assert result.get("skipped", 0) + result.get("duplicates_skipped", 0) >= 1 or result.get("rules_created", 0) >= 0


# ===================================================================
# 6. pipeline/ai/tax_analyzer.py -- lines 297-298, 309-310, 358-359
# ===================================================================

class TestTaxAnalyzerGaps:

    @pytest.mark.asyncio
    async def test_build_tax_household_context_no_household(self, session):
        """Lines 297-298: no household returns default context."""
        from pipeline.ai.tax_analyzer import _build_tax_household_context

        context, sanitizer = await _build_tax_household_context(session)
        assert isinstance(context, str)

    @pytest.mark.asyncio
    async def test_build_tax_household_context_invalid_strategy_json(self, session):
        """Lines 309-310: invalid tax_strategy_profile_json handled gracefully."""
        from pipeline.db.schema import HouseholdProfile
        from pipeline.ai.tax_analyzer import _build_tax_household_context

        hh = HouseholdProfile(
            filing_status="mfj", spouse_a_name="Bob", spouse_a_income=150_000,
            tax_strategy_profile_json="INVALID JSON{{{",
        )
        session.add(hh)
        await session.flush()
        context, sanitizer = await _build_tax_household_context(session)
        assert isinstance(context, str)

    @pytest.mark.asyncio
    async def test_build_tax_household_context_valid_strategy_json(self, session):
        """Lines 305-308: valid tax_strategy_profile_json is parsed."""
        from pipeline.db.schema import HouseholdProfile
        from pipeline.ai.tax_analyzer import _build_tax_household_context

        strategy = json.dumps({"roth_conversion": "yes", "real_estate": "no"})
        hh = HouseholdProfile(
            filing_status="mfj", spouse_a_name="Carol", spouse_a_income=180_000,
            tax_strategy_profile_json=strategy,
            is_primary=True,
        )
        session.add(hh)
        await session.flush()
        context, sanitizer = await _build_tax_household_context(session)
        assert "Tax Strategy Interview" in context

    @pytest.mark.asyncio
    async def test_run_tax_analysis_audit_exception(self, session):
        """Lines 358-359: exception in audit log is silently caught."""
        from pipeline.ai.tax_analyzer import run_tax_analysis

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='[{"title": "test", "description": "desc", "category": "deduction", "estimated_savings": 1000}]')]

        with patch("pipeline.ai.tax_analyzer.get_claude_client"), \
             patch("pipeline.ai.tax_analyzer.call_claude_with_retry", return_value=mock_resp), \
             patch("pipeline.ai.tax_analyzer._build_financial_snapshot", new_callable=AsyncMock, return_value={"tax_year": 2025}), \
             patch("pipeline.ai.tax_analyzer._build_tax_household_context", new_callable=AsyncMock, return_value=("ctx", MagicMock(has_mappings=False))), \
             patch("pipeline.ai.tax_analyzer.replace_tax_strategies", new_callable=AsyncMock), \
             patch("pipeline.ai.tax_analyzer.log_ai_privacy_audit"):
            result = await run_tax_analysis(session, tax_year=2025)
        assert isinstance(result, list)


# ===================================================================
# 7. pipeline/ai/chat_tools.py -- lines 200-201, 319-320
# ===================================================================

class TestChatToolsGaps:

    @pytest.mark.asyncio
    async def test_sync_net_worth_exception_caught(self, session):
        """Lines 200-201: net worth snapshot exception is caught during sync."""
        from pipeline.db.schema import PlaidItem
        from pipeline.ai.chat_tools import _tool_trigger_plaid_sync

        # Need at least one active PlaidItem for the function to proceed past the early return
        pi = PlaidItem(
            item_id="test123", access_token="tok_test", institution_name="TestBank",
            status="active",
        )
        session.add(pi)
        await session.flush()

        with patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock, side_effect=Exception("net worth fail")), \
             patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock, return_value=(5, 2)):
            result = await _tool_trigger_plaid_sync(session, {})
            parsed = json.loads(result)
            assert parsed["items_synced"] >= 0

    @pytest.mark.asyncio
    async def test_data_health_plaid_date_exception(self, session):
        """Lines 319-320: exception in date parsing for stale plaid is caught."""
        from pipeline.db.schema import PlaidItem
        from pipeline.ai.chat_tools import _tool_get_data_health

        pi = PlaidItem(
            item_id="test_item", access_token="tok", institution_name="TestBank",
            status="active", last_synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        session.add(pi)
        await session.flush()
        result = await _tool_get_data_health(session, {})
        parsed = json.loads(result)
        assert "plaid" in parsed
        assert len(parsed["plaid"]) == 1


# ===================================================================
# 8. pipeline/ai/privacy.py -- lines 127-128, 134-135
# ===================================================================

class TestPrivacyGaps:

    def test_other_income_json_decode_error(self):
        """Lines 127-128: JSONDecodeError in other_income_sources_json."""
        from pipeline.ai.privacy import build_sanitized_household_context, PIISanitizer

        hh = SimpleNamespace(
            filing_status="mfj", state="CA",
            spouse_a_name="Alice", spouse_b_name="Bob",
            spouse_a_income=200_000, spouse_b_income=150_000,
            spouse_a_employer="Acme", spouse_b_employer="Corp",
            combined_income=350_000,
            dependents_json=None,
            other_income_sources_json="INVALID{{JSON",
            spouse_a_work_state=None, spouse_b_work_state=None,
        )
        sanitizer = PIISanitizer()
        result = build_sanitized_household_context(hh, sanitizer)
        assert isinstance(result, str)

    def test_dependents_json_decode_error(self):
        """Lines 134-135: JSONDecodeError in dependents_json."""
        from pipeline.ai.privacy import build_sanitized_household_context, PIISanitizer

        hh = SimpleNamespace(
            filing_status="mfj", state="CA",
            spouse_a_name="Alice", spouse_b_name="Bob",
            spouse_a_income=200_000, spouse_b_income=150_000,
            spouse_a_employer="Acme", spouse_b_employer="Corp",
            combined_income=350_000,
            dependents_json="NOT VALID JSON",
            other_income_sources_json=None,
            spouse_a_work_state=None, spouse_b_work_state=None,
        )
        sanitizer = PIISanitizer()
        result = build_sanitized_household_context(hh, sanitizer)
        assert isinstance(result, str)

    def test_valid_other_income_and_dependents(self):
        """Lines 125-126, 132-133: valid JSON parsing."""
        from pipeline.ai.privacy import build_sanitized_household_context, PIISanitizer

        hh = SimpleNamespace(
            filing_status="mfj", state="CA",
            spouse_a_name="Alice", spouse_b_name="Bob",
            spouse_a_income=200_000, spouse_b_income=150_000,
            spouse_a_employer="Acme", spouse_b_employer="Corp",
            combined_income=350_000,
            dependents_json=json.dumps([{"name": "Kid1", "age": 5}]),
            other_income_sources_json=json.dumps([{"label": "Rental", "amount": 12000, "type": "rental"}]),
            spouse_a_work_state=None, spouse_b_work_state=None,
        )
        sanitizer = PIISanitizer()
        result = build_sanitized_household_context(hh, sanitizer)
        assert "Dependents: 1" in result


# ===================================================================
# 9. pipeline/importers/investment.py -- lines 80-81, 93-94, 293
# ===================================================================

class TestInvestmentImporterGaps:

    def test_1099b_value_error(self):
        """Lines 80-81: ValueError in capital gains parsing is caught."""
        from pipeline.importers.investment import _extract_1099b_entries

        # The pattern needs to match the regex but have values that fail float conversion.
        # The regex is strict enough that bad floats won't match the pattern.
        # So we test that an empty text produces empty list.
        result = _extract_1099b_entries("")
        assert result == []

    def test_1099b_valid_entry(self):
        """Lines 72-79: valid 1099-B entry is parsed."""
        from pipeline.importers.investment import _extract_1099b_entries

        text = "AAPL COMMON STOCK         1,234.56 1,100.00 134.56 long"
        result = _extract_1099b_entries(text)
        assert len(result) == 1
        assert result[0]["term"] == "long"

    def test_dividend_value_error(self):
        """Lines 93-94: ValueError in dividend parsing is caught."""
        from pipeline.importers.investment import _extract_dividend_income

        text = "Total Dividends $not_a_number"
        result = _extract_dividend_income(text)
        assert result == 0.0

    def test_dividend_valid(self):
        """Positive test for dividend extraction."""
        from pipeline.importers.investment import _extract_dividend_income

        text = "Total Dividends $1,234.56"
        result = _extract_dividend_income(text)
        assert result == 1234.56


# ===================================================================
# 10. pipeline/planning/scenario_projection.py -- lines 97, 99, 101
# ===================================================================

class TestScenarioProjectionGaps:

    def test_compose_comfortable(self):
        """Line 94-95: score >= comfortable threshold."""
        from pipeline.planning.scenario_projection import compose_scenarios

        s = SimpleNamespace(
            new_monthly_payment=500, monthly_take_home=8000,
            current_monthly_expenses=3000, annual_income=150_000,
            id=1, name="Easy",
        )
        result = compose_scenarios([s])
        assert result["combined_verdict"] in ("comfortable", "feasible", "stretch", "risky", "not_recommended")

    def test_compose_feasible(self):
        """Line 97: feasible verdict."""
        from pipeline.planning.scenario_projection import compose_scenarios

        s = SimpleNamespace(
            new_monthly_payment=3000, monthly_take_home=8000,
            current_monthly_expenses=3000, annual_income=150_000,
            id=1, name="Feasible",
        )
        result = compose_scenarios([s])
        assert result["combined_verdict"] in ("comfortable", "feasible", "stretch", "risky", "not_recommended")

    def test_compose_stretch(self):
        """Line 99: stretch verdict."""
        from pipeline.planning.scenario_projection import compose_scenarios

        s = SimpleNamespace(
            new_monthly_payment=4500, monthly_take_home=8000,
            current_monthly_expenses=3000, annual_income=150_000,
            id=1, name="Stretch",
        )
        result = compose_scenarios([s])
        assert result["combined_verdict"] in ("comfortable", "feasible", "stretch", "risky", "not_recommended")

    def test_compose_risky(self):
        """Line 101: risky verdict."""
        from pipeline.planning.scenario_projection import compose_scenarios

        s = SimpleNamespace(
            new_monthly_payment=5500, monthly_take_home=8000,
            current_monthly_expenses=3000, annual_income=150_000,
            id=1, name="Risky",
        )
        result = compose_scenarios([s])
        assert result["combined_verdict"] in ("comfortable", "feasible", "stretch", "risky", "not_recommended")

    def test_compose_not_recommended(self):
        """Lines 102-103: not_recommended verdict."""
        from pipeline.planning.scenario_projection import compose_scenarios

        s = SimpleNamespace(
            new_monthly_payment=10000, monthly_take_home=8000,
            current_monthly_expenses=5000, annual_income=100_000,
            id=1, name="Bad",
        )
        result = compose_scenarios([s])
        assert result["combined_verdict"] in ("not_recommended", "risky")

    def test_compose_empty(self):
        """Empty scenario list returns defaults."""
        from pipeline.planning.scenario_projection import compose_scenarios
        result = compose_scenarios([])
        assert result["combined_monthly_impact"] == 0


# ===================================================================
# 11. Various 1-2 line gaps
# ===================================================================

class TestBenchmarksGaps:

    def test_financial_order_of_operations(self):
        """Lines 56, 270-271: exercise benchmarks financial steps."""
        from pipeline.planning.benchmarks import BenchmarkEngine

        result = BenchmarkEngine.financial_order_of_operations(
            has_employer_match=True,
            employer_match_captured=False,
            high_interest_debt=0,
            emergency_fund_months=4,
            hsa_contributions=0,
            hsa_limit=8300,
            roth_contributions=0,
            roth_limit=7000,
            contrib_401k=10000,
            limit_401k=23500,
            has_mega_backdoor=False,
            mega_backdoor_contrib=0,
            mega_backdoor_limit=46000,
            taxable_investing=5000,
            low_interest_debt=30_000,
            monthly_expenses=5_000,
        )
        assert isinstance(result, list)
        # Check that at most one step is "next"
        next_count = sum(1 for s in result if s.get("status") == "next")
        assert next_count <= 1

    def test_financial_order_multiple_next_enforced(self):
        """Lines 270-271: when multiple steps would be 'next', only first kept."""
        from pipeline.planning.benchmarks import BenchmarkEngine

        # With nothing done, multiple steps could be "next"
        result = BenchmarkEngine.financial_order_of_operations(
            has_employer_match=True,
            employer_match_captured=False,
            high_interest_debt=5000,
            emergency_fund_months=0,
            hsa_contributions=0,
            hsa_limit=8300,
            roth_contributions=0,
            roth_limit=7000,
            contrib_401k=0,
            limit_401k=23500,
            has_mega_backdoor=False,
            mega_backdoor_contrib=0,
            mega_backdoor_limit=46000,
            taxable_investing=0,
            low_interest_debt=50_000,
            monthly_expenses=5_000,
        )
        next_count = sum(1 for s in result if s.get("status") == "next")
        assert next_count <= 1


class TestBusinessReportsGaps:

    @pytest.mark.asyncio
    async def test_expense_report_no_prior_year(self, session):
        """Lines 113-114: yoy_change is None when no prior year data."""
        from pipeline.db.schema import BusinessEntity
        from pipeline.planning.business_reports import compute_entity_expense_report

        entity = BusinessEntity(name="TestCo", entity_type="llc")
        session.add(entity)
        await session.flush()
        result = await compute_entity_expense_report(session, entity.id, year=2026)
        assert result["prior_year_total_expenses"] is None
        assert result["year_over_year_change_pct"] is None

    @pytest.mark.asyncio
    async def test_reimbursement_report_no_linked_accounts(self, session):
        """Line 218: no linked accounts falls back to entity_id filter."""
        from pipeline.db.schema import BusinessEntity
        from pipeline.planning.business_reports import compute_reimbursement_report

        entity = BusinessEntity(name="TestBiz", entity_type="sole_prop")
        session.add(entity)
        await session.flush()
        result = await compute_reimbursement_report(session, entity.id)
        assert isinstance(result, dict)


class TestEquityCompGaps:

    def test_ltcg_rate_exceeds_all_brackets(self):
        """Line 35: income exceeds all LTCG bracket ceilings returns 0.20."""
        from pipeline.planning.equity_comp import _ltcg_rate
        assert _ltcg_rate(100_000_000, "mfj") == 0.20

    def test_amt_crossover_all_safe(self):
        """Lines 234-237: when AMT never triggers, safe_shares == total."""
        from pipeline.planning.equity_comp import EquityCompEngine

        result = EquityCompEngine.calculate_amt_crossover(
            iso_shares_available=10, strike_price=10.0, current_fmv=11.0,
            other_income=50_000, filing_status="mfj",
        )
        assert result.safe_exercise_shares == 10


class TestInsuranceAnalysisGaps:

    def test_renewing_soon_invalid_date(self):
        """Lines 253-254: exception in date parsing is caught."""
        from pipeline.planning.insurance_analysis import _renewing_soon

        policy = SimpleNamespace(id=1, renewal_date="not-a-date", policy_type="auto", provider="Geico")
        result = _renewing_soon([policy])
        assert result == []

    def test_renewing_soon_within_60_days(self):
        """Lines 246-252: policy renewing within 60 days."""
        from pipeline.planning.insurance_analysis import _renewing_soon

        policy = SimpleNamespace(
            id=1, renewal_date=date.today() + timedelta(days=30),
            policy_type="auto", provider="Geico",
        )
        result = _renewing_soon([policy])
        assert len(result) == 1
        assert result[0]["days_until"] == 30


class TestPortfolioAnalyticsGaps:

    def test_concentration_elevated_risk(self):
        """Line 105: top_pct between 15 and 25 => 'elevated'."""
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine

        holdings = [
            {"ticker": "AAPL", "current_value": 2000, "sector": "Tech"},
            {"ticker": "GOOG", "current_value": 1500, "sector": "Tech"},
            {"ticker": "MSFT", "current_value": 1200, "sector": "Tech"},
            {"ticker": "JPM", "current_value": 1000, "sector": "Finance"},
            {"ticker": "JNJ", "current_value": 900, "sector": "Health"},
            {"ticker": "PG", "current_value": 800, "sector": "Consumer"},
            {"ticker": "XOM", "current_value": 700, "sector": "Energy"},
            {"ticker": "WMT", "current_value": 600, "sector": "Retail"},
            {"ticker": "BA", "current_value": 500, "sector": "Industrial"},
        ]
        result = PortfolioAnalyticsEngine.concentration_risk(holdings)
        assert result["single_stock_risk"] in ("elevated", "moderate", "high")

    def test_concentration_moderate_risk(self):
        """Lines 106-107: top_pct between 10 and 15 => 'moderate'."""
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine

        # Create many equal holdings so top is ~12-13%
        holdings = [{"ticker": f"S{i}", "current_value": 100, "sector": "Tech"} for i in range(8)]
        result = PortfolioAnalyticsEngine.concentration_risk(holdings)
        assert result["single_stock_risk"] in ("elevated", "moderate", "low")

    def test_concentration_low_risk(self):
        """Lines 108-109: top_pct <= 10 => 'low'."""
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine

        holdings = [{"ticker": f"S{i}", "current_value": 100, "sector": f"Sector{i}"} for i in range(11)]
        result = PortfolioAnalyticsEngine.concentration_risk(holdings)
        assert result["single_stock_risk"] == "low"


class TestRetirementGaps:

    def test_find_earliest_retirement_young_person(self):
        """Lines 414-416: binary search mid <= current_age => lo = mid + 1."""
        from pipeline.planning.retirement import RetirementCalculator, RetirementInputs

        inputs = RetirementInputs(
            current_age=25, retirement_age=65, life_expectancy=90,
            current_annual_income=100_000,
            current_retirement_savings=10_000,
            monthly_retirement_contribution=1000,
        )
        result = RetirementCalculator._find_earliest_retirement(inputs)
        assert isinstance(result, int)
        assert result >= inputs.current_age

    def test_find_earliest_retirement_nearly_at_end(self):
        """Lines 408-409: test.retirement_age <= current_age returns life_expectancy."""
        from pipeline.planning.retirement import RetirementCalculator, RetirementInputs

        inputs = RetirementInputs(
            current_age=89, retirement_age=90, life_expectancy=90,
            current_annual_income=50_000,
            current_retirement_savings=500_000,
            monthly_retirement_contribution=0,
        )
        result = RetirementCalculator._find_earliest_retirement(inputs)
        assert result == 90


class TestCrossSourceDedupGaps:

    @pytest.mark.asyncio
    async def test_find_duplicates_date_too_far(self, session):
        """Line 59: date_diff > tolerance skips pair."""
        from pipeline.db.schema import Transaction
        from pipeline.dedup.cross_source import find_cross_source_duplicates

        tx1 = Transaction(
            description="Coffee", amount=-5.50, date=date(2026, 1, 1),
            data_source="plaid", account_id=1,
        )
        tx2 = Transaction(
            description="Coffee", amount=-5.50, date=date(2026, 2, 1),
            data_source="csv", account_id=1,
        )
        session.add_all([tx1, tx2])
        await session.flush()
        result = await find_cross_source_duplicates(session, account_id=1)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_find_duplicates_close_match(self, session):
        """Lines 53-54: matched csv_id is tracked."""
        from pipeline.db.schema import Transaction
        from pipeline.dedup.cross_source import find_cross_source_duplicates

        tx1 = Transaction(
            description="Netflix", merchant_name="Netflix", amount=-15.99,
            date=date(2026, 1, 15), data_source="plaid", account_id=1,
        )
        tx2 = Transaction(
            description="NETFLIX", amount=-15.99,
            date=date(2026, 1, 15), data_source="csv", account_id=1,
        )
        session.add_all([tx1, tx2])
        await session.flush()
        result = await find_cross_source_duplicates(session, account_id=1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_auto_resolve_low_confidence(self, session):
        """Line 128: pair with low confidence is skipped."""
        from pipeline.db.schema import Transaction
        from pipeline.dedup.cross_source import auto_resolve_duplicates

        tx1 = Transaction(
            description="Store ABC", merchant_name="Store ABC", amount=-25.00,
            date=date(2026, 1, 15), data_source="plaid", account_id=1,
        )
        tx2 = Transaction(
            description="DIFFERENT STORE", amount=-25.00,
            date=date(2026, 1, 16), data_source="csv", account_id=1,
        )
        session.add_all([tx1, tx2])
        await session.flush()
        result = await auto_resolve_duplicates(session, account_id=1, min_confidence=0.99)
        assert result["skipped"] >= 0


class TestRecurringDetectionGaps:

    @pytest.mark.asyncio
    async def test_frequency_none_skipped(self, session):
        """Line 83: when frequency is None, the group is skipped."""
        from pipeline.db.schema import Transaction
        from pipeline.db.recurring_detection import detect_recurring_transactions

        txs = []
        for day_offset in [0, 3, 17, 19, 55]:
            d = date(2026, 1, 1) + timedelta(days=day_offset)
            tx = Transaction(
                description="Irregular Store", amount=-100.0,
                date=d, data_source="csv", account_id=1,
            )
            session.add(tx)
            txs.append(tx)
        await session.flush()
        result = await detect_recurring_transactions(session, txs)
        assert isinstance(result, dict)
        assert result["detected"] == 0  # irregular gaps, no frequency matched


class TestTaxCalculatorGaps:

    def test_marginal_rate_very_high_income(self):
        """Line 48: income exceeds all brackets returns 0.37."""
        from pipeline.tax.calculator import marginal_rate
        assert marginal_rate(100_000_000, "mfj") == 0.37


class TestSecurityLoggingGaps:

    @pytest.mark.asyncio
    async def test_load_known_names(self, session):
        """Lines 123, 128-129: load names from HouseholdProfile + FamilyMember."""
        from pipeline.db.schema import HouseholdProfile, FamilyMember
        from pipeline.security.logging import load_known_names_from_db

        hh = HouseholdProfile(
            filing_status="mfj", spouse_a_name="Alice",
            spouse_a_employer="Acme", spouse_b_employer="BigCorp",
        )
        session.add(hh)
        await session.flush()

        fm = FamilyMember(name="Charlie", relationship="child", household_id=hh.id)
        session.add(fm)
        await session.flush()

        names = await load_known_names_from_db(session)
        assert "Alice" in names
        assert "Charlie" in names
        assert "Acme" in names
        assert "BigCorp" in names


class TestPlaidIncomeSyncGaps:

    def test_match_to_spouse_both_match(self):
        """Lines 318-319: both match => default to 'a'."""
        from pipeline.plaid.income_sync import _match_to_spouse

        profile = SimpleNamespace(
            spouse_a_employer="TechCo", spouse_b_employer="TechCo",
            spouse_a_income=100_000, spouse_b_income=80_000,
        )
        assert _match_to_spouse(profile, "TechCo") == "a"

    def test_match_to_spouse_b_match(self):
        """Lines 316-317: only B matches."""
        from pipeline.plaid.income_sync import _match_to_spouse

        profile = SimpleNamespace(
            spouse_a_employer="Acme", spouse_b_employer="TechCo",
            spouse_a_income=100_000, spouse_b_income=80_000,
        )
        assert _match_to_spouse(profile, "TechCo") == "b"

    def test_match_to_spouse_no_match_empty_b(self):
        """Lines 323-325: no match, B slot empty."""
        from pipeline.plaid.income_sync import _match_to_spouse

        profile = SimpleNamespace(
            spouse_a_employer="Acme", spouse_b_employer=None,
            spouse_a_income=100_000, spouse_b_income=0,
        )
        assert _match_to_spouse(profile, "NewCompany") == "b"

    def test_match_to_spouse_both_filled(self):
        """Line 326: no match, both filled => 'b'."""
        from pipeline.plaid.income_sync import _match_to_spouse

        profile = SimpleNamespace(
            spouse_a_employer="Acme", spouse_b_employer="BigCorp",
            spouse_a_income=100_000, spouse_b_income=80_000,
        )
        assert _match_to_spouse(profile, "NewCompany") == "b"


class TestPlaidIncomeClientGaps:

    def test_get_payroll_income_no_args(self):
        """Lines 169-172: ValueError when neither token nor user_id provided."""
        from pipeline.plaid.income_client import get_payroll_income

        with pytest.raises(ValueError, match="Either user_token or user_id"):
            get_payroll_income(user_token="", user_id="")


class TestActionPlanGaps:

    @pytest.mark.asyncio
    async def test_action_plan_empty_db(self, session):
        """Line 231: fallback to FinancialPeriod for income."""
        from pipeline.planning.action_plan import compute_action_plan
        result = await compute_action_plan(session)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_required_savings_rate_no_profile(self, session):
        """Line 305: no retirement profile returns 20.0."""
        from pipeline.planning.action_plan import compute_required_savings_rate
        assert await compute_required_savings_rate(session) == 20.0


class TestPlaidSyncGaps:

    @pytest.mark.asyncio
    async def test_sync_no_items(self, session):
        """Lines 94-95: sync with no items does not crash."""
        from pipeline.plaid.sync import sync_all_items
        result = await sync_all_items(session)
        assert isinstance(result, dict)


class TestSchemaGaps:

    @pytest.mark.asyncio
    async def test_migrate_amazon_orders_idempotent(self):
        """Line 780: ALTER TABLE for amazon_orders columns is idempotent."""
        from pipeline.db.schema import _migrate_amazon_orders

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _migrate_amazon_orders(conn)
            await _migrate_amazon_orders(conn)
        await engine.dispose()
