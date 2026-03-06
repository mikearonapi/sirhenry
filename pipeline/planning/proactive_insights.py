"""
Proactive Insights Engine — rules-based analysis that surfaces actionable
alerts without requiring AI. Runs on user data and returns prioritized insights.
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Budget,
    BusinessEntity,
    EquityGrant,
    Goal,
    HouseholdProfile,
    InsurancePolicy,
    RecurringTransaction,
    TaxItem,
    Transaction,
    VestingEvent,
)

logger = logging.getLogger(__name__)


async def compute_proactive_insights(session: AsyncSession) -> list[dict]:
    """Compute all proactive insights. Returns list sorted by severity."""
    insights: list[dict] = []

    insights.extend(await _underwithholding_gap(session))
    insights.extend(await _quarterly_estimated_tax(session))
    insights.extend(await _goal_milestones(session))
    insights.extend(await _budget_overruns(session))
    insights.extend(await _uncategorized_transactions(session))
    insights.extend(await _missing_tax_docs(session))
    insights.extend(await _upcoming_vests(session))
    insights.extend(await _insurance_renewals(session))

    # Sort: action > warning > info
    severity_order = {"action": 0, "warning": 1, "info": 2}
    insights.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 3))

    return insights[:10]  # Return top 10


# ---------------------------------------------------------------------------
# Individual insight generators
# ---------------------------------------------------------------------------

async def _underwithholding_gap(session: AsyncSession) -> list[dict]:
    """Detect RSU/equity underwithholding vs marginal tax rate."""
    today = date.today()
    year = today.year

    # Get upcoming vest income in next 12 months
    result = await session.execute(
        select(func.sum(VestingEvent.shares * EquityGrant.current_fmv))
        .join(EquityGrant, VestingEvent.grant_id == EquityGrant.id)
        .where(
            VestingEvent.vest_date >= today,
            VestingEvent.vest_date <= today + timedelta(days=365),
            VestingEvent.status == "upcoming",
            EquityGrant.is_active.is_(True),
        )
    )
    vest_income = result.scalar() or 0
    if vest_income < 10000:
        return []

    # Supplemental withholding is 22%, but marginal rate for HENRYs is 32-37%
    withholding_at_22 = vest_income * 0.22
    # Estimate marginal rate based on income
    household = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True)).limit(1)
    )
    profile = household.scalar_one_or_none()
    combined = (profile.combined_income or 0) if profile else 0

    if combined > 578125:
        marginal = 0.37
    elif combined > 364200:
        marginal = 0.35
    elif combined > 231250:
        marginal = 0.32
    elif combined > 190750:
        marginal = 0.24
    else:
        marginal = 0.22

    if marginal <= 0.22:
        return []

    gap = vest_income * (marginal - 0.22)
    return [{
        "type": "underwithholding",
        "severity": "warning",
        "title": "Equity Underwithholding Gap",
        "message": f"Your upcoming equity vests (~${vest_income:,.0f}) will be withheld at 22%, "
                   f"but your marginal rate is {marginal:.0%}. Estimated gap: ${gap:,.0f}.",
        "link_to": "/equity-comp",
        "value": gap,
    }]


async def _quarterly_estimated_tax(session: AsyncSession) -> list[dict]:
    """Remind self-employed users about quarterly estimated payments."""
    today = date.today()
    year = today.year

    # Check if user has business entities
    biz_count = (await session.execute(
        select(func.count(BusinessEntity.id)).where(BusinessEntity.is_active.is_(True))
    )).scalar() or 0
    if biz_count == 0:
        return []

    # Q1: Apr 15, Q2: Jun 15, Q3: Sep 15, Q4: Jan 15 next year
    due_dates = [
        (date(year, 4, 15), "Q1"),
        (date(year, 6, 15), "Q2"),
        (date(year, 9, 15), "Q3"),
        (date(year + 1, 1, 15), "Q4"),
    ]

    insights = []
    for due, quarter in due_dates:
        days_until = (due - today).days
        if 0 < days_until <= 30:
            insights.append({
                "type": "estimated_tax",
                "severity": "action",
                "title": f"{quarter} Estimated Tax Due",
                "message": f"Quarterly estimated tax payment due {due.strftime('%B %d')} ({days_until} days).",
                "link_to": "/tax-strategy",
                "value": None,
            })

    return insights


async def _goal_milestones(session: AsyncSession) -> list[dict]:
    """Celebrate goal progress milestones."""
    result = await session.execute(
        select(Goal).where(Goal.status == "active")
    )
    insights = []
    for goal in result.scalars():
        if not goal.target_amount or goal.target_amount == 0:
            continue
        pct = goal.current_amount / goal.target_amount * 100
        # Check for milestone proximity (within 2%)
        for milestone in [25, 50, 75, 90]:
            if milestone - 2 <= pct <= milestone + 2:
                insights.append({
                    "type": "goal_milestone",
                    "severity": "info",
                    "title": f"{goal.name}: {milestone}% Complete",
                    "message": f"${goal.current_amount:,.0f} of ${goal.target_amount:,.0f} target reached.",
                    "link_to": "/goals",
                    "value": pct,
                })
                break

    return insights


async def _budget_overruns(session: AsyncSession) -> list[dict]:
    """Detect categories significantly over budget mid-month."""
    today = date.today()
    if today.day < 10:
        return []  # Too early in month to warn

    year, month = today.year, today.month
    day_pct = today.day / 30  # Approximate month progress

    # Get budgets for this month
    budget_result = await session.execute(
        select(Budget).where(Budget.year == year, Budget.month == month)
    )
    budgets = {b.category: b.budget_amount for b in budget_result.scalars()}
    if not budgets:
        return []

    # Get actual spending by category
    actual_result = await session.execute(
        select(
            Transaction.effective_category,
            func.sum(Transaction.amount * -1),
        ).where(
            Transaction.period_year == year,
            Transaction.period_month == month,
            Transaction.amount < 0,
            Transaction.is_excluded.is_(False),
            Transaction.effective_category.isnot(None),
        ).group_by(Transaction.effective_category)
    )
    actuals = {r[0]: r[1] for r in actual_result if r[0]}

    insights = []
    for cat, budgeted in budgets.items():
        actual = actuals.get(cat, 0)
        if budgeted <= 0:
            continue
        # Projected overage: if spending at current pace exceeds budget
        projected = actual / day_pct if day_pct > 0 else actual
        if projected > budgeted * 1.2 and actual > budgeted * 0.8:
            overage_pct = round((projected / budgeted - 1) * 100)
            insights.append({
                "type": "budget_overrun",
                "severity": "warning",
                "title": f"{cat} Over Budget",
                "message": f"${actual:,.0f} spent of ${budgeted:,.0f} budget with "
                           f"{30 - today.day} days left. Projected {overage_pct}% over.",
                "link_to": "/budget",
                "value": actual - budgeted,
            })

    return insights[:3]  # Max 3 budget warnings


async def _uncategorized_transactions(session: AsyncSession) -> list[dict]:
    """Alert about uncategorized transactions."""
    count = (await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.effective_category.is_(None),
            Transaction.is_excluded.is_(False),
            Transaction.is_manually_reviewed.is_(False),
        )
    )).scalar() or 0

    if count < 10:
        return []

    return [{
        "type": "uncategorized",
        "severity": "info",
        "title": f"{count} Uncategorized Transactions",
        "message": "Run AI categorization or review manually for accurate budgets and tax reports.",
        "link_to": "/transactions",
        "value": count,
    }]


async def _missing_tax_docs(session: AsyncSession) -> list[dict]:
    """Check for expected tax documents that haven't been uploaded."""
    today = date.today()
    year = today.year

    # Only relevant Jan-Apr (tax season)
    if today.month > 4:
        return []

    # Get prior year payers
    prior = await session.execute(
        select(TaxItem.form_type, TaxItem.payer_name)
        .where(TaxItem.tax_year == year - 1)
    )
    expected = {(r[0], r[1]) for r in prior}

    # Get current year uploads
    current = await session.execute(
        select(TaxItem.form_type, TaxItem.payer_name)
        .where(TaxItem.tax_year == year)
    )
    received = {(r[0], r[1]) for r in current}

    missing = expected - received
    if not missing:
        return []

    form_labels = {
        "w2": "W-2", "1099_nec": "1099-NEC", "1099_div": "1099-DIV",
        "1099_b": "1099-B", "1099_int": "1099-INT", "k1": "K-1",
    }
    names = [f"{form_labels.get(ft, ft)} from {pn}" for ft, pn in list(missing)[:3]]
    more = f" and {len(missing) - 3} more" if len(missing) > 3 else ""

    return [{
        "type": "missing_tax_docs",
        "severity": "action" if today.month >= 2 else "info",
        "title": f"{len(missing)} Expected Tax Documents Missing",
        "message": f"Still waiting for: {', '.join(names)}{more}.",
        "link_to": "/tax-documents",
        "value": len(missing),
    }]


async def _upcoming_vests(session: AsyncSession) -> list[dict]:
    """Alert about equity vesting events in the next 30 days."""
    today = date.today()
    soon = today + timedelta(days=30)

    result = await session.execute(
        select(VestingEvent, EquityGrant)
        .join(EquityGrant, VestingEvent.grant_id == EquityGrant.id)
        .where(
            VestingEvent.vest_date >= today,
            VestingEvent.vest_date <= soon,
            VestingEvent.status == "upcoming",
        )
    )
    insights = []
    for vest, grant in result:
        value = (vest.shares or 0) * (grant.current_fmv or 0)
        if value < 1000:
            continue
        days = (vest.vest_date - today).days
        insights.append({
            "type": "upcoming_vest",
            "severity": "info",
            "title": f"{grant.employer_name} Vest in {days} Days",
            "message": f"{vest.shares:,.0f} shares (~${value:,.0f}) vesting {vest.vest_date.strftime('%b %d')}.",
            "link_to": "/equity-comp",
            "value": value,
        })

    return insights[:2]


async def _insurance_renewals(session: AsyncSession) -> list[dict]:
    """Alert about insurance policies renewing in the next 60 days."""
    today = date.today()
    soon = today + timedelta(days=60)

    result = await session.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.is_active.is_(True),
            InsurancePolicy.renewal_date.isnot(None),
            InsurancePolicy.renewal_date >= today,
            InsurancePolicy.renewal_date <= soon,
        )
    )
    insights = []
    for policy in result.scalars():
        days = (policy.renewal_date - today).days
        insights.append({
            "type": "insurance_renewal",
            "severity": "info",
            "title": f"{policy.policy_type.title()} Insurance Renewing",
            "message": f"{policy.provider or 'Policy'} renews in {days} days ({policy.renewal_date.strftime('%b %d')}).",
            "link_to": "/insurance",
            "value": policy.annual_premium,
        })

    return insights
