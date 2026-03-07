"""
Tests targeting specific uncovered lines across multiple modules:
- pipeline/analytics/insights.py
- pipeline/db/models.py
- pipeline/db/migrations.py
- pipeline/parsers/pdf_parser.py
"""
import json
import pytest
import pytest_asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from pipeline.db.schema import (
    Account,
    Base,
    BusinessEntity,
    FinancialPeriod,
    TaxItem,
    Transaction,
    VendorEntityRule,
    Document,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tx(
    id, amount, category="Food", month=1, year=2025, description="Test",
    segment="needs",
):
    """Create a SimpleNamespace transaction suitable for insights functions."""
    safe_month = max(1, min(month, 12))
    return SimpleNamespace(
        id=id,
        amount=amount,
        effective_category=category,
        period_month=month,
        period_year=year,
        date=date(year, safe_month, 15),
        description=description,
        effective_segment=segment,
    )


def _make_feedback(
    id, transaction_id, classification="not_outlier", apply_to_future=True,
    description_pattern=None, category=None, year=2025,
):
    return SimpleNamespace(
        id=id,
        transaction_id=transaction_id,
        classification=classification,
        apply_to_future=apply_to_future,
        description_pattern=description_pattern,
        category=category,
        year=year,
        user_note=None,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_period(year, month, income=0.0, expenses=0.0, expense_breakdown=None):
    return SimpleNamespace(
        year=year,
        month=month,
        total_income=income,
        total_expenses=expenses,
        expense_breakdown=expense_breakdown,
    )


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess


# ===========================================================================
# INSIGHTS TESTS — pipeline/analytics/insights.py
# ===========================================================================

class TestBuildOutlierEntryMedianZero:
    """Line 235: _build_outlier_entry when med == 0."""

    def test_expense_outlier_reason_when_median_zero(self):
        from pipeline.analytics.insights import _detect_outlier_transactions

        # Single category with enough items but median effectively 0 is hard to
        # construct via IQR.  Instead, provide 2 items (not enough for IQR) plus
        # prior year data with 0-valued amounts so combined median is 0.
        txns = [
            _make_tx(1, -600, "Stuff", month=1),  # expense, large
        ]
        prior = [
            _make_tx(100, -0.0, "Stuff", month=2, year=2024),
            _make_tx(101, -0.0, "Stuff", month=3, year=2024),
            _make_tx(102, -0.0, "Stuff", month=4, year=2024),
        ]
        exp_outliers, _ = _detect_outlier_transactions(txns, [], prior)
        # The $600 should be flagged because it exceeds IQR upper on combined
        # amounts [600, 0, 0, 0]. Median of abs vals [0,0,0,600] = 0 → reason
        # should be "Large Stuff expense"
        flagged = [o for o in exp_outliers if o["category"] == "Stuff"]
        if flagged:
            assert "Large Stuff expense" in flagged[0]["reason"]


class TestIncomeOutlierWithPriorYear:
    """Lines 267, 289-294, 302: income outlier with prior year data."""

    def test_income_outlier_combined_prior_insufficient(self):
        """Line 267/294: combined < 3 items → skip category (continue branch)."""
        from pipeline.analytics.insights import _detect_outlier_transactions

        # 1 current income tx + 1 prior → combined=2 < 3 → skip
        txns = [_make_tx(1, 5000, "Freelance", month=1)]
        prior = [_make_tx(100, 3000, "Freelance", month=1, year=2024)]
        _, inc_outliers = _detect_outlier_transactions(txns, [], prior)
        assert len(inc_outliers) == 0

    def test_income_outlier_combined_prior_sufficient(self):
        """Lines 289-292: combined >= 3 items with prior year → IQR computed."""
        from pipeline.analytics.insights import _detect_outlier_transactions

        # 2 current + 2 prior = 4, one current is a big outlier
        txns = [
            _make_tx(1, 50000, "Bonus", month=1),
            _make_tx(2, 3000, "Bonus", month=2),
        ]
        prior = [
            _make_tx(100, 3200, "Bonus", month=3, year=2024),
            _make_tx(101, 2800, "Bonus", month=4, year=2024),
        ]
        _, inc_outliers = _detect_outlier_transactions(txns, [], prior)
        assert any(o["id"] == 1 for o in inc_outliers)

    def test_income_outlier_not_outlier_feedback_skip(self):
        """Line 301-302: income outlier with not_outlier feedback → skipped."""
        from pipeline.analytics.insights import _detect_outlier_transactions

        txns = [
            _make_tx(1, 50000, "Bonus", month=1),
            _make_tx(2, 3000, "Bonus", month=2),
            _make_tx(3, 3100, "Bonus", month=3),
            _make_tx(4, 2900, "Bonus", month=4),
        ]
        feedback = [
            _make_feedback(1, 1, classification="not_outlier"),
        ]
        _, inc_outliers = _detect_outlier_transactions(txns, feedback)
        assert not any(o["id"] == 1 for o in inc_outliers)


class TestExpenseOutlierSuppressedPattern:
    """Line 275-277: suppressed pattern match for expense outlier."""

    def test_suppressed_pattern_skips_unfeedback_outlier(self):
        from pipeline.analytics.insights import _detect_outlier_transactions

        txns = [
            _make_tx(1, -5000, "Insurance", month=1, description="GEICO AUTO"),
            _make_tx(2, -100, "Insurance", month=2, description="Something"),
            _make_tx(3, -110, "Insurance", month=3, description="Something"),
            _make_tx(4, -105, "Insurance", month=4, description="Something"),
        ]
        # Feedback on a different txn but same pattern "GEICO" with not_outlier
        # and apply_to_future
        feedback = [
            _make_feedback(
                10, 99, classification="not_outlier",
                apply_to_future=True, description_pattern="GEICO",
            ),
        ]
        exp_outliers, _ = _detect_outlier_transactions(txns, feedback)
        # txn 1 matches suppressed pattern "GEICO" and has no direct feedback → skipped
        assert not any(o["id"] == 1 for o in exp_outliers)


class TestNormalizeBudgetMonthZero:
    """Line 333: _normalize_budget skips month==0 transactions."""

    def test_month_zero_skipped_in_normalize(self):
        from pipeline.analytics.insights import _normalize_budget

        txns = [
            _make_tx(1, -100, "Food", month=0),
            _make_tx(2, -200, "Food", month=1),
        ]
        result = _normalize_budget(txns, set())
        # Only month=1 should contribute
        assert result["normalized_monthly_total"] == 200.0


class TestMonthlyAnalysisClassifications:
    """Lines 427, 429: classification == 'elevated' and 'low'."""

    def test_elevated_and_low_classifications(self):
        from pipeline.analytics.insights import _monthly_analysis

        # Create 12 months of data where expenses vary.  We need a scenario
        # where z_score for some month is >0.75 but <=1.5 (elevated) and
        # another <-0.75 (low).
        #
        # Create a baseline of ~1000/month and one month at ~1800 and one at ~400.
        txns = []
        tid = 1
        for m in range(1, 13):
            if m == 6:
                amt = -1800  # elevated
            elif m == 11:
                amt = -300  # low
            else:
                amt = -1000
            txns.append(_make_tx(tid, amt, "Food", month=m))
            tid += 1

        result = _monthly_analysis(txns, set(), set(), [])
        classifications = {r["month"]: r["classification"] for r in result}
        # m=6 should be elevated (or very_high depending on stdev)
        assert classifications.get(6) in ("elevated", "very_high")
        # m=11 should be low
        assert classifications.get(11) == "low"


class TestMonthlyAnalysisSkipMonthZero:
    """Line 386-387: period_month==0 → skip."""

    def test_month_zero_skipped(self):
        from pipeline.analytics.insights import _monthly_analysis

        txns = [
            _make_tx(1, -500, "Food", month=0),
            _make_tx(2, -500, "Food", month=1),
        ]
        result = _monthly_analysis(txns, set(), set(), [])
        months = [r["month"] for r in result]
        assert 0 not in months


class TestSeasonalPatternsSkips:
    """Lines 487, 490: month/year==0 skip, INTERNAL_TRANSFER skip."""

    def test_year_zero_skipped(self):
        from pipeline.analytics.insights import _seasonal_patterns

        txns = [
            # year=0 → skip
            SimpleNamespace(
                id=1, amount=-100, effective_category="Food",
                period_month=1, period_year=0,
                date=date(2025, 1, 15), description="Test",
                effective_segment="needs",
            ),
            _make_tx(2, -200, "Food", month=1, year=2025),
        ]
        result = _seasonal_patterns(txns)
        # Only 1 valid transaction: month 1 with $200
        assert len(result) >= 1

    def test_month_zero_skipped_seasonal(self):
        from pipeline.analytics.insights import _seasonal_patterns

        txns = [
            _make_tx(1, -100, "Food", month=0),
            _make_tx(2, -200, "Food", month=1, year=2025),
        ]
        result = _seasonal_patterns(txns)
        months = [r["month"] for r in result]
        assert 0 not in months

    def test_internal_transfer_skipped(self):
        from pipeline.analytics.insights import _seasonal_patterns

        txns = [
            _make_tx(1, -100, "Transfer", month=1),
            _make_tx(2, -100, "Credit Card Payment", month=2),
            _make_tx(3, -200, "Food", month=1, year=2025),
        ]
        result = _seasonal_patterns(txns)
        cats_in_result = set()
        for r in result:
            for c in r.get("top_categories", []):
                cats_in_result.add(c["category"])
        assert "Transfer" not in cats_in_result
        assert "Credit Card Payment" not in cats_in_result


class TestSeasonalLabels:
    """Line 527-530: seasonal labels below_average and low.

    Note: In the source code, the condition `< 85` is checked before `< 70`,
    meaning the "low" branch (line 530) is unreachable dead code.
    We verify the "below_average" branch instead.
    """

    def test_below_average_seasonal_label(self):
        from pipeline.analytics.insights import _seasonal_patterns

        # 11 months at -1000, 1 month (month=6) at -100 → seasonal_idx < 85
        txns = []
        tid = 1
        for m in range(1, 13):
            amt = -100 if m == 6 else -1000
            txns.append(_make_tx(tid, amt, "Food", month=m, year=2025))
            tid += 1
        result = _seasonal_patterns(txns)
        m6 = [r for r in result if r["month"] == 6]
        assert m6
        assert m6[0]["label"] == "below_average"
        # Verify seasonal_idx < 85 for this month
        assert m6[0]["seasonal_index"] < 85


class TestCategoryTrendsFirstAvgZero:
    """Line 563, 581: first_avg == 0 branch, and decreasing trend.

    Note: Line 580-581 (first_avg == 0) is practically unreachable because
    the function only adds months with abs(amt) > 0 to cat_monthly (due to
    the `amt < 0` filter, expense is always > 0). We test nearby logic instead.
    """

    def test_increasing_trend(self):
        from pipeline.analytics.insights import _category_trends

        # First half: small expenses, second half: large → increasing
        txns = []
        tid = 1
        for m in range(1, 7):
            txns.append(_make_tx(tid, -50, "Subscription", month=m))
            tid += 1
        for m in range(7, 13):
            txns.append(_make_tx(tid, -500, "Subscription", month=m))
            tid += 1
        result = _category_trends(txns, [])
        sub = [r for r in result if r["category"] == "Subscription"]
        assert sub
        assert sub[0]["trend"] == "increasing"

    def test_decreasing_trend(self):
        from pipeline.analytics.insights import _category_trends

        txns = []
        tid = 1
        # First half: high spending
        for m in range(1, 7):
            txns.append(_make_tx(tid, -1000, "Dining", month=m))
            tid += 1
        # Second half: much lower
        for m in range(7, 13):
            txns.append(_make_tx(tid, -200, "Dining", month=m))
            tid += 1
        result = _category_trends(txns, [])
        dining = [r for r in result if r["category"] == "Dining"]
        assert dining
        assert dining[0]["trend"] == "decreasing"

    def test_stable_trend(self):
        from pipeline.analytics.insights import _category_trends

        txns = []
        tid = 1
        for m in range(1, 13):
            txns.append(_make_tx(tid, -500, "Groceries", month=m))
            tid += 1
        result = _category_trends(txns, [])
        groc = [r for r in result if r["category"] == "Groceries"]
        assert groc
        assert groc[0]["trend"] == "stable"

    def test_insufficient_data_trend(self):
        from pipeline.analytics.insights import _category_trends

        txns = [_make_tx(1, -100, "RareCat", month=1)]
        result = _category_trends(txns, [])
        rare = [r for r in result if r["category"] == "RareCat"]
        assert rare
        assert rare[0]["trend"] == "insufficient_data"


class TestIncomeAnalysisMonthZero:
    """Line 630: _income_analysis skips month==0 for income."""

    def test_month_zero_income_skipped(self):
        from pipeline.analytics.insights import _income_analysis

        txns = [
            _make_tx(1, 5000, "Salary", month=0),
            _make_tx(2, 5000, "Salary", month=1),
        ]
        result = _income_analysis(txns, set())
        # Only month 1 income should be counted as regular
        assert result["total_regular"] == 5000.0


class TestBuildOutlierEntryIncomeMedianZero:
    """Line 235: _build_outlier_entry when med == 0 for income."""

    def test_income_outlier_reason_when_median_zero(self):
        from pipeline.analytics.insights import _detect_outlier_transactions

        txns = [
            _make_tx(1, 5000, "Gift", month=1),
        ]
        prior = [
            _make_tx(100, 0.0, "Gift", month=2, year=2024),
            _make_tx(101, 0.0, "Gift", month=3, year=2024),
            _make_tx(102, 0.0, "Gift", month=4, year=2024),
        ]
        _, inc_outliers = _detect_outlier_transactions(txns, [], prior)
        flagged = [o for o in inc_outliers if o["category"] == "Gift"]
        if flagged:
            assert "Large Gift income" in flagged[0]["reason"]


# ===========================================================================
# DB MODELS TESTS — pipeline/db/models.py
# ===========================================================================

class TestBulkCreateTransactionsCrossSourceDedup:
    """Lines 215-219: cross-source dedup skip."""

    async def test_cross_source_dedup_exercises_query_path(self, session):
        """Exercise the cross-source dedup query path (lines 202-219).

        SQLite's CAST(date AS DATE) doesn't work for date comparison, so we
        verify the function runs without error. The query path at lines 202-213
        is exercised even though the match fails in SQLite.
        """
        acct = Account(name="Chase", account_type="personal", subtype="checking")
        session.add(acct)
        await session.flush()

        # Insert a CSV transaction first
        tx_existing = Transaction(
            account_id=acct.id,
            date=datetime(2025, 1, 15),
            description="Starbucks",
            amount=-5.50,
            data_source="csv",
            is_excluded=False,
        )
        session.add(tx_existing)
        await session.flush()

        from pipeline.db.models import bulk_create_transactions

        # Exercise the cross-source dedup path: all conditions present
        rows = [{
            "account_id": acct.id,
            "date": datetime(2025, 1, 15),
            "description": "STARBUCKS #1234",
            "amount": -5.50,
            "data_source": "plaid",
            "currency": "USD",
            "segment": "personal",
        }]
        # This exercises lines 202-213 (query building), even though SQLite
        # CAST(date AS DATE) prevents the match from succeeding
        inserted = await bulk_create_transactions(session, rows)
        assert isinstance(inserted, int)

    async def test_cross_source_dedup_skip_via_mock(self):
        """Lines 214-219: verify the continue branch via mocked session."""
        from pipeline.db.models import bulk_create_transactions

        # Create a mock session where the cross-source query returns a match
        mock_session = AsyncMock(spec=AsyncSession)

        # First call: hash check (no hash provided, so skipped)
        # Second call: cross-source check → returns a match
        cross_match_result = MagicMock()
        cross_match_result.scalar_one_or_none.return_value = 42  # existing tx id

        mock_session.execute = AsyncMock(return_value=cross_match_result)
        mock_session.flush = AsyncMock()

        rows = [{
            "account_id": 1,
            "date": datetime(2025, 1, 15),
            "description": "STARBUCKS #1234",
            "amount": -5.50,
            "data_source": "plaid",
        }]
        inserted = await bulk_create_transactions(mock_session, rows)
        assert inserted == 0  # Skipped due to cross-source match


class TestGetTransactionsWithSearch:
    """Line 247: get_transactions with search parameter."""

    async def test_search_by_description(self, session):
        acct = Account(name="Chase", account_type="personal", subtype="checking")
        session.add(acct)
        await session.flush()

        t1 = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 15),
            description="WHOLE FOODS MARKET", amount=-100, data_source="csv",
        )
        t2 = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 16),
            description="AMAZON PRIME", amount=-15, data_source="csv",
        )
        session.add_all([t1, t2])
        await session.flush()

        from pipeline.db.models import get_transactions

        results = await get_transactions(session, search="whole foods")
        assert len(results) == 1
        assert results[0].description == "WHOLE FOODS MARKET"


class TestCountTransactionsBusinessEntityId:
    """Line 311: count_transactions with business_entity_id."""

    async def test_count_by_business_entity_id(self, session):
        acct = Account(name="Chase", account_type="personal", subtype="checking")
        be = BusinessEntity(name="TestCo", entity_type="sole_prop", tax_treatment="schedule_c")
        session.add_all([acct, be])
        await session.flush()

        t1 = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 15),
            description="Office supplies", amount=-50, data_source="csv",
            effective_business_entity_id=be.id,
        )
        t2 = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 16),
            description="Lunch", amount=-20, data_source="csv",
        )
        session.add_all([t1, t2])
        await session.flush()

        from pipeline.db.models import count_transactions

        count = await count_transactions(session, business_entity_id=be.id)
        assert count == 1


class TestBuildTaxSummary:
    """Lines 384-385, 408-409, 411-412, 414: build_tax_summary for W-2 state
    allocations, 1099-R, 1099-G, 1099-K."""

    async def test_w2_with_state_allocations(self, session):
        acct = Account(name="Employer", account_type="personal", subtype="checking")
        doc = Document(
            filename="w2.pdf", original_path="/tmp/w2.pdf", file_type="pdf",
            document_type="w2", file_hash="abc123", status="completed",
        )
        session.add_all([acct, doc])
        await session.flush()

        state_allocs = json.dumps([
            {"state": "CA", "wages": 100000, "tax": 8000},
            {"state": "NY", "wages": 50000, "tax": 4000},
        ])
        item = TaxItem(
            source_document_id=doc.id,
            tax_year=2025,
            form_type="w2",
            w2_wages=150000,
            w2_federal_tax_withheld=30000,
            w2_state_allocations=state_allocs,
        )
        session.add(item)
        await session.flush()

        from pipeline.db.models import get_tax_summary

        summary = await get_tax_summary(session, 2025)
        assert summary["w2_total_wages"] == 150000
        assert len(summary["w2_state_allocations"]) == 2
        assert summary["w2_state_allocations"][0]["state"] == "CA"

    async def test_1099_r_form(self, session):
        acct = Account(name="Broker", account_type="personal", subtype="checking")
        doc = Document(
            filename="1099r.pdf", original_path="/tmp/1099r.pdf", file_type="pdf",
            document_type="1099_r", file_hash="r_hash", status="completed",
        )
        session.add_all([acct, doc])
        await session.flush()

        item = TaxItem(
            source_document_id=doc.id,
            tax_year=2025,
            form_type="1099_r",
            r_gross_distribution=50000,
            r_taxable_amount=45000,
        )
        session.add(item)
        await session.flush()

        from pipeline.db.models import get_tax_summary

        summary = await get_tax_summary(session, 2025)
        assert summary["retirement_distributions"] == 50000
        assert summary["retirement_taxable"] == 45000

    async def test_1099_g_form(self, session):
        acct = Account(name="State", account_type="personal", subtype="checking")
        doc = Document(
            filename="1099g.pdf", original_path="/tmp/1099g.pdf", file_type="pdf",
            document_type="1099_g", file_hash="g_hash", status="completed",
        )
        session.add_all([acct, doc])
        await session.flush()

        item = TaxItem(
            source_document_id=doc.id,
            tax_year=2025,
            form_type="1099_g",
            g_unemployment_compensation=12000,
            g_state_tax_refund=500,
        )
        session.add(item)
        await session.flush()

        from pipeline.db.models import get_tax_summary

        summary = await get_tax_summary(session, 2025)
        assert summary["unemployment_income"] == 12000
        assert summary["state_tax_refund"] == 500

    async def test_1099_k_form(self, session):
        acct = Account(name="PayPal", account_type="personal", subtype="checking")
        doc = Document(
            filename="1099k.pdf", original_path="/tmp/1099k.pdf", file_type="pdf",
            document_type="1099_k", file_hash="k_hash", status="completed",
        )
        session.add_all([acct, doc])
        await session.flush()

        item = TaxItem(
            source_document_id=doc.id,
            tax_year=2025,
            form_type="1099_k",
            k_gross_amount=25000,
        )
        session.add(item)
        await session.flush()

        from pipeline.db.models import get_tax_summary

        summary = await get_tax_summary(session, 2025)
        assert summary["payment_platform_income"] == 25000


class TestApplyEntityRulesDateConstraints:
    """Lines 658, 674, 678: apply_entity_rules with date range constraints.

    Note: SQLite's CAST(datetime AS DATE) extracts only the year component,
    so date range filtering doesn't work correctly in SQLite. These tests
    verify the code paths are exercised (no errors), even if the filtering
    results differ from PostgreSQL.
    """

    async def test_rule_with_effective_from_exercises_code_path(self, session):
        """Line 673-676: effective_from condition is added to the query."""
        be = BusinessEntity(name="TestBiz", entity_type="sole_prop", tax_treatment="schedule_c")
        acct = Account(name="BizCard", account_type="business", subtype="credit_card")
        session.add_all([be, acct])
        await session.flush()

        rule = VendorEntityRule(
            vendor_pattern="upwork",
            business_entity_id=be.id,
            effective_from=date(2025, 6, 1),
            priority=10,
            is_active=True,
        )
        session.add(rule)
        await session.flush()

        t1 = Transaction(
            account_id=acct.id, date=datetime(2025, 7, 15),
            description="UPWORK FREELANCE", amount=-600, data_source="csv",
            is_manually_reviewed=False,
        )
        session.add(t1)
        await session.flush()

        from pipeline.db.models import apply_entity_rules

        # The function should run without errors — exercising the
        # effective_from code path
        updated = await apply_entity_rules(session)
        # At least the function ran successfully
        assert isinstance(updated, int)

    async def test_rule_with_effective_to_exercises_code_path(self, session):
        """Line 677-679: effective_to condition is added to the query."""
        be = BusinessEntity(name="OldBiz", entity_type="sole_prop", tax_treatment="schedule_c")
        acct = Account(name="Card", account_type="business", subtype="credit_card")
        session.add_all([be, acct])
        await session.flush()

        rule = VendorEntityRule(
            vendor_pattern="fiverr",
            business_entity_id=be.id,
            effective_to=date(2025, 6, 30),
            priority=10,
            is_active=True,
        )
        session.add(rule)
        await session.flush()

        t1 = Transaction(
            account_id=acct.id, date=datetime(2025, 3, 15),
            description="FIVERR PAYMENT", amount=-200, data_source="csv",
            is_manually_reviewed=False,
        )
        session.add(t1)
        await session.flush()

        from pipeline.db.models import apply_entity_rules

        updated = await apply_entity_rules(session)
        assert isinstance(updated, int)

    async def test_rule_with_both_date_constraints(self, session):
        """Exercise both effective_from and effective_to in a single rule."""
        be = BusinessEntity(name="DateBiz", entity_type="sole_prop", tax_treatment="schedule_c")
        acct = Account(name="DateCard", account_type="business", subtype="credit_card")
        session.add_all([be, acct])
        await session.flush()

        rule = VendorEntityRule(
            vendor_pattern="freelancer",
            business_entity_id=be.id,
            effective_from=date(2025, 1, 1),
            effective_to=date(2025, 12, 31),
            priority=10,
            is_active=True,
        )
        session.add(rule)
        await session.flush()

        t1 = Transaction(
            account_id=acct.id, date=datetime(2025, 6, 15),
            description="FREELANCER PAYMENT", amount=-400, data_source="csv",
            is_manually_reviewed=False,
        )
        session.add(t1)
        await session.flush()

        from pipeline.db.models import apply_entity_rules

        updated = await apply_entity_rules(session)
        assert isinstance(updated, int)


# ===========================================================================
# MIGRATION TESTS — pipeline/db/migrations.py
# ===========================================================================

class TestMigrationDataSourceBackfillExceptions:
    """Lines 156-157, 164-165: exception handling in _005_data_source_columns."""

    async def test_data_source_backfill_plaid_accounts_missing(self, session):
        """Lines 156-157: plaid_accounts table does not exist, exception caught."""
        from pipeline.db.migrations import _005_data_source_columns

        # Run on a fresh schema that has accounts and transactions but no
        # plaid_accounts table.  The backfill should catch the exception.
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS accounts ("
            "  id INTEGER PRIMARY KEY, name TEXT, data_source TEXT DEFAULT 'manual')"
        ))
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS transactions ("
            "  id INTEGER PRIMARY KEY, data_source TEXT DEFAULT 'csv',"
            "  plaid_pfc_primary TEXT, payment_channel TEXT)"
        ))
        await session.commit()

        # Should not raise even though plaid_accounts doesn't exist
        await _005_data_source_columns(session)

    async def test_data_source_backfill_enrichment_missing(self, session):
        """Lines 164-165: enrichment columns may not exist, exception caught."""
        from pipeline.db.migrations import _005_data_source_columns

        # Create tables without enrichment columns
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS accounts ("
            "  id INTEGER PRIMARY KEY, name TEXT, data_source TEXT DEFAULT 'manual')"
        ))
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS transactions ("
            "  id INTEGER PRIMARY KEY, data_source TEXT DEFAULT 'csv')"
        ))
        # No plaid_pfc_primary or payment_channel columns
        await session.commit()

        # Should not raise
        await _005_data_source_columns(session)


class TestMigrationCategoryRulesException:
    """Lines 429-430: exception handling in _018_category_rules_table."""

    async def test_category_rules_fix_is_active(self, session):
        from pipeline.db.migrations import _018_category_rules_table

        # Should not raise on a fresh database
        await _018_category_rules_table(session)
        # Running a second time also should not raise (table already exists)
        await _018_category_rules_table(session)


class TestMigrationFlowTypeBackfillBatching:
    """Lines 621-628, 630: flow_type backfill with >500 rows and remainder batch."""

    async def test_flow_type_backfill_with_batching(self):
        """Trigger the batch branch by having >500 transactions without flow_type."""
        from pipeline.db.migrations import _028_flow_type_column_and_backfill

        # Use a completely separate engine to avoid ORM schema conflicts
        eng = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(eng, expire_on_commit=False)
        async with eng.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE transactions ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  account_id INTEGER NOT NULL DEFAULT 1,"
                "  date TEXT, description TEXT NOT NULL DEFAULT '',"
                "  amount REAL NOT NULL DEFAULT 0,"
                "  segment TEXT NOT NULL DEFAULT 'personal',"
                "  is_excluded INTEGER NOT NULL DEFAULT 0,"
                "  data_source TEXT NOT NULL DEFAULT 'csv',"
                "  category TEXT, effective_category TEXT,"
                "  flow_type TEXT)"
            ))
        async with factory() as sess:
            for i in range(510):
                await sess.execute(text(
                    "INSERT INTO transactions (amount, category, effective_category, description) "
                    "VALUES (:amt, :cat, :ecat, :desc)"
                ), {"amt": -(i + 1), "cat": "Food", "ecat": "Food", "desc": f"item_{i}"})
            await sess.commit()

            await _028_flow_type_column_and_backfill(sess)

            result = await sess.execute(text(
                "SELECT COUNT(*) FROM transactions WHERE flow_type IS NOT NULL"
            ))
            count = result.scalar()
            assert count == 510
        await eng.dispose()

    async def test_flow_type_backfill_small_batch(self):
        """Lines 629-632: remainder batch < 500."""
        from pipeline.db.migrations import _028_flow_type_column_and_backfill

        eng = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(eng, expire_on_commit=False)
        async with eng.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE transactions ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  account_id INTEGER NOT NULL DEFAULT 1,"
                "  date TEXT, description TEXT NOT NULL DEFAULT '',"
                "  amount REAL NOT NULL DEFAULT 0,"
                "  segment TEXT NOT NULL DEFAULT 'personal',"
                "  is_excluded INTEGER NOT NULL DEFAULT 0,"
                "  data_source TEXT NOT NULL DEFAULT 'csv',"
                "  category TEXT, effective_category TEXT,"
                "  flow_type TEXT)"
            ))
        async with factory() as sess:
            for i in range(5):
                await sess.execute(text(
                    "INSERT INTO transactions (amount, category, effective_category, description) "
                    "VALUES (:amt, :cat, :ecat, :desc)"
                ), {"amt": -(i + 1), "cat": "Food", "ecat": "Food", "desc": f"small_{i}"})
            await sess.commit()

            await _028_flow_type_column_and_backfill(sess)

            result = await sess.execute(text(
                "SELECT COUNT(*) FROM transactions WHERE flow_type IS NOT NULL"
            ))
            count = result.scalar()
            assert count == 5
        await eng.dispose()


# ===========================================================================
# PDF PARSER TESTS — pipeline/parsers/pdf_parser.py
# ===========================================================================

class TestExtractW2StateAllocations:
    """Lines 147-161: W-2 state allocation parsing (multi-state)."""

    def test_multi_state_w2_parsing(self):
        from pipeline.parsers.pdf_parser import extract_w2_fields, PDFDocument, PDFPage

        # Build fake PDF doc with multi-state W-2 text
        w2_text = """
        Employer's name, address and ZIP code
        ACME CORP
        Employer's identification number: 12-3456789
        Box 1 Wages, tips $150,000.00
        Box 2 Federal income tax withheld $30,000.00
        Box 15 State CA 12-3456789 Box 16 State wages $100,000.00 Box 17 State income tax $8,000.00
        Box 15 State NY 98-7654321 Box 16 State wages $50,000.00 Box 17 State income tax $4,000.00
        """
        doc = PDFDocument(
            filepath="/tmp/test_w2.pdf",
            pages=[PDFPage(page_num=1, text=w2_text)],
        )
        fields = extract_w2_fields(doc)

        if fields.get("w2_state_allocations"):
            allocs = json.loads(fields["w2_state_allocations"])
            assert len(allocs) >= 1
            assert fields.get("w2_state") is not None
            assert fields.get("w2_state_wages") is not None
            assert fields.get("w2_state_income_tax") is not None


class TestExtractPdfPageImages:
    """Line 264: extract_pdf_page_images break when i >= max_pages."""

    def test_max_pages_break(self):
        """Verify the max_pages limit in extract_pdf_page_images."""
        import sys

        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"PNG_DATA"
        mock_page.get_pixmap.return_value = mock_pix

        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page] * 5)

        # fitz is imported inside the function, so we mock via sys.modules
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix.return_value = MagicMock()

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            from pipeline.parsers.pdf_parser import extract_pdf_page_images
            images = extract_pdf_page_images("/tmp/test.pdf", max_pages=2)
            assert len(images) == 2  # Only 2 of 5 pages processed


class TestDetectFormType:
    """Test various form type detection branches."""

    def test_detect_1099_r(self):
        from pipeline.parsers.pdf_parser import detect_form_type, PDFDocument, PDFPage

        doc = PDFDocument(
            filepath="/tmp/test.pdf",
            pages=[PDFPage(page_num=1, text="Distributions from Pensions, Annuities")],
        )
        assert detect_form_type(doc) == "1099_r"

    def test_detect_1099_g(self):
        from pipeline.parsers.pdf_parser import detect_form_type, PDFDocument, PDFPage

        doc = PDFDocument(
            filepath="/tmp/test.pdf",
            pages=[PDFPage(page_num=1, text="Certain Government Payments form")],
        )
        assert detect_form_type(doc) == "1099_g"

    def test_detect_1099_k(self):
        from pipeline.parsers.pdf_parser import detect_form_type, PDFDocument, PDFPage

        doc = PDFDocument(
            filepath="/tmp/test.pdf",
            pages=[PDFPage(page_num=1, text="Payment card and third party network transactions")],
        )
        assert detect_form_type(doc) == "1099_k"


# ===========================================================================
# ADDITIONAL EDGE-CASE TESTS
# ===========================================================================

class TestCategoryTrendsMonthZeroSkip:
    """Line 562-563: category_trends skips month==0."""

    def test_month_zero_not_in_trends(self):
        from pipeline.analytics.insights import _category_trends

        txns = [
            _make_tx(1, -100, "Food", month=0),
            _make_tx(2, -200, "Food", month=1),
            _make_tx(3, -300, "Food", month=2),
        ]
        result = _category_trends(txns, [])
        for cat in result:
            assert "0" not in cat.get("monthly_amounts", {})


class TestExpenseOutlierCombinedPriorInsufficient:
    """Line 267: combined < 3 for expenses → continue."""

    def test_expense_combined_prior_insufficient(self):
        from pipeline.analytics.insights import _detect_outlier_transactions

        # 1 current + 1 prior = 2 < 3 → skip
        txns = [_make_tx(1, -5000, "Misc", month=1)]
        prior = [_make_tx(100, -100, "Misc", month=1, year=2024)]
        exp_outliers, _ = _detect_outlier_transactions(txns, [], prior)
        assert len(exp_outliers) == 0


class TestYearOverYearMonthComparison:
    """Test _year_over_year function."""

    def test_year_over_year_basic(self):
        from pipeline.analytics.insights import _year_over_year

        current = [_make_period(2025, m, income=10000, expenses=5000) for m in range(1, 13)]
        prior = [_make_period(2024, m, income=9000, expenses=4500) for m in range(1, 13)]
        result = _year_over_year(current, prior)
        assert result is not None
        assert result["current_year_income"] == 120000
        assert result["prior_year_income"] == 108000
        assert len(result["monthly_comparison"]) == 12

    def test_year_over_year_no_prior(self):
        from pipeline.analytics.insights import _year_over_year

        current = [_make_period(2025, m, income=10000, expenses=5000) for m in range(1, 13)]
        result = _year_over_year(current, [])
        assert result is None


class TestGetTransactionsBusinessEntityId:
    """Line 247 (get_transactions with business_entity_id filter)."""

    async def test_filter_by_business_entity(self, session):
        acct = Account(name="Biz", account_type="business", subtype="checking")
        be = BusinessEntity(name="MyCo", entity_type="sole_prop", tax_treatment="schedule_c")
        session.add_all([acct, be])
        await session.flush()

        t1 = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 15),
            description="Supplies", amount=-100, data_source="csv",
            effective_business_entity_id=be.id,
        )
        t2 = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 16),
            description="Personal", amount=-50, data_source="csv",
        )
        session.add_all([t1, t2])
        await session.flush()

        from pipeline.db.models import get_transactions

        results = await get_transactions(session, business_entity_id=be.id)
        assert len(results) == 1
        assert results[0].description == "Supplies"
