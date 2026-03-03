"""
Data Access Layer (DAL) — async SQLAlchemy helpers for all tables.
All functions accept an AsyncSession and return typed Python objects.
"""
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .schema import (
    Account,
    BusinessEntity,
    Document,
    FinancialPeriod,
    TaxItem,
    TaxStrategy,
    Transaction,
    VendorEntityRule,
)
from .schema_extended import (
    Budget,
    Goal,
    Reminder,
    RecurringTransaction,
    AmazonOrder,
    NetWorthSnapshot,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

async def get_account(session: AsyncSession, account_id: int) -> Optional[Account]:
    result = await session.execute(select(Account).where(Account.id == account_id))
    return result.scalar_one_or_none()


async def get_all_accounts(session: AsyncSession) -> list[Account]:
    result = await session.execute(select(Account).where(Account.is_active.is_(True)))
    return list(result.scalars().all())


async def upsert_account(session: AsyncSession, data: dict[str, Any]) -> Account:
    """Insert or update existing account matched by name + subtype."""
    result = await session.execute(
        select(Account).where(Account.name == data["name"], Account.subtype == data.get("subtype"))
    )
    existing = result.scalar_one_or_none()
    if existing:
        for key in ("institution", "last_four", "currency", "notes"):
            if key in data and data[key] is not None:
                setattr(existing, key, data[key])
        return existing
    account = Account(**data)
    session.add(account)
    await session.flush()
    return account


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

async def get_document_by_hash(session: AsyncSession, file_hash: str) -> Optional[Document]:
    result = await session.execute(select(Document).where(Document.file_hash == file_hash))
    return result.scalar_one_or_none()


async def create_document(session: AsyncSession, data: dict[str, Any]) -> Document:
    doc = Document(**data)
    session.add(doc)
    await session.flush()
    return doc


async def update_document_status(
    session: AsyncSession,
    document_id: int,
    status: str,
    error_message: Optional[str] = None,
    processed_path: Optional[str] = None,
) -> None:
    values: dict[str, Any] = {
        "status": status,
        "processed_at": datetime.now(timezone.utc),
    }
    if error_message is not None:
        values["error_message"] = error_message
    if processed_path is not None:
        values["processed_path"] = processed_path
    await session.execute(
        update(Document).where(Document.id == document_id).values(**values)
    )


async def get_all_documents(
    session: AsyncSession,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Document]:
    q = select(Document)
    if document_type:
        q = q.where(Document.document_type == document_type)
    if status:
        q = q.where(Document.status == status)
    q = q.order_by(Document.imported_at.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    return list(result.scalars().all())


async def count_documents(
    session: AsyncSession,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    q = select(func.count(Document.id))
    if document_type:
        q = q.where(Document.document_type == document_type)
    if status:
        q = q.where(Document.status == status)
    result = await session.execute(q)
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

async def create_transaction(session: AsyncSession, data: dict[str, Any]) -> Transaction:
    tx = Transaction(**data)
    session.add(tx)
    await session.flush()
    return tx


async def bulk_create_transactions(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> int:
    """Insert many transactions; skip duplicates by transaction_hash."""
    inserted = 0
    for row in rows:
        if row.get("transaction_hash"):
            existing = await session.execute(
                select(Transaction.id).where(
                    Transaction.transaction_hash == row["transaction_hash"]
                )
            )
            if existing.scalar_one_or_none():
                continue
        tx = Transaction(**row)
        session.add(tx)
        inserted += 1
    await session.flush()
    return inserted


async def get_transactions(
    session: AsyncSession,
    segment: Optional[str] = None,
    category: Optional[str] = None,
    business_entity_id: Optional[int] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    account_id: Optional[int] = None,
    is_excluded: bool = False,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Transaction]:
    q = select(Transaction).where(Transaction.is_excluded == is_excluded)
    if segment:
        q = q.where(Transaction.effective_segment == segment)
    if category:
        q = q.where(Transaction.effective_category == category)
    if business_entity_id is not None:
        q = q.where(Transaction.effective_business_entity_id == business_entity_id)
    if year:
        q = q.where(Transaction.period_year == year)
    if month:
        q = q.where(Transaction.period_month == month)
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if search:
        like_term = f"%{search}%"
        q = q.where(
            Transaction.description.ilike(like_term)
            | Transaction.effective_category.ilike(like_term)
        )
    q = q.order_by(Transaction.date.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    return list(result.scalars().all())


async def update_transaction_category(
    session: AsyncSession,
    transaction_id: int,
    category_override: Optional[str],
    tax_category_override: Optional[str],
    segment_override: Optional[str],
) -> None:
    values: dict[str, Any] = {
        "is_manually_reviewed": True,
        "updated_at": datetime.now(timezone.utc),
    }
    if category_override is not None:
        values["category_override"] = category_override
        values["effective_category"] = category_override
    if tax_category_override is not None:
        values["tax_category_override"] = tax_category_override
        values["effective_tax_category"] = tax_category_override
    if segment_override is not None:
        values["segment_override"] = segment_override
        values["effective_segment"] = segment_override
    await session.execute(
        update(Transaction).where(Transaction.id == transaction_id).values(**values)
    )


async def count_transactions(
    session: AsyncSession,
    year: Optional[int] = None,
    month: Optional[int] = None,
    segment: Optional[str] = None,
    category: Optional[str] = None,
    business_entity_id: Optional[int] = None,
    account_id: Optional[int] = None,
    is_excluded: bool = False,
    search: Optional[str] = None,
) -> int:
    q = select(func.count(Transaction.id)).where(Transaction.is_excluded == is_excluded)
    if year:
        q = q.where(Transaction.period_year == year)
    if month:
        q = q.where(Transaction.period_month == month)
    if segment:
        q = q.where(Transaction.effective_segment == segment)
    if category:
        q = q.where(Transaction.effective_category == category)
    if business_entity_id is not None:
        q = q.where(Transaction.effective_business_entity_id == business_entity_id)
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if search:
        like_term = f"%{search}%"
        q = q.where(
            Transaction.description.ilike(like_term)
            | Transaction.effective_category.ilike(like_term)
        )
    result = await session.execute(q)
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Tax Items
# ---------------------------------------------------------------------------

async def create_tax_item(session: AsyncSession, data: dict[str, Any]) -> TaxItem:
    item = TaxItem(**data)
    session.add(item)
    await session.flush()
    return item


async def get_tax_items(
    session: AsyncSession,
    tax_year: Optional[int] = None,
    form_type: Optional[str] = None,
) -> list[TaxItem]:
    q = select(TaxItem)
    if tax_year:
        q = q.where(TaxItem.tax_year == tax_year)
    if form_type:
        q = q.where(TaxItem.form_type == form_type)
    q = q.order_by(TaxItem.tax_year.desc(), TaxItem.form_type)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_tax_summary(session: AsyncSession, tax_year: int) -> dict[str, Any]:
    """Aggregate all tax items for a given year into a summary dict."""
    items = await get_tax_items(session, tax_year=tax_year)
    summary: dict[str, Any] = {
        "tax_year": tax_year,
        "w2_total_wages": 0.0,
        "w2_federal_withheld": 0.0,
        "w2_state_allocations": [],
        "nec_total": 0.0,
        "div_ordinary": 0.0,
        "div_qualified": 0.0,
        "div_capital_gain": 0.0,
        "capital_gains_short": 0.0,
        "capital_gains_long": 0.0,
        "interest_income": 0.0,
    }
    for item in items:
        if item.form_type == "w2":
            summary["w2_total_wages"] += item.w2_wages or 0.0
            summary["w2_federal_withheld"] += item.w2_federal_tax_withheld or 0.0
            if item.w2_state_allocations:
                allocs = json.loads(item.w2_state_allocations)
                summary["w2_state_allocations"].extend(allocs)
        elif item.form_type == "1099_nec":
            summary["nec_total"] += item.nec_nonemployee_compensation or 0.0
        elif item.form_type == "1099_div":
            summary["div_ordinary"] += item.div_total_ordinary or 0.0
            summary["div_qualified"] += item.div_qualified or 0.0
            summary["div_capital_gain"] += item.div_total_capital_gain or 0.0
        elif item.form_type == "1099_b":
            gain = item.b_gain_loss or 0.0
            if item.b_term == "short":
                summary["capital_gains_short"] += gain
            else:
                summary["capital_gains_long"] += gain
        elif item.form_type == "1099_int":
            summary["interest_income"] += item.int_interest or 0.0
    return summary


# ---------------------------------------------------------------------------
# Tax Strategies
# ---------------------------------------------------------------------------

async def replace_tax_strategies(
    session: AsyncSession, tax_year: int, strategies: list[dict[str, Any]]
) -> list[TaxStrategy]:
    """Delete non-dismissed strategies for the year and insert fresh ones."""
    await session.execute(
        delete(TaxStrategy).where(
            TaxStrategy.tax_year == tax_year,
            TaxStrategy.is_dismissed == False,
        )
    )
    created = []
    for s in strategies:
        obj = TaxStrategy(tax_year=tax_year, **s)
        session.add(obj)
        created.append(obj)
    await session.flush()
    return created


async def get_tax_strategies(
    session: AsyncSession,
    tax_year: Optional[int] = None,
    include_dismissed: bool = False,
) -> list[TaxStrategy]:
    q = select(TaxStrategy)
    if tax_year:
        q = q.where(TaxStrategy.tax_year == tax_year)
    if not include_dismissed:
        q = q.where(TaxStrategy.is_dismissed == False)
    q = q.order_by(TaxStrategy.priority.asc(), TaxStrategy.estimated_savings_high.desc())
    result = await session.execute(q)
    return list(result.scalars().all())


async def dismiss_strategy(session: AsyncSession, strategy_id: int) -> None:
    await session.execute(
        update(TaxStrategy)
        .where(TaxStrategy.id == strategy_id)
        .values(is_dismissed=True)
    )


# ---------------------------------------------------------------------------
# Financial Periods
# ---------------------------------------------------------------------------

async def upsert_financial_period(
    session: AsyncSession, data: dict[str, Any]
) -> FinancialPeriod:
    """Insert or update a financial period summary."""
    q = select(FinancialPeriod).where(
        FinancialPeriod.year == data["year"],
        FinancialPeriod.month == data.get("month"),
        FinancialPeriod.segment == data.get("segment", "all"),
    )
    result = await session.execute(q)
    existing = result.scalar_one_or_none()
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        existing.computed_at = datetime.now(timezone.utc)
        return existing
    period = FinancialPeriod(**data)
    session.add(period)
    await session.flush()
    return period


async def get_financial_periods(
    session: AsyncSession,
    year: Optional[int] = None,
    segment: str = "all",
) -> list[FinancialPeriod]:
    q = select(FinancialPeriod).where(FinancialPeriod.segment == segment)
    if year:
        q = q.where(FinancialPeriod.year == year)
    q = q.order_by(FinancialPeriod.year.desc(), FinancialPeriod.month.asc())
    result = await session.execute(q)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Business Entities
# ---------------------------------------------------------------------------

async def get_all_business_entities(
    session: AsyncSession,
    include_inactive: bool = False,
) -> list[BusinessEntity]:
    q = select(BusinessEntity)
    if not include_inactive:
        q = q.where(BusinessEntity.is_active.is_(True))
    q = q.order_by(BusinessEntity.name)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_business_entity(session: AsyncSession, entity_id: int) -> Optional[BusinessEntity]:
    result = await session.execute(select(BusinessEntity).where(BusinessEntity.id == entity_id))
    return result.scalar_one_or_none()


async def get_business_entity_by_name(session: AsyncSession, name: str) -> Optional[BusinessEntity]:
    result = await session.execute(select(BusinessEntity).where(BusinessEntity.name == name))
    return result.scalar_one_or_none()


async def upsert_business_entity(session: AsyncSession, data: dict[str, Any]) -> BusinessEntity:
    """Insert or update a business entity matched by name."""
    result = await session.execute(
        select(BusinessEntity).where(BusinessEntity.name == data["name"])
    )
    existing = result.scalar_one_or_none()
    if existing:
        for k, v in data.items():
            if k != "name" and v is not None:
                setattr(existing, k, v)
        existing.updated_at = datetime.now(timezone.utc)
        return existing
    entity = BusinessEntity(**data)
    session.add(entity)
    await session.flush()
    return entity


async def delete_business_entity(session: AsyncSession, entity_id: int) -> bool:
    result = await session.execute(
        select(BusinessEntity).where(BusinessEntity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        return False
    entity.is_active = False
    entity.updated_at = datetime.now(timezone.utc)
    return True


# ---------------------------------------------------------------------------
# Vendor Entity Rules
# ---------------------------------------------------------------------------

async def get_all_vendor_rules(
    session: AsyncSession,
    entity_id: Optional[int] = None,
    active_only: bool = True,
) -> list[VendorEntityRule]:
    q = select(VendorEntityRule)
    if active_only:
        q = q.where(VendorEntityRule.is_active.is_(True))
    if entity_id is not None:
        q = q.where(VendorEntityRule.business_entity_id == entity_id)
    q = q.order_by(VendorEntityRule.priority.desc(), VendorEntityRule.vendor_pattern)
    result = await session.execute(q)
    return list(result.scalars().all())


async def create_vendor_rule(session: AsyncSession, data: dict[str, Any]) -> VendorEntityRule:
    rule = VendorEntityRule(**data)
    session.add(rule)
    await session.flush()
    return rule


async def delete_vendor_rule(session: AsyncSession, rule_id: int) -> bool:
    result = await session.execute(
        select(VendorEntityRule).where(VendorEntityRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return False
    rule.is_active = False
    return True


# ---------------------------------------------------------------------------
# Entity Assignment Engine
# ---------------------------------------------------------------------------

async def apply_entity_rules(
    session: AsyncSession,
    transaction_id: Optional[int] = None,
    document_id: Optional[int] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> int:
    """
    Apply entity assignment rules to transactions. Priority order:
    1. Manual override (business_entity_override) — skip if set
    2. Vendor pattern + date match (VendorEntityRule)
    3. Account-level default (Account.default_business_entity_id)
    4. Leave null for AI to assign later

    Returns count of transactions updated.
    """
    q = select(Transaction).where(
        Transaction.business_entity_override.is_(None),
        Transaction.is_manually_reviewed.is_(False),
    )
    if transaction_id:
        q = q.where(Transaction.id == transaction_id)
    if document_id:
        q = q.where(Transaction.source_document_id == document_id)
    if year:
        q = q.where(Transaction.period_year == year)
    if month:
        q = q.where(Transaction.period_month == month)

    result = await session.execute(q)
    transactions = list(result.scalars().all())

    if not transactions:
        return 0

    rules = await get_all_vendor_rules(session, active_only=True)
    account_ids = {t.account_id for t in transactions}
    acct_result = await session.execute(
        select(Account).where(Account.id.in_(account_ids))
    )
    accounts_by_id = {a.id: a for a in acct_result.scalars().all()}

    updated = 0
    for tx in transactions:
        entity_id = None
        segment_from_rule = None
        tx_date = tx.date.date() if isinstance(tx.date, datetime) else tx.date

        for rule in rules:
            if not rule.is_active:
                continue
            if rule.effective_from and tx_date < rule.effective_from:
                continue
            if rule.effective_to and tx_date > rule.effective_to:
                continue
            pattern = rule.vendor_pattern.lower()
            desc = tx.description.lower()
            if re.search(pattern, desc):
                entity_id = rule.business_entity_id
                segment_from_rule = rule.segment_override
                break

        if entity_id is None:
            acct = accounts_by_id.get(tx.account_id)
            if acct and acct.default_business_entity_id:
                entity_id = acct.default_business_entity_id
            if acct and acct.default_segment:
                segment_from_rule = segment_from_rule or acct.default_segment

        changed = False
        if entity_id and tx.business_entity_id != entity_id:
            tx.business_entity_id = entity_id
            tx.effective_business_entity_id = entity_id
            changed = True
        if segment_from_rule and tx.segment != segment_from_rule:
            tx.segment = segment_from_rule
            tx.effective_segment = segment_from_rule
            changed = True
        if changed:
            tx.updated_at = datetime.now(timezone.utc)
            updated += 1

    if updated:
        await session.flush()
    logger.info(f"Entity rules applied: {updated}/{len(transactions)} transactions updated")
    return updated


async def bulk_reassign_entity(
    session: AsyncSession,
    from_entity_id: int,
    to_entity_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """Reassign all transactions from one entity to another, optionally within a date range."""
    q = (
        update(Transaction)
        .where(Transaction.effective_business_entity_id == from_entity_id)
    )
    if date_from:
        q = q.where(Transaction.date >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.where(Transaction.date <= datetime.combine(date_to, datetime.max.time()))

    q = q.values(
        business_entity_id=to_entity_id,
        effective_business_entity_id=to_entity_id,
        updated_at=datetime.now(timezone.utc),
    )
    result = await session.execute(q)
    return result.rowcount


async def update_transaction_entity(
    session: AsyncSession,
    transaction_id: int,
    business_entity_id: Optional[int],
) -> None:
    """Manually set entity override on a single transaction."""
    values: dict[str, Any] = {
        "business_entity_override": business_entity_id,
        "effective_business_entity_id": business_entity_id,
        "is_manually_reviewed": True,
        "updated_at": datetime.now(timezone.utc),
    }
    await session.execute(
        update(Transaction).where(Transaction.id == transaction_id).values(**values)
    )


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

async def get_budgets(
    session: AsyncSession,
    year: int,
    month: int,
    segment: Optional[str] = None,
) -> list[Budget]:
    q = select(Budget).where(Budget.year == year, Budget.month == month)
    if segment:
        q = q.where(Budget.segment == segment)
    q = q.order_by(Budget.category)
    result = await session.execute(q)
    return list(result.scalars().all())


async def upsert_budget(session: AsyncSession, data: dict[str, Any]) -> Budget:
    """Insert or update a budget matched by year+month+category+segment."""
    result = await session.execute(
        select(Budget).where(
            Budget.year == data["year"],
            Budget.month == data["month"],
            Budget.category == data["category"],
            Budget.segment == data.get("segment", "personal"),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        for k, v in data.items():
            if v is not None:
                setattr(existing, k, v)
        existing.updated_at = datetime.now(timezone.utc)
        return existing
    budget = Budget(**data)
    session.add(budget)
    await session.flush()
    return budget


async def delete_budget(session: AsyncSession, budget_id: int) -> bool:
    result = await session.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if not budget:
        return False
    await session.execute(delete(Budget).where(Budget.id == budget_id))
    return True


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

async def get_goals(
    session: AsyncSession,
    status: Optional[str] = None,
) -> list[Goal]:
    q = select(Goal)
    if status:
        q = q.where(Goal.status == status)
    q = q.order_by(Goal.created_at.desc())
    result = await session.execute(q)
    return list(result.scalars().all())


async def upsert_goal(session: AsyncSession, data: dict[str, Any]) -> Goal:
    """Insert or update a goal matched by id."""
    if data.get("id"):
        result = await session.execute(select(Goal).where(Goal.id == data["id"]))
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in data.items():
                if k != "id" and v is not None:
                    setattr(existing, k, v)
            existing.updated_at = datetime.now(timezone.utc)
            return existing
    goal = Goal(**{k: v for k, v in data.items() if k != "id"})
    session.add(goal)
    await session.flush()
    return goal


async def delete_goal(session: AsyncSession, goal_id: int) -> bool:
    result = await session.execute(select(Goal).where(Goal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        return False
    await session.execute(delete(Goal).where(Goal.id == goal_id))
    return True


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

async def get_reminders(
    session: AsyncSession,
    reminder_type: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Reminder]:
    q = select(Reminder)
    if reminder_type:
        q = q.where(Reminder.reminder_type == reminder_type)
    if status:
        q = q.where(Reminder.status == status)
    q = q.order_by(Reminder.due_date.asc())
    result = await session.execute(q)
    return list(result.scalars().all())


async def create_reminder_record(session: AsyncSession, data: dict[str, Any]) -> Reminder:
    reminder = Reminder(**data)
    session.add(reminder)
    await session.flush()
    return reminder


# ---------------------------------------------------------------------------
# Recurring Transactions
# ---------------------------------------------------------------------------

async def get_recurring(
    session: AsyncSession,
    status: Optional[str] = None,
) -> list[RecurringTransaction]:
    q = select(RecurringTransaction)
    if status:
        q = q.where(RecurringTransaction.status == status)
    q = q.order_by(RecurringTransaction.name)
    result = await session.execute(q)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Net Worth Snapshots
# ---------------------------------------------------------------------------

async def get_net_worth_snapshots(
    session: AsyncSession,
    year: Optional[int] = None,
) -> list[NetWorthSnapshot]:
    q = select(NetWorthSnapshot)
    if year:
        q = q.where(NetWorthSnapshot.year == year)
    q = q.order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
    result = await session.execute(q)
    return list(result.scalars().all())
