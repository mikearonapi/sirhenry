"""
AI-powered financial chatbot using Claude tool_use.

The chatbot can search transactions, explain categories, recategorize,
get spending summaries, tax info, and more. It runs an agentic loop:
  1. User message + history sent to Claude with tool definitions
  2. Claude responds with text or tool_use blocks
  3. Backend executes tools against the DB
  4. Tool results sent back to Claude for final response
"""
import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import (
    Account,
    BusinessEntity,
    FinancialPeriod,
    TaxStrategy,
    Transaction,
)
from pipeline.db.schema_extended import Budget, RecurringTransaction
from pipeline.utils import CLAUDE_MODEL

load_dotenv()
logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8

_SYSTEM_PROMPT_BASE = """You are Sir Henry, a senior personal financial advisor and CPA assistant embedded in the SirHENRY platform. You have deep access to the household's complete financial data and can take real actions on their behalf.

## Your Role
You are the household's dedicated AI financial advisor. You know their financial situation intimately based on data in the system.

## What You Can Do
1. **Search & Analyze** — Find any transaction by description, date, amount, category. Cross-reference spending patterns.
2. **Explain & Educate** — Tell them exactly what a charge is, why it's categorized a certain way, whether it's tax-deductible.
3. **Recategorize & Correct** — Fix miscategorized transactions immediately. Change category, tax category, segment, or business entity.
4. **Spending Insights** — Break down spending by category and period. Spot anomalies, trends, and opportunities to save.
5. **Tax Strategy** — Surface tax optimization opportunities. Explain deduction eligibility. Flag items that need documentation.
6. **Budget Coaching** — Show budget vs. actual, highlight overspending, suggest adjustments.
7. **Goal Tracking** — Help evaluate progress toward financial goals and whether spending habits support them.
8. **Subscription Audit** — Review recurring charges, flag ones that may no longer be needed, calculate potential savings.

## How to Respond
- **Be specific with numbers.** Always include dollar amounts, dates, percentages. Never be vague.
- **Use markdown formatting.** Use **bold** for key figures, bullet lists for breakdowns, and tables when comparing data.
- **Be proactive.** If you notice something worth mentioning while answering a question (e.g., a miscategorized charge, an unusual spike, a tax opportunity), mention it.
- **Show your work.** When you look up data, briefly summarize what you found before giving your analysis.
- **Be actionable.** Don't just describe problems — recommend specific steps. If you can fix it right now (like recategorizing), offer to do so.
- **Think like a CPA.** Every transaction has tax implications. Note when something is deductible, when receipts are needed, when a charge affects their estimated tax.
- **Be conversational but professional.** You're a trusted advisor, not a robot. Be warm but precise.

## Formatting Guidelines
- Use **bold** for dollar amounts and key metrics
- Use bullet points (•) for lists of transactions or categories
- Use markdown tables for comparisons (budget vs actual, month-over-month)
- When listing transactions, format as: `date | description | $amount | category`
- When you make a change, clearly state: what was changed, from what, to what
- Keep responses focused but thorough — aim for the detail level of a professional financial review"""


async def _build_system_prompt(session: AsyncSession) -> str:
    """Build the Sir Henry system prompt with dynamic household context from DB."""
    from sqlalchemy import select as sa_select
    from pipeline.db.schema import HouseholdProfile, BusinessEntity

    lines: list[str] = []

    result = await session.execute(
        sa_select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    if household:
        filing = (household.filing_status or "unknown").upper()
        lines.append(f"- Filing status: {filing}")
        if household.spouse_a_name and household.spouse_a_employer:
            lines.append(f"- {household.spouse_a_name}: W-2 income from {household.spouse_a_employer}")
        elif household.spouse_a_name:
            lines.append(f"- Primary earner: {household.spouse_a_name}")
        if household.spouse_b_name and household.spouse_b_employer:
            lines.append(f"- {household.spouse_b_name}: income from {household.spouse_b_employer}")
        elif household.spouse_b_name:
            lines.append(f"- Spouse/partner: {household.spouse_b_name}")

    entity_result = await session.execute(
        sa_select(BusinessEntity).where(BusinessEntity.is_active == True)
    )
    active_entities = entity_result.scalars().all()
    if active_entities:
        entity_lines = [
            f"  - {e.name} ({e.entity_type}, {e.tax_treatment}"
            + (f", owner: {e.owner}" if e.owner else "")
            + ")"
            for e in active_entities
        ]
        lines.append("- Active business entities:")
        lines.extend(entity_lines)

    if lines:
        household_section = "\n## Household Context\n" + "\n".join(lines)
        return _SYSTEM_PROMPT_BASE + household_section

    return _SYSTEM_PROMPT_BASE

TOOLS = [
    {
        "name": "search_transactions",
        "description": "Search transactions by description keyword, date range, amount range, category, segment, or account. Returns up to 20 matching transactions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search in transaction descriptions (case-insensitive partial match)",
                },
                "year": {"type": "integer", "description": "Filter by year (e.g. 2025)"},
                "month": {"type": "integer", "description": "Filter by month (1-12)"},
                "min_amount": {"type": "number", "description": "Minimum transaction amount (use negative for expenses)"},
                "max_amount": {"type": "number", "description": "Maximum transaction amount"},
                "category": {"type": "string", "description": "Filter by expense category"},
                "segment": {
                    "type": "string",
                    "enum": ["personal", "business", "investment", "reimbursable"],
                    "description": "Filter by segment",
                },
                "limit": {"type": "integer", "description": "Max results to return (default 20, max 50)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_transaction_detail",
        "description": "Get full details of a specific transaction by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer", "description": "The transaction ID"},
            },
            "required": ["transaction_id"],
        },
    },
    {
        "name": "recategorize_transaction",
        "description": "Update a transaction's category, tax category, segment, or business entity. Sets override fields so the change persists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer", "description": "The transaction ID to update"},
                "category_override": {"type": "string", "description": "New expense category"},
                "tax_category_override": {"type": "string", "description": "New tax category (IRS schedule reference)"},
                "segment_override": {
                    "type": "string",
                    "enum": ["personal", "business", "investment", "reimbursable"],
                    "description": "New segment",
                },
                "business_entity_name": {
                    "type": "string",
                    "description": "Name of the business entity to assign (e.g. 'AutoRev'). Use null to clear.",
                },
                "notes": {"type": "string", "description": "Optional note to add to the transaction"},
            },
            "required": ["transaction_id"],
        },
    },
    {
        "name": "get_spending_summary",
        "description": "Get a spending breakdown by category for a given time period. Shows top categories with totals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Year to summarize"},
                "month": {"type": "integer", "description": "Month (1-12). Omit for full year."},
                "segment": {
                    "type": "string",
                    "enum": ["all", "personal", "business", "investment", "reimbursable"],
                    "description": "Segment filter (default: all)",
                },
            },
            "required": ["year"],
        },
    },
    {
        "name": "get_account_balances",
        "description": "Get all accounts with their current balances and transaction counts.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_tax_info",
        "description": "Get tax summary for a given year including W-2 wages, 1099 income, investment income, and active tax strategies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tax_year": {"type": "integer", "description": "Tax year (e.g. 2025)"},
            },
            "required": ["tax_year"],
        },
    },
    {
        "name": "get_budget_status",
        "description": "Get budget vs. actual spending for a given month. Shows each budgeted category with target, actual, and variance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["year", "month"],
        },
    },
    {
        "name": "get_recurring_expenses",
        "description": "Get all detected recurring expenses/subscriptions with their amounts and frequencies.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


async def _exec_tool(session: AsyncSession, tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a JSON string."""
    try:
        if tool_name == "search_transactions":
            return await _tool_search_transactions(session, tool_input)
        elif tool_name == "get_transaction_detail":
            return await _tool_get_transaction_detail(session, tool_input)
        elif tool_name == "recategorize_transaction":
            return await _tool_recategorize_transaction(session, tool_input)
        elif tool_name == "get_spending_summary":
            return await _tool_get_spending_summary(session, tool_input)
        elif tool_name == "get_account_balances":
            return await _tool_get_account_balances(session)
        elif tool_name == "get_tax_info":
            return await _tool_get_tax_info(session, tool_input)
        elif tool_name == "get_budget_status":
            return await _tool_get_budget_status(session, tool_input)
        elif tool_name == "get_recurring_expenses":
            return await _tool_get_recurring_expenses(session)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return json.dumps({"error": str(e)})


async def _tool_search_transactions(session: AsyncSession, params: dict) -> str:
    query_text = params.get("query", "")
    year = params.get("year")
    month = params.get("month")
    min_amount = params.get("min_amount")
    max_amount = params.get("max_amount")
    category = params.get("category")
    segment = params.get("segment")
    limit = min(params.get("limit", 20), 50)

    q = select(Transaction).where(Transaction.is_excluded == False)

    if query_text:
        q = q.where(Transaction.description.ilike(f"%{query_text}%"))
    if year:
        q = q.where(Transaction.period_year == year)
    if month:
        q = q.where(Transaction.period_month == month)
    if min_amount is not None:
        q = q.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        q = q.where(Transaction.amount <= max_amount)
    if category:
        q = q.where(Transaction.effective_category.ilike(f"%{category}%"))
    if segment:
        q = q.where(Transaction.effective_segment == segment)

    q = q.order_by(Transaction.date.desc()).limit(limit)
    result = await session.execute(q)
    rows = result.scalars().all()

    transactions = [
        {
            "id": t.id,
            "date": str(t.date)[:10],
            "description": t.description,
            "amount": t.amount,
            "category": t.effective_category,
            "tax_category": t.effective_tax_category,
            "segment": t.effective_segment,
            "ai_confidence": t.ai_confidence,
            "is_manually_reviewed": t.is_manually_reviewed,
            "notes": t.notes,
            "account_id": t.account_id,
        }
        for t in rows
    ]
    return json.dumps({"count": len(transactions), "transactions": transactions})


async def _tool_get_transaction_detail(session: AsyncSession, params: dict) -> str:
    tid = params["transaction_id"]
    result = await session.execute(
        select(Transaction).where(Transaction.id == tid)
    )
    t = result.scalar_one_or_none()
    if not t:
        return json.dumps({"error": f"Transaction {tid} not found"})

    account = None
    if t.account_id:
        acc_result = await session.execute(select(Account).where(Account.id == t.account_id))
        acc = acc_result.scalar_one_or_none()
        if acc:
            account = {"id": acc.id, "name": acc.name, "institution": acc.institution}

    entity = None
    if t.effective_business_entity_id:
        ent_result = await session.execute(
            select(BusinessEntity).where(BusinessEntity.id == t.effective_business_entity_id)
        )
        ent = ent_result.scalar_one_or_none()
        if ent:
            entity = {"id": ent.id, "name": ent.name, "tax_treatment": ent.tax_treatment}

    return json.dumps({
        "id": t.id,
        "date": str(t.date)[:10],
        "description": t.description,
        "amount": t.amount,
        "category": t.effective_category,
        "original_category": t.category,
        "category_override": t.category_override,
        "tax_category": t.effective_tax_category,
        "segment": t.effective_segment,
        "original_segment": t.segment,
        "segment_override": t.segment_override,
        "ai_confidence": t.ai_confidence,
        "is_manually_reviewed": t.is_manually_reviewed,
        "notes": t.notes,
        "account": account,
        "business_entity": entity,
        "is_excluded": t.is_excluded,
    })


async def _tool_recategorize_transaction(session: AsyncSession, params: dict) -> str:
    tid = params["transaction_id"]
    result = await session.execute(select(Transaction).where(Transaction.id == tid))
    t = result.scalar_one_or_none()
    if not t:
        return json.dumps({"error": f"Transaction {tid} not found"})

    values: dict[str, Any] = {"is_manually_reviewed": True}
    changes: list[str] = []

    if "category_override" in params and params["category_override"] is not None:
        values["category_override"] = params["category_override"]
        values["effective_category"] = params["category_override"]
        changes.append(f"category → {params['category_override']}")

    if "tax_category_override" in params and params["tax_category_override"] is not None:
        values["tax_category_override"] = params["tax_category_override"]
        values["effective_tax_category"] = params["tax_category_override"]
        changes.append(f"tax_category → {params['tax_category_override']}")

    if "segment_override" in params and params["segment_override"] is not None:
        values["segment_override"] = params["segment_override"]
        values["effective_segment"] = params["segment_override"]
        changes.append(f"segment → {params['segment_override']}")

    if "business_entity_name" in params:
        entity_name = params["business_entity_name"]
        if entity_name:
            ent_result = await session.execute(
                select(BusinessEntity).where(func.lower(BusinessEntity.name) == entity_name.lower())
            )
            ent = ent_result.scalar_one_or_none()
            if ent:
                values["business_entity_override"] = ent.id
                values["effective_business_entity_id"] = ent.id
                changes.append(f"business_entity → {ent.name}")
            else:
                return json.dumps({"error": f"Business entity '{entity_name}' not found"})
        else:
            values["business_entity_override"] = None
            values["effective_business_entity_id"] = None
            changes.append("business_entity → cleared")

    if "notes" in params and params["notes"] is not None:
        values["notes"] = params["notes"]
        changes.append(f"notes updated")

    if not changes:
        return json.dumps({"error": "No changes specified"})

    await session.execute(
        sa_update(Transaction).where(Transaction.id == tid).values(**values)
    )
    await session.flush()

    return json.dumps({
        "success": True,
        "transaction_id": tid,
        "description": t.description,
        "changes": changes,
    })


async def _tool_get_spending_summary(session: AsyncSession, params: dict) -> str:
    year = params["year"]
    month = params.get("month")
    segment = params.get("segment", "all")

    q = select(
        Transaction.effective_category,
        Transaction.effective_segment,
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

    q = q.group_by(Transaction.effective_category, Transaction.effective_segment)
    result = await session.execute(q)
    rows = result.all()

    total_income = 0.0
    total_expenses = 0.0
    expense_categories: dict[str, float] = {}
    income_categories: dict[str, float] = {}

    for row in rows:
        cat = row.effective_category or "Unknown"
        total = float(row.total or 0)
        if total > 0:
            total_income += total
            income_categories[cat] = income_categories.get(cat, 0) + total
        else:
            total_expenses += abs(total)
            expense_categories[cat] = expense_categories.get(cat, 0) + abs(total)

    top_expenses = sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)[:15]
    top_income = sorted(income_categories.items(), key=lambda x: x[1], reverse=True)[:10]

    period_label = f"{year}" if not month else f"{year}-{month:02d}"

    return json.dumps({
        "period": period_label,
        "segment": segment,
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_cash_flow": round(total_income - total_expenses, 2),
        "top_expense_categories": [{"category": c, "amount": round(a, 2)} for c, a in top_expenses],
        "top_income_sources": [{"source": c, "amount": round(a, 2)} for c, a in top_income],
    })


async def _tool_get_account_balances(session: AsyncSession) -> str:
    result = await session.execute(
        select(
            Account.id,
            Account.name,
            Account.account_type,
            Account.subtype,
            Account.institution,
            Account.is_active,
            func.count(Transaction.id).label("tx_count"),
            func.sum(Transaction.amount).label("balance"),
        )
        .outerjoin(Transaction, Transaction.account_id == Account.id)
        .group_by(Account.id)
    )
    rows = result.all()
    accounts = [
        {
            "id": r.id,
            "name": r.name,
            "type": r.account_type,
            "subtype": r.subtype,
            "institution": r.institution,
            "is_active": r.is_active,
            "transaction_count": r.tx_count or 0,
            "balance": round(float(r.balance or 0), 2),
        }
        for r in rows
    ]
    return json.dumps({"accounts": accounts})


async def _tool_get_tax_info(session: AsyncSession, params: dict) -> str:
    from pipeline.db import get_tax_summary, get_tax_strategies

    tax_year = params["tax_year"]
    summary = await get_tax_summary(session, tax_year)
    strategies = await get_tax_strategies(session, tax_year)

    strategy_list = [
        {
            "priority": s.priority,
            "title": s.title,
            "description": s.description[:200],
            "type": s.strategy_type,
            "savings_range": f"${s.estimated_savings_low:,.0f}–${s.estimated_savings_high:,.0f}"
            if s.estimated_savings_low and s.estimated_savings_high
            else None,
            "deadline": s.deadline,
        }
        for s in strategies
        if not s.is_dismissed
    ]

    return json.dumps({
        "tax_year": tax_year,
        "w2_wages": summary.get("w2_total_wages", 0),
        "w2_federal_withheld": summary.get("w2_federal_withheld", 0),
        "nec_income": summary.get("nec_total", 0),
        "dividend_income": summary.get("div_ordinary", 0),
        "qualified_dividends": summary.get("div_qualified", 0),
        "capital_gains_long": summary.get("capital_gains_long", 0),
        "capital_gains_short": summary.get("capital_gains_short", 0),
        "interest_income": summary.get("interest_income", 0),
        "active_strategies": strategy_list,
    })


async def _tool_get_budget_status(session: AsyncSession, params: dict) -> str:
    year = params["year"]
    month = params["month"]

    result = await session.execute(
        select(Budget).where(Budget.year == year, Budget.month == month)
    )
    budgets = result.scalars().all()

    if not budgets:
        return json.dumps({"message": f"No budgets set for {year}-{month:02d}"})

    # Get actuals for budgeted categories
    items = []
    for b in budgets:
        actual_result = await session.execute(
            select(func.sum(func.abs(Transaction.amount))).where(
                Transaction.period_year == year,
                Transaction.period_month == month,
                Transaction.effective_category == b.category,
                Transaction.is_excluded == False,
                Transaction.amount < 0,
            )
        )
        actual = float(actual_result.scalar() or 0)
        items.append({
            "category": b.category,
            "segment": b.segment,
            "budgeted": round(b.budget_amount, 2),
            "actual": round(actual, 2),
            "variance": round(b.budget_amount - actual, 2),
            "utilization_pct": round((actual / b.budget_amount * 100) if b.budget_amount else 0, 1),
        })

    total_budgeted = sum(i["budgeted"] for i in items)
    total_actual = sum(i["actual"] for i in items)

    return json.dumps({
        "year": year,
        "month": month,
        "total_budgeted": round(total_budgeted, 2),
        "total_actual": round(total_actual, 2),
        "total_variance": round(total_budgeted - total_actual, 2),
        "categories": sorted(items, key=lambda x: x["actual"], reverse=True),
    })


async def _tool_get_recurring_expenses(session: AsyncSession) -> str:
    result = await session.execute(
        select(RecurringTransaction).where(RecurringTransaction.status == "active")
    )
    items = result.scalars().all()

    recurring = [
        {
            "name": r.name,
            "amount": round(abs(r.amount), 2),
            "frequency": r.frequency,
            "category": r.category,
            "segment": r.segment,
            "annual_cost": round(r.annual_cost, 2) if r.annual_cost else None,
            "last_seen": str(r.last_seen_date)[:10] if r.last_seen_date else None,
        }
        for r in items
    ]

    total_monthly = sum(r["amount"] for r in recurring if r["frequency"] == "monthly")
    total_annual = sum(r["annual_cost"] or 0 for r in recurring)

    return json.dumps({
        "count": len(recurring),
        "total_monthly_cost": round(total_monthly, 2),
        "total_annual_cost": round(total_annual, 2),
        "subscriptions": recurring,
    })


async def run_chat(
    session: AsyncSession,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Run the chat agentic loop.

    Args:
        session: DB session
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts

    Returns:
        {"response": "...", "actions": [...], "tool_calls_made": int}
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    actions: list[dict] = []

    system_prompt = await _build_system_prompt(session)

    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=api_messages,
            tools=TOOLS,
        )

        if response.stop_reason == "end_turn":
            text_parts = [b.text for b in response.content if b.type == "text"]
            return {
                "response": "\n".join(text_parts),
                "actions": actions,
                "tool_calls_made": round_num,
            }

        if response.stop_reason == "tool_use":
            # Collect all tool_use blocks
            assistant_content = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    logger.info(f"Chat tool call: {block.name}({json.dumps(block.input)[:200]})")
                    result_str = await _exec_tool(session, block.name, block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

                    actions.append({
                        "tool": block.name,
                        "input": block.input,
                        "result_preview": result_str[:300],
                    })

            api_messages.append({"role": "assistant", "content": assistant_content})
            api_messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        text_parts = [b.text for b in response.content if b.type == "text"]
        return {
            "response": "\n".join(text_parts) or "I wasn't able to complete that request.",
            "actions": actions,
            "tool_calls_made": round_num + 1,
        }

    return {
        "response": "I've reached the maximum number of steps for this request. Please try a more specific question.",
        "actions": actions,
        "tool_calls_made": MAX_TOOL_ROUNDS,
    }
