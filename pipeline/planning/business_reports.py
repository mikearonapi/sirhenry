"""
Business entity expense reporting.

Computes per-entity monthly expense summaries, category breakdowns,
and year-over-year comparisons. Also provides transaction export data.
"""
import calendar
import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import Account, BusinessEntity, Transaction

logger = logging.getLogger(__name__)

# Categories that are internal money movements, not real expenses
_EXCLUDED_CATEGORIES = ("Credit Card Payment", "Transfer", "Payment")


async def compute_entity_expense_report(
    session: AsyncSession,
    entity_id: int,
    year: int,
) -> dict[str, Any]:
    """Compute a full expense report for a single business entity.

    Returns:
        {entity_id, entity_name, year, monthly_totals, category_breakdown,
         year_total_expenses, prior_year_total_expenses, year_over_year_change_pct}
    """
    # Verify entity exists
    ent_result = await session.execute(
        select(BusinessEntity).where(BusinessEntity.id == entity_id)
    )
    entity = ent_result.scalar_one_or_none()
    if not entity:
        return {"error": f"Entity {entity_id} not found"}

    # --- Monthly totals ---
    base_filter = [
        Transaction.effective_business_entity_id == entity_id,
        Transaction.is_excluded == False,
        Transaction.amount < 0,  # Only expenses (negative amounts)
    ]
    # Exclude internal movements (handle NULL categories)
    for cat in _EXCLUDED_CATEGORIES:
        base_filter.append(or_(
            Transaction.effective_category.not_ilike(f"%{cat}%"),
            Transaction.effective_category.is_(None),
        ))

    monthly_result = await session.execute(
        select(
            Transaction.period_month,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("cnt"),
        ).where(
            *base_filter,
            Transaction.period_year == year,
        ).group_by(Transaction.period_month).order_by(Transaction.period_month)
    )
    monthly_rows = monthly_result.all()
    monthly_map = {row[0]: (row[1], row[2]) for row in monthly_rows}

    monthly_totals = []
    for m in range(1, 13):
        total, count = monthly_map.get(m, (0.0, 0))
        monthly_totals.append({
            "month": m,
            "month_name": calendar.month_abbr[m],
            "total_expenses": round(abs(total), 2),
            "transaction_count": count,
        })

    year_total = sum(mt["total_expenses"] for mt in monthly_totals)

    # --- Category breakdown ---
    cat_result = await session.execute(
        select(
            Transaction.effective_category,
            func.sum(Transaction.amount).label("total"),
        ).where(
            *base_filter,
            Transaction.period_year == year,
        ).group_by(Transaction.effective_category).order_by(func.sum(Transaction.amount))
    )
    cat_rows = cat_result.all()

    category_breakdown = []
    for row in cat_rows:
        cat_name = row[0] or "Uncategorized"
        cat_total = round(abs(row[1]), 2)
        pct = round(cat_total / year_total * 100, 1) if year_total > 0 else 0.0
        category_breakdown.append({
            "category": cat_name,
            "total": cat_total,
            "percentage": pct,
        })

    # --- Prior year comparison ---
    prior_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            *base_filter,
            Transaction.period_year == year - 1,
        )
    )
    prior_total_raw = prior_result.scalar()
    prior_year_total = round(abs(prior_total_raw), 2) if prior_total_raw else None

    yoy_change = None
    if prior_year_total and prior_year_total > 0:
        yoy_change = round((year_total - prior_year_total) / prior_year_total * 100, 1)

    return {
        "entity_id": entity.id,
        "entity_name": entity.name,
        "year": year,
        "monthly_totals": monthly_totals,
        "category_breakdown": category_breakdown,
        "year_total_expenses": round(year_total, 2),
        "prior_year_total_expenses": prior_year_total,
        "year_over_year_change_pct": yoy_change,
    }


async def get_entity_transactions(
    session: AsyncSession,
    entity_id: int,
    year: int,
    month: int | None = None,
) -> list[dict[str, Any]]:
    """Get transaction list for a business entity, suitable for CSV export.

    Returns list of dicts with: date, description, amount, category,
    tax_category, account_name, segment, notes.
    """
    q = (
        select(Transaction, Account.name.label("account_name"))
        .outerjoin(Account, Transaction.account_id == Account.id)
        .where(
            Transaction.effective_business_entity_id == entity_id,
            Transaction.is_excluded == False,
            Transaction.period_year == year,
        )
        .order_by(Transaction.date.desc())
    )
    if month:
        q = q.where(Transaction.period_month == month)

    result = await session.execute(q)
    rows = result.all()

    transactions = []
    for tx, acct_name in rows:
        transactions.append({
            "date": str(tx.date)[:10],
            "description": tx.description,
            "amount": tx.amount,
            "category": tx.effective_category or "",
            "tax_category": tx.effective_tax_category or "",
            "account": acct_name or "",
            "segment": tx.effective_segment or "",
            "notes": tx.notes or "",
        })

    return transactions


# ---------------------------------------------------------------------------
# Reimbursement Tracking
# ---------------------------------------------------------------------------

async def compute_reimbursement_report(
    session: AsyncSession,
    entity_id: int,
) -> dict[str, Any]:
    """Compare expenses on accounts linked to an entity vs reimbursement income.

    Finds accounts whose default_business_entity_id matches, sums their charges,
    and compares against income (positive-amount transactions) tagged to the entity
    with reimbursement-like categories.
    """
    # Verify entity
    ent_result = await session.execute(
        select(BusinessEntity).where(BusinessEntity.id == entity_id)
    )
    entity = ent_result.scalar_one_or_none()
    if not entity:
        return {"error": f"Entity {entity_id} not found"}

    # Find accounts linked to this entity (e.g., corporate card)
    acct_result = await session.execute(
        select(Account).where(Account.default_business_entity_id == entity_id)
    )
    linked_accounts = list(acct_result.scalars().all())
    linked_account_ids = [a.id for a in linked_accounts]

    # --- Expenses ---
    # If linked accounts exist (e.g., corporate card), track charges on those accounts.
    # Otherwise, track all negative-amount transactions tagged to this entity.
    expense_q = (
        select(
            func.strftime("%Y-%m", Transaction.date).label("month"),
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("cnt"),
        )
        .where(
            Transaction.amount < 0,
            Transaction.is_excluded == False,
        )
        .group_by(func.strftime("%Y-%m", Transaction.date))
    )
    if linked_account_ids:
        expense_q = expense_q.where(Transaction.account_id.in_(linked_account_ids))
    else:
        expense_q = expense_q.where(Transaction.effective_business_entity_id == entity_id)
    # Exclude internal movements (handle NULL categories)
    for cat in _EXCLUDED_CATEGORIES:
        expense_q = expense_q.where(or_(
            Transaction.effective_category.not_ilike(f"%{cat}%"),
            Transaction.effective_category.is_(None),
        ))

    expense_result = await session.execute(expense_q)
    expense_by_month = {r[0]: (abs(r[1]), r[2]) for r in expense_result.all()}

    # --- Reimbursements: income tagged to this entity from non-linked accounts ---
    # These are deposits to checking/savings categorized as entity expenses.
    # Exclude the linked accounts themselves (card payment credits aren't reimbursements).
    reimb_q = (
        select(
            func.strftime("%Y-%m", Transaction.date).label("month"),
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("cnt"),
        )
        .where(
            Transaction.effective_business_entity_id == entity_id,
            Transaction.amount > 0,
            Transaction.is_excluded == False,
        )
        .group_by(func.strftime("%Y-%m", Transaction.date))
    )
    if linked_account_ids:
        reimb_q = reimb_q.where(Transaction.account_id.not_in(linked_account_ids))
    # Exclude paychecks/salary — only want expense reimbursements and partner payments
    reimb_q = reimb_q.where(or_(
        Transaction.effective_category.not_ilike("%paycheck%"),
        Transaction.effective_category.is_(None),
    ))
    reimb_q = reimb_q.where(or_(
        Transaction.effective_category.not_ilike("%salary%"),
        Transaction.effective_category.is_(None),
    ))
    # Exclude credit card payments (those are from the user paying their own card)
    reimb_q = reimb_q.where(or_(
        Transaction.effective_category.not_ilike("%credit card payment%"),
        Transaction.effective_category.is_(None),
    ))

    reimb_result = await session.execute(reimb_q)
    reimb_by_month = {r[0]: (r[1], r[2]) for r in reimb_result.all()}

    # Merge months
    all_months = sorted(set(expense_by_month.keys()) | set(reimb_by_month.keys()))
    monthly = []
    running_balance = 0.0
    total_expenses = 0.0
    total_reimbursed = 0.0
    for m in all_months:
        exp_amt, exp_cnt = expense_by_month.get(m, (0.0, 0))
        reimb_amt, reimb_cnt = reimb_by_month.get(m, (0.0, 0))
        net = reimb_amt - exp_amt
        running_balance += net
        total_expenses += exp_amt
        total_reimbursed += reimb_amt
        monthly.append({
            "month": m,
            "expenses": round(exp_amt, 2),
            "expense_count": exp_cnt,
            "reimbursed": round(reimb_amt, 2),
            "reimbursement_count": reimb_cnt,
            "net": round(net, 2),
            "running_balance": round(running_balance, 2),
        })

    return {
        "entity_id": entity.id,
        "entity_name": entity.name,
        "linked_accounts": [{"id": a.id, "name": a.name, "institution": a.institution} for a in linked_accounts],
        "monthly": monthly,
        "total_expenses": round(total_expenses, 2),
        "total_reimbursed": round(total_reimbursed, 2),
        "balance": round(total_reimbursed - total_expenses, 2),
    }
