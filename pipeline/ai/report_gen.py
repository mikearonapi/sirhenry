"""
Monthly and annual financial report generator.
Computes FinancialPeriod summaries from transaction data and optionally
generates Claude-written AI insights for the monthly report narrative.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import upsert_financial_period
from pipeline.db.schema import Transaction
from pipeline.utils import CLAUDE_MODEL, get_claude_client, call_claude_with_retry

load_dotenv()
logger = logging.getLogger(__name__)

# Categories that represent internal money movements between accounts.
# These must be excluded from income/expense totals to avoid double-counting.
# - "Transfer": checking ↔ savings, checking ↔ external accounts
# - "Credit Card Payment": checking → credit card (charges already counted on CC)
# - "Savings": transfers from checking to savings sub-accounts
INTERNAL_TRANSFER_CATEGORIES = {"Transfer", "Credit Card Payment", "Savings"}


async def compute_period_summary(
    session: AsyncSession,
    year: int,
    month: Optional[int] = None,
    segment: str = "all",
) -> dict[str, Any]:
    """
    Compute income/expense summary for a given period.
    If month is None, computes annual summary.
    """
    q = select(
        Transaction.effective_segment,
        Transaction.effective_category,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).where(
        Transaction.period_year == year,
        Transaction.is_excluded == False,
    )
    if month:
        q = q.where(Transaction.period_month == month)
    if segment != "all":
        q = q.where(Transaction.effective_segment == segment)
    q = q.group_by(Transaction.effective_segment, Transaction.effective_category)

    result = await session.execute(q)
    rows = result.all()

    total_income = 0.0
    total_expenses = 0.0
    w2_income = 0.0
    investment_income = 0.0
    board_income = 0.0
    business_expenses = 0.0
    personal_expenses = 0.0
    income_breakdown: dict[str, float] = {}
    expense_breakdown: dict[str, float] = {}

    for row in rows:
        seg = row.effective_segment or "personal"
        cat = row.effective_category or "Unknown"
        total = float(row.total or 0)

        if cat in INTERNAL_TRANSFER_CATEGORIES:
            continue

        if total > 0:
            total_income += total
            income_breakdown[cat] = income_breakdown.get(cat, 0) + total
            if cat == "W-2 Wages":
                w2_income += total
            elif cat in ("Dividend Income", "Interest Income", "Capital Gain"):
                investment_income += total
            elif cat == "Board / Director Income":
                board_income += total
        else:
            total_expenses += abs(total)
            expense_breakdown[cat] = expense_breakdown.get(cat, 0) + abs(total)
            if seg == "business":
                business_expenses += abs(total)
            else:
                personal_expenses += abs(total)

    net_cash_flow = total_income - total_expenses

    period_data = {
        "year": year,
        "month": month,
        "segment": segment,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_cash_flow": net_cash_flow,
        "w2_income": w2_income,
        "investment_income": investment_income,
        "board_income": board_income,
        "business_expenses": business_expenses,
        "personal_expenses": personal_expenses,
        "expense_breakdown": json.dumps(
            dict(sorted(expense_breakdown.items(), key=lambda x: x[1], reverse=True))
        ),
        "income_breakdown": json.dumps(
            dict(sorted(income_breakdown.items(), key=lambda x: x[1], reverse=True))
        ),
    }

    await upsert_financial_period(session, period_data)
    return period_data


async def recompute_all_periods(session: AsyncSession, year: int) -> list[dict[str, Any]]:
    """Recompute all monthly + annual period summaries for a year, across all segments."""
    results = []
    for segment in ("all", "personal", "business", "investment"):
        for month in range(1, 13):
            data = await compute_period_summary(session, year, month=month, segment=segment)
            results.append(data)
        annual = await compute_period_summary(session, year, month=None, segment=segment)
        results.append(annual)
    logger.info(f"Recomputed {len(results)} period summaries for {year}.")
    return results


async def generate_monthly_insights(
    session: AsyncSession,
    year: int,
    month: int,
    period_data: dict[str, Any],
    prior_month_data: Optional[dict[str, Any]] = None,
) -> str:
    """
    Generate a narrative AI insights summary for the monthly report.
    Returns markdown-formatted text.
    """
    client = get_claude_client()
    month_name = datetime(year, month, 1).strftime("%B %Y")

    expense_breakdown = json.loads(period_data.get("expense_breakdown") or "{}")
    income_breakdown = json.loads(period_data.get("income_breakdown") or "{}")

    prior_context = ""
    if prior_month_data:
        prior_context = f"""
Prior month comparison:
- Income: ${prior_month_data['total_income']:,.0f} vs ${period_data['total_income']:,.0f} this month
- Expenses: ${prior_month_data['total_expenses']:,.0f} vs ${period_data['total_expenses']:,.0f} this month
- Net: ${prior_month_data['net_cash_flow']:,.0f} vs ${period_data['net_cash_flow']:,.0f} this month
"""

    prompt = f"""You are a personal financial advisor reviewing monthly finances.

Month: {month_name}

Financial Summary:
- Total Income: ${period_data['total_income']:,.2f}
- Total Expenses: ${period_data['total_expenses']:,.2f}
- Net Cash Flow: ${period_data['net_cash_flow']:,.2f}
- Business Expenses: ${period_data['business_expenses']:,.2f}
- W-2 Income: ${period_data['w2_income']:,.2f}
- Investment Income: ${period_data['investment_income']:,.2f}
- Board Income: ${period_data['board_income']:,.2f}

Top Expense Categories: {json.dumps(dict(list(expense_breakdown.items())[:8]), indent=2)}
Income Sources: {json.dumps(income_breakdown, indent=2)}
{prior_context}

Provide a concise 3-5 paragraph financial review with:
1. Overall financial health summary for the month
2. Notable spending patterns or anomalies
3. Business expense documentation reminder (any categories that need receipts)
4. Any tax-relevant observations (e.g., large charitable donations, business meals that need documentation)
5. One or two actionable suggestions for next month

Keep the tone professional but conversational. Format as markdown. Be specific with numbers."""

    response = call_claude_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()
