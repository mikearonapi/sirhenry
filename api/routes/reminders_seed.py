"""Reminder seeding, categorization, and bulk operations.

Contains reminder definition generators and the seed_all_reminders function
used both by the API seed endpoints and by main.py at startup.
"""
import logging
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from pipeline.db import Reminder

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reminders"])

# ---------------------------------------------------------------------------
# Reminder definitions — year-relative, generated dynamically
# ---------------------------------------------------------------------------

RECURRENCE_DELTAS = {
    "monthly": relativedelta(months=1),
    "quarterly": relativedelta(months=3),
    "semi-annual": relativedelta(months=6),
    "annual": relativedelta(years=1),
}


def _generate_tax_reminders(year: int) -> list[dict]:
    """Federal + state tax deadlines for a given filing year.
    `year` = the tax year being filed (reminders span year -> year+1)."""
    fy = year + 1  # filing year
    return [
        # -- Estimated quarterly payments --
        {"title": f"Q4 {year} Estimated Tax Payment (Federal & State)",
         "due_date": f"{fy}-01-15", "reminder_type": "tax",
         "advance_notice": "14_days", "is_recurring": True, "recurrence_rule": "annual",
         "description": "Pay federal (1040-ES) and state estimated tax for Q4. Covers W-2 underwithholding, K-1/partnership income, consulting SE tax, and investment income."},
        {"title": f"Q1 {fy} Estimated Tax Payment (Federal & State)",
         "due_date": f"{fy}-04-15", "reminder_type": "tax",
         "advance_notice": "14_days", "is_recurring": True, "recurrence_rule": "annual",
         "description": "Pay federal and state estimated tax for Q1. Covers any K-1/partnership income, consulting SE tax, and investment income not covered by withholding."},
        {"title": f"Q2 {fy} Estimated Tax Payment (Federal & State)",
         "due_date": f"{fy}-06-16", "reminder_type": "tax",
         "advance_notice": "14_days", "is_recurring": True, "recurrence_rule": "annual",
         "description": "Pay federal and state estimated tax for Q2."},
        {"title": f"Q3 {fy} Estimated Tax Payment (Federal & State)",
         "due_date": f"{fy}-09-15", "reminder_type": "tax",
         "advance_notice": "14_days", "is_recurring": True, "recurrence_rule": "annual",
         "description": "Pay federal and state estimated tax for Q3."},

        # -- Document collection --
        {"title": f"W-2 / 1099-NEC Due to Recipients ({year} tax year)",
         "due_date": f"{fy}-01-31", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": "W-2s from employers and any 1099-NECs for contract income should arrive by this date."},
        {"title": f"Collect 1099-B/DIV/INT from Brokerages ({year} tax year)",
         "due_date": f"{fy}-02-15", "reminder_type": "tax",
         "advance_notice": "7_days",
         "description": (
             "Collect 1099-B, 1099-DIV, and 1099-INT from all brokerage and investment accounts. "
             "Brokerages must issue by Feb 15 but corrections often arrive through mid-March. "
             "Wait for corrected forms before filing."
         )},
        {"title": f"Verify All Tax Documents Received ({year} tax year)",
         "due_date": f"{fy}-03-01", "reminder_type": "tax",
         "advance_notice": "7_days",
         "description": (
             "Verify you have: W-2(s) from all employers, K-1(s) from partnerships/S-corps (if applicable), "
             "1099-B/DIV/INT from all brokerages, 1099-NEC for any consulting income, "
             "1098 mortgage interest. Follow up on anything missing."
         )},

        # -- Filing deadlines --
        {"title": f"K-1 Deadline — Partnerships & S-Corps ({year} tax year)",
         "due_date": f"{fy}-03-15", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": "K-1s from partnerships and S-corps should arrive by this date (entity return deadline). Follow up immediately if not received."},
        {"title": f"Review Business Expenses for Tax Filing ({year} tax year)",
         "due_date": f"{fy}-03-15", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": (
             "Review all business/consulting expenses tracked in this system before filing. "
             "Ensure business transactions are properly categorized and receipts are in order."
         )},
        {"title": f"{year} Federal Tax Return Deadline (or file extension)",
         "due_date": f"{fy}-04-15", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": "File federal return or Form 4868 extension. If you earned income in multiple states, file in each applicable state."},
        {"title": f"{year} Extended Tax Return Deadline",
         "due_date": f"{fy}-10-15", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": "Final deadline if extension was filed."},

        # -- Mid-year tax check-in --
        {"title": f"Mid-Year Estimated Payment Review ({fy})",
         "due_date": f"{fy}-07-15", "reminder_type": "tax",
         "advance_notice": "14_days", "is_recurring": True, "recurrence_rule": "annual",
         "description": (
             "Review YTD income vs estimated payments. Are W-2 withholdings on track? "
             "Has K-1/partnership income changed? Any consulting income not covered by withholding? "
             "Adjust Q3/Q4 estimated payments if needed to avoid underpayment penalty."
         )},

        # -- Retirement & savings --
        {"title": f"Max Out 401(k) Contributions ($23,500 for {year})",
         "due_date": f"{year}-12-31", "amount": 23500, "reminder_type": "tax",
         "advance_notice": "14_days", "is_recurring": True, "recurrence_rule": "annual",
         "description": "Review paycheck deductions to ensure you hit the annual 401(k) limit. Check catch-up contribution eligibility if age 50+."},
        {"title": f"IRA Contribution Deadline ({year} tax year)",
         "due_date": f"{fy}-04-15", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": "Last day to make IRA contributions ($7,000) for prior tax year. Consider backdoor Roth if income exceeds direct Roth limits."},
        {"title": f"HSA Contribution Deadline ({year} tax year)",
         "due_date": f"{fy}-04-15", "amount": 8550, "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": "Last day to make HSA contributions ($8,550 family) for prior tax year. Only if enrolled in HDHP."},

        # -- Year-end planning --
        {"title": f"{year} Year-End Tax Planning Review",
         "due_date": f"{year}-11-15", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": (
             "Comprehensive year-end review: (1) Harvest capital losses in brokerage accounts, "
             "(2) Review estimated payment accuracy, (3) Maximize charitable giving (consider "
             "donor-advised fund), (4) Review Section 199A QBI deduction eligibility for any "
             "business income, (5) Check state tax liability across all filing states."
         )},
        {"title": f"Charitable Donations Deadline ({year})",
         "due_date": f"{year}-12-31", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": "Last day for charitable donations to count for this tax year. Gather receipts for all donations >$250."},

        # -- Section 195 / startup costs --
        {"title": f"Section 195 Amortization — Business Startup Costs ({year})",
         "due_date": f"{year}-12-31", "reminder_type": "tax",
         "advance_notice": "14_days",
         "description": (
             "If any business startup costs are being amortized under Section 195, "
             "ensure the annual amortization deduction is captured on the Schedule C return."
         )},
    ]


def _generate_amazon_reminders(year: int) -> list[dict]:
    """Quarterly Amazon data dump reminders."""
    return [
        {"title": f"Request Amazon data dump (Q{q} {year})",
         "due_date": f"{year}-{month:02d}-15",
         "reminder_type": "custom",
         "advance_notice": "7_days",
         "is_recurring": True, "recurrence_rule": "quarterly",
         "description": (
             "Go to https://www.amazon.com/privacy/data-request -> "
             "request 'Order History'. Import the CSV via the dashboard "
             "or: python -m pipeline.importers.amazon --file <path>"
         )}
        for q, month in [(1, 1), (2, 4), (3, 7), (4, 10)]
    ]


def _generate_financial_reminders(year: int) -> list[dict]:
    """Recurring financial health and system maintenance reminders."""
    return [
        # -- Monthly / quarterly reviews --
        {"title": f"Monthly Financial Review — Jan {year}",
         "due_date": f"{year}-01-05", "reminder_type": "custom",
         "advance_notice": "3_days",
         "is_recurring": True, "recurrence_rule": "monthly",
         "description": (
             "Review last month's spending vs budget. Check uncategorized transactions. "
             "Verify recurring charges. Review Amazon reconciliation for unmatched items."
         )},

        {"title": f"Quarterly Budget & Goals Check-In (Q1 {year})",
         "due_date": f"{year}-04-05", "reminder_type": "custom",
         "advance_notice": "7_days",
         "is_recurring": True, "recurrence_rule": "quarterly",
         "description": (
             "Quarterly financial review: (1) Are we on track for savings goals? "
             "(2) Any budget categories consistently over/under? (3) Review large expenses "
             "and upcoming planned purchases. (4) Check progress toward financial goals."
         )},

        {"title": f"Reimbursable Expense Reconciliation (Q1 {year})",
         "due_date": f"{year}-04-01", "reminder_type": "custom",
         "advance_notice": "7_days",
         "is_recurring": True, "recurrence_rule": "quarterly",
         "description": (
             "Review all transactions tagged 'reimbursable'. Verify each has been "
             "submitted and reimbursed by the appropriate employer. Flag any outstanding items."
         )},

        # -- System maintenance --
        {"title": f"Verify Plaid Bank Connections (Q1 {year})",
         "due_date": f"{year}-01-15", "reminder_type": "custom",
         "advance_notice": "7_days",
         "is_recurring": True, "recurrence_rule": "quarterly",
         "description": "Check Plaid connection status in Settings. Re-authenticate any expired or errored connections. Verify transaction sync is current."},

        # -- Annual financial health --
        {"title": f"Pull Free Annual Credit Report ({year})",
         "due_date": f"{year}-01-15", "reminder_type": "custom",
         "advance_notice": "7_days",
         "is_recurring": True, "recurrence_rule": "annual",
         "description": "Request free credit reports at https://www.annualcreditreport.com — check all 3 bureaus (Equifax, Experian, TransUnion)."},

        {"title": f"Annual Insurance Review ({year})",
         "due_date": f"{year}-10-01", "reminder_type": "custom",
         "advance_notice": "14_days",
         "is_recurring": True, "recurrence_rule": "annual",
         "description": (
             "Review all insurance policies before open enrollment: health (HDHP vs PPO), "
             "dental, vision, auto, homeowners/renters, umbrella, life, disability. "
             "Compare premiums, deductibles, and coverage limits."
         )},

        {"title": f"Open Enrollment — Employer Benefits ({year})",
         "due_date": f"{year}-11-01", "reminder_type": "custom",
         "advance_notice": "14_days",
         "is_recurring": True, "recurrence_rule": "annual",
         "description": (
             "Open enrollment period for employer benefits. Review and select: health plan (impacts HSA "
             "eligibility), dental, vision, FSA/dependent care, life insurance, disability, "
             "401(k) contribution rate, legal plan. Deadline is typically mid-November."
         )},

        {"title": f"Review Beneficiaries & Estate Docs ({year})",
         "due_date": f"{year}-06-01", "reminder_type": "custom",
         "advance_notice": "14_days",
         "is_recurring": True, "recurrence_rule": "annual",
         "description": (
             "Verify beneficiaries on: 401(k), IRA, life insurance, all brokerage accounts. "
             "Review will, trust, power of attorney, healthcare directive. "
             "Update if any life changes occurred."
         )},

        {"title": f"Subscription Audit ({year})",
         "due_date": f"{year}-03-01", "reminder_type": "subscription",
         "advance_notice": "7_days",
         "is_recurring": True, "recurrence_rule": "semi-annual",
         "description": (
             "Review all recurring subscriptions and memberships. Cancel unused services. "
             "Check for price increases. Verify business vs personal split on shared "
             "subscriptions (Cursor, GitHub, cloud services, etc.)."
         )},

        {"title": f"Net Worth & Investment Review ({year})",
         "due_date": f"{year}-07-01", "reminder_type": "custom",
         "advance_notice": "7_days",
         "is_recurring": True, "recurrence_rule": "semi-annual",
         "description": (
             "Review investment allocation across all brokerage and retirement accounts. "
             "Check asset allocation vs target. Review net worth trend. "
             "Rebalance if any asset class is >5% off target."
         )},
    ]


async def seed_all_reminders(session: AsyncSession) -> dict[str, int]:
    """Seed all reminder categories for the current and next year.
    Idempotent: skips any reminder whose exact title already exists as pending/snoozed."""
    now = datetime.now(timezone.utc)
    current_year = now.year

    all_reminders: list[dict] = []
    for year in [current_year - 1, current_year, current_year + 1]:
        all_reminders.extend(_generate_tax_reminders(year))
    for year in [current_year, current_year + 1]:
        all_reminders.extend(_generate_amazon_reminders(year))
        all_reminders.extend(_generate_financial_reminders(year))

    # Only seed reminders whose due date is in the future (or within 30 days past for overdue visibility)
    cutoff = now - relativedelta(days=30)

    seeded_by_type: dict[str, int] = {}
    for reminder_def in all_reminders:
        due = datetime.fromisoformat(reminder_def["due_date"])
        if due < cutoff:
            continue

        existing = await session.execute(
            select(Reminder).where(
                Reminder.title == reminder_def["title"],
                Reminder.status.in_(["pending", "snoozed"]),
            )
        )
        if existing.scalar_one_or_none():
            continue

        r = Reminder(
            title=reminder_def["title"],
            description=reminder_def.get("description"),
            reminder_type=reminder_def.get("reminder_type", "custom"),
            due_date=due,
            amount=reminder_def.get("amount"),
            advance_notice=reminder_def.get("advance_notice", "7_days"),
            is_recurring=reminder_def.get("is_recurring", False),
            recurrence_rule=reminder_def.get("recurrence_rule"),
        )
        session.add(r)
        rtype = r.reminder_type
        seeded_by_type[rtype] = seeded_by_type.get(rtype, 0) + 1

    await session.flush()
    return seeded_by_type


def _advance_recurring(reminder: Reminder) -> Reminder | None:
    """Given a completed recurring reminder, create the next occurrence.
    Returns the new Reminder or None if not recurring."""
    if not reminder.is_recurring or not reminder.recurrence_rule:
        return None

    delta = RECURRENCE_DELTAS.get(reminder.recurrence_rule)
    if not delta:
        logger.warning(f"Unknown recurrence_rule '{reminder.recurrence_rule}' on reminder #{reminder.id}")
        return None

    due = reminder.due_date if isinstance(reminder.due_date, datetime) else datetime.fromisoformat(str(reminder.due_date))
    next_due = due + delta

    # For year-relative titles, advance the year in the title
    old_year = str(due.year)
    new_year = str(next_due.year)
    new_title = reminder.title.replace(old_year, new_year) if old_year in reminder.title else reminder.title

    return Reminder(
        title=new_title,
        description=reminder.description,
        reminder_type=reminder.reminder_type,
        due_date=next_due,
        amount=reminder.amount,
        advance_notice=reminder.advance_notice,
        is_recurring=True,
        recurrence_rule=reminder.recurrence_rule,
        related_account_id=reminder.related_account_id,
    )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.post("/seed-all", response_model=dict)
async def seed_all(session: AsyncSession = Depends(get_session)):
    """Seed all reminder categories (tax, Amazon, financial, Plaid)."""
    result = await seed_all_reminders(session)
    total = sum(result.values())
    return {"seeded": total, "by_type": result}


@router.post("/seed-tax-deadlines", response_model=dict)
async def seed_tax_deadlines(session: AsyncSession = Depends(get_session)):
    """Seed tax deadlines only (backward-compatible with existing UI button)."""
    result = await seed_all_reminders(session)
    return {"seeded": sum(result.values())}
