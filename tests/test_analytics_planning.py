"""Comprehensive tests for analytics/insights and planning modules.

Covers:
    - pipeline/analytics/insights.py   (financial insights engine)
    - pipeline/planning/action_plan.py  (action plan generator)
    - pipeline/planning/proactive_insights.py (proactive financial insights)
    - pipeline/planning/business_reports.py  (business financial reports)
    - pipeline/planning/retirement_budget.py (retirement budget calculator)
    - pipeline/planning/milestones.py  (financial milestone tracker)
    - pipeline/planning/portfolio_analytics.py (portfolio analytics engine)

Uses realistic financial data for a HENRY household earning $350k+ with
investments, retirement accounts, debt, and business entities.
"""
import json
import math
import pytest
import pytest_asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    Base,
    BenefitPackage,
    Budget,
    BusinessEntity,
    EquityGrant,
    FinancialPeriod,
    Goal,
    HouseholdProfile,
    InsurancePolicy,
    ManualAsset,
    NetWorthSnapshot,
    OutlierFeedback,
    PlaidAccount,
    PlaidItem,
    RetirementProfile,
    TaxItem,
    Transaction,
    VestingEvent,
    Document,
    FamilyMember,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures: Realistic HENRY household data
# ═══════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def henry_household(session: AsyncSession):
    """Create a realistic HENRY household: dual income ~$380k, investments,
    retirement accounts, a business entity, and 12 months of transactions."""

    # --- Account setup ---
    checking = Account(
        name="Chase Checking",
        account_type="personal",
        subtype="bank",
        institution="Chase",
        is_active=True,
        data_source="plaid",
    )
    credit_card = Account(
        name="Amex Gold",
        account_type="personal",
        subtype="credit_card",
        institution="American Express",
        is_active=True,
        data_source="csv",
    )
    biz_card = Account(
        name="Ink Business Preferred",
        account_type="business",
        subtype="credit_card",
        institution="Chase",
        is_active=True,
        data_source="csv",
    )
    session.add_all([checking, credit_card, biz_card])
    await session.flush()

    # --- Business entity ---
    biz = BusinessEntity(
        name="Aron Consulting LLC",
        entity_type="llc",
        tax_treatment="schedule_c",
        is_active=True,
    )
    session.add(biz)
    await session.flush()

    # Link biz_card to entity
    biz_card.default_business_entity_id = biz.id
    await session.flush()

    # --- Household profile ---
    hh = HouseholdProfile(
        name="Aron Household",
        filing_status="mfj",
        state="CA",
        spouse_a_name="Mike",
        spouse_a_income=220000.0,
        spouse_a_employer="TechCorp",
        spouse_b_name="Sarah",
        spouse_b_income=160000.0,
        spouse_b_employer="BigBank",
        combined_income=380000.0,
        is_primary=True,
    )
    session.add(hh)
    await session.flush()

    # --- Benefits ---
    bp_a = BenefitPackage(
        household_id=hh.id,
        spouse="A",
        employer_name="TechCorp",
        has_401k=True,
        employer_match_pct=4.0,
        employer_match_limit_pct=6.0,
        annual_401k_contribution=18000.0,
        has_hsa=True,
        hsa_employer_contribution=1000.0,
        has_mega_backdoor=True,
        mega_backdoor_limit=46000.0,
    )
    bp_b = BenefitPackage(
        household_id=hh.id,
        spouse="B",
        employer_name="BigBank",
        has_401k=True,
        employer_match_pct=3.0,
        employer_match_limit_pct=6.0,
        annual_401k_contribution=15000.0,
        has_hsa=False,
    )
    session.add_all([bp_a, bp_b])
    await session.flush()

    # --- Retirement profile ---
    ret = RetirementProfile(
        name="Primary Plan",
        current_age=35,
        retirement_age=60,
        life_expectancy=90,
        current_annual_income=380000.0,
        monthly_retirement_contribution=2750.0,
        employer_match_pct=4.0,
        employer_match_limit_pct=6.0,
        current_retirement_savings=250000.0,
        current_other_investments=150000.0,
        is_primary=True,
    )
    session.add(ret)
    await session.flush()

    # --- Plaid item + accounts for action plan queries ---
    plaid_item = PlaidItem(
        item_id="test_item_001",
        access_token="encrypted_token_placeholder",
        institution_id="ins_1",
        institution_name="Chase",
        status="active",
    )
    session.add(plaid_item)
    await session.flush()

    plaid_checking = PlaidAccount(
        plaid_item_id=plaid_item.id,
        plaid_account_id="pa_checking_001",
        name="Chase Checking",
        type="depository",
        subtype="checking",
        current_balance=45000.0,
    )
    plaid_savings = PlaidAccount(
        plaid_item_id=plaid_item.id,
        plaid_account_id="pa_savings_001",
        name="Chase Savings",
        type="depository",
        subtype="savings",
        current_balance=30000.0,
    )
    plaid_cc = PlaidAccount(
        plaid_item_id=plaid_item.id,
        plaid_account_id="pa_cc_001",
        name="Amex Gold",
        type="credit",
        subtype="credit_card",
        current_balance=-4500.0,  # owed
    )
    plaid_invest = PlaidAccount(
        plaid_item_id=plaid_item.id,
        plaid_account_id="pa_invest_001",
        name="Schwab Brokerage",
        type="investment",
        subtype="brokerage",
        current_balance=180000.0,
    )
    session.add_all([plaid_checking, plaid_savings, plaid_cc, plaid_invest])
    await session.flush()

    # --- Manual assets ---
    roth_ira = ManualAsset(
        name="Roth IRA - Fidelity",
        asset_type="brokerage",
        is_liability=False,
        current_value=85000.0,
        institution="Fidelity",
        is_active=True,
        tax_treatment="roth_ira",
        is_retirement_account=True,
        employee_contribution_ytd=7000.0,
    )
    student_loan = ManualAsset(
        name="Student Loans",
        asset_type="student_loan",
        is_liability=True,
        current_value=28000.0,
        is_active=True,
    )
    session.add_all([roth_ira, student_loan])
    await session.flush()

    # --- Net Worth Snapshot ---
    nw = NetWorthSnapshot(
        snapshot_date=datetime(2025, 12, 1, tzinfo=timezone.utc),
        year=2025,
        month=12,
        total_assets=600000.0,
        total_liabilities=32500.0,
        net_worth=567500.0,
        checking_savings=75000.0,
        investment_value=180000.0,
    )
    session.add(nw)
    await session.flush()

    # --- 12 months of transactions for 2025 ---
    _MONTHLY_EXPENSES = {
        "Groceries": -1200,
        "Restaurants & Dining": -600,
        "Gas & Fuel": -250,
        "Mortgage & Rent": -3200,
        "Medical": -150,
        "Fitness": -120,
        "Insurance": -450,
        "Clothing & Apparel": -200,
        "Entertainment & Recreation": -300,
        "Childcare & Education": -1500,
        "Coffee & Beverages": -80,
    }
    _MONTHLY_INCOME = {
        "Paycheck": 14500,
        "Paycheck B": 10500,
    }

    # Outlier transactions — one big medical bill, one large purchase
    outlier_txns = [
        Transaction(
            account_id=credit_card.id,
            date=datetime(2025, 3, 15, tzinfo=timezone.utc),
            description="Major Surgery Copay",
            amount=-5500.0,
            effective_category="Medical",
            effective_segment="personal",
            period_month=3,
            period_year=2025,
            is_excluded=False,
        ),
        Transaction(
            account_id=credit_card.id,
            date=datetime(2025, 7, 20, tzinfo=timezone.utc),
            description="New Furniture Purchase",
            amount=-4200.0,
            effective_category="Home & Garden",
            effective_segment="personal",
            period_month=7,
            period_year=2025,
            is_excluded=False,
        ),
        Transaction(
            account_id=checking.id,
            date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            description="Annual Performance Bonus",
            amount=25000.0,
            effective_category="Bonus",
            effective_segment="personal",
            period_month=6,
            period_year=2025,
            is_excluded=False,
        ),
    ]
    session.add_all(outlier_txns)

    all_txns = []
    for month in range(1, 13):
        for cat, amt in _MONTHLY_EXPENSES.items():
            # Add slight variation per month
            variation = (month % 3 - 1) * 20
            tx = Transaction(
                account_id=credit_card.id,
                date=datetime(2025, month, 15, tzinfo=timezone.utc),
                description=f"{cat} - Month {month}",
                amount=float(amt + variation),
                effective_category=cat,
                effective_segment="personal",
                period_month=month,
                period_year=2025,
                is_excluded=False,
            )
            all_txns.append(tx)

        for cat, amt in _MONTHLY_INCOME.items():
            tx = Transaction(
                account_id=checking.id,
                date=datetime(2025, month, 1, tzinfo=timezone.utc),
                description=f"{cat} - Month {month}",
                amount=float(amt),
                effective_category=cat,
                effective_segment="personal",
                period_month=month,
                period_year=2025,
                is_excluded=False,
            )
            all_txns.append(tx)

    # Business transactions
    for month in range(1, 13):
        tx = Transaction(
            account_id=biz_card.id,
            date=datetime(2025, month, 10, tzinfo=timezone.utc),
            description=f"Client Lunch - Month {month}",
            amount=-180.0,
            effective_category="Meals & Entertainment",
            effective_segment="business",
            effective_business_entity_id=biz.id,
            period_month=month,
            period_year=2025,
            is_excluded=False,
        )
        all_txns.append(tx)
        tx2 = Transaction(
            account_id=biz_card.id,
            date=datetime(2025, month, 20, tzinfo=timezone.utc),
            description=f"Software Subscription - Month {month}",
            amount=-250.0,
            effective_category="Software & SaaS",
            effective_segment="business",
            effective_business_entity_id=biz.id,
            period_month=month,
            period_year=2025,
            is_excluded=False,
        )
        all_txns.append(tx2)

    session.add_all(all_txns)
    await session.flush()

    # --- Financial periods for 2025 ---
    expense_categories = json.dumps({
        "Groceries": 1200,
        "Restaurants & Dining": 600,
        "Mortgage & Rent": 3200,
        "Medical": 150,
        "Gas & Fuel": 250,
        "Childcare & Education": 1500,
    })
    for month in range(1, 13):
        fp = FinancialPeriod(
            year=2025,
            month=month,
            segment="all",
            total_income=25000.0,
            total_expenses=8050.0,
            net_cash_flow=16950.0,
            expense_breakdown=expense_categories,
        )
        session.add(fp)

    # --- Prior year financial periods (2024) ---
    expense_categories_2024 = json.dumps({
        "Groceries": 1100,
        "Restaurants & Dining": 550,
        "Mortgage & Rent": 3200,
        "Medical": 120,
    })
    for month in range(1, 13):
        fp = FinancialPeriod(
            year=2024,
            month=month,
            segment="all",
            total_income=22000.0,
            total_expenses=7200.0,
            net_cash_flow=14800.0,
            expense_breakdown=expense_categories_2024,
        )
        session.add(fp)

    await session.flush()

    return {
        "checking": checking,
        "credit_card": credit_card,
        "biz_card": biz_card,
        "biz": biz,
        "hh": hh,
        "bp_a": bp_a,
        "bp_b": bp_b,
        "ret": ret,
        "roth_ira": roth_ira,
        "student_loan": student_loan,
        "nw": nw,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Analytics Insights Engine Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestInsightsHelpers:
    """Unit tests for pure helper functions in analytics/insights.py."""

    def test_percentile_empty_list(self):
        from pipeline.analytics.insights import _percentile
        assert _percentile([], 0.5) == 0.0

    def test_percentile_single_value(self):
        from pipeline.analytics.insights import _percentile
        assert _percentile([100.0], 0.5) == 100.0

    def test_percentile_interpolation(self):
        from pipeline.analytics.insights import _percentile
        vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        # Median of [10,20,30,40,50] = 30
        assert _percentile(vals, 0.5) == 30.0
        # 25th percentile = 20
        assert _percentile(vals, 0.25) == 20.0
        # 75th percentile = 40
        assert _percentile(vals, 0.75) == 40.0

    def test_iqr_fences_normal_data(self):
        from pipeline.analytics.insights import _iqr_fences
        values = [100, 200, 300, 400, 500, 600, 700, 800]
        lower, upper = _iqr_fences(values)
        # IQR = Q3 - Q1 = 625 - 275 = 350; fences at 275-525, 625+525
        assert lower < 0  # 275 - 1.5*350 = -250
        assert upper > 1000  # 625 + 1.5*350 = 1150
        assert lower == pytest.approx(-250.0, abs=1)
        assert upper == pytest.approx(1150.0, abs=1)

    def test_iqr_fences_few_values(self):
        from pipeline.analytics.insights import _iqr_fences
        # With < 4 values, should return min-1, max+1
        lower, upper = _iqr_fences([10, 20])
        assert lower == 9
        assert upper == 21

    def test_median_basic(self):
        from pipeline.analytics.insights import _median
        assert _median([3, 1, 2]) == 2.0
        assert _median([]) == 0.0

    def test_mean_basic(self):
        from pipeline.analytics.insights import _mean
        assert _mean([10, 20, 30]) == 20.0
        assert _mean([]) == 0.0

    def test_stdev_basic(self):
        from pipeline.analytics.insights import _stdev
        assert _stdev([10, 10, 10]) == 0.0
        assert _stdev([1]) == 0.0  # single value
        # stdev of [10, 20, 30] (sample) = ~10.0
        result = _stdev([10.0, 20.0, 30.0])
        assert result == pytest.approx(10.0, abs=0.01)


class TestOutlierDetection:
    """Test outlier detection logic with realistic transaction data."""

    def _make_tx(self, id, amount, category, description="Test", month=1, year=2025):
        return SimpleNamespace(
            id=id,
            date=datetime(year, month, 15),
            description=description,
            amount=amount,
            effective_category=category,
            effective_segment="personal",
            period_month=month,
            period_year=year,
        )

    def test_detect_expense_outlier_large_medical_bill(self):
        from pipeline.analytics.insights import _detect_outlier_transactions
        # 11 normal medical transactions + 1 huge outlier
        txns = [self._make_tx(i, -150.0, "Medical", month=i) for i in range(1, 12)]
        txns.append(self._make_tx(12, -5500.0, "Medical", month=12))
        exp_outliers, inc_outliers = _detect_outlier_transactions(txns)
        assert len(exp_outliers) == 1
        assert exp_outliers[0]["amount"] == -5500.0
        assert exp_outliers[0]["category"] == "Medical"
        assert "above the typical" in exp_outliers[0]["reason"]
        assert len(inc_outliers) == 0

    def test_no_outliers_in_consistent_spending(self):
        from pipeline.analytics.insights import _detect_outlier_transactions
        # All transactions within normal range
        txns = [self._make_tx(i, -500.0 - (i * 5), "Groceries", month=i) for i in range(1, 13)]
        exp_outliers, _ = _detect_outlier_transactions(txns)
        assert len(exp_outliers) == 0

    def test_never_outlier_categories_excluded(self):
        """Mortgage and Rent should never be flagged as outliers."""
        from pipeline.analytics.insights import _detect_outlier_transactions
        txns = [self._make_tx(i, -3200.0, "Mortgage & Rent", month=i) for i in range(1, 12)]
        txns.append(self._make_tx(12, -9600.0, "Mortgage & Rent", month=12))
        exp_outliers, _ = _detect_outlier_transactions(txns)
        assert len(exp_outliers) == 0

    def test_income_outlier_detected(self):
        from pipeline.analytics.insights import _detect_outlier_transactions
        txns = [self._make_tx(i, 14500.0, "Paycheck", month=i) for i in range(1, 12)]
        txns.append(self._make_tx(12, 40000.0, "Paycheck", month=12))
        _, inc_outliers = _detect_outlier_transactions(txns)
        assert len(inc_outliers) == 1
        assert inc_outliers[0]["amount"] == 40000.0

    def test_minimum_outlier_thresholds(self):
        """Small amounts should not be flagged even if statistically outlying."""
        from pipeline.analytics.insights import _detect_outlier_transactions
        txns = [self._make_tx(i, -10.0, "Coffee", month=i) for i in range(1, 12)]
        txns.append(self._make_tx(12, -200.0, "Coffee", month=12))  # Below MIN_EXPENSE_OUTLIER ($500)
        exp_outliers, _ = _detect_outlier_transactions(txns)
        assert len(exp_outliers) == 0

    def test_feedback_suppresses_not_outlier(self):
        from pipeline.analytics.insights import _detect_outlier_transactions
        txns = [self._make_tx(i, -150.0, "Medical", month=i) for i in range(1, 12)]
        txns.append(self._make_tx(12, -5500.0, "Medical", month=12))
        fb = SimpleNamespace(
            id=1,
            transaction_id=12,
            classification="not_outlier",
            user_note=None,
            description_pattern=None,
            category="Medical",
            apply_to_future=False,
            year=2025,
            created_at=datetime.now(),
        )
        exp_outliers, _ = _detect_outlier_transactions(txns, feedback_rows=[fb])
        assert len(exp_outliers) == 0

    def test_feedback_pattern_suppression(self):
        from pipeline.analytics.insights import _detect_outlier_transactions, _build_feedback_index
        txns = [self._make_tx(i, -150.0, "Medical", month=i) for i in range(1, 12)]
        txns.append(self._make_tx(12, -5500.0, "Medical", description="KAISER SURGERY", month=12))
        fb = SimpleNamespace(
            id=1,
            transaction_id=99,  # different txn
            classification="not_outlier",
            user_note=None,
            description_pattern="KAISER",
            category="Medical",
            apply_to_future=True,
            year=2025,
            created_at=datetime.now(),
        )
        exp_outliers, _ = _detect_outlier_transactions(txns, feedback_rows=[fb])
        # txn 12 matches pattern "KAISER" and should be suppressed
        assert len(exp_outliers) == 0

    def test_prior_year_used_for_small_categories(self):
        """When current year has < 3 transactions, prior year data helps."""
        from pipeline.analytics.insights import _detect_outlier_transactions
        current = [self._make_tx(1, -200.0, "Auto Repair"), self._make_tx(2, -5000.0, "Auto Repair")]
        prior = [
            self._make_tx(100, -180.0, "Auto Repair", year=2024),
            self._make_tx(101, -250.0, "Auto Repair", year=2024),
            self._make_tx(102, -200.0, "Auto Repair", year=2024),
        ]
        exp_outliers, _ = _detect_outlier_transactions(current, prior_year_transactions=prior)
        assert len(exp_outliers) == 1
        assert exp_outliers[0]["amount"] == -5000.0


class TestNormalizedBudget:
    """Test budget normalization logic."""

    def _make_tx(self, id, amount, category, month):
        return SimpleNamespace(
            id=id,
            amount=amount,
            effective_category=category,
            period_month=month,
        )

    def test_normalized_budget_excludes_outliers(self):
        from pipeline.analytics.insights import _normalize_budget
        txns = []
        tid = 1
        for m in range(1, 13):
            txns.append(self._make_tx(tid, -1200.0, "Groceries", m))
            tid += 1
        # Add one outlier in month 6
        outlier_id = tid
        txns.append(self._make_tx(outlier_id, -4000.0, "Groceries", 6))

        result = _normalize_budget(txns, expense_outlier_ids={outlier_id})
        cats = {c["category"]: c for c in result["by_category"]}
        assert "Groceries" in cats
        # Normalized monthly should be around $1,200 (excluding the $4,000 outlier)
        assert cats["Groceries"]["normalized_monthly"] == 1200.0

    def test_normalized_budget_with_empty_data(self):
        from pipeline.analytics.insights import _normalize_budget
        result = _normalize_budget([], expense_outlier_ids=set())
        assert result["normalized_monthly_total"] == 0
        assert result["by_category"] == []

    def test_normalized_budget_multiple_categories(self):
        from pipeline.analytics.insights import _normalize_budget
        txns = []
        tid = 1
        for m in range(1, 7):
            txns.append(self._make_tx(tid, -1000.0, "Groceries", m))
            tid += 1
            txns.append(self._make_tx(tid, -500.0, "Gas", m))
            tid += 1

        result = _normalize_budget(txns, expense_outlier_ids=set())
        cats = {c["category"]: c for c in result["by_category"]}
        assert cats["Groceries"]["normalized_monthly"] == 1000.0
        assert cats["Gas"]["normalized_monthly"] == 500.0
        assert result["normalized_monthly_total"] == 1500.0


class TestMonthlyAnalysis:
    """Test monthly spending analysis and classification."""

    def _make_tx(self, id, amount, category, month):
        return SimpleNamespace(
            id=id,
            amount=amount,
            effective_category=category,
            period_month=month,
            period_year=2025,
        )

    def test_monthly_analysis_classification(self):
        from pipeline.analytics.insights import _monthly_analysis
        txns = []
        tid = 1
        # 11 months of normal spending ($8,000/mo)
        for m in range(1, 12):
            txns.append(self._make_tx(tid, -4000.0, "Groceries", m))
            tid += 1
            txns.append(self._make_tx(tid, -4000.0, "Housing", m))
            tid += 1
        # Month 12: elevated spending ($15,000)
        txns.append(self._make_tx(tid, -8000.0, "Groceries", 12))
        tid += 1
        txns.append(self._make_tx(tid, -7000.0, "Shopping", 12))
        tid += 1

        result = _monthly_analysis(txns, set(), set(), [])
        assert len(result) == 12
        # Month 12 should have higher classification
        month_12 = next(m for m in result if m["month"] == 12)
        assert month_12["total_expenses"] == 15000.0
        # Check that some months are classified as normal
        normal_months = [m for m in result if m["classification"] == "normal"]
        assert len(normal_months) > 0

    def test_monthly_analysis_with_income(self):
        from pipeline.analytics.insights import _monthly_analysis
        txns = [
            self._make_tx(1, -5000.0, "Groceries", 1),
            self._make_tx(2, 14500.0, "Paycheck", 1),
        ]
        result = _monthly_analysis(txns, set(), set(), [])
        assert len(result) == 1
        assert result[0]["total_income"] == 14500.0
        assert result[0]["total_expenses"] == 5000.0

    def test_monthly_analysis_empty_months_skipped(self):
        from pipeline.analytics.insights import _monthly_analysis
        txns = [self._make_tx(1, -1000.0, "Groceries", 3)]
        result = _monthly_analysis(txns, set(), set(), [])
        assert len(result) == 1
        assert result[0]["month"] == 3


class TestCategoryTrends:
    """Test category trend analysis (increasing, decreasing, stable)."""

    def _make_tx(self, id, amount, category, month):
        return SimpleNamespace(
            id=id,
            amount=amount,
            effective_category=category,
            period_month=month,
            period_year=2025,
        )

    def test_increasing_trend_detected(self):
        from pipeline.analytics.insights import _category_trends
        txns = []
        tid = 1
        # Steadily increasing spending: $500 to $1500
        for m in range(1, 13):
            amt = -(500 + m * 100)
            txns.append(self._make_tx(tid, amt, "Dining", m))
            tid += 1

        result = _category_trends(txns, [])
        dining = next(t for t in result if t["category"] == "Dining")
        assert dining["trend"] == "increasing"
        assert dining["months_active"] == 12
        assert dining["budget_share_pct"] == 100.0

    def test_decreasing_trend_detected(self):
        from pipeline.analytics.insights import _category_trends
        txns = []
        tid = 1
        # Steadily decreasing spending: $1500 to $500
        for m in range(1, 13):
            amt = -(1500 - m * 80)
            txns.append(self._make_tx(tid, amt, "Shopping", m))
            tid += 1

        result = _category_trends(txns, [])
        shopping = next(t for t in result if t["category"] == "Shopping")
        assert shopping["trend"] == "decreasing"

    def test_stable_trend_detected(self):
        from pipeline.analytics.insights import _category_trends
        txns = []
        tid = 1
        for m in range(1, 13):
            txns.append(self._make_tx(tid, -1000.0, "Mortgage", m))
            tid += 1

        result = _category_trends(txns, [])
        mortgage = next(t for t in result if t["category"] == "Mortgage")
        assert mortgage["trend"] == "stable"
        assert mortgage["monthly_average"] == 1000.0
        assert mortgage["total_annual"] == 12000.0

    def test_insufficient_data_trend(self):
        from pipeline.analytics.insights import _category_trends
        txns = [self._make_tx(1, -500.0, "OneOff", 5)]
        result = _category_trends(txns, [])
        one_off = next(t for t in result if t["category"] == "OneOff")
        assert one_off["trend"] == "insufficient_data"


class TestIncomeAnalysis:
    """Test income breakdown: regular vs irregular."""

    def _make_tx(self, id, amount, category, month):
        return SimpleNamespace(
            id=id,
            amount=amount,
            effective_category=category,
            period_month=month,
            date=datetime(2025, month, 1),
            description=f"Income {category}",
        )

    def test_regular_income_identified(self):
        from pipeline.analytics.insights import _income_analysis
        txns = [self._make_tx(i, 14500.0, "Paycheck", i) for i in range(1, 13)]
        result = _income_analysis(txns, income_outlier_ids=set())
        assert result["regular_monthly_median"] == 14500.0
        assert result["total_regular"] == 14500.0 * 12
        assert result["total_irregular"] == 0.0

    def test_irregular_income_separated(self):
        from pipeline.analytics.insights import _income_analysis
        txns = [self._make_tx(i, 14500.0, "Paycheck", i) for i in range(1, 13)]
        bonus = self._make_tx(13, 25000.0, "Bonus", 6)
        txns.append(bonus)
        result = _income_analysis(txns, income_outlier_ids={13})
        assert result["total_irregular"] == 25000.0
        assert len(result["irregular_items"]) == 1
        assert result["irregular_items"][0]["amount"] == 25000.0

    def test_income_by_source_breakdown(self):
        from pipeline.analytics.insights import _income_analysis
        txns = [
            self._make_tx(1, 14500.0, "Paycheck", 1),
            self._make_tx(2, 10500.0, "Paycheck B", 1),
            self._make_tx(3, 500.0, "Interest", 1),
        ]
        result = _income_analysis(txns, income_outlier_ids=set())
        sources = {s["source"]: s["total"] for s in result["by_source"]}
        assert sources["Paycheck"] == 14500.0
        assert sources["Paycheck B"] == 10500.0
        assert sources["Interest"] == 500.0


class TestSeasonalPatterns:
    """Test seasonal spending pattern detection."""

    def _make_tx(self, id, amount, category, month, year=2025):
        return SimpleNamespace(
            id=id,
            amount=amount,
            effective_category=category,
            period_month=month,
            period_year=year,
        )

    def test_december_peak_detected(self):
        from pipeline.analytics.insights import _seasonal_patterns
        txns = []
        tid = 1
        for m in range(1, 13):
            # December has 2x spending (holiday season)
            multiplier = 2.0 if m == 12 else 1.0
            txns.append(self._make_tx(tid, -5000.0 * multiplier, "Shopping", m))
            tid += 1

        result = _seasonal_patterns(txns)
        dec = next(p for p in result if p["month"] == 12)
        assert dec["seasonal_index"] > 130  # peak threshold
        assert dec["label"] == "peak"

    def test_summer_below_average_detected(self):
        from pipeline.analytics.insights import _seasonal_patterns
        txns = []
        tid = 1
        for m in range(1, 13):
            # Summer months have half spending
            multiplier = 0.5 if m in (6, 7, 8) else 1.2
            txns.append(self._make_tx(tid, -5000.0 * multiplier, "Groceries", m))
            tid += 1

        result = _seasonal_patterns(txns)
        jul = next(p for p in result if p["month"] == 7)
        assert jul["seasonal_index"] < 85
        assert jul["label"] in ("below_average", "low")


class TestYearOverYear:
    """Test year-over-year comparison."""

    def test_yoy_basic(self):
        from pipeline.analytics.insights import _year_over_year
        current = [
            FinancialPeriod(year=2025, month=m, segment="all",
                            total_income=25000.0, total_expenses=8000.0,
                            expense_breakdown=json.dumps({"Groceries": 1200}))
            for m in range(1, 13)
        ]
        prior = [
            FinancialPeriod(year=2024, month=m, segment="all",
                            total_income=22000.0, total_expenses=7000.0,
                            expense_breakdown=json.dumps({"Groceries": 1100}))
            for m in range(1, 13)
        ]
        result = _year_over_year(current, prior)
        assert result is not None
        assert result["current_year_income"] == 300000.0  # 25k * 12
        assert result["prior_year_income"] == 264000.0    # 22k * 12
        assert result["income_change_pct"] == pytest.approx(13.6, abs=0.1)
        assert result["current_year_expenses"] == 96000.0
        assert result["prior_year_expenses"] == 84000.0
        assert len(result["monthly_comparison"]) == 12

    def test_yoy_no_prior_data(self):
        from pipeline.analytics.insights import _year_over_year
        result = _year_over_year([], [])
        assert result is None


class TestComputeAnnualInsights:
    """Integration test for the full compute_annual_insights function."""

    @pytest.mark.asyncio
    async def test_full_insights_with_real_data(self, session, henry_household):
        from pipeline.analytics.insights import compute_annual_insights
        result = await compute_annual_insights(session, 2025)

        # --- Structure checks ---
        assert result["year"] == 2025
        assert result["transaction_count"] > 100  # 12 months * ~13 txns + outliers

        # --- Summary ---
        summary = result["summary"]
        assert summary["normalized_monthly_budget"] > 0
        assert summary["actual_monthly_average"] > 0

        # --- Outlier detection ---
        # The $5,500 medical bill and $4,200 furniture should be flagged
        expense_outliers = result["expense_outliers"]
        outlier_amounts = [abs(o["amount"]) for o in expense_outliers]
        assert 5500.0 in outlier_amounts or len(expense_outliers) > 0

        # --- Income analysis ---
        income = result["income_analysis"]
        assert income["total_regular"] > 0  # Regular paycheck income
        assert len(income["by_source"]) >= 2  # Paycheck + Paycheck B

        # --- Category trends ---
        trends = result["category_trends"]
        assert len(trends) > 5
        grocery_trend = next((t for t in trends if t["category"] == "Groceries"), None)
        assert grocery_trend is not None
        assert grocery_trend["months_active"] == 12

        # --- Monthly analysis ---
        monthly = result["monthly_analysis"]
        assert len(monthly) == 12

        # --- Year over year ---
        yoy = result["year_over_year"]
        assert yoy is not None
        assert yoy["current_year_income"] > 0
        assert yoy["prior_year_income"] > 0

        # --- Normalized budget ---
        norm = result["normalized_budget"]
        assert norm["normalized_monthly_total"] > 0
        assert len(norm["by_category"]) > 5


# ═══════════════════════════════════════════════════════════════════════════
# 2. Action Plan Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestActionPlan:
    """Test the action plan generator with DB data."""

    @pytest.mark.asyncio
    async def test_compute_action_plan_with_henry_data(self, session, henry_household):
        from pipeline.planning.action_plan import compute_action_plan
        steps = await compute_action_plan(session)

        assert len(steps) >= 8
        step_names = [s["name"] for s in steps]

        # Should include all core FOO steps
        assert "Capture Employer Match" in step_names
        assert "Pay Off High-Interest Debt" in step_names
        assert "Build Emergency Fund (3-6 months)" in step_names
        assert "Max HSA" in step_names
        assert "Max Roth IRA (or Backdoor Roth)" in step_names
        assert "Max 401(k) / 403(b)" in step_names

        # With $4,500 CC debt, high-interest debt step should not be done
        debt_step = next(s for s in steps if "High-Interest" in s["name"])
        assert debt_step["current_value"] == pytest.approx(4500.0, abs=1)

        # Employer match should be detected (both spouses have 401k)
        match_step = next(s for s in steps if "Employer Match" in s["name"])
        assert match_step is not None

        # Mega Backdoor should be included (bp_a has it)
        assert "Mega Backdoor Roth" in step_names

        # Only one "next" step at a time
        next_count = sum(1 for s in steps if s["status"] == "next")
        assert next_count == 1

    @pytest.mark.asyncio
    async def test_compute_required_savings_rate(self, session, henry_household):
        from pipeline.planning.action_plan import compute_required_savings_rate
        rate = await compute_required_savings_rate(session)
        # For a 35-year-old earning $380k with $250k saved, rate should be reasonable
        assert 5.0 <= rate <= 80.0
        # With current savings and long time horizon, should be moderate
        assert rate < 50.0

    @pytest.mark.asyncio
    async def test_compute_benchmarks_from_db(self, session, henry_household):
        from pipeline.planning.action_plan import compute_benchmarks_from_db
        result = await compute_benchmarks_from_db(session)
        assert result["user_age"] == 35
        assert result["net_worth"] > 0
        assert "nw_percentile" in result
        assert "savings_percentile" in result
        assert "required_savings_rate" in result
        assert result["required_savings_rate"] >= 5.0

    @pytest.mark.asyncio
    async def test_action_plan_no_data(self, session):
        """Action plan should still work with empty DB (using defaults)."""
        from pipeline.planning.action_plan import compute_action_plan
        steps = await compute_action_plan(session)
        assert len(steps) >= 8
        # Should use default monthly expenses ($5,000)
        ef_step = next(s for s in steps if "Emergency" in s["name"])
        assert ef_step["target_value"] == pytest.approx(30000.0, abs=1)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Proactive Insights Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProactiveInsights:
    """Test proactive financial insights engine."""

    @pytest.mark.asyncio
    async def test_underwithholding_high_income(self, session, henry_household):
        """Should detect underwithholding for high earner with upcoming vests."""
        from pipeline.planning.proactive_insights import compute_proactive_insights

        # Add equity grants with upcoming vests
        grant = EquityGrant(
            employer_name="TechCorp",
            grant_type="RSU",
            grant_date=date(2023, 1, 1),
            total_shares=1000,
            vested_shares=500,
            unvested_shares=500,
            current_fmv=200.0,
            is_active=True,
        )
        session.add(grant)
        await session.flush()

        vest = VestingEvent(
            grant_id=grant.id,
            vest_date=date.today() + timedelta(days=60),
            shares=250,
            status="upcoming",
        )
        session.add(vest)
        await session.flush()

        insights = await compute_proactive_insights(session)

        # Should detect underwithholding because combined_income=$380k -> 35% marginal rate
        withholding_insights = [i for i in insights if i["type"] == "underwithholding"]
        assert len(withholding_insights) == 1
        gap = withholding_insights[0]["value"]
        # 250 shares * $200 = $50,000; gap = $50k * (0.35 - 0.22) = $6,500
        assert gap == pytest.approx(6500.0, abs=100)

    @pytest.mark.asyncio
    async def test_quarterly_estimated_tax_with_business(self, session, henry_household):
        """Should remind about quarterly taxes when business entities exist."""
        from pipeline.planning.proactive_insights import _quarterly_estimated_tax
        insights = await _quarterly_estimated_tax(session)
        # Whether we get insights depends on current date proximity to due dates
        for insight in insights:
            assert insight["type"] == "estimated_tax"
            assert insight["severity"] == "action"
            assert "Estimated Tax Due" in insight["title"]

    @pytest.mark.asyncio
    async def test_goal_milestone_at_50_percent(self, session, henry_household):
        """Should celebrate when a goal reaches 50%."""
        from pipeline.planning.proactive_insights import _goal_milestones
        goal = Goal(
            name="Emergency Fund",
            target_amount=100000.0,
            current_amount=50000.0,  # Exactly 50%
            status="active",
        )
        session.add(goal)
        await session.flush()

        insights = await _goal_milestones(session)
        assert len(insights) == 1
        assert insights[0]["type"] == "goal_milestone"
        assert "50%" in insights[0]["title"]
        assert "$50,000" in insights[0]["message"]

    @pytest.mark.asyncio
    async def test_no_goal_milestone_at_35_percent(self, session, henry_household):
        """Should not trigger milestone at non-milestone percentages."""
        from pipeline.planning.proactive_insights import _goal_milestones
        goal = Goal(
            name="Down Payment",
            target_amount=200000.0,
            current_amount=70000.0,  # 35%
            status="active",
        )
        session.add(goal)
        await session.flush()

        insights = await _goal_milestones(session)
        assert len(insights) == 0

    @pytest.mark.asyncio
    async def test_uncategorized_transactions_alert(self, session, henry_household):
        """Should alert when > 10 transactions have no category."""
        from pipeline.planning.proactive_insights import _uncategorized_transactions
        data = henry_household
        for i in range(15):
            tx = Transaction(
                account_id=data["checking"].id,
                date=datetime(2025, 6, i + 1, tzinfo=timezone.utc),
                description=f"Unknown Charge {i}",
                amount=-50.0,
                effective_category=None,
                period_month=6,
                period_year=2025,
                is_excluded=False,
                is_manually_reviewed=False,
            )
            session.add(tx)
        await session.flush()

        insights = await _uncategorized_transactions(session)
        assert len(insights) == 1
        assert insights[0]["type"] == "uncategorized"
        assert insights[0]["value"] >= 15

    @pytest.mark.asyncio
    async def test_insurance_renewal_alert(self, session, henry_household):
        """Should alert about upcoming insurance renewals."""
        from pipeline.planning.proactive_insights import _insurance_renewals
        data = henry_household
        policy = InsurancePolicy(
            household_id=data["hh"].id,
            policy_type="homeowners",
            provider="State Farm",
            is_active=True,
            renewal_date=date.today() + timedelta(days=30),
            annual_premium=2400.0,
        )
        session.add(policy)
        await session.flush()

        insights = await _insurance_renewals(session)
        assert len(insights) == 1
        assert insights[0]["type"] == "insurance_renewal"
        assert "Homeowners" in insights[0]["title"]

    @pytest.mark.asyncio
    async def test_upcoming_vests_alert(self, session, henry_household):
        """Should alert about equity vesting events within 30 days."""
        from pipeline.planning.proactive_insights import _upcoming_vests
        grant = EquityGrant(
            employer_name="TechCorp",
            grant_type="RSU",
            grant_date=date(2023, 1, 1),
            total_shares=1000,
            current_fmv=150.0,
            is_active=True,
        )
        session.add(grant)
        await session.flush()

        vest = VestingEvent(
            grant_id=grant.id,
            vest_date=date.today() + timedelta(days=15),
            shares=100,
            status="upcoming",
        )
        session.add(vest)
        await session.flush()

        insights = await _upcoming_vests(session)
        assert len(insights) == 1
        assert insights[0]["type"] == "upcoming_vest"
        assert insights[0]["value"] == pytest.approx(15000.0, abs=100)

    @pytest.mark.asyncio
    async def test_insights_sorted_by_severity(self, session, henry_household):
        """Insights should be sorted: action > warning > info."""
        from pipeline.planning.proactive_insights import compute_proactive_insights
        # Add a goal at 50% for an info-level insight
        goal = Goal(
            name="Test Goal",
            target_amount=10000.0,
            current_amount=5000.0,
            status="active",
        )
        session.add(goal)
        await session.flush()

        insights = await compute_proactive_insights(session)
        if len(insights) >= 2:
            severity_order = {"action": 0, "warning": 1, "info": 2}
            for i in range(len(insights) - 1):
                current_sev = severity_order.get(insights[i]["severity"], 3)
                next_sev = severity_order.get(insights[i + 1]["severity"], 3)
                assert current_sev <= next_sev


# ═══════════════════════════════════════════════════════════════════════════
# 4. Business Reports Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBusinessReports:
    """Test business entity expense reporting."""

    @pytest.mark.asyncio
    async def test_entity_expense_report(self, session, henry_household):
        from pipeline.planning.business_reports import compute_entity_expense_report
        data = henry_household

        report = await compute_entity_expense_report(session, data["biz"].id, 2025)

        assert report["entity_name"] == "Aron Consulting LLC"
        assert report["year"] == 2025

        # 12 months of $180 lunch + $250 software = $430/mo
        assert report["year_total_expenses"] == pytest.approx(430.0 * 12, abs=10)

        # Monthly totals should have 12 entries
        assert len(report["monthly_totals"]) == 12
        for mt in report["monthly_totals"]:
            assert mt["total_expenses"] == pytest.approx(430.0, abs=5)

        # Category breakdown should include both expense types
        cats = {c["category"]: c["total"] for c in report["category_breakdown"]}
        assert "Meals & Entertainment" in cats
        assert "Software & SaaS" in cats
        assert cats["Meals & Entertainment"] == pytest.approx(180.0 * 12, abs=10)
        assert cats["Software & SaaS"] == pytest.approx(250.0 * 12, abs=10)

        # No prior year data for this biz entity
        assert report["prior_year_total_expenses"] is None

    @pytest.mark.asyncio
    async def test_entity_not_found(self, session, henry_household):
        from pipeline.planning.business_reports import compute_entity_expense_report
        report = await compute_entity_expense_report(session, 99999, 2025)
        assert "error" in report

    @pytest.mark.asyncio
    async def test_entity_transactions_list(self, session, henry_household):
        from pipeline.planning.business_reports import get_entity_transactions
        data = henry_household
        txns = await get_entity_transactions(session, data["biz"].id, 2025)
        assert len(txns) == 24  # 12 months * 2 txns
        # All should be negative (expenses)
        assert all(t["amount"] < 0 for t in txns)

    @pytest.mark.asyncio
    async def test_entity_transactions_by_month(self, session, henry_household):
        from pipeline.planning.business_reports import get_entity_transactions
        data = henry_household
        txns = await get_entity_transactions(session, data["biz"].id, 2025, month=3)
        assert len(txns) == 2  # 1 lunch + 1 software for March

    @pytest.mark.asyncio
    async def test_reimbursement_report(self, session, henry_household):
        from pipeline.planning.business_reports import compute_reimbursement_report
        data = henry_household
        report = await compute_reimbursement_report(session, data["biz"].id)
        assert report["entity_name"] == "Aron Consulting LLC"
        assert report["total_expenses"] > 0

    @pytest.mark.asyncio
    async def test_reimbursement_report_entity_not_found(self, session, henry_household):
        from pipeline.planning.business_reports import compute_reimbursement_report
        report = await compute_reimbursement_report(session, 99999)
        assert "error" in report


# ═══════════════════════════════════════════════════════════════════════════
# 5. Retirement Budget Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRetirementBudget:
    """Test retirement budget translation engine."""

    def _base_budget_lines(self):
        return [
            {"category": "Groceries", "monthly_amount": 1200.0, "source": "budget"},
            {"category": "Mortgage & Rent", "monthly_amount": 3200.0, "source": "budget"},
            {"category": "Childcare & Education", "monthly_amount": 1500.0, "source": "budget"},
            {"category": "Medical", "monthly_amount": 150.0, "source": "budget"},
            {"category": "Gas & Fuel", "monthly_amount": 250.0, "source": "budget"},
            {"category": "Clothing & Apparel", "monthly_amount": 200.0, "source": "budget"},
            {"category": "Restaurants & Dining", "monthly_amount": 600.0, "source": "budget"},
            {"category": "Vacation", "monthly_amount": 400.0, "source": "budget"},
            {"category": "Fitness & Gym", "monthly_amount": 120.0, "source": "budget"},
            {"category": "Entertainment & Recreation", "monthly_amount": 300.0, "source": "budget"},
            {"category": "Insurance", "monthly_amount": 450.0, "source": "budget"},
            {"category": "Coffee & Beverages", "monthly_amount": 80.0, "source": "budget"},
            {"category": "Utilities", "monthly_amount": 350.0, "source": "budget"},
        ]

    def test_smart_defaults_applied(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        lines = self._base_budget_lines()
        result = compute_retirement_budget(lines, [], retirement_age=65, debt_payoffs=[])

        result_map = {r["category"]: r for r in result["lines"]}

        # Childcare should be eliminated (0x multiplier)
        assert result_map["Childcare & Education"]["retirement_monthly"] == 0.0
        assert result_map["Childcare & Education"]["multiplier"] == 0.0

        # Medical should double
        assert result_map["Medical"]["retirement_monthly"] == 300.0
        assert result_map["Medical"]["multiplier"] == 2.0

        # Groceries should be 75% of current
        assert result_map["Groceries"]["retirement_monthly"] == 900.0
        assert result_map["Groceries"]["multiplier"] == 0.75

        # Vacation should increase 1.5x
        assert result_map["Vacation"]["retirement_monthly"] == 600.0

        # Gas should be 50% (less commuting)
        assert result_map["Gas & Fuel"]["retirement_monthly"] == 125.0

        # Clothing at 60%
        assert result_map["Clothing & Apparel"]["retirement_monthly"] == 120.0

        # Utilities have no default — should stay same (1.0)
        assert result_map["Utilities"]["retirement_monthly"] == 350.0
        assert result_map["Utilities"]["multiplier"] == 1.0

    def test_mortgage_eliminated_by_default(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        lines = [{"category": "Mortgage & Rent", "monthly_amount": 3200.0}]
        result = compute_retirement_budget(lines, [], retirement_age=65, debt_payoffs=[])
        assert result["lines"][0]["retirement_monthly"] == 0.0
        assert "Paid off before retirement" in result["lines"][0]["reason"]

    def test_debt_payoff_before_retirement(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        # "Auto Loan" category matches "auto" in both the category and debt name
        lines = [{"category": "Auto Loan", "monthly_amount": 450.0}]
        payoffs = [{"name": "Auto Loan Payment", "payoff_age": 55}]
        result = compute_retirement_budget(lines, [], retirement_age=65, debt_payoffs=payoffs)
        auto = result["lines"][0]
        # Paid off before retirement age 65 (payoff_age=55)
        assert auto["retirement_monthly"] == 0.0
        assert "Paid off before age 65" in auto["reason"]

    def test_debt_not_paid_off_before_retirement(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        # Debt payoff at age 70, retirement at 65 — debt NOT paid off before retirement
        lines = [{"category": "auto payment", "monthly_amount": 450.0}]
        payoffs = [{"name": "auto loan", "payoff_age": 70}]
        result = compute_retirement_budget(lines, [], retirement_age=65, debt_payoffs=payoffs)
        assert result["lines"][0]["retirement_monthly"] == 450.0

    def test_user_override_fixed_amount(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        lines = [{"category": "Groceries", "monthly_amount": 1200.0}]
        overrides = [{"category": "Groceries", "fixed_amount": 800.0, "reason": "Smaller household"}]
        result = compute_retirement_budget(lines, overrides, retirement_age=65, debt_payoffs=[])
        assert result["lines"][0]["retirement_monthly"] == 800.0
        assert result["lines"][0]["is_user_override"] is True
        assert "Smaller household" in result["lines"][0]["reason"]

    def test_user_override_multiplier(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        lines = [{"category": "Dining", "monthly_amount": 600.0}]
        overrides = [{"category": "Dining", "multiplier": 0.5}]
        result = compute_retirement_budget(lines, overrides, retirement_age=65, debt_payoffs=[])
        assert result["lines"][0]["retirement_monthly"] == 300.0

    def test_business_categories_excluded(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        lines = [
            {"category": "Business Travel", "monthly_amount": 500.0},
            {"category": "business supplies", "monthly_amount": 200.0},
            {"category": "Groceries", "monthly_amount": 1200.0},
        ]
        result = compute_retirement_budget(lines, [], retirement_age=65, debt_payoffs=[])
        cats = [r["category"] for r in result["lines"]]
        assert "Business Travel" not in cats
        assert "business supplies" not in cats
        assert "Groceries" in cats

    def test_totals_computed_correctly(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        lines = self._base_budget_lines()
        result = compute_retirement_budget(lines, [], retirement_age=65, debt_payoffs=[])

        current_total = sum(l["monthly_amount"] for l in lines)
        assert result["current_monthly_total"] == round(current_total, 2)
        assert result["current_annual_total"] == round(current_total * 12, 2)

        ret_total = sum(r["retirement_monthly"] for r in result["lines"])
        assert result["retirement_monthly_total"] == round(ret_total, 2)
        assert result["retirement_annual_total"] == round(ret_total * 12, 2)

        # Retirement budget should be lower (childcare eliminated, mortgage gone, etc.)
        assert result["retirement_monthly_total"] < result["current_monthly_total"]

    def test_empty_budget(self):
        from pipeline.planning.retirement_budget import compute_retirement_budget
        result = compute_retirement_budget([], [], retirement_age=65, debt_payoffs=[])
        assert result["lines"] == []
        assert result["current_monthly_total"] == 0.0
        assert result["retirement_monthly_total"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 6. Milestones Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMilestones:
    """Test financial milestone computation for family members."""

    def _make_member(self, id, name, relationship, dob, college_start_year=None):
        return SimpleNamespace(
            id=id,
            name=name,
            relationship=relationship,
            date_of_birth=dob,
            college_start_year=college_start_year,
        )

    def test_adult_milestones_35_year_old(self):
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        dob = date(today.year - 35, today.month, today.day)
        member = self._make_member(1, "Mike", "self", dob)
        milestones = compute_milestones([member])

        types = {m["type"] for m in milestones}
        # At 35: SS FRA is 32 years away (always shows if > 0)
        assert "social_security_fra" in types
        # Medicare (30 years away) and RMD (38 years away) are > 20 years out,
        # so the code excludes them (only shows within 20 years)
        assert "medicare_eligible" not in types
        assert "rmd_start" not in types

        fra = next(m for m in milestones if m["type"] == "social_security_fra")
        assert fra["years_away"] == 32
        assert fra["age_at_event"] == 67
        assert fra["category"] == "retirement"

    def test_adult_milestones_50_year_old(self):
        """A 50-year-old should see Medicare (15y) and RMD (23y exceeds 20y limit)."""
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        dob = date(today.year - 50, today.month, today.day)
        member = self._make_member(1, "Pat", "self", dob)
        milestones = compute_milestones([member])

        types = {m["type"] for m in milestones}
        assert "social_security_fra" in types
        assert "medicare_eligible" in types  # 15 years away (<= 20)
        assert "rmd_start" not in types  # 23 years away (> 20)

        medicare = next(m for m in milestones if m["type"] == "medicare_eligible")
        assert medicare["years_away"] == 15
        assert medicare["age_at_event"] == 65

    def test_child_milestones_10_year_old(self):
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        dob = date(today.year - 10, today.month, today.day)
        member = self._make_member(2, "Emma", "child", dob)
        milestones = compute_milestones([member])

        types = {m["type"] for m in milestones}
        assert "driving_age" in types  # 6 years away (<= 8)
        assert "college_start" in types  # 8 years away (<= 18)
        # Health insurance rolloff at 26 is 16 years away, but code only
        # shows it within 8 years, so it should NOT appear for a 10-year-old
        assert "health_insurance_rolloff" not in types

        driving = next(m for m in milestones if m["type"] == "driving_age")
        assert driving["years_away"] == 6

        college = next(m for m in milestones if m["type"] == "college_start")
        assert college["years_away"] == 8

    def test_child_milestones_20_year_old(self):
        """A 20-year-old child should show health insurance rolloff (6 years away)."""
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        dob = date(today.year - 20, today.month, today.day)
        member = self._make_member(2, "Alex", "child", dob)
        milestones = compute_milestones([member])

        types = {m["type"] for m in milestones}
        assert "health_insurance_rolloff" in types  # 6 years away (<= 8)
        rolloff = next(m for m in milestones if m["type"] == "health_insurance_rolloff")
        assert rolloff["years_away"] == 6
        assert rolloff["age_at_event"] == 26

    def test_child_custom_college_year(self):
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        dob = date(today.year - 15, today.month, today.day)
        member = self._make_member(3, "Jack", "child", dob, college_start_year=today.year + 4)
        milestones = compute_milestones([member])
        college = next(m for m in milestones if m["type"] == "college_start")
        assert college["years_away"] == 4
        assert college["target_year"] == today.year + 4

    def test_child_near_tax_dependent_limit(self):
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        dob = date(today.year - 16, today.month, today.day)
        member = self._make_member(4, "Zoe", "child", dob)
        milestones = compute_milestones([member])
        tax_dep = next((m for m in milestones if m["type"] == "tax_dependent_age_limit"), None)
        assert tax_dep is not None
        assert tax_dep["years_away"] == 3
        assert "Child Tax Credit" in tax_dep["action"]

    def test_milestones_sorted_by_years_away(self):
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        members = [
            self._make_member(1, "Mike", "self", date(today.year - 35, 1, 1)),
            self._make_member(2, "Emma", "child", date(today.year - 10, 6, 15)),
        ]
        milestones = compute_milestones(members)
        for i in range(len(milestones) - 1):
            assert milestones[i]["years_away"] <= milestones[i + 1]["years_away"]

    def test_empty_members_list(self):
        from pipeline.planning.milestones import compute_milestones
        assert compute_milestones([]) == []

    def test_member_without_dob_skipped(self):
        from pipeline.planning.milestones import compute_milestones
        member = self._make_member(1, "Unknown", "self", None)
        assert compute_milestones([member]) == []

    def test_already_passed_milestones_excluded(self):
        """A 70-year-old should not have Medicare or SS milestones (already passed)."""
        from pipeline.planning.milestones import compute_milestones
        today = date.today()
        dob = date(today.year - 70, today.month, today.day)
        member = self._make_member(1, "Retiree", "self", dob)
        milestones = compute_milestones([member])
        types = {m["type"] for m in milestones}
        assert "medicare_eligible" not in types  # Already 70
        # RMD at 73 should still appear (3 years away)
        assert "rmd_start" in types


# ═══════════════════════════════════════════════════════════════════════════
# 7. Portfolio Analytics Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPortfolioAnalytics:
    """Test the portfolio analytics engine."""

    def _sample_holdings(self):
        return [
            {"ticker": "AAPL", "current_value": 50000, "asset_class": "stock", "sector": "Technology"},
            {"ticker": "MSFT", "current_value": 35000, "asset_class": "stock", "sector": "Technology"},
            {"ticker": "VTI", "current_value": 80000, "asset_class": "etf", "sector": "Broad Market"},
            {"ticker": "VXUS", "current_value": 40000, "asset_class": "etf", "sector": "International"},
            {"ticker": "BND", "current_value": 30000, "asset_class": "bond", "sector": "Fixed Income"},
            {"ticker": "GOOGL", "current_value": 25000, "asset_class": "stock", "sector": "Technology"},
        ]

    def test_rebalancing_buy_sell_hold(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        holdings = self._sample_holdings()
        total = sum(h["current_value"] for h in holdings)
        assert total == 260000

        target = {"stock": 40, "etf": 40, "bond": 20}
        recs = PortfolioAnalyticsEngine.rebalancing_recommendations(holdings, target)
        rec_map = {r["asset_class"]: r for r in recs}

        # Stock: has $110k (42.3%), target 40% -> sell
        assert rec_map["stock"]["action"] == "sell"
        assert rec_map["stock"]["current_pct"] == pytest.approx(42.31, abs=0.5)

        # ETF: has $120k (46.2%), target 40% -> sell
        assert rec_map["etf"]["action"] == "sell"

        # Bond: has $30k (11.5%), target 20% -> buy
        assert rec_map["bond"]["action"] == "buy"
        assert rec_map["bond"]["amount"] == pytest.approx(22000.0, abs=500)

    def test_rebalancing_empty_portfolio(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        recs = PortfolioAnalyticsEngine.rebalancing_recommendations([], {"stock": 60, "bond": 40})
        assert recs == []

    def test_rebalancing_hold_within_threshold(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        holdings = [
            {"ticker": "VTI", "current_value": 60000, "asset_class": "stock"},
            {"ticker": "BND", "current_value": 40000, "asset_class": "bond"},
        ]
        target = {"stock": 60, "bond": 40}
        recs = PortfolioAnalyticsEngine.rebalancing_recommendations(holdings, target)
        # All within 1% threshold, so all should be "hold"
        for rec in recs:
            assert rec["action"] == "hold"

    def test_benchmark_comparison(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        snapshots = [
            {"total_portfolio_value": 100000},
            {"total_portfolio_value": 108000},
            {"total_portfolio_value": 115000},
        ]
        result = PortfolioAnalyticsEngine.benchmark_comparison(
            snapshots, benchmark_returns=0.10, period_months=12
        )
        assert result["portfolio_return"] == pytest.approx(0.15, abs=0.01)
        assert result["benchmark_return"] == 0.10
        assert result["alpha"] == pytest.approx(0.05, abs=0.01)
        assert result["benchmark_ticker"] == "SPY"

    def test_benchmark_comparison_insufficient_data(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        result = PortfolioAnalyticsEngine.benchmark_comparison([])
        assert result["portfolio_return"] == 0
        assert result["alpha"] == pytest.approx(-0.10, abs=0.01)

    def test_concentration_risk_diversified(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        holdings = self._sample_holdings()
        result = PortfolioAnalyticsEngine.concentration_risk(holdings)
        # VTI is largest at $80k / $260k = 30.8%
        assert result["top_holding_pct"] == pytest.approx(30.77, abs=0.5)
        assert result["single_stock_risk"] == "high"  # >25%
        assert result["top_holding"] == "VTI"
        # Sector breakdown should sum to 100%
        sector_total = sum(result["by_sector"].values())
        assert sector_total == pytest.approx(100.0, abs=0.5)

    def test_concentration_risk_single_stock(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        holdings = [
            {"ticker": "TSLA", "current_value": 500000, "asset_class": "stock", "sector": "Auto"},
            {"ticker": "VTI", "current_value": 50000, "asset_class": "etf", "sector": "Broad Market"},
        ]
        result = PortfolioAnalyticsEngine.concentration_risk(holdings)
        assert result["single_stock_risk"] == "critical"  # >40%
        assert result["top_holding_pct"] > 90

    def test_concentration_risk_low(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        # 20 equally-weighted holdings
        holdings = [
            {"ticker": f"HOLD{i}", "current_value": 5000, "asset_class": "stock", "sector": f"Sector{i}"}
            for i in range(20)
        ]
        result = PortfolioAnalyticsEngine.concentration_risk(holdings)
        assert result["single_stock_risk"] == "low"
        assert result["top_holding_pct"] == 5.0

    def test_concentration_risk_empty(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        result = PortfolioAnalyticsEngine.concentration_risk([])
        assert result["top_holding_pct"] == 0
        assert result["single_stock_risk"] == "low"

    def test_performance_metrics(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        # Simulate 12 months of portfolio growth with one drawdown
        snapshots = [
            {"total_portfolio_value": 100000},
            {"total_portfolio_value": 105000},
            {"total_portfolio_value": 108000},
            {"total_portfolio_value": 102000},  # drawdown
            {"total_portfolio_value": 110000},
            {"total_portfolio_value": 115000},
            {"total_portfolio_value": 118000},
            {"total_portfolio_value": 120000},
            {"total_portfolio_value": 116000},  # another drawdown
            {"total_portfolio_value": 122000},
            {"total_portfolio_value": 125000},
            {"total_portfolio_value": 130000},
        ]
        result = PortfolioAnalyticsEngine.performance_metrics(snapshots)
        assert result["time_weighted_return"] == pytest.approx(0.30, abs=0.01)
        assert result["max_drawdown"] > 0
        # Max drawdown should be from 108k to 102k = ~5.6%
        assert result["max_drawdown"] == pytest.approx(0.0556, abs=0.01)
        assert result["sharpe_ratio"] is not None
        assert result["volatility"] is not None
        assert result["period_months"] == 12

    def test_performance_metrics_insufficient_data(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        result = PortfolioAnalyticsEngine.performance_metrics([])
        assert result["time_weighted_return"] == 0
        assert result["sharpe_ratio"] is None
        assert result["max_drawdown"] == 0

    def test_net_worth_trend(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        snapshots = [
            {"snapshot_date": "2025-01-01", "net_worth": 400000},
            {"snapshot_date": "2025-06-01", "net_worth": 450000},
            {"snapshot_date": "2025-12-01", "net_worth": 520000},
        ]
        result = PortfolioAnalyticsEngine.net_worth_trend(snapshots)
        assert result["current_net_worth"] == 520000
        assert result["growth_rate"] == pytest.approx(0.30, abs=0.01)
        assert len(result["monthly_series"]) == 3

    def test_net_worth_trend_empty(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        result = PortfolioAnalyticsEngine.net_worth_trend([])
        assert result["monthly_series"] == []
        assert result["growth_rate"] == 0
        assert result["current_net_worth"] == 0

    def test_net_worth_trend_single_snapshot(self):
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        snapshots = [{"snapshot_date": "2025-01-01", "net_worth": 500000}]
        result = PortfolioAnalyticsEngine.net_worth_trend(snapshots)
        assert result["current_net_worth"] == 500000
        assert result["growth_rate"] == 0  # Can't compute growth from single point


# ═══════════════════════════════════════════════════════════════════════════
# Edge Case & Financial Sanity Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFinancialSanity:
    """Verify that outputs make financial sense for real HENRY scenarios."""

    def test_high_saver_gets_positive_insights(self):
        """A household saving 30% should have positive metrics."""
        from pipeline.analytics.insights import _income_analysis
        # 12 months of $25k income, $17.5k expenses = 30% savings rate
        txns = []
        tid = 1
        for m in range(1, 13):
            txns.append(SimpleNamespace(
                id=tid, amount=25000.0, effective_category="Paycheck",
                period_month=m, date=datetime(2025, m, 1), description="Paycheck",
            ))
            tid += 1
        result = _income_analysis(txns, income_outlier_ids=set())
        assert result["regular_monthly_median"] == 25000.0
        assert result["total_regular"] == 300000.0

    def test_retirement_budget_reasonable_amounts(self):
        """Retirement budget should produce sensible monthly amounts."""
        from pipeline.planning.retirement_budget import compute_retirement_budget
        lines = [
            {"category": "Groceries", "monthly_amount": 1200.0},
            {"category": "Mortgage & Rent", "monthly_amount": 3200.0},
            {"category": "Medical", "monthly_amount": 150.0},
            {"category": "Childcare & Education", "monthly_amount": 1500.0},
            {"category": "Vacation", "monthly_amount": 400.0},
            {"category": "Utilities", "monthly_amount": 350.0},
        ]
        result = compute_retirement_budget(lines, [], retirement_age=65, debt_payoffs=[])
        # Mortgage + childcare removed (~$4,700), medical doubled (+$150), vacation up (+$200)
        # Should be significantly less than current
        assert result["retirement_monthly_total"] < result["current_monthly_total"]
        # But not zero — people still have expenses in retirement
        assert result["retirement_monthly_total"] > 1000
        # Annual retirement budget should be a realistic number (not absurdly low/high)
        assert 12000 < result["retirement_annual_total"] < result["current_annual_total"]

    def test_portfolio_metrics_financial_validity(self):
        """Portfolio metrics should be within reasonable financial ranges."""
        from pipeline.planning.portfolio_analytics import PortfolioAnalyticsEngine
        # 8% annual return over 12 months
        start = 100000
        monthly_return = (1.08 ** (1 / 12)) - 1
        snapshots = []
        val = start
        for i in range(13):
            snapshots.append({"total_portfolio_value": round(val, 2)})
            val *= (1 + monthly_return)

        result = PortfolioAnalyticsEngine.performance_metrics(snapshots)
        assert result["time_weighted_return"] == pytest.approx(0.08, abs=0.01)
        assert result["max_drawdown"] == 0  # No drawdowns in steady growth
        assert result["volatility"] is not None
