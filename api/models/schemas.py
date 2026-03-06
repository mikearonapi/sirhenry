"""
Pydantic v2 schemas for all API request/response models.
These define the contract between the FastAPI backend and the Next.js frontend.
"""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    account_type: str
    subtype: Optional[str]
    institution: Optional[str]
    last_four: Optional[str]
    currency: str
    is_active: bool
    data_source: str = "manual"
    default_segment: Optional[str]
    default_business_entity_id: Optional[int]
    notes: Optional[str]
    created_at: datetime


class AccountWithBalanceOut(AccountOut):
    balance: float = 0.0
    transaction_count: int = 0
    # Plaid metadata (populated for plaid-sourced accounts)
    current_balance: Optional[float] = None
    available_balance: Optional[float] = None
    plaid_mask: Optional[str] = None
    plaid_type: Optional[str] = None
    plaid_subtype: Optional[str] = None
    plaid_last_synced: Optional[str] = None
    plaid_institution: Optional[str] = None


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    document_type: str
    status: str
    tax_year: Optional[int]
    account_id: Optional[int]
    error_message: Optional[str]
    imported_at: datetime
    processed_at: Optional[datetime]


class DocumentListOut(BaseModel):
    total: int
    items: list[DocumentOut]


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    source_document_id: Optional[int]
    date: datetime
    description: str
    amount: float
    currency: str
    segment: str
    business_entity_id: Optional[int]
    business_entity_override: Optional[int]
    effective_business_entity_id: Optional[int]
    reimbursement_status: Optional[str]
    reimbursement_match_id: Optional[int]
    category: Optional[str]
    tax_category: Optional[str]
    ai_confidence: Optional[float]
    category_override: Optional[str]
    tax_category_override: Optional[str]
    segment_override: Optional[str]
    is_manually_reviewed: bool
    effective_category: Optional[str]
    effective_tax_category: Optional[str]
    effective_segment: Optional[str]
    period_month: Optional[int]
    period_year: Optional[int]
    notes: Optional[str]
    is_excluded: bool
    data_source: str = "csv"
    merchant_name: Optional[str] = None
    merchant_logo_url: Optional[str] = None
    parent_transaction_id: Optional[int] = None
    children: list["TransactionOut"] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _prevent_lazy_load(cls, data: object) -> object:
        """Prevent SQLAlchemy lazy-load of 'children' when validating from ORM."""
        if hasattr(data, "__dict__"):
            # Check if 'children' is loaded in the ORM instance state;
            # if not, inject an empty list to avoid a lazy-load greenlet error.
            from sqlalchemy import inspect as sa_inspect
            try:
                state = sa_inspect(data)
                if "children" not in state.dict:
                    state.dict["children"] = []
            except Exception:
                pass
        return data


class TransactionUpdateIn(BaseModel):
    category_override: Optional[str] = None
    tax_category_override: Optional[str] = None
    segment_override: Optional[str] = None
    business_entity_override: Optional[int] = None
    notes: Optional[str] = None
    is_excluded: Optional[bool] = None


class TransactionListOut(BaseModel):
    total: int
    items: list[TransactionOut]


# ---------------------------------------------------------------------------
# Business Entities
# ---------------------------------------------------------------------------

class BusinessEntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner: Optional[str]
    entity_type: str
    tax_treatment: str
    ein: Optional[str]
    is_active: bool
    is_provisional: bool
    active_from: Optional[date]
    active_to: Optional[date]
    notes: Optional[str]
    description: Optional[str]
    expected_expenses: Optional[str]
    created_at: datetime


class BusinessEntityCreateIn(BaseModel):
    name: str
    owner: Optional[str] = None
    entity_type: str = "sole_prop"
    tax_treatment: str = "schedule_c"
    ein: Optional[str] = None
    is_provisional: bool = False
    active_from: Optional[date] = None
    active_to: Optional[date] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    expected_expenses: Optional[str] = None


class BusinessEntityUpdateIn(BaseModel):
    name: Optional[str] = None
    owner: Optional[str] = None
    entity_type: Optional[str] = None
    tax_treatment: Optional[str] = None
    ein: Optional[str] = None
    is_active: Optional[bool] = None
    is_provisional: Optional[bool] = None
    active_from: Optional[date] = None
    active_to: Optional[date] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    expected_expenses: Optional[str] = None


# --- Entity Expense Report ---

class EntityMonthlyTotalOut(BaseModel):
    month: int
    month_name: str
    total_expenses: float
    transaction_count: int


class EntityCategoryBreakdownOut(BaseModel):
    category: str
    total: float
    percentage: float


class EntityExpenseReportOut(BaseModel):
    entity_id: int
    entity_name: str
    year: int
    monthly_totals: list[EntityMonthlyTotalOut]
    category_breakdown: list[EntityCategoryBreakdownOut]
    year_total_expenses: float
    prior_year_total_expenses: Optional[float]
    year_over_year_change_pct: Optional[float]


class VendorEntityRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_pattern: str
    business_entity_id: int
    segment_override: Optional[str]
    effective_from: Optional[date]
    effective_to: Optional[date]
    priority: int
    is_active: bool
    created_at: datetime


class VendorEntityRuleCreateIn(BaseModel):
    vendor_pattern: str
    business_entity_id: int
    segment_override: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    priority: int = 0


class EntityReassignIn(BaseModel):
    from_entity_id: int
    to_entity_id: int
    date_from: Optional[date] = None
    date_to: Optional[date] = None


# ---------------------------------------------------------------------------
# Tax Items
# ---------------------------------------------------------------------------

class TaxItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_document_id: int
    tax_year: int
    form_type: str
    payer_name: Optional[str]
    payer_ein: Optional[str]
    w2_wages: Optional[float]
    w2_federal_tax_withheld: Optional[float]
    w2_state: Optional[str]
    w2_state_wages: Optional[float]
    w2_state_income_tax: Optional[float]
    w2_state_allocations: Optional[str]
    nec_nonemployee_compensation: Optional[float]
    nec_federal_tax_withheld: Optional[float]
    div_total_ordinary: Optional[float]
    div_qualified: Optional[float]
    div_total_capital_gain: Optional[float]
    b_proceeds: Optional[float]
    b_cost_basis: Optional[float]
    b_gain_loss: Optional[float]
    b_term: Optional[str]
    int_interest: Optional[float]
    raw_fields: Optional[str]


class TaxSummaryOut(BaseModel):
    tax_year: int
    w2_total_wages: float
    w2_federal_withheld: float
    w2_state_allocations: list[Any]
    nec_total: float
    div_ordinary: float
    div_qualified: float
    div_capital_gain: float
    capital_gains_short: float
    capital_gains_long: float
    interest_income: float
    k1_ordinary_income: float = 0.0
    k1_rental_income: float = 0.0
    k1_guaranteed_payments: float = 0.0
    k1_interest_income: float = 0.0
    k1_dividends: float = 0.0
    k1_capital_gains: float = 0.0
    retirement_distributions: float = 0.0
    retirement_taxable: float = 0.0
    unemployment_income: float = 0.0
    state_tax_refund: float = 0.0
    payment_platform_income: float = 0.0
    mortgage_interest_deduction: float = 0.0
    property_tax_deduction: float = 0.0
    data_source: Optional[str] = None


# ---------------------------------------------------------------------------
# Tax Strategies
# ---------------------------------------------------------------------------

class TaxStrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tax_year: int
    priority: int
    title: str
    description: str
    strategy_type: str
    estimated_savings_low: Optional[float]
    estimated_savings_high: Optional[float]
    action_required: Optional[str]
    deadline: Optional[str]
    is_dismissed: bool
    generated_at: datetime
    # Enhanced AI analysis fields
    confidence: Optional[float] = None
    confidence_reasoning: Optional[str] = None
    category: Optional[str] = None
    complexity: Optional[str] = None
    prerequisites_json: Optional[str] = None
    who_its_for: Optional[str] = None
    related_simulator: Optional[str] = None


# ---------------------------------------------------------------------------
# Tax Checklist
# ---------------------------------------------------------------------------

class TaxChecklistItemOut(BaseModel):
    id: str
    label: str
    description: str
    status: str
    detail: Optional[str] = None
    category: str

class TaxChecklistOut(BaseModel):
    tax_year: int
    items: list[TaxChecklistItemOut]
    completed: int
    total: int
    progress_pct: float


# ---------------------------------------------------------------------------
# Deduction Opportunities
# ---------------------------------------------------------------------------

class DeductionOpportunityOut(BaseModel):
    id: str
    title: str
    description: str
    category: str
    estimated_tax_savings_low: float
    estimated_tax_savings_high: float
    estimated_cost: Optional[float] = None
    net_benefit_explanation: str
    urgency: str
    deadline: Optional[str] = None
    applicable: bool = True

class TaxDeductionInsightsOut(BaseModel):
    tax_year: int
    estimated_balance_due: float
    effective_rate: float
    marginal_rate: float
    opportunities: list[DeductionOpportunityOut]
    summary: str
    data_source: str = "documents"


# ---------------------------------------------------------------------------
# Manual Assets (net worth tracking)
# ---------------------------------------------------------------------------

class ManualAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    asset_type: str
    is_liability: bool
    current_value: float
    purchase_price: Optional[float]
    purchase_date: Optional[datetime]
    institution: Optional[str]
    address: Optional[str]
    description: Optional[str]
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    owner: Optional[str] = None
    account_subtype: Optional[str] = None
    custodian: Optional[str] = None
    employer: Optional[str] = None
    tax_treatment: Optional[str] = None
    is_retirement_account: Optional[bool] = None
    as_of_date: Optional[datetime] = None
    vested_balance: Optional[float] = None
    contribution_type: Optional[str] = None
    contribution_rate_pct: Optional[float] = None
    employee_contribution_ytd: Optional[float] = None
    employer_contribution_ytd: Optional[float] = None
    employer_match_pct: Optional[float] = None
    employer_match_limit_pct: Optional[float] = None
    annual_return_pct: Optional[float] = None
    allocation_json: Optional[str] = None
    beneficiary: Optional[str] = None
    linked_account_id: Optional[int] = None


class ManualAssetCreateIn(BaseModel):
    name: str
    asset_type: str = Field(..., pattern="^(real_estate|vehicle|investment|other_asset|mortgage|loan|other_liability)$")
    current_value: float
    purchase_price: Optional[float] = None
    purchase_date: Optional[datetime] = None
    institution: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    owner: Optional[str] = None
    account_subtype: Optional[str] = None
    custodian: Optional[str] = None
    employer: Optional[str] = None
    tax_treatment: Optional[str] = None
    is_retirement_account: Optional[bool] = None
    as_of_date: Optional[datetime] = None
    vested_balance: Optional[float] = None
    contribution_type: Optional[str] = None
    contribution_rate_pct: Optional[float] = None
    employee_contribution_ytd: Optional[float] = None
    employer_contribution_ytd: Optional[float] = None
    employer_match_pct: Optional[float] = None
    employer_match_limit_pct: Optional[float] = None
    annual_return_pct: Optional[float] = None
    allocation_json: Optional[str] = None
    beneficiary: Optional[str] = None


class ManualAssetUpdateIn(BaseModel):
    name: Optional[str] = None
    current_value: Optional[float] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[datetime] = None
    institution: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    owner: Optional[str] = None
    account_subtype: Optional[str] = None
    custodian: Optional[str] = None
    employer: Optional[str] = None
    tax_treatment: Optional[str] = None
    is_retirement_account: Optional[bool] = None
    as_of_date: Optional[datetime] = None
    vested_balance: Optional[float] = None
    contribution_type: Optional[str] = None
    contribution_rate_pct: Optional[float] = None
    employee_contribution_ytd: Optional[float] = None
    employer_contribution_ytd: Optional[float] = None
    employer_match_pct: Optional[float] = None
    employer_match_limit_pct: Optional[float] = None
    annual_return_pct: Optional[float] = None
    allocation_json: Optional[str] = None
    beneficiary: Optional[str] = None


# ---------------------------------------------------------------------------
# Financial Periods / Reports
# ---------------------------------------------------------------------------

class FinancialPeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    month: Optional[int]
    segment: str
    total_income: float
    total_expenses: float
    net_cash_flow: float
    w2_income: float
    investment_income: float
    board_income: float
    business_expenses: float
    personal_expenses: float
    expense_breakdown: Optional[str]
    income_breakdown: Optional[str]
    computed_at: datetime


class MonthlyReportOut(BaseModel):
    period: FinancialPeriodOut
    top_expense_categories: list[dict[str, Any]]
    top_income_sources: list[dict[str, Any]]
    vs_prior_month: Optional[dict[str, float]]
    ai_insights: Optional[str]


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class ImportResultOut(BaseModel):
    document_id: int
    filename: str
    status: str
    transactions_imported: int
    transactions_skipped: int
    message: str


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardOut(BaseModel):
    current_year: int
    current_month: int
    ytd_income: float
    ytd_expenses: float
    ytd_net: float
    ytd_tax_estimate: float
    current_month_income: float
    current_month_expenses: float
    current_month_net: float
    current_month_tax_estimate: float = 0.0
    recent_transactions: list[TransactionOut]
    monthly_trend: list[FinancialPeriodOut]
    top_strategies_count: int


# ---------------------------------------------------------------------------
# AI Chat
# ---------------------------------------------------------------------------

class ChatMessageIn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequestIn(BaseModel):
    messages: list[ChatMessageIn] = Field(..., min_length=1)
    conversation_id: Optional[int] = None
    page_context: Optional[str] = None


class ChatActionOut(BaseModel):
    tool: str
    input: dict[str, Any]
    result_preview: str


class ChatResponseOut(BaseModel):
    response: Optional[str]
    requires_consent: bool = False
    actions: list[ChatActionOut] = []
    tool_calls_made: int = 0
    conversation_id: Optional[int] = None


class ChatConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    page_context: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatMessageRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    actions_json: Optional[str] = None
    created_at: datetime


class ChatConversationDetailOut(ChatConversationOut):
    messages: list[ChatMessageRecordOut] = []


# ---------------------------------------------------------------------------
# Insights / Analytics
# ---------------------------------------------------------------------------

class OutlierFeedbackIn(BaseModel):
    transaction_id: int
    classification: str = Field(pattern=r"^(recurring|one_time|not_outlier)$")
    user_note: Optional[str] = None
    apply_to_future: bool = True
    year: int


class OutlierFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    classification: str
    user_note: Optional[str]
    description_pattern: Optional[str]
    category: Optional[str]
    apply_to_future: bool
    year: int
    created_at: datetime


class OutlierTransactionOut(BaseModel):
    id: int
    date: Optional[str]
    description: str
    amount: float
    category: str
    segment: Optional[str]
    typical_amount: float
    threshold: float
    excess_pct: float
    reason: str
    feedback: Optional[OutlierFeedbackOut] = None


class InsightsSummaryOut(BaseModel):
    total_outlier_expenses: float
    total_outlier_income: float
    expense_outlier_count: int
    income_outlier_count: int
    normalized_monthly_budget: float
    actual_monthly_average: float
    normalization_savings: float


class NormalizedCategoryOut(BaseModel):
    category: str
    normalized_monthly: float
    mean_monthly: float
    min_monthly: float
    max_monthly: float
    months_active: int


class NormalizedBudgetOut(BaseModel):
    normalized_monthly_total: float
    mean_monthly_total: float
    min_month: float
    max_month: float
    by_category: list[NormalizedCategoryOut]


class CategoryAmountOut(BaseModel):
    category: str
    amount: float


class MonthlyAnalysisOut(BaseModel):
    month: int
    month_name: str
    total_expenses: float
    expenses_excl_outliers: float
    total_income: float
    outlier_expense_total: float
    outlier_count: int
    classification: str
    deviation_pct: float
    top_categories: list[CategoryAmountOut]
    explanation: Optional[str]


class SeasonalCategoryOut(BaseModel):
    category: str
    avg_amount: float


class SeasonalPatternOut(BaseModel):
    month: int
    month_name: str
    average_expenses: float
    seasonal_index: float
    label: str
    years_of_data: int
    top_categories: list[SeasonalCategoryOut]


class CategoryTrendOut(BaseModel):
    category: str
    trend: str
    total_annual: float
    monthly_average: float
    monthly_median: float
    volatility: float
    budget_share_pct: float
    months_active: int
    monthly_amounts: dict[str, float]


class IncomeSourceOut(BaseModel):
    source: str
    total: float


class IrregularIncomeItemOut(BaseModel):
    date: Optional[str]
    description: str
    amount: float
    category: str


class IncomeAnalysisOut(BaseModel):
    regular_monthly_median: float
    regular_monthly_mean: float
    total_regular: float
    total_irregular: float
    irregular_items: list[IrregularIncomeItemOut]
    by_source: list[IncomeSourceOut]


class MonthlyComparisonOut(BaseModel):
    month: int
    month_name: str
    current_expenses: float
    prior_expenses: float
    current_income: float
    prior_income: float
    prior_2_expenses: float = 0
    prior_2_income: float = 0


class CategoryYoYOut(BaseModel):
    category: str
    current_year: float
    prior_year: float
    change_pct: float


class YearOverYearOut(BaseModel):
    current_year_income: float
    prior_year_income: float
    income_change_pct: float
    current_year_expenses: float
    prior_year_expenses: float
    expense_change_pct: float
    current_year_net: float
    prior_year_net: float
    monthly_comparison: list[MonthlyComparisonOut]
    category_changes: list[CategoryYoYOut]
    prior_year_2: Optional[int] = None
    prior_year_2_income: Optional[float] = None
    prior_year_2_expenses: Optional[float] = None


class OutlierReviewSummaryOut(BaseModel):
    total_outliers: int
    reviewed: int
    recurring: int
    one_time: int
    not_outlier: int


class InsightsOut(BaseModel):
    year: int
    transaction_count: int
    summary: InsightsSummaryOut
    expense_outliers: list[OutlierTransactionOut]
    income_outliers: list[OutlierTransactionOut]
    outlier_review: Optional[OutlierReviewSummaryOut] = None
    normalized_budget: NormalizedBudgetOut
    monthly_analysis: list[MonthlyAnalysisOut]
    seasonal_patterns: list[SeasonalPatternOut]
    category_trends: list[CategoryTrendOut]
    income_analysis: IncomeAnalysisOut
    year_over_year: Optional[YearOverYearOut]


# ---------------------------------------------------------------------------
# Budget endpoint responses
# ---------------------------------------------------------------------------

class OverBudgetCategoryOut(BaseModel):
    category: str
    budgeted: float
    actual: float


class YearOverYearDataOut(BaseModel):
    year: int
    total_expenses: float


class BudgetSummaryOut(BaseModel):
    year: int
    month: int
    total_budgeted: float
    total_actual: float
    variance: float
    utilization_pct: float
    over_budget_categories: list[OverBudgetCategoryOut]
    year_over_year: list[YearOverYearDataOut]


class ForecastCategory(BaseModel):
    category: str
    predicted_amount: float
    confidence: float
    historical_avg: float


class ForecastResult(BaseModel):
    month: int
    year: int
    categories: list[ForecastCategory]
    total_predicted: float


class SeasonalPatternDetail(BaseModel):
    monthly_averages: dict[int, float]
    peaks: dict[int, float]


class BudgetForecastOut(BaseModel):
    forecast: ForecastResult
    seasonal: dict[str, SeasonalPatternDetail]
    target_month: int
    target_year: int


class SpendVelocityOut(BaseModel):
    category: str
    budget: float
    spent_so_far: float
    projected_total: float
    on_track: bool
    status: str


class UnbudgetedCategoryOut(BaseModel):
    category: str
    actual_amount: float


# ---------------------------------------------------------------------------
# Recurring endpoint responses
# ---------------------------------------------------------------------------

class RecurringSummaryOut(BaseModel):
    total_monthly_cost: float
    total_annual_cost: float
    subscription_count: int
    by_category: dict[str, float]


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

class BudgetIn(BaseModel):
    year: int
    month: int
    category: str
    segment: str = "personal"
    budget_amount: float
    notes: Optional[str] = None


class BudgetUpdateIn(BaseModel):
    budget_amount: Optional[float] = None
    notes: Optional[str] = None


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    month: int
    category: str
    segment: str
    budget_amount: float
    notes: Optional[str]
    actual_amount: float = 0.0
    variance: float = 0.0
    utilization_pct: float = 0.0


# ---------------------------------------------------------------------------
# Recurring Transactions
# ---------------------------------------------------------------------------

class RecurringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    amount: float
    frequency: str
    category: Optional[str]
    segment: str
    status: str
    last_seen_date: Optional[str]
    next_expected_date: Optional[str]
    is_auto_detected: bool
    notes: Optional[str]
    annual_cost: float = 0.0


class RecurringUpdateIn(BaseModel):
    status: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

class GoalIn(BaseModel):
    name: str
    description: Optional[str] = None
    goal_type: str = "savings"
    target_amount: float
    current_amount: float = 0.0
    target_date: Optional[str] = None
    color: str = "#6366f1"
    icon: Optional[str] = None
    monthly_contribution: Optional[float] = None
    notes: Optional[str] = None


class GoalUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    goal_type: Optional[str] = None
    current_amount: Optional[float] = None
    target_amount: Optional[float] = None
    target_date: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    monthly_contribution: Optional[float] = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    goal_type: str
    target_amount: float
    current_amount: float
    target_date: Optional[str]
    status: str
    color: str
    icon: Optional[str]
    monthly_contribution: Optional[float]
    notes: Optional[str]
    progress_pct: float = 0.0
    months_remaining: Optional[int] = None
    on_track: Optional[bool] = None


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

class ReminderIn(BaseModel):
    title: str
    description: Optional[str] = None
    reminder_type: str = "custom"
    due_date: str
    amount: Optional[float] = None
    advance_notice: str = "7_days"
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    related_account_id: Optional[int] = None


class ReminderUpdateIn(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    due_date: Optional[str] = None
    amount: Optional[float] = None
    notes: Optional[str] = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    reminder_type: str
    due_date: str
    amount: Optional[float]
    advance_notice: str
    status: str
    is_recurring: bool
    recurrence_rule: Optional[str] = None
    days_until_due: int = 0
    is_overdue: bool = False


# ---------------------------------------------------------------------------
# Plaid
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Account CRUD
# ---------------------------------------------------------------------------


class AccountCreateIn(BaseModel):
    name: str
    account_type: str
    subtype: Optional[str] = None
    institution: Optional[str] = None
    last_four: Optional[str] = None
    currency: str = "USD"
    notes: Optional[str] = None
    data_source: str = "manual"
    default_segment: Optional[str] = None
    default_business_entity_id: Optional[int] = None


class AccountUpdateIn(BaseModel):
    name: Optional[str] = None
    account_type: Optional[str] = None
    subtype: Optional[str] = None
    institution: Optional[str] = None
    last_four: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    default_segment: Optional[str] = None
    default_business_entity_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Account Linking
# ---------------------------------------------------------------------------


class LinkAccountIn(BaseModel):
    target_account_id: int
    link_type: str = "same_account"


class AccountLinkOut(BaseModel):
    id: int
    primary_account_id: int
    secondary_account_id: int
    link_type: str
    created_at: str


class MergeResultOut(BaseModel):
    primary_account_id: int
    secondary_account_id: int
    transactions_moved: int
    documents_moved: int
    secondary_deactivated: bool


class SuggestedLinkOut(BaseModel):
    account_a_id: int
    account_a_name: str
    account_a_source: str
    account_b_id: int
    account_b_name: str
    account_b_source: str
    match_reason: str


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TransactionCreateIn(BaseModel):
    account_id: int
    date: datetime
    description: str
    amount: float
    currency: str = "USD"
    segment: str = "personal"
    category: Optional[str] = None
    tax_category: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Life Events
# ---------------------------------------------------------------------------


class LifeEventIn(BaseModel):
    household_id: Optional[int] = None
    event_type: str
    event_subtype: Optional[str] = None
    title: str
    event_date: Optional[str] = None
    tax_year: Optional[int] = None
    amounts_json: Optional[str] = None
    status: str = "completed"
    action_items_json: Optional[str] = None
    document_ids_json: Optional[str] = None
    notes: Optional[str] = None


class LifeEventUpdateIn(BaseModel):
    household_id: Optional[int] = None
    event_type: Optional[str] = None
    event_subtype: Optional[str] = None
    title: Optional[str] = None
    event_date: Optional[str] = None
    tax_year: Optional[int] = None
    amounts_json: Optional[str] = None
    status: Optional[str] = None
    action_items_json: Optional[str] = None
    document_ids_json: Optional[str] = None
    notes: Optional[str] = None


class ActionItemUpdate(BaseModel):
    index: int
    completed: bool


class LifeEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: Optional[int]
    event_type: str
    event_subtype: Optional[str]
    title: str
    event_date: Optional[date] = None
    tax_year: Optional[int]
    amounts_json: Optional[str]
    status: str
    action_items_json: Optional[str]
    document_ids_json: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Insurance
# ---------------------------------------------------------------------------


class InsurancePolicyIn(BaseModel):
    household_id: Optional[int] = None
    owner_spouse: Optional[str] = None
    policy_type: str
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    coverage_amount: Optional[float] = None
    deductible: Optional[float] = None
    oop_max: Optional[float] = None
    annual_premium: Optional[float] = None
    monthly_premium: Optional[float] = None
    renewal_date: Optional[str] = None
    beneficiaries_json: Optional[str] = None
    employer_provided: bool = False
    is_active: bool = True
    notes: Optional[str] = None


class InsurancePolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: Optional[int]
    owner_spouse: Optional[str]
    policy_type: str
    provider: Optional[str]
    policy_number: Optional[str]
    coverage_amount: Optional[float]
    deductible: Optional[float]
    oop_max: Optional[float]
    annual_premium: Optional[float]
    monthly_premium: Optional[float]
    renewal_date: Optional[str] = None
    beneficiaries_json: Optional[str]
    employer_provided: bool
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class GapAnalysisIn(BaseModel):
    household_id: Optional[int] = None
    spouse_a_income: float = 0
    spouse_b_income: float = 0
    total_debt: float = 0
    dependents: int = 0
    net_worth: float = 0


# ---------------------------------------------------------------------------
# Plaid
# ---------------------------------------------------------------------------


class ExchangeTokenIn(BaseModel):
    public_token: str
    institution_name: str


class PlaidItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    institution_name: str | None
    status: str
    last_synced_at: str | None
    account_count: int = 0


class PlaidAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    official_name: str | None = None
    type: str
    subtype: str | None = None
    current_balance: float | None = None
    available_balance: float | None = None
    limit_balance: float | None = None
    mask: str | None = None
    last_updated: datetime | str | None = None


# ---------------------------------------------------------------------------
# Privacy & Consent
# ---------------------------------------------------------------------------


class ConsentIn(BaseModel):
    consent_type: str  # ai_features | plaid_sync | telemetry
    consented: bool


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consent_type: str
    consented: bool
    consent_version: str
    consented_at: datetime | None = None


class PrivacyDisclosure(BaseModel):
    data_handling: list[str]
    ai_privacy: list[str]
    encryption: list[str]
    data_retention: list[str]
