"""
SQLite schema definitions via SQLAlchemy ORM.
Run `python -m pipeline.db.schema` to initialize or migrate the database.
"""
import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from pipeline.utils import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Account(Base):
    """
    Represents a financial account: credit card, investment brokerage,
    W-2 employer, or board income source.
    """
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    # personal | business | investment | income
    account_type = Column(String(50), nullable=False)
    # credit_card | brokerage | w2_employer | board_income | bank
    subtype = Column(String(50), nullable=True)
    institution = Column(String(255), nullable=True)
    last_four = Column(String(4), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    is_active = Column(Boolean, nullable=False, default=True)

    # Card/account-level defaults: all new transactions inherit these
    # personal | business | investment | reimbursable
    default_segment = Column(String(20), nullable=True)
    default_business_entity_id = Column(Integer, ForeignKey("business_entities.id"), nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="account")
    documents = relationship("Document", back_populates="account")
    default_business_entity = relationship("BusinessEntity", foreign_keys=[default_business_entity_id])


class Document(Base):
    """
    Tracks every imported file (CSV or PDF). Dedup via SHA-256 hash.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), nullable=False)
    original_path = Column(String(1000), nullable=False)
    processed_path = Column(String(1000), nullable=True)
    # csv | pdf
    file_type = Column(String(10), nullable=False)
    # credit_card | w2 | 1099_nec | 1099_div | 1099_b | brokerage_statement | other
    document_type = Column(String(50), nullable=False)
    # pending | processing | completed | failed
    status = Column(String(20), nullable=False, default="pending")
    file_hash = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    tax_year = Column(Integer, nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    imported_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("file_hash", name="uq_document_hash"),)

    account = relationship("Account", back_populates="documents")
    transactions = relationship("Transaction", back_populates="source_document")
    tax_items = relationship("TaxItem", back_populates="source_document")


class Transaction(Base):
    """
    Single financial transaction. May come from CSV (credit card) or be
    manually entered. AI-categorized fields stored alongside any manual overrides.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # Core transaction data
    date = Column(DateTime, nullable=False)
    description = Column(String(500), nullable=False)
    amount = Column(Float, nullable=False)  # negative = debit/expense, positive = credit/income
    currency = Column(String(3), nullable=False, default="USD")

    # Segmentation
    # personal | business | investment | reimbursable
    segment = Column(String(20), nullable=False, default="personal")

    # Business entity tracking
    business_entity_id = Column(Integer, ForeignKey("business_entities.id"), nullable=True)
    business_entity_override = Column(Integer, ForeignKey("business_entities.id"), nullable=True)
    effective_business_entity_id = Column(Integer, ForeignKey("business_entities.id"), nullable=True)

    # Reimbursement tracking (for corporate card expenses)
    # pending | submitted | reimbursed | denied | n/a
    reimbursement_status = Column(String(20), nullable=True)
    reimbursement_match_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    # AI-assigned categorization
    category = Column(String(100), nullable=True)
    # IRS Schedule / line item reference (e.g., "Schedule C Line 14 - Employee Benefits")
    tax_category = Column(String(200), nullable=True)
    ai_confidence = Column(Float, nullable=True)  # 0.0–1.0

    # Manual override fields (set when user corrects AI categorization)
    category_override = Column(String(100), nullable=True)
    tax_category_override = Column(String(200), nullable=True)
    segment_override = Column(String(20), nullable=True)
    is_manually_reviewed = Column(Boolean, nullable=False, default=False)

    # Effective values (override takes precedence over AI)
    # These are computed properties accessed via @property in Python but
    # stored for query performance
    effective_category = Column(String(100), nullable=True)
    effective_tax_category = Column(String(200), nullable=True)
    effective_segment = Column(String(20), nullable=True)

    # Period tracking
    period_month = Column(Integer, nullable=True)  # 1–12
    period_year = Column(Integer, nullable=True)

    # Deduplication
    transaction_hash = Column(String(64), nullable=True)

    # Plaid-enriched fields (populated for Plaid-sourced transactions)
    merchant_name = Column(String(255), nullable=True)
    authorized_date = Column(DateTime, nullable=True)
    payment_channel = Column(String(20), nullable=True)  # online | in store | other
    plaid_pfc_primary = Column(String(100), nullable=True)  # e.g. "FOOD_AND_DRINK"
    plaid_pfc_detailed = Column(String(100), nullable=True)  # e.g. "FOOD_AND_DRINK_COFFEE"
    plaid_pfc_confidence = Column(String(20), nullable=True)  # VERY_HIGH | HIGH | MEDIUM | LOW
    merchant_logo_url = Column(String(500), nullable=True)
    merchant_website = Column(String(500), nullable=True)
    plaid_location_json = Column(Text, nullable=True)  # JSON: {address, city, region, postal_code, country, lat, lon}
    plaid_counterparties_json = Column(Text, nullable=True)  # JSON array of counterparty objects

    notes = Column(Text, nullable=True)
    is_excluded = Column(Boolean, nullable=False, default=False)  # hide from reports

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_transaction_hash", "transaction_hash"),
        Index("ix_transaction_period", "period_year", "period_month"),
        Index("ix_transaction_segment_category", "effective_segment", "effective_category"),
    )

    account = relationship("Account", back_populates="transactions")
    source_document = relationship("Document", back_populates="transactions")
    business_entity = relationship("BusinessEntity", foreign_keys=[business_entity_id])
    effective_entity = relationship("BusinessEntity", foreign_keys=[effective_business_entity_id])
    reimbursement_match = relationship("Transaction", remote_side=[id], foreign_keys=[reimbursement_match_id])


class BusinessEntity(Base):
    """
    A business, employer, or entity that transactions can be attributed to.
    Supports W-2 employers, Schedule C businesses, K-1 partnerships, and
    provisional entities for startup cost tracking (Section 195).
    """
    __tablename__ = "business_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    # Owner of this entity (for multi-person households)
    owner = Column(String(100), nullable=True)
    # sole_prop | partnership | llc | s_corp | c_corp | employer
    entity_type = Column(String(50), nullable=False, default="sole_prop")
    # w2 | schedule_c | k1 | section_195 | none
    tax_treatment = Column(String(50), nullable=False, default="schedule_c")
    ein = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_provisional = Column(Boolean, nullable=False, default=False)
    active_from = Column(Date, nullable=True)
    active_to = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class VendorEntityRule(Base):
    """
    Maps vendor/merchant patterns to business entities with optional date ranges.
    Enables time-based transitions (e.g., Upwork -> MAV before 2026, Upwork -> AutoRev after).
    """
    __tablename__ = "vendor_entity_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendor_pattern = Column(String(255), nullable=False)
    business_entity_id = Column(Integer, ForeignKey("business_entities.id"), nullable=False)
    # Optional segment override (e.g., force "business" for this vendor)
    segment_override = Column(String(20), nullable=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    priority = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    business_entity = relationship("BusinessEntity")

    __table_args__ = (
        Index("ix_vendor_rule_pattern", "vendor_pattern"),
    )


class TaxItem(Base):
    """
    Structured tax data extracted from W-2, 1099-NEC, 1099-DIV, 1099-B, etc.
    Each row represents one box/field from one document.
    """
    __tablename__ = "tax_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    tax_year = Column(Integer, nullable=False)
    # w2 | 1099_nec | 1099_div | 1099_b | 1099_int | k1
    form_type = Column(String(20), nullable=False)

    # Payer / employer info
    payer_name = Column(String(255), nullable=True)
    payer_ein = Column(String(20), nullable=True)

    # W-2 fields (boxes 1–20)
    w2_wages = Column(Float, nullable=True)                    # Box 1
    w2_federal_tax_withheld = Column(Float, nullable=True)     # Box 2
    w2_ss_wages = Column(Float, nullable=True)                 # Box 3
    w2_ss_tax_withheld = Column(Float, nullable=True)          # Box 4
    w2_medicare_wages = Column(Float, nullable=True)           # Box 5
    w2_medicare_tax_withheld = Column(Float, nullable=True)    # Box 6
    w2_state = Column(String(2), nullable=True)                # Box 15
    w2_state_wages = Column(Float, nullable=True)              # Box 16
    w2_state_income_tax = Column(Float, nullable=True)         # Box 17
    # Multi-state: JSON array of {state, wages, tax} dicts
    w2_state_allocations = Column(Text, nullable=True)

    # 1099-NEC fields
    nec_nonemployee_compensation = Column(Float, nullable=True)  # Box 1
    nec_federal_tax_withheld = Column(Float, nullable=True)      # Box 4

    # 1099-DIV fields
    div_total_ordinary = Column(Float, nullable=True)    # Box 1a
    div_qualified = Column(Float, nullable=True)         # Box 1b
    div_total_capital_gain = Column(Float, nullable=True) # Box 2a
    div_federal_tax_withheld = Column(Float, nullable=True) # Box 4

    # 1099-B fields (capital gains/losses)
    b_proceeds = Column(Float, nullable=True)
    b_cost_basis = Column(Float, nullable=True)
    b_gain_loss = Column(Float, nullable=True)
    b_term = Column(String(10), nullable=True)  # short | long
    b_wash_sale_loss = Column(Float, nullable=True)

    # 1099-INT fields
    int_interest = Column(Float, nullable=True)          # Box 1
    int_federal_tax_withheld = Column(Float, nullable=True) # Box 4

    # Raw JSON of all extracted fields (for future expansion)
    raw_fields = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    source_document = relationship("Document", back_populates="tax_items")


class TaxStrategy(Base):
    """
    AI-generated tax optimization recommendations.
    Regenerated each time the tax analyzer runs.
    """
    __tablename__ = "tax_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tax_year = Column(Integer, nullable=False)
    # 1 (highest) – 5 (lowest)
    priority = Column(Integer, nullable=False, default=3)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    # bracket | deduction | credit | structure | timing | retirement | investment
    strategy_type = Column(String(50), nullable=False)
    estimated_savings_low = Column(Float, nullable=True)
    estimated_savings_high = Column(Float, nullable=True)
    action_required = Column(Text, nullable=True)
    deadline = Column(String(100), nullable=True)
    is_dismissed = Column(Boolean, nullable=False, default=False)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OutlierFeedback(Base):
    """
    User feedback on flagged outlier transactions. Drives learning:
    - recurring: expected annual/periodic cost → amortize into monthly budget
    - one_time:  true one-off purchase → exclude from normalized budget
    - not_outlier: regular expense wrongly flagged → suppress in future detection
    """
    __tablename__ = "outlier_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    classification = Column(
        String(20), nullable=False
    )  # recurring | one_time | not_outlier
    user_note = Column(Text, nullable=True)
    # Pattern extracted from the description for matching future transactions
    description_pattern = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    # If true, this feedback suppresses/classifies future matching outliers
    apply_to_future = Column(Boolean, nullable=False, default=True)
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_outlier_feedback_txn"),
        Index("ix_outlier_feedback_year", "year"),
        Index("ix_outlier_feedback_pattern", "description_pattern"),
    )

    transaction = relationship("Transaction")


class FinancialPeriod(Base):
    """
    Pre-computed monthly/annual financial period summaries for fast dashboard reads.
    Regenerated by the report engine after each import.
    """
    __tablename__ = "financial_periods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)   # NULL = annual summary
    segment = Column(String(20), nullable=False, default="all")  # all | personal | business | investment | reimbursable

    total_income = Column(Float, nullable=False, default=0.0)
    total_expenses = Column(Float, nullable=False, default=0.0)
    net_cash_flow = Column(Float, nullable=False, default=0.0)
    w2_income = Column(Float, nullable=False, default=0.0)
    investment_income = Column(Float, nullable=False, default=0.0)
    board_income = Column(Float, nullable=False, default=0.0)
    business_expenses = Column(Float, nullable=False, default=0.0)
    personal_expenses = Column(Float, nullable=False, default=0.0)

    # JSON blob of category-level breakdowns
    expense_breakdown = Column(Text, nullable=True)
    income_breakdown = Column(Text, nullable=True)

    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("year", "month", "segment", name="uq_period_segment"),
    )


async def init_db(engine: Optional[AsyncEngine] = None) -> AsyncEngine:
    """Create all tables. Safe to call on existing DB (no-op if tables exist)."""
    if engine is None:
        engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine


# ═══════════════════════════════════════════════════════════════════════════
# Extended schema (formerly schema_extended.py)
# Budget, Recurring, Goals, Reminders, Plaid, Amazon, ManualAssets, NetWorth
# ═══════════════════════════════════════════════════════════════════════════


class PlaidItem(Base):
    __tablename__ = "plaid_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(100), nullable=False, unique=True)
    access_token = Column(String(200), nullable=False)
    institution_id = Column(String(100), nullable=True)
    institution_name = Column(String(255), nullable=True)
    account_types = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    error_code = Column(String(100), nullable=True)
    plaid_cursor = Column(String(500), nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    consent_expiration = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    plaid_accounts = relationship("PlaidAccount", back_populates="plaid_item")


class PlaidAccount(Base):
    __tablename__ = "plaid_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plaid_item_id = Column(Integer, ForeignKey("plaid_items.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    plaid_account_id = Column(String(100), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    official_name = Column(String(255), nullable=True)
    type = Column(String(50), nullable=False)
    subtype = Column(String(50), nullable=True)
    current_balance = Column(Float, nullable=True)
    available_balance = Column(Float, nullable=True)
    limit_balance = Column(Float, nullable=True)
    iso_currency = Column(String(3), nullable=False, default="USD")
    last_updated = Column(DateTime, nullable=True)
    mask = Column(String(4), nullable=True)

    plaid_item = relationship("PlaidItem", back_populates="plaid_accounts")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    category = Column(String(100), nullable=False)
    segment = Column(String(20), nullable=False, default="personal")
    budget_amount = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("year", "month", "category", "segment", name="uq_budget_period_category"),
    )


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description_pattern = Column(String(500), nullable=True)
    amount = Column(Float, nullable=False)
    amount_tolerance = Column(Float, nullable=False, default=2.0)
    currency = Column(String(3), nullable=False, default="USD")
    frequency = Column(String(20), nullable=False, default="monthly")
    category = Column(String(100), nullable=True)
    segment = Column(String(20), nullable=False, default="personal")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    last_seen_date = Column(DateTime, nullable=True)
    next_expected_date = Column(DateTime, nullable=True)
    first_seen_date = Column(DateTime, nullable=True)
    is_auto_detected = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    goal_type = Column(String(50), nullable=False, default="savings")
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, nullable=False, default=0.0)
    target_date = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    color = Column(String(7), nullable=True, default="#6366f1")
    icon = Column(String(50), nullable=True)
    monthly_contribution = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    reminder_type = Column(String(50), nullable=False, default="custom")
    due_date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=True)
    advance_notice = Column(String(20), nullable=False, default="7_days")
    status = Column(String(20), nullable=False, default="pending")
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_rule = Column(String(100), nullable=True)
    last_notified_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    related_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AmazonOrder(Base):
    __tablename__ = "amazon_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(80), nullable=False, unique=True)
    parent_order_id = Column(String(50), nullable=True)
    order_date = Column(DateTime, nullable=False)
    items_description = Column(Text, nullable=False)
    total_charged = Column(Float, nullable=False)
    suggested_category = Column(String(100), nullable=True)
    effective_category = Column(String(100), nullable=True)
    segment = Column(String(20), nullable=False, default="personal")
    is_business = Column(Boolean, nullable=False, default=False)
    is_gift = Column(Boolean, nullable=False, default=False)
    is_digital = Column(Boolean, nullable=False, default=False)
    is_refund = Column(Boolean, nullable=False, default=False)
    owner = Column(String(50), nullable=True)
    payment_method_last4 = Column(String(50), nullable=True)
    matched_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    raw_items = Column(Text, nullable=True)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ManualAsset(Base):
    __tablename__ = "manual_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    asset_type = Column(String(50), nullable=False)
    is_liability = Column(Boolean, nullable=False, default=False)
    current_value = Column(Float, nullable=False, default=0.0)
    purchase_price = Column(Float, nullable=True)
    purchase_date = Column(DateTime, nullable=True)
    institution = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = Column(String(100), nullable=True)
    account_subtype = Column(String(50), nullable=True)
    custodian = Column(String(255), nullable=True)
    employer = Column(String(255), nullable=True)
    tax_treatment = Column(String(30), nullable=True)
    is_retirement_account = Column(Boolean, nullable=True, default=False)
    as_of_date = Column(DateTime, nullable=True)
    vested_balance = Column(Float, nullable=True)
    contribution_type = Column(String(20), nullable=True)
    contribution_rate_pct = Column(Float, nullable=True)
    employee_contribution_ytd = Column(Float, nullable=True)
    employer_contribution_ytd = Column(Float, nullable=True)
    employer_match_pct = Column(Float, nullable=True)
    employer_match_limit_pct = Column(Float, nullable=True)
    annual_return_pct = Column(Float, nullable=True)
    allocation_json = Column(Text, nullable=True)
    beneficiary = Column(String(255), nullable=True)


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(DateTime, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    total_assets = Column(Float, nullable=False, default=0.0)
    total_liabilities = Column(Float, nullable=False, default=0.0)
    net_worth = Column(Float, nullable=False, default=0.0)
    checking_savings = Column(Float, nullable=False, default=0.0)
    investment_value = Column(Float, nullable=False, default=0.0)
    real_estate_value = Column(Float, nullable=False, default=0.0)
    vehicle_value = Column(Float, nullable=False, default=0.0)
    other_assets = Column(Float, nullable=False, default=0.0)
    credit_card_debt = Column(Float, nullable=False, default=0.0)
    loan_balance = Column(Float, nullable=False, default=0.0)
    mortgage_balance = Column(Float, nullable=False, default=0.0)
    account_balances = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_net_worth_period"),
    )


_AMAZON_ORDER_NEW_COLS = [
    ("owner", "VARCHAR(50)"),
    ("payment_method_last4", "VARCHAR(50)"),
    ("is_digital", "BOOLEAN NOT NULL DEFAULT 0"),
    ("is_refund", "BOOLEAN NOT NULL DEFAULT 0"),
    ("parent_order_id", "VARCHAR(50)"),
]


async def _migrate_amazon_orders(conn) -> None:
    """Add new columns to amazon_orders for existing databases (idempotent)."""
    from sqlalchemy import text
    result = await conn.execute(text("PRAGMA table_info(amazon_orders)"))
    existing = {row[1] for row in result.fetchall()}
    for col_name, col_def in _AMAZON_ORDER_NEW_COLS:
        if col_name not in existing:
            await conn.execute(
                text(f"ALTER TABLE amazon_orders ADD COLUMN {col_name} {col_def}")
            )


async def init_extended_db():
    """Add extended tables to the existing database."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_amazon_orders(conn)
    await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════
# HENRY schema (formerly schema_henry.py)
# Investments, Market, Retirement, Scenarios, Crypto, Equity Comp
# ═══════════════════════════════════════════════════════════════════════════


class InvestmentHolding(Base):
    __tablename__ = "investment_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    ticker = Column(String(20), nullable=False)
    name = Column(String(255), nullable=True)
    asset_class = Column(String(50), nullable=False, default="stock")
    shares = Column(Float, nullable=False)
    cost_basis_per_share = Column(Float, nullable=True)
    total_cost_basis = Column(Float, nullable=True)
    purchase_date = Column(Date, nullable=True)
    current_price = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    unrealized_gain_loss = Column(Float, nullable=True)
    unrealized_gain_loss_pct = Column(Float, nullable=True)
    tax_lot_id = Column(String(100), nullable=True)
    term = Column(String(10), nullable=True)
    sector = Column(String(100), nullable=True)
    dividend_yield = Column(Float, nullable=True)
    last_price_update = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_holding_ticker", "ticker"),
        Index("ix_holding_account", "account_id"),
    )

    account = relationship("Account", foreign_keys=[account_id])


class MarketQuoteCache(Base):
    __tablename__ = "market_quotes_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, unique=True)
    company_name = Column(String(255), nullable=True)
    price = Column(Float, nullable=True)
    previous_close = Column(Float, nullable=True)
    change = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    market_cap = Column(Float, nullable=True)
    pe_ratio = Column(Float, nullable=True)
    forward_pe = Column(Float, nullable=True)
    dividend_yield = Column(Float, nullable=True)
    fifty_two_week_high = Column(Float, nullable=True)
    fifty_two_week_low = Column(Float, nullable=True)
    beta = Column(Float, nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    earnings_per_share = Column(Float, nullable=True)
    book_value = Column(Float, nullable=True)
    profit_margin = Column(Float, nullable=True)
    revenue_growth = Column(Float, nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EconomicIndicatorCache(Base):
    __tablename__ = "economic_indicators_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(String(50), nullable=False)
    source = Column(String(20), nullable=False, default="alpha_vantage")
    label = Column(String(255), nullable=True)
    date = Column(Date, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("series_id", "date", name="uq_indicator_series_date"),
        Index("ix_indicator_series", "series_id"),
    )


class RetirementProfile(Base):
    __tablename__ = "retirement_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, default="My Retirement Plan")
    current_age = Column(Integer, nullable=False)
    retirement_age = Column(Integer, nullable=False, default=65)
    life_expectancy = Column(Integer, nullable=False, default=90)
    current_annual_income = Column(Float, nullable=False)
    expected_income_growth_pct = Column(Float, nullable=False, default=3.0)
    expected_social_security_monthly = Column(Float, nullable=False, default=0.0)
    social_security_start_age = Column(Integer, nullable=False, default=67)
    pension_monthly = Column(Float, nullable=False, default=0.0)
    other_retirement_income_monthly = Column(Float, nullable=False, default=0.0)
    current_retirement_savings = Column(Float, nullable=False, default=0.0)
    current_other_investments = Column(Float, nullable=False, default=0.0)
    monthly_retirement_contribution = Column(Float, nullable=False, default=0.0)
    employer_match_pct = Column(Float, nullable=False, default=0.0)
    employer_match_limit_pct = Column(Float, nullable=False, default=6.0)
    desired_annual_retirement_income = Column(Float, nullable=True)
    income_replacement_pct = Column(Float, nullable=False, default=80.0)
    healthcare_annual_estimate = Column(Float, nullable=False, default=12000.0)
    additional_annual_expenses = Column(Float, nullable=False, default=0.0)
    current_annual_expenses = Column(Float, nullable=True)
    debt_payoffs_json = Column(Text, nullable=True)
    inflation_rate_pct = Column(Float, nullable=False, default=3.0)
    pre_retirement_return_pct = Column(Float, nullable=False, default=7.0)
    post_retirement_return_pct = Column(Float, nullable=False, default=5.0)
    tax_rate_in_retirement_pct = Column(Float, nullable=False, default=22.0)
    target_nest_egg = Column(Float, nullable=True)
    projected_nest_egg_at_retirement = Column(Float, nullable=True)
    monthly_savings_needed = Column(Float, nullable=True)
    retirement_readiness_pct = Column(Float, nullable=True)
    years_money_will_last = Column(Float, nullable=True)
    projected_monthly_retirement_income = Column(Float, nullable=True)
    savings_gap = Column(Float, nullable=True)
    fire_number = Column(Float, nullable=True)
    coast_fire_number = Column(Float, nullable=True)
    earliest_retirement_age = Column(Integer, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    last_computed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LifeScenario(Base):
    __tablename__ = "life_scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    scenario_type = Column(String(50), nullable=False)
    parameters = Column(Text, nullable=False, default="{}")
    annual_income = Column(Float, nullable=True)
    monthly_take_home = Column(Float, nullable=True)
    current_monthly_expenses = Column(Float, nullable=True)
    current_monthly_debt_payments = Column(Float, nullable=True)
    current_savings = Column(Float, nullable=True)
    current_investments = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    new_monthly_payment = Column(Float, nullable=True)
    monthly_surplus_after = Column(Float, nullable=True)
    savings_rate_before_pct = Column(Float, nullable=True)
    savings_rate_after_pct = Column(Float, nullable=True)
    dti_before_pct = Column(Float, nullable=True)
    dti_after_pct = Column(Float, nullable=True)
    affordability_score = Column(Float, nullable=True)
    verdict = Column(String(20), nullable=True)
    results_detail = Column(Text, nullable=True)
    ai_analysis = Column(Text, nullable=True)
    composite_scenario_ids = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    is_favorite = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CryptoHolding(Base):
    __tablename__ = "crypto_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    coin_id = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=False)
    name = Column(String(255), nullable=True)
    quantity = Column(Float, nullable=False)
    cost_basis_per_unit = Column(Float, nullable=True)
    total_cost_basis = Column(Float, nullable=True)
    purchase_date = Column(Date, nullable=True)
    current_price = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    unrealized_gain_loss = Column(Float, nullable=True)
    price_change_24h_pct = Column(Float, nullable=True)
    last_price_update = Column(DateTime, nullable=True)
    wallet_or_exchange = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_crypto_coin", "coin_id"),
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    total_stock_value = Column(Float, nullable=False, default=0.0)
    total_etf_value = Column(Float, nullable=False, default=0.0)
    total_bond_value = Column(Float, nullable=False, default=0.0)
    total_crypto_value = Column(Float, nullable=False, default=0.0)
    total_other_value = Column(Float, nullable=False, default=0.0)
    total_portfolio_value = Column(Float, nullable=False, default=0.0)
    total_cost_basis = Column(Float, nullable=False, default=0.0)
    total_unrealized_gain_loss = Column(Float, nullable=False, default=0.0)
    day_change = Column(Float, nullable=True)
    day_change_pct = Column(Float, nullable=True)
    allocation_by_sector = Column(Text, nullable=True)
    allocation_by_asset_class = Column(Text, nullable=True)
    top_holdings = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("snapshot_date", name="uq_portfolio_snapshot_date"),
    )


class EquityGrant(Base):
    __tablename__ = "equity_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employer_name = Column(String(255), nullable=False)
    grant_type = Column(String(20), nullable=False)
    grant_date = Column(Date, nullable=False)
    total_shares = Column(Float, nullable=False)
    vested_shares = Column(Float, nullable=False, default=0.0)
    unvested_shares = Column(Float, nullable=False, default=0.0)
    vesting_schedule_json = Column(Text, nullable=True)
    strike_price = Column(Float, nullable=True)
    current_fmv = Column(Float, nullable=True)
    exercise_price = Column(Float, nullable=True)
    expiration_date = Column(Date, nullable=True)
    ticker = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_equity_grant_employer", "employer_name"),
        Index("ix_equity_grant_type", "grant_type"),
    )

    vesting_events = relationship("VestingEvent", back_populates="grant", cascade="all, delete-orphan")


class VestingEvent(Base):
    __tablename__ = "vesting_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grant_id = Column(Integer, ForeignKey("equity_grants.id", ondelete="CASCADE"), nullable=False)
    vest_date = Column(Date, nullable=False)
    shares = Column(Float, nullable=False)
    price_at_vest = Column(Float, nullable=True)
    withheld_shares = Column(Float, nullable=True)
    federal_withholding_pct = Column(Float, nullable=True, default=22.0)
    state_withholding_pct = Column(Float, nullable=True, default=0.0)
    is_sold = Column(Boolean, nullable=False, default=False)
    sale_price = Column(Float, nullable=True)
    sale_date = Column(Date, nullable=True)
    net_proceeds = Column(Float, nullable=True)
    tax_impact_json = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="upcoming")

    __table_args__ = (
        Index("ix_vesting_grant", "grant_id"),
        Index("ix_vesting_date", "vest_date"),
    )

    grant = relationship("EquityGrant", back_populates="vesting_events")


class EquityTaxProjection(Base):
    __tablename__ = "equity_tax_projections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grant_id = Column(Integer, ForeignKey("equity_grants.id", ondelete="CASCADE"), nullable=False)
    tax_year = Column(Integer, nullable=False)
    projected_vest_income = Column(Float, nullable=False, default=0.0)
    projected_withholding = Column(Float, nullable=False, default=0.0)
    withholding_gap = Column(Float, nullable=False, default=0.0)
    marginal_rate_used = Column(Float, nullable=True)
    amt_exposure = Column(Float, nullable=True, default=0.0)
    recommendations_json = Column(Text, nullable=True)
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("grant_id", "tax_year", name="uq_equity_tax_grant_year"),
    )


class TargetAllocation(Base):
    __tablename__ = "target_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, default="My Target Allocation")
    allocation_json = Column(Text, nullable=False, default="{}")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Household schema (formerly schema_household.py)
# Household profiles, Benefits, Tax projections, Insurance, Life events
# ═══════════════════════════════════════════════════════════════════════════


class HouseholdProfile(Base):
    __tablename__ = "household_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, default="Our Household")
    filing_status = Column(String(20), nullable=False, default="mfj")
    state = Column(String(2), nullable=True)
    dependents_json = Column(Text, nullable=True)
    spouse_a_name = Column(String(255), nullable=True)
    spouse_a_income = Column(Float, nullable=False, default=0.0)
    spouse_a_employer = Column(String(255), nullable=True)
    spouse_a_work_state = Column(String(2), nullable=True)
    spouse_a_start_date = Column(Date, nullable=True)
    spouse_b_name = Column(String(255), nullable=True)
    spouse_b_income = Column(Float, nullable=False, default=0.0)
    spouse_b_employer = Column(String(255), nullable=True)
    spouse_b_work_state = Column(String(2), nullable=True)
    spouse_b_start_date = Column(Date, nullable=True)
    combined_income = Column(Float, nullable=False, default=0.0)
    other_income_annual = Column(Float, nullable=True, default=0.0)
    other_income_sources_json = Column(Text, nullable=True)
    estate_will_status = Column(String(20), nullable=True)
    estate_poa_status = Column(String(20), nullable=True)
    estate_hcd_status = Column(String(20), nullable=True)
    estate_trust_status = Column(String(20), nullable=True)
    beneficiaries_reviewed = Column(Boolean, nullable=True, default=False)
    beneficiaries_reviewed_date = Column(Date, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class BenefitPackage(Base):
    __tablename__ = "benefit_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(Integer, ForeignKey("household_profiles.id", ondelete="CASCADE"), nullable=False)
    spouse = Column(String(1), nullable=False)
    employer_name = Column(String(255), nullable=True)
    has_401k = Column(Boolean, nullable=False, default=False)
    employer_match_pct = Column(Float, nullable=True, default=0.0)
    employer_match_limit_pct = Column(Float, nullable=True, default=6.0)
    has_roth_401k = Column(Boolean, nullable=False, default=False)
    has_mega_backdoor = Column(Boolean, nullable=False, default=False)
    annual_401k_limit = Column(Float, nullable=True, default=23500.0)
    mega_backdoor_limit = Column(Float, nullable=True, default=46000.0)
    annual_401k_contribution = Column(Float, nullable=True, default=0.0)
    has_hsa = Column(Boolean, nullable=False, default=False)
    hsa_employer_contribution = Column(Float, nullable=True, default=0.0)
    has_fsa = Column(Boolean, nullable=False, default=False)
    has_dep_care_fsa = Column(Boolean, nullable=False, default=False)
    health_premium_monthly = Column(Float, nullable=True, default=0.0)
    dental_vision_monthly = Column(Float, nullable=True, default=0.0)
    health_plan_options_json = Column(Text, nullable=True)
    life_insurance_coverage = Column(Float, nullable=True, default=0.0)
    life_insurance_cost_monthly = Column(Float, nullable=True, default=0.0)
    std_coverage_pct = Column(Float, nullable=True)
    std_waiting_days = Column(Integer, nullable=True)
    ltd_coverage_pct = Column(Float, nullable=True)
    ltd_waiting_days = Column(Integer, nullable=True)
    commuter_monthly_limit = Column(Float, nullable=True, default=0.0)
    tuition_reimbursement_annual = Column(Float, nullable=True, default=0.0)
    has_espp = Column(Boolean, nullable=False, default=False)
    espp_discount_pct = Column(Float, nullable=True, default=15.0)
    open_enrollment_start = Column(Date, nullable=True)
    open_enrollment_end = Column(Date, nullable=True)
    other_benefits_json = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("household_id", "spouse", name="uq_benefit_household_spouse"),
    )


class HouseholdOptimization(Base):
    __tablename__ = "household_optimizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(Integer, ForeignKey("household_profiles.id", ondelete="CASCADE"), nullable=False)
    tax_year = Column(Integer, nullable=False)
    optimal_filing_status = Column(String(20), nullable=True)
    mfj_tax = Column(Float, nullable=True)
    mfs_tax = Column(Float, nullable=True)
    filing_savings = Column(Float, nullable=True)
    optimal_retirement_strategy_json = Column(Text, nullable=True)
    optimal_insurance_selection = Column(Text, nullable=True)
    childcare_strategy_json = Column(Text, nullable=True)
    total_annual_savings = Column(Float, nullable=True)
    recommendations_json = Column(Text, nullable=True)
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_household_opt_year", "household_id", "tax_year"),
    )


class TaxProjection(Base):
    __tablename__ = "tax_projections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    tax_year = Column(Integer, nullable=False)
    scenario_json = Column(Text, nullable=True)
    federal_tax = Column(Float, nullable=True)
    state_tax = Column(Float, nullable=True)
    fica = Column(Float, nullable=True)
    niit = Column(Float, nullable=True)
    amt = Column(Float, nullable=True)
    total_tax = Column(Float, nullable=True)
    effective_rate = Column(Float, nullable=True)
    marginal_rate = Column(Float, nullable=True)
    credits_json = Column(Text, nullable=True)
    deductions_json = Column(Text, nullable=True)
    comparison_baseline_id = Column(Integer, ForeignKey("tax_projections.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tax_projection_year", "tax_year"),
    )


class LifeEvent(Base):
    __tablename__ = "life_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(Integer, ForeignKey("household_profiles.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)
    event_subtype = Column(String(100), nullable=True)
    title = Column(String(255), nullable=False)
    event_date = Column(Date, nullable=True)
    tax_year = Column(Integer, nullable=True)
    amounts_json = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="completed")
    action_items_json = Column(Text, nullable=True)
    document_ids_json = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_life_event_type", "event_type"),
        Index("ix_life_event_year", "tax_year"),
    )


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(Integer, ForeignKey("household_profiles.id", ondelete="SET NULL"), nullable=True)
    owner_spouse = Column(String(1), nullable=True)
    policy_type = Column(String(50), nullable=False)
    provider = Column(String(255), nullable=True)
    policy_number = Column(String(255), nullable=True)
    coverage_amount = Column(Float, nullable=True)
    deductible = Column(Float, nullable=True)
    oop_max = Column(Float, nullable=True)
    annual_premium = Column(Float, nullable=True)
    monthly_premium = Column(Float, nullable=True)
    renewal_date = Column(Date, nullable=True)
    beneficiaries_json = Column(Text, nullable=True)
    employer_provided = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_insurance_type", "policy_type"),
    )


class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(Integer, ForeignKey("household_profiles.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    relationship = Column(String(20), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    ssn_last4 = Column(String(4), nullable=True)
    is_earner = Column(Boolean, nullable=False, default=False)
    income = Column(Float, nullable=True, default=0.0)
    employer = Column(String(255), nullable=True)
    work_state = Column(String(2), nullable=True)
    employer_start_date = Column(Date, nullable=True)
    grade_level = Column(String(50), nullable=True)
    school_name = Column(String(255), nullable=True)
    care_cost_annual = Column(Float, nullable=True)
    college_start_year = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_family_member_household", "household_id"),
    )


class BenchmarkSnapshot(Base):
    __tablename__ = "benchmark_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    user_age = Column(Integer, nullable=True)
    income = Column(Float, nullable=True)
    net_worth = Column(Float, nullable=True)
    savings_rate = Column(Float, nullable=True)
    retirement_savings = Column(Float, nullable=True)
    debt_total = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_benchmark_date", "snapshot_date"),
    )


if __name__ == "__main__":
    print(f"Initializing database at: {DATABASE_URL}")
    asyncio.run(init_db())
    print("Database initialized successfully.")
