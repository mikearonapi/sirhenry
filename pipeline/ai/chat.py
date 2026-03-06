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
from pipeline.ai.chat_tools import (
    _tool_list_manual_assets,
    _tool_update_asset_value,
    _tool_get_stock_quote,
    _tool_trigger_plaid_sync,
    _tool_run_categorization,
    _tool_get_data_health,
    _tool_update_transaction,
    _tool_create_transaction,
    _tool_exclude_transactions,
    _tool_manage_budget,
    _tool_manage_goal,
    _tool_create_reminder,
    _tool_update_business_entity,
    _tool_create_business_entity,
    _tool_save_user_context,
    _tool_get_user_context,
)

load_dotenv()
logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8

TOOL_LABELS: dict[str, str] = {
    "search_transactions": "Searching transactions",
    "get_transaction_detail": "Looking up transaction",
    "recategorize_transaction": "Updating transaction",
    "get_spending_summary": "Analyzing spending",
    "get_account_balances": "Checking balances",
    "get_tax_info": "Pulling tax data",
    "get_budget_status": "Reviewing budget",
    "get_recurring_expenses": "Checking subscriptions",
    "get_setup_status": "Checking setup",
    "get_household_summary": "Loading household data",
    "get_goals_summary": "Checking goals",
    "get_portfolio_overview": "Reviewing portfolio",
    "get_retirement_status": "Analyzing retirement",
    "get_life_scenarios": "Loading scenarios",
    "list_manual_assets": "Loading assets",
    "update_asset_value": "Updating asset value",
    "get_stock_quote": "Fetching stock quote",
    "trigger_plaid_sync": "Syncing bank data",
    "run_categorization": "Categorizing transactions",
    "get_data_health": "Running data health check",
    "update_transaction": "Updating transaction",
    "create_transaction": "Creating transaction",
    "exclude_transactions": "Updating transactions",
    "manage_budget": "Updating budget",
    "manage_goal": "Updating goal",
    "create_reminder": "Setting reminder",
    "update_business_entity": "Updating business profile",
    "create_business_entity": "Creating business entity",
    "save_user_context": "Remembering context",
    "get_user_context": "Recalling context",
}

TOOL_DONE_LABELS: dict[str, str] = {
    "search_transactions": "Found transactions",
    "get_transaction_detail": "Retrieved transaction",
    "recategorize_transaction": "Updated transaction",
    "get_spending_summary": "Spending analyzed",
    "get_account_balances": "Balances loaded",
    "get_tax_info": "Tax data loaded",
    "get_budget_status": "Budget reviewed",
    "get_recurring_expenses": "Subscriptions loaded",
    "get_setup_status": "Setup checked",
    "get_household_summary": "Household loaded",
    "get_goals_summary": "Goals loaded",
    "get_portfolio_overview": "Portfolio reviewed",
    "get_retirement_status": "Retirement analyzed",
    "get_life_scenarios": "Scenarios loaded",
    "list_manual_assets": "Assets loaded",
    "update_asset_value": "Asset updated",
    "get_stock_quote": "Quote fetched",
    "trigger_plaid_sync": "Sync complete",
    "run_categorization": "Categorization complete",
    "get_data_health": "Health check done",
    "update_transaction": "Transaction updated",
    "create_transaction": "Transaction created",
    "exclude_transactions": "Transactions updated",
    "manage_budget": "Budget updated",
    "manage_goal": "Goal updated",
    "create_reminder": "Reminder set",
    "update_business_entity": "Business profile updated",
    "create_business_entity": "Business entity created",
    "save_user_context": "Context remembered",
    "get_user_context": "Context recalled",
}

_SYSTEM_PROMPT_BASE = """You are Sir Henry, a senior personal financial advisor and CPA assistant embedded in the SirHENRY platform. You have deep access to the household's complete financial data and can take real actions on their behalf.

## Your Role
You are the household's dedicated AI financial advisor. You know their financial situation intimately based on data in the system.

## What You Can Do
1. **Search & Analyze** — Find any transaction by description, date, amount, category. Cross-reference spending patterns.
2. **Explain & Educate** — Tell them exactly what a charge is, why it's categorized a certain way, whether it's tax-deductible.
3. **Recategorize & Correct** — Fix miscategorized transactions immediately. Change category, tax category, segment, or business entity. Exclude duplicates, add notes, mark as reviewed.
4. **Spending Insights** — Break down spending by category and period. Spot anomalies, trends, and opportunities to save.
11. **Fix Data Issues** — Exclude duplicate transactions, add missing manual entries, update transaction notes. Handle bulk cleanup conversationally.
12. **Manage Budgets & Goals** — Create, update, and delete budget targets and financial goals. Set reminders for financial deadlines.
5. **Tax Strategy** — Surface tax optimization opportunities. Explain deduction eligibility. Flag items that need documentation.
6. **Budget Coaching** — Show budget vs. actual, highlight overspending, suggest adjustments.
7. **Goal Tracking** — Help evaluate progress toward financial goals and whether spending habits support them.
8. **Subscription Audit** — Review recurring charges, flag ones that may no longer be needed, calculate potential savings.
9. **Manage Assets** — View and update manual asset values (home, vehicles, trusts, retirement accounts). Look up current stock prices to keep values current.
10. **Sync & Maintain** — Trigger bank account syncs via Plaid, run AI categorization on new transactions, and run data health checks to identify gaps.
13. **Business Profile Management** — Create and enrich business entity profiles through conversation. When a user mentions a business, proactively ask follow-up questions to complete the profile: what does the business do? (description), what are common expense types? (expected_expenses), how is it structured? (entity_type, tax_treatment), who owns it? (owner — match to household members), when did it start? (active_from). Use update_business_entity to save answers progressively — don't wait to collect everything at once.
14. **Remember Context** — When the user shares important information about their financial situation, preferences, or goals, proactively save it using save_user_context. Don't ask for confirmation — just save it. The user will see a notification. Examples: their risk tolerance, business details, tax preferences, career plans, upcoming life changes.

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
- Keep responses focused but thorough — aim for the detail level of a professional financial review

## Data Interpretation Rules
- **Credit Card Payments**: Transactions categorized as "Credit Card Payment" are debt repayments to credit card issuers — they are NOT expenses. The underlying spending is already captured as individual purchase transactions. ALWAYS exclude "Credit Card Payment" category transactions when analyzing: large transactions, unusual charges, spending totals, cash outflows, or any expense-based analysis. Never flag a credit card payment as a notable transaction.
- **Transfers**: Inter-account transfers are also not expenses. Exclude them from spending analysis."""


async def _build_system_prompt(session: AsyncSession) -> tuple[str, "PIISanitizer"]:
    """Build the Sir Henry system prompt with dynamic household context from DB.

    PII (names, employers, entity names) is replaced with generic labels
    via PIISanitizer before the prompt is sent to Claude.

    Returns (prompt_text, sanitizer) so the caller can desanitize Claude's response.
    """
    from sqlalchemy import select as sa_select
    from pipeline.db.schema import (
        HouseholdProfile, BusinessEntity, Account, BenefitPackage, InsurancePolicy,
    )
    from pipeline.ai.privacy import (
        PIISanitizer, build_sanitized_household_context, log_ai_privacy_audit,
    )

    # ---------- Load data ----------
    result = await session.execute(
        sa_select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    entity_result = await session.execute(
        sa_select(BusinessEntity).where(BusinessEntity.is_active == True)
    )
    active_entities = entity_result.scalars().all()

    # ---------- Build sanitizer ----------
    sanitizer = PIISanitizer()
    sanitizer.register_household(household, active_entities)

    # ---------- Household context (sanitized) ----------
    lines: list[str] = []
    if household:
        household_context = build_sanitized_household_context(household, sanitizer)
        lines.extend(household_context.split("\n"))

    # ---------- Business Entities (sanitized) ----------
    if active_entities:
        entity_lines = [
            f"  - {sanitizer.sanitize_text(e.name)} ({e.entity_type}, {e.tax_treatment}"
            + (f", owner: {sanitizer.sanitize_text(e.owner)}" if e.owner else ", owner: unassigned")
            + ")"
            for e in active_entities
        ]
        lines.append("- Active business entities:")
        lines.extend(entity_lines)

    # ---------- Entity completeness ----------
    if active_entities:
        incomplete = []
        for e in active_entities:
            missing = []
            if not e.description:
                missing.append("description")
            if not e.expected_expenses:
                missing.append("expense types")
            if not e.owner:
                missing.append("owner")
            if not e.ein:
                missing.append("EIN")
            if missing:
                incomplete.append(
                    f"  - {sanitizer.sanitize_text(e.name)}: missing {', '.join(missing)}"
                )
        if incomplete:
            lines.append("- Business entities needing enrichment:")
            lines.extend(incomplete)

    # ---------- User Context (learned facts) ----------
    from pipeline.db.schema import UserContext
    ctx_result = await session.execute(
        sa_select(UserContext).where(UserContext.is_active == True).order_by(UserContext.category)
    )
    user_facts = ctx_result.scalars().all()

    if user_facts:
        ctx_lines: list[str] = []
        current_cat = None
        for fact in user_facts:
            if fact.category != current_cat:
                current_cat = fact.category
                ctx_lines.append(f"  [{fact.category.upper()}]")
            ctx_lines.append(f"  - {sanitizer.sanitize_text(fact.value)}")
        lines.append("")
        lines.append("## What You Know About This Household")
        lines.extend(ctx_lines)
        lines.append("")
        lines.append("Use this context to personalize your responses. Update or add context entries when the user shares new information.")

    log_ai_privacy_audit("chat_system_prompt", ["household", "entities", "accounts", "user_context"], sanitized=True)

    # ---------- Setup Status ----------
    acct_result = await session.execute(
        sa_select(func.count(Account.id)).where(Account.is_active == True)
    )
    account_count = acct_result.scalar() or 0

    benefit_result = await session.execute(sa_select(func.count(BenefitPackage.id)))
    benefit_count = benefit_result.scalar() or 0

    policy_result = await session.execute(
        sa_select(func.count(InsurancePolicy.id)).where(InsurancePolicy.is_active == True)
    )
    policy_count = policy_result.scalar() or 0

    setup_lines: list[str] = []
    setup_lines.append(f"- Household profile: {'COMPLETE' if household else 'NOT SET UP'}")
    setup_lines.append(f"- Accounts connected: {account_count}")
    setup_lines.append(f"- Benefits packages: {benefit_count}")
    setup_lines.append(f"- Insurance policies: {policy_count}")
    setup_lines.append(f"- Business entities: {len(active_entities)}")

    # Flag gaps that affect features
    gaps: list[str] = []
    if not household:
        gaps.append("- No household profile → Tax strategy, W-4 optimization, and insurance gap analysis won't work correctly")
    else:
        if not household.spouse_a_income and not household.spouse_b_income:
            gaps.append("- No income data → Tax bracket analysis will be inaccurate")
    if account_count == 0:
        gaps.append("- No accounts connected → Cash flow, budget, and spending insights unavailable")
    for e in active_entities:
        if not e.owner:
            gaps.append(f"- {sanitizer.sanitize_text(e.name)} has no owner assigned → Can't attribute to correct spouse for tax filing")
    if benefit_count == 0 and household:
        gaps.append("- No benefits configured → 401k optimization, HSA strategy unavailable")

    # ---------- Assemble ----------
    prompt = _SYSTEM_PROMPT_BASE
    if lines:
        prompt += "\n\n## Household Context\n" + "\n".join(lines)
    prompt += "\n\n## Setup Progress\n" + "\n".join(setup_lines)
    if gaps:
        prompt += "\n\n## Missing Data Affecting Features\n" + "\n".join(gaps)
        prompt += "\n\nWhen relevant to the user's question, proactively mention missing data that would improve your analysis. Guide them to complete setup if it would help answer their question."

    return prompt, sanitizer

TOOLS = [
    {
        "name": "search_transactions",
        "description": "Search transactions by description keyword, date range, amount range, category, segment, or account. Returns up to 20 matching transactions. IMPORTANT: Credit Card Payment and Transfer transactions are automatically excluded (they are debt repayments/inter-account moves, not actual expenses). To search credit card payments specifically, pass category='Credit Card Payment'.",
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
    {
        "name": "get_setup_status",
        "description": "Get the user's setup/onboarding status showing what's configured and what's missing, with feature impact for each gap.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_household_summary",
        "description": "Get the complete household profile including incomes, other income sources, benefits, insurance policies, business entities, and dependents.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_goals_summary",
        "description": "Get all financial goals with progress percentages, on-track status, and monthly contribution needs.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_portfolio_overview",
        "description": "Get portfolio summary including total value, holdings by asset class, allocation percentages, top holdings, and gain/loss.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_retirement_status",
        "description": "Get retirement readiness including saved amount, target nest egg, FIRE number, projected gap, and on-track percentage.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_life_scenarios",
        "description": "Get saved life scenarios (home purchase, job change, etc.) with affordability scores, verdicts, and key financial impacts.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_manual_assets",
        "description": "List all manually tracked assets and liabilities (home, vehicles, trusts, retirement accounts not on Plaid). Shows current values and when they were last updated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_type": {
                    "type": "string",
                    "description": "Filter by type: real_estate, vehicle, investment, retirement, other",
                },
            },
            "required": [],
        },
    },
    {
        "name": "update_asset_value",
        "description": "Update the current value of a manual asset (home, vehicle, trust balance, etc.). Use after looking up current market values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "integer", "description": "The manual asset ID to update"},
                "new_value": {"type": "number", "description": "New current value in dollars"},
                "notes": {"type": "string", "description": "Reason for update (e.g., 'Zillow estimate March 2026')"},
            },
            "required": ["asset_id", "new_value"],
        },
    },
    {
        "name": "get_stock_quote",
        "description": "Get real-time stock quote for a ticker symbol. Useful for checking RSU values, portfolio holdings, or market conditions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g., ACN, AAPL, SPY)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "trigger_plaid_sync",
        "description": "Sync latest transactions and balances from connected bank accounts via Plaid. Can sync all institutions or a specific one.",
        "input_schema": {
            "type": "object",
            "properties": {
                "institution": {"type": "string", "description": "Sync only this institution (e.g., 'Bank of America'). Omit to sync all."},
            },
            "required": [],
        },
    },
    {
        "name": "run_categorization",
        "description": "Run AI categorization on uncategorized transactions. Assigns expense category, tax category, segment, and business entity using Claude.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Categorize only transactions from this year. Omit for all uncategorized."},
                "month": {"type": "integer", "description": "Categorize only transactions from this month (1-12). Requires year."},
            },
            "required": [],
        },
    },
    {
        "name": "get_data_health",
        "description": "Run a comprehensive data quality check across accounts, transactions, Plaid connections, and manual assets. Identifies gaps like uncategorized transactions, stale asset values, and failed syncs.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "update_transaction",
        "description": "Update a transaction's metadata: add notes, exclude/include it from reports (useful for duplicates or erroneous entries), or mark it as manually reviewed. For category, segment, or entity changes use recategorize_transaction instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer", "description": "The transaction ID to update"},
                "is_excluded": {"type": "boolean", "description": "Set to true to exclude from reports (e.g., duplicates), false to re-include"},
                "notes": {"type": "string", "description": "Notes to add to the transaction (replaces existing notes)"},
                "is_manually_reviewed": {"type": "boolean", "description": "Mark as manually reviewed (confirms categorization is correct)"},
            },
            "required": ["transaction_id"],
        },
    },
    {
        "name": "create_transaction",
        "description": "Create a manual transaction. Use this to add missing income, adjustments, or other entries not captured by imports. Requires an account_id (use get_account_balances to find account IDs).",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer", "description": "The account ID this transaction belongs to (use get_account_balances to find IDs)"},
                "date": {"type": "string", "description": "Transaction date in YYYY-MM-DD format"},
                "description": {"type": "string", "description": "Transaction description (e.g., 'Freelance payment from Client X')"},
                "amount": {"type": "number", "description": "Amount in dollars. Negative for expenses, positive for income/credits"},
                "category": {"type": "string", "description": "Expense category (e.g., 'Income', 'Freelance Income', 'Reimbursement')"},
                "segment": {
                    "type": "string",
                    "enum": ["personal", "business", "investment", "reimbursable"],
                    "description": "Transaction segment (default: personal)",
                },
                "notes": {"type": "string", "description": "Optional notes about this transaction"},
            },
            "required": ["account_id", "date", "description", "amount"],
        },
    },
    {
        "name": "exclude_transactions",
        "description": "Batch exclude or include multiple transactions matching criteria. Useful for handling duplicates, bulk cleanup, or re-including previously excluded data. Returns count of affected transactions. ALWAYS preview with search_transactions first before excluding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["exclude", "include"],
                    "description": "'exclude' to hide from reports, 'include' to restore",
                },
                "transaction_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Specific transaction IDs to exclude/include (max 50)",
                },
                "query": {"type": "string", "description": "Text to match in transaction descriptions (alternative to listing IDs)"},
                "year": {"type": "integer", "description": "Filter by year when using query-based matching"},
                "month": {"type": "integer", "description": "Filter by month (1-12) when using query-based matching"},
                "account_id": {"type": "integer", "description": "Filter by account when using query-based matching"},
                "reason": {"type": "string", "description": "Reason for excluding/including (stored in notes)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "manage_budget",
        "description": "Create, update, or delete budget entries. Use 'upsert' to create a new budget or update an existing one (matched by year+month+category+segment). Use 'delete' to remove a budget entry by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["upsert", "delete"],
                    "description": "'upsert' to create or update, 'delete' to remove",
                },
                "budget_id": {"type": "integer", "description": "Budget ID (required for delete)"},
                "year": {"type": "integer", "description": "Budget year (required for upsert)"},
                "month": {"type": "integer", "description": "Budget month 1-12 (required for upsert)"},
                "category": {"type": "string", "description": "Expense category (required for upsert, e.g., 'Groceries', 'Dining Out')"},
                "budget_amount": {"type": "number", "description": "Monthly budget amount in dollars (required for upsert)"},
                "segment": {
                    "type": "string",
                    "enum": ["personal", "business"],
                    "description": "Segment (default: personal)",
                },
                "notes": {"type": "string", "description": "Optional notes"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "manage_goal",
        "description": "Create, update, or delete financial goals. Use 'upsert' to create a new goal or update an existing one. Use 'delete' to remove a goal by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["upsert", "delete"],
                    "description": "'upsert' to create or update, 'delete' to remove",
                },
                "goal_id": {"type": "integer", "description": "Goal ID (required for delete, optional for upsert to update existing)"},
                "name": {"type": "string", "description": "Goal name (required for new goals, e.g., 'Emergency Fund', 'House Down Payment')"},
                "goal_type": {
                    "type": "string",
                    "enum": ["savings", "debt_payoff", "investment", "retirement", "education", "custom"],
                    "description": "Type of goal (default: savings)",
                },
                "target_amount": {"type": "number", "description": "Target amount in dollars (required for new goals)"},
                "current_amount": {"type": "number", "description": "Current amount saved toward this goal"},
                "target_date": {"type": "string", "description": "Target date in YYYY-MM-DD format"},
                "monthly_contribution": {"type": "number", "description": "Monthly contribution amount in dollars"},
                "status": {
                    "type": "string",
                    "enum": ["active", "paused", "completed", "cancelled"],
                    "description": "Goal status",
                },
                "notes": {"type": "string", "description": "Optional notes"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "create_reminder",
        "description": "Create a reminder for a financial deadline (tax filing, estimated payment, enrollment window, bill due date, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Reminder title (e.g., 'Q1 Estimated Tax Payment Due')"},
                "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format"},
                "description": {"type": "string", "description": "Additional details about the reminder"},
                "reminder_type": {
                    "type": "string",
                    "enum": ["tax_deadline", "payment_due", "enrollment", "review", "custom"],
                    "description": "Type of reminder (default: custom)",
                },
                "amount": {"type": "number", "description": "Dollar amount associated (e.g., estimated tax payment amount)"},
                "advance_notice": {
                    "type": "string",
                    "enum": ["1_day", "3_days", "7_days", "14_days", "30_days"],
                    "description": "How far in advance to notify (default: 7_days)",
                },
            },
            "required": ["title", "due_date"],
        },
    },
    {
        "name": "update_business_entity",
        "description": "Update a business entity's profile. Use this to rename entities, enrich details through conversation — description, expected expense types, tax treatment, owner assignment, EIN, and notes. Look up entities with get_household_summary first if you need the entity name or ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {"type": "string", "description": "Name of the entity to update (case-insensitive match)"},
                "entity_id": {"type": "integer", "description": "ID of the entity to update (alternative to entity_name)"},
                "new_name": {"type": "string", "description": "New name for the entity (rename)"},
                "description": {"type": "string", "description": "What the business does (1-3 sentences)"},
                "expected_expenses": {"type": "string", "description": "Comma-separated common expense types (e.g., 'Inventory, Rent, Marketing, Software')"},
                "entity_type": {
                    "type": "string",
                    "enum": ["sole_prop", "llc", "s_corp", "c_corp", "partnership", "employer"],
                    "description": "Business structure type",
                },
                "tax_treatment": {
                    "type": "string",
                    "enum": ["w2", "schedule_c", "k1", "section_195", "none"],
                    "description": "How the entity is taxed",
                },
                "ein": {"type": "string", "description": "Employer Identification Number"},
                "owner": {"type": "string", "description": "Name of the household member who owns this entity"},
                "is_provisional": {"type": "boolean", "description": "True if business hasn't started generating revenue (Section 195 startup costs)"},
                "active_from": {"type": "string", "description": "Date business became active (YYYY-MM-DD)"},
                "active_to": {"type": "string", "description": "Date business ceased operations (YYYY-MM-DD)"},
                "notes": {"type": "string", "description": "Additional notes (appended to existing notes)"},
            },
            "required": [],
        },
    },
    {
        "name": "create_business_entity",
        "description": "Create a new business entity. Use when a user mentions a business that doesn't exist yet. After creating, ask follow-up questions to complete the profile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Business or entity name"},
                "description": {"type": "string", "description": "What the business does"},
                "expected_expenses": {"type": "string", "description": "Comma-separated common expense types"},
                "entity_type": {
                    "type": "string",
                    "enum": ["sole_prop", "llc", "s_corp", "c_corp", "partnership", "employer"],
                    "description": "Business structure type (default: sole_prop)",
                },
                "tax_treatment": {
                    "type": "string",
                    "enum": ["w2", "schedule_c", "k1", "section_195", "none"],
                    "description": "How the entity is taxed (default: schedule_c)",
                },
                "ein": {"type": "string", "description": "Employer Identification Number"},
                "owner": {"type": "string", "description": "Name of the household member who owns this entity"},
                "is_provisional": {"type": "boolean", "description": "True if business hasn't started generating revenue"},
                "active_from": {"type": "string", "description": "Date business became active (YYYY-MM-DD)"},
                "notes": {"type": "string", "description": "Additional notes"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "save_user_context",
        "description": "Save a learned fact about the user for future reference. Use this proactively when the user shares important context about their financial situation, preferences, or goals. Each fact has a category and a short key for deduplication. Don't ask for confirmation — just save it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["business", "tax", "preference", "household", "financial_goal", "investment", "career"],
                    "description": "Category of the context fact",
                },
                "key": {"type": "string", "description": "Short identifier for dedup (e.g., 'primary_business', 'tax_strategy_preference', 'risk_tolerance')"},
                "value": {"type": "string", "description": "The fact to remember (1-2 sentences)"},
            },
            "required": ["category", "key", "value"],
        },
    },
    {
        "name": "get_user_context",
        "description": "Retrieve stored context facts about the user. Use this to recall previously learned information when needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["business", "tax", "preference", "household", "financial_goal", "investment", "career"],
                    "description": "Filter by category. Omit for all.",
                },
            },
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
        elif tool_name == "get_setup_status":
            return await _tool_get_setup_status(session)
        elif tool_name == "get_household_summary":
            return await _tool_get_household_summary(session)
        elif tool_name == "get_goals_summary":
            return await _tool_get_goals_summary(session)
        elif tool_name == "get_portfolio_overview":
            return await _tool_get_portfolio_overview(session)
        elif tool_name == "get_retirement_status":
            return await _tool_get_retirement_status(session)
        elif tool_name == "get_life_scenarios":
            return await _tool_get_life_scenarios(session)
        elif tool_name == "list_manual_assets":
            return await _tool_list_manual_assets(session, tool_input)
        elif tool_name == "update_asset_value":
            return await _tool_update_asset_value(session, tool_input)
        elif tool_name == "get_stock_quote":
            return await _tool_get_stock_quote(session, tool_input)
        elif tool_name == "trigger_plaid_sync":
            return await _tool_trigger_plaid_sync(session, tool_input)
        elif tool_name == "run_categorization":
            return await _tool_run_categorization(session, tool_input)
        elif tool_name == "get_data_health":
            return await _tool_get_data_health(session, tool_input)
        elif tool_name == "update_transaction":
            return await _tool_update_transaction(session, tool_input)
        elif tool_name == "create_transaction":
            return await _tool_create_transaction(session, tool_input)
        elif tool_name == "exclude_transactions":
            return await _tool_exclude_transactions(session, tool_input)
        elif tool_name == "manage_budget":
            return await _tool_manage_budget(session, tool_input)
        elif tool_name == "manage_goal":
            return await _tool_manage_goal(session, tool_input)
        elif tool_name == "create_reminder":
            return await _tool_create_reminder(session, tool_input)
        elif tool_name == "update_business_entity":
            return await _tool_update_business_entity(session, tool_input)
        elif tool_name == "create_business_entity":
            return await _tool_create_business_entity(session, tool_input)
        elif tool_name == "save_user_context":
            return await _tool_save_user_context(session, tool_input)
        elif tool_name == "get_user_context":
            return await _tool_get_user_context(session, tool_input)
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

    # Auto-exclude credit card payments and transfers unless caller explicitly filters by category.
    # These are debt repayments / inter-account moves — not actual expenses.
    if not category:
        EXCLUDED = ("Credit Card Payment", "Transfer", "Payment")
        for excl in EXCLUDED:
            q = q.where(Transaction.effective_category.not_ilike(f"%{excl}%"))

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

    # Exclude credit card payments and transfers — they are debt repayments/inter-account
    # moves, not actual expenses. The underlying spending is captured as individual transactions.
    EXCLUDED_CATEGORIES = ("Credit Card Payment", "Transfer", "Payment")

    q = select(
        Transaction.effective_category,
        Transaction.effective_segment,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).where(
        Transaction.period_year == year,
        Transaction.is_excluded == False,
        ~Transaction.effective_category.in_(EXCLUDED_CATEGORIES),
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


async def _tool_get_setup_status(session: AsyncSession) -> str:
    """Return setup completeness with feature impact for each gap."""
    from pipeline.db.schema import (
        HouseholdProfile, Account, BenefitPackage, InsurancePolicy, BusinessEntity, LifeEvent,
    )

    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    acct_result = await session.execute(
        select(func.count(Account.id)).where(Account.is_active == True)
    )
    account_count = acct_result.scalar() or 0

    benefit_result = await session.execute(select(func.count(BenefitPackage.id)))
    benefit_count = benefit_result.scalar() or 0

    policy_result = await session.execute(
        select(func.count(InsurancePolicy.id)).where(InsurancePolicy.is_active == True)
    )
    policy_count = policy_result.scalar() or 0

    entity_result = await session.execute(
        select(BusinessEntity).where(BusinessEntity.is_active == True)
    )
    entities = entity_result.scalars().all()

    event_result = await session.execute(select(func.count(LifeEvent.id)))
    event_count = event_result.scalar() or 0

    sections = {
        "household": {
            "status": "complete" if household else "missing",
            "detail": f"Filing: {household.filing_status}, State: {household.state}" if household else None,
            "features_affected": ["Tax Strategy", "W-4 Optimization", "Insurance Gap Analysis"],
        },
        "accounts": {
            "status": "complete" if account_count > 0 else "missing",
            "count": account_count,
            "features_affected": ["Cash Flow", "Budget Tracking", "Spending Insights"],
        },
        "benefits": {
            "status": "complete" if benefit_count > 0 else "missing",
            "count": benefit_count,
            "features_affected": ["401k Optimization", "HSA Strategy", "Retirement Projections"],
        },
        "insurance": {
            "status": "complete" if policy_count > 0 else "missing",
            "count": policy_count,
            "features_affected": ["Coverage Gap Analysis", "Premium Optimization"],
        },
        "business_entities": {
            "status": "complete" if len(entities) > 0 else "none",
            "entities": [
                {"name": e.name, "type": e.entity_type, "owner": e.owner or "unassigned"}
                for e in entities
            ],
            "features_affected": ["Business Expense Tracking", "Schedule C/K-1 Tax Planning"],
        },
        "life_events": {
            "status": "complete" if event_count > 0 else "none",
            "count": event_count,
            "features_affected": ["Tax Impact Checklists", "Action Items"],
        },
    }

    gaps: list[str] = []
    if not household:
        gaps.append("No household profile — Tax strategy, W-4 optimization, and insurance gap analysis won't work")
    else:
        if not household.spouse_a_income and not household.spouse_b_income:
            gaps.append("No income data — Tax bracket analysis will be inaccurate")
    if account_count == 0:
        gaps.append("No accounts connected — Cash flow, budget, and spending insights unavailable")
    for e in entities:
        if not e.owner:
            gaps.append(f"'{e.name}' has no owner assigned — Can't attribute to correct spouse for tax filing")
    if benefit_count == 0 and household:
        gaps.append("No benefits configured — 401k optimization, HSA strategy unavailable")

    return json.dumps({
        "sections": sections,
        "gaps": gaps,
        "overall_completeness": sum(1 for s in sections.values() if s["status"] == "complete") / len(sections),
    })


async def _tool_get_household_summary(session: AsyncSession) -> str:
    """Return full household profile with all related data."""
    from pipeline.db.schema import (
        HouseholdProfile, BenefitPackage, InsurancePolicy, BusinessEntity,
    )

    result = await session.execute(
        select(HouseholdProfile).where(HouseholdProfile.is_primary == True).limit(1)
    )
    household = result.scalar_one_or_none()

    if not household:
        return json.dumps({"error": "No household profile set up yet"})

    # Parse other income sources
    other_incomes: list[dict] = []
    if household.other_income_sources_json:
        try:
            other_incomes = json.loads(household.other_income_sources_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse dependents
    dependents: list[dict] = []
    if household.dependents_json:
        try:
            dependents = json.loads(household.dependents_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Benefits
    benefit_result = await session.execute(select(BenefitPackage))
    benefits = benefit_result.scalars().all()
    benefit_list = [
        {
            "spouse": b.spouse,
            "employer": b.employer_name,
            "has_401k": b.has_401k,
            "employer_match_pct": b.employer_match_pct,
            "has_hsa": b.has_hsa,
            "has_espp": b.has_espp,
            "life_insurance_coverage": b.life_insurance_coverage,
        }
        for b in benefits
    ]

    # Insurance
    policy_result = await session.execute(
        select(InsurancePolicy).where(InsurancePolicy.is_active == True)
    )
    policies = policy_result.scalars().all()
    policy_list = [
        {"type": p.policy_type, "provider": p.provider}
        for p in policies
    ]

    # Entities
    entity_result = await session.execute(
        select(BusinessEntity).where(BusinessEntity.is_active == True)
    )
    entities = entity_result.scalars().all()
    entity_list = [
        {"name": e.name, "type": e.entity_type, "tax_treatment": e.tax_treatment, "owner": e.owner}
        for e in entities
    ]

    return json.dumps({
        "filing_status": household.filing_status,
        "state": household.state,
        "spouse_a": {
            "name": household.spouse_a_name,
            "w2_income": household.spouse_a_income,
            "employer": household.spouse_a_employer,
        },
        "spouse_b": {
            "name": household.spouse_b_name,
            "w2_income": household.spouse_b_income,
            "employer": household.spouse_b_employer,
        },
        "other_income_sources": other_incomes,
        "other_income_total": household.other_income_annual,
        "combined_income": household.combined_income,
        "dependents": dependents,
        "benefits": benefit_list,
        "insurance_policies": policy_list,
        "business_entities": entity_list,
    })


async def _tool_get_goals_summary(session: AsyncSession) -> str:
    """Return all financial goals with progress and on-track analysis."""
    from pipeline.db.schema import Goal

    result = await session.execute(
        select(Goal).where(Goal.status == "active")
    )
    goals = result.scalars().all()

    if not goals:
        return json.dumps({"count": 0, "goals": [], "message": "No financial goals set up yet"})

    from datetime import datetime, date
    now = datetime.utcnow()
    goal_list = []
    for g in goals:
        progress_pct = (g.current_amount / g.target_amount * 100) if g.target_amount else 0
        remaining = max(0, g.target_amount - g.current_amount)

        # Calculate months remaining and required monthly contribution
        months_remaining = None
        monthly_needed = None
        on_track = None
        if g.target_date:
            td = g.target_date if isinstance(g.target_date, date) else g.target_date.date() if hasattr(g.target_date, "date") else g.target_date
            delta = (td.year - now.year) * 12 + (td.month - now.month)
            months_remaining = max(0, delta)
            if months_remaining > 0:
                monthly_needed = round(remaining / months_remaining, 2)
                if g.monthly_contribution and g.monthly_contribution > 0:
                    projected = g.current_amount + g.monthly_contribution * months_remaining
                    on_track = projected >= g.target_amount

        goal_list.append({
            "id": g.id,
            "name": g.name,
            "type": g.goal_type,
            "target_amount": g.target_amount,
            "current_amount": g.current_amount,
            "progress_pct": round(progress_pct, 1),
            "remaining": round(remaining, 2),
            "target_date": str(g.target_date)[:10] if g.target_date else None,
            "months_remaining": months_remaining,
            "monthly_contribution": g.monthly_contribution,
            "monthly_needed": monthly_needed,
            "on_track": on_track,
        })

    total_target = sum(g["target_amount"] for g in goal_list)
    total_saved = sum(g["current_amount"] for g in goal_list)

    return json.dumps({
        "count": len(goal_list),
        "total_target": round(total_target, 2),
        "total_saved": round(total_saved, 2),
        "overall_progress_pct": round(total_saved / total_target * 100, 1) if total_target else 0,
        "goals": goal_list,
    })


async def _tool_get_portfolio_overview(session: AsyncSession) -> str:
    """Return portfolio summary: holdings, allocation, total value, gains."""
    from pipeline.db.schema import InvestmentHolding, CryptoHolding, ManualAsset

    # Investment holdings
    hold_result = await session.execute(
        select(InvestmentHolding).where(InvestmentHolding.is_active == True)
    )
    holdings = hold_result.scalars().all()

    # Crypto holdings
    crypto_result = await session.execute(
        select(CryptoHolding).where(CryptoHolding.is_active == True)
    )
    crypto = crypto_result.scalars().all()

    # Manual investment assets (retirement accounts, etc.)
    manual_result = await session.execute(
        select(ManualAsset).where(
            ManualAsset.is_active == True,
            ManualAsset.is_liability == False,
            ManualAsset.asset_type.in_(["retirement_account", "brokerage", "investment", "529_plan"]),
        )
    )
    manual = manual_result.scalars().all()

    # Aggregate by asset class
    asset_class_totals: dict[str, float] = {}
    total_value = 0.0
    total_cost = 0.0
    top_holdings = []

    for h in holdings:
        val = h.current_value or 0
        cost = h.total_cost_basis or 0
        total_value += val
        total_cost += cost
        cls = h.asset_class or "stock"
        asset_class_totals[cls] = asset_class_totals.get(cls, 0) + val
        top_holdings.append({
            "ticker": h.ticker,
            "name": h.name,
            "value": round(val, 2),
            "shares": h.shares,
            "gain_loss": round(val - cost, 2) if cost else None,
            "gain_loss_pct": round((val - cost) / cost * 100, 1) if cost and cost != 0 else None,
            "asset_class": cls,
        })

    crypto_total = sum(c.current_value or 0 for c in crypto)
    if crypto_total > 0:
        asset_class_totals["crypto"] = crypto_total
        total_value += crypto_total

    manual_total = sum(m.current_value or 0 for m in manual)
    if manual_total > 0:
        asset_class_totals["retirement/other"] = manual_total
        total_value += manual_total

    # Sort top holdings by value
    top_holdings.sort(key=lambda x: x["value"], reverse=True)

    # Allocation percentages
    allocation = {
        cls: {"value": round(v, 2), "pct": round(v / total_value * 100, 1) if total_value else 0}
        for cls, v in sorted(asset_class_totals.items(), key=lambda x: x[1], reverse=True)
    }

    total_gain = total_value - total_cost if total_cost > 0 else None

    return json.dumps({
        "total_value": round(total_value, 2),
        "total_cost_basis": round(total_cost, 2) if total_cost > 0 else None,
        "total_gain_loss": round(total_gain, 2) if total_gain is not None else None,
        "total_gain_loss_pct": round(total_gain / total_cost * 100, 1) if total_gain is not None and total_cost > 0 else None,
        "holdings_count": len(holdings),
        "crypto_count": len(crypto),
        "manual_accounts": len(manual),
        "allocation": allocation,
        "top_holdings": top_holdings[:10],
        "crypto_holdings": [
            {"symbol": c.symbol, "name": c.name, "value": round(c.current_value or 0, 2), "quantity": c.quantity}
            for c in crypto
        ],
    })


async def _tool_get_retirement_status(session: AsyncSession) -> str:
    """Return retirement readiness: savings, target, FIRE number, on-track %."""
    from pipeline.db.schema import RetirementProfile

    result = await session.execute(
        select(RetirementProfile).order_by(RetirementProfile.is_primary.desc()).limit(1)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return json.dumps({"error": "No retirement profile set up yet"})

    years_to_retirement = max(0, (profile.retirement_age or 65) - (profile.current_age or 35))
    years_in_retirement = max(0, (profile.life_expectancy or 90) - (profile.retirement_age or 65))

    # Simple projection
    current_savings = profile.current_retirement_savings or 0
    monthly_contrib = profile.monthly_retirement_contribution or 0
    annual_return = (profile.pre_retirement_return_pct or 7) / 100

    projected_at_retirement = current_savings
    for _ in range(years_to_retirement):
        projected_at_retirement = projected_at_retirement * (1 + annual_return) + monthly_contrib * 12

    target = profile.target_nest_egg or 0
    fire_number = profile.fire_number or 0
    readiness_pct = (projected_at_retirement / target * 100) if target > 0 else 0

    return json.dumps({
        "profile_name": profile.name,
        "current_age": profile.current_age,
        "retirement_age": profile.retirement_age,
        "life_expectancy": profile.life_expectancy,
        "years_to_retirement": years_to_retirement,
        "current_savings": round(current_savings, 2),
        "monthly_contribution": round(monthly_contrib, 2),
        "employer_match_pct": profile.employer_match_pct,
        "projected_at_retirement": round(projected_at_retirement, 2),
        "target_nest_egg": round(target, 2),
        "fire_number": round(fire_number, 2),
        "readiness_pct": round(readiness_pct, 1),
        "on_track": readiness_pct >= 90,
        "gap": round(max(0, target - projected_at_retirement), 2),
        "social_security_monthly": profile.expected_social_security_monthly,
        "social_security_start_age": profile.social_security_start_age,
        "income_replacement_pct": profile.income_replacement_pct,
    })


async def _tool_get_life_scenarios(session: AsyncSession) -> str:
    """Return saved life scenarios with verdicts and financial impacts."""
    from pipeline.db.schema import LifeScenario

    result = await session.execute(
        select(LifeScenario).order_by(LifeScenario.created_at.desc())
    )
    scenarios = result.scalars().all()

    if not scenarios:
        return json.dumps({"count": 0, "scenarios": [], "message": "No life scenarios saved yet"})

    scenario_list = [
        {
            "id": s.id,
            "name": s.name,
            "type": s.scenario_type,
            "status": s.status,
            "is_favorite": s.is_favorite,
            "total_cost": round(s.total_cost or 0, 2),
            "new_monthly_payment": round(s.new_monthly_payment or 0, 2),
            "monthly_surplus_after": round(s.monthly_surplus_after or 0, 2),
            "savings_rate_before_pct": round(s.savings_rate_before_pct or 0, 1),
            "savings_rate_after_pct": round(s.savings_rate_after_pct or 0, 1),
            "dti_before_pct": round(s.dti_before_pct or 0, 1),
            "dti_after_pct": round(s.dti_after_pct or 0, 1),
            "affordability_score": round(s.affordability_score or 0, 1),
            "verdict": s.verdict,
            "has_ai_analysis": bool(s.ai_analysis),
        }
        for s in scenarios
    ]

    return json.dumps({
        "count": len(scenario_list),
        "scenarios": scenario_list,
    })


async def run_chat(
    session: AsyncSession,
    messages: list[dict[str, str]],
    conversation_id: int | None = None,
    page_context: str | None = None,
) -> dict[str, Any]:
    """
    Run the chat agentic loop with persistent history.

    Args:
        session: DB session
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts
        conversation_id: Existing conversation to continue (None = create new)
        page_context: Page slug this chat originated from (None = global Sir Henry page)

    Returns:
        {"response": "...", "actions": [...], "tool_calls_made": int, "conversation_id": int}
    """
    from datetime import datetime as _dt
    from pipeline.db.schema import ChatConversation, ChatMessage as ChatMessageModel
    from pipeline.db import UserPrivacyConsent

    # Check AI consent before proceeding
    consent_result = await session.execute(
        select(UserPrivacyConsent).where(
            UserPrivacyConsent.consent_type == "ai_features",
            UserPrivacyConsent.consented == True,
        )
    )
    if not consent_result.scalar_one_or_none():
        return {
            "response": None,
            "requires_consent": True,
            "actions": [],
            "tool_calls_made": 0,
            "conversation_id": None,
        }

    # ---------- Conversation persistence: pre-loop ----------
    user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if conversation_id is None:
        # Derive a readable title from the first user message
        raw_title = user_text[:80]
        # Trim to last space to avoid mid-word cuts
        if len(user_text) > 80 and " " in raw_title:
            raw_title = raw_title.rsplit(" ", 1)[0]
        conv = ChatConversation(
            title=raw_title or "New Conversation",
            page_context=page_context,
        )
        session.add(conv)
        await session.flush()  # get conv.id
    else:
        result = await session.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            # Conversation was deleted; start fresh
            conv = ChatConversation(title=user_text[:80] or "New Conversation", page_context=page_context)
            session.add(conv)
            await session.flush()

    # Persist the user's message
    if user_text:
        session.add(ChatMessageModel(conversation_id=conv.id, role="user", content=user_text))
        await session.flush()

    import time as _time
    from pipeline.security.audit import log_audit
    _chat_start = _time.monotonic()

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    actions: list[dict] = []

    system_prompt, sanitizer = await _build_system_prompt(session)

    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
    ]

    final_response: str = "I wasn't able to complete that request."
    final_round: int = 0

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
            raw_response = "\n".join(text_parts)
            final_response = sanitizer.desanitize_text(raw_response) if sanitizer.has_mappings else raw_response
            final_round = round_num
            _elapsed = int((_time.monotonic() - _chat_start) * 1000)
            await log_audit(session, "ai_chat", "conversation", f"tools_used={len(actions)}", _elapsed)
            break

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

                    logger.info(f"Chat tool call: {block.name}")
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
        raw_response = "\n".join(text_parts) or "I wasn't able to complete that request."
        final_response = sanitizer.desanitize_text(raw_response) if sanitizer.has_mappings else raw_response
        final_round = round_num + 1
        _elapsed = int((_time.monotonic() - _chat_start) * 1000)
        await log_audit(session, "ai_chat", "conversation", f"tools_used={len(actions)}", _elapsed)
        break
    else:
        # Hit MAX_TOOL_ROUNDS
        final_response = "I've reached the maximum number of steps for this request. Please try a more specific question."
        final_round = MAX_TOOL_ROUNDS
        _elapsed = int((_time.monotonic() - _chat_start) * 1000)
        await log_audit(session, "ai_chat", "conversation", f"tools_used={len(actions)},max_rounds=true", _elapsed)

    # ---------- Conversation persistence: post-loop ----------
    session.add(ChatMessageModel(
        conversation_id=conv.id,
        role="assistant",
        content=final_response,
        actions_json=json.dumps(actions) if actions else None,
    ))
    conv.updated_at = _dt.utcnow()
    await session.flush()

    return {
        "response": final_response,
        "actions": actions,
        "tool_calls_made": final_round,
        "conversation_id": conv.id,
    }


async def run_chat_stream(
    session: AsyncSession,
    messages: list[dict[str, str]],
    conversation_id: int | None = None,
    page_context: str | None = None,
):
    """
    Async generator that yields SSE-ready event dicts for streaming chat.

    Event types yielded:
        {"type": "text_delta", "text": "..."}       — incremental response text
        {"type": "tool_start", "tool": "...", "label": "..."}  — tool execution started
        {"type": "tool_done",  "tool": "...", "preview": "..."} — tool completed
        {"type": "done", "conversation_id": int}    — stream complete
        {"type": "requires_consent"}                — user must accept privacy terms first
        {"type": "error", "message": "..."}         — error occurred
    """
    from datetime import datetime as _dt
    from pipeline.db.schema import ChatConversation, ChatMessage as ChatMessageModel
    from pipeline.db import UserPrivacyConsent
    from pipeline.security.audit import log_audit
    import time as _time

    # ── Consent check ──
    consent_result = await session.execute(
        select(UserPrivacyConsent).where(
            UserPrivacyConsent.consent_type == "ai_features",
            UserPrivacyConsent.consented == True,
        )
    )
    if not consent_result.scalar_one_or_none():
        yield {"type": "requires_consent"}
        return

    # ── Conversation setup (same as run_chat) ──
    user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if conversation_id is None:
        raw_title = user_text[:80]
        if len(user_text) > 80 and " " in raw_title:
            raw_title = raw_title.rsplit(" ", 1)[0]
        conv = ChatConversation(
            title=raw_title or "New Conversation",
            page_context=page_context,
        )
        session.add(conv)
        await session.flush()
    else:
        result = await session.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            conv = ChatConversation(title=user_text[:80] or "New Conversation", page_context=page_context)
            session.add(conv)
            await session.flush()

    if user_text:
        session.add(ChatMessageModel(conversation_id=conv.id, role="user", content=user_text))
        await session.flush()

    # ── Agentic streaming loop ──
    async_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    system_prompt, sanitizer = await _build_system_prompt(session)

    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    actions: list[dict] = []
    _chat_start = _time.monotonic()

    for round_num in range(MAX_TOOL_ROUNDS):
        full_text = ""
        stop_reason = "end_turn"

        try:
            async with async_client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=api_messages,
                tools=TOOLS,
            ) as stream:
                async for event in stream:
                    etype = getattr(event, "type", None)

                    if etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta and getattr(delta, "type", None) == "text_delta":
                            chunk = delta.text
                            full_text += chunk
                            yield {"type": "text_delta", "text": chunk}

                # Get final resolved message after stream completes
                final = await stream.get_final_message()
                stop_reason = final.stop_reason

        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
            return

        if stop_reason == "end_turn":
            # Desanitize and persist
            final_response = sanitizer.desanitize_text(full_text) if sanitizer.has_mappings else full_text
            _elapsed = int((_time.monotonic() - _chat_start) * 1000)
            await log_audit(session, "ai_chat", "conversation", f"tools_used={len(actions)},streaming=true", _elapsed)

            session.add(ChatMessageModel(
                conversation_id=conv.id,
                role="assistant",
                content=final_response,
                actions_json=json.dumps(actions) if actions else None,
            ))
            conv.updated_at = _dt.utcnow()
            await session.flush()

            yield {"type": "done", "conversation_id": conv.id, "actions": actions}
            return

        if stop_reason == "tool_use":
            # Execute all tool calls from the final message
            assistant_content = []
            tool_results = []

            for block in final.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    label = TOOL_LABELS.get(block.name, block.name.replace("_", " ").title())
                    yield {"type": "tool_start", "tool": block.name, "label": label}

                    result_str = await _exec_tool(session, block.name, block.input)

                    done_label = TOOL_DONE_LABELS.get(block.name, label)
                    yield {"type": "tool_done", "tool": block.name, "label": done_label, "preview": result_str[:200]}

                    # Emit learning events for tools that store learned knowledge
                    if block.name == "save_user_context":
                        try:
                            parsed = json.loads(result_str)
                            if parsed.get("remembered"):
                                yield {"type": "learning", "message": f"Remembered: {parsed.get('value', '')[:80]}"}
                        except Exception:
                            pass
                    elif block.name in ("update_business_entity", "create_business_entity"):
                        try:
                            parsed = json.loads(result_str)
                            if parsed.get("success"):
                                entity_name = parsed.get("entity_name", "entity")
                                changes = parsed.get("fields_updated", []) or ["profile"]
                                yield {"type": "learning", "message": f"Updated {entity_name}: {', '.join(changes[:3])}"}
                        except Exception:
                            pass

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
        yield {"type": "error", "message": f"Unexpected stop reason: {stop_reason}"}
        return

    # Hit MAX_TOOL_ROUNDS
    final_response = "I've reached the maximum number of steps for this request. Please try a more specific question."
    session.add(ChatMessageModel(conversation_id=conv.id, role="assistant", content=final_response))
    conv.updated_at = _dt.utcnow()
    await session.flush()
    yield {"type": "done", "conversation_id": conv.id, "actions": actions}
