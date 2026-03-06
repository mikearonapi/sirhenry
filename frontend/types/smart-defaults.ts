// Smart Defaults — unified data aggregated from all domain tables.
// Used by any page to auto-fill forms without redundant data entry.

export interface SmartDefaults {
  household: HouseholdDefaults;
  age: AgeDefaults;
  income: IncomeDefaults;
  retirement: RetirementDefaults;
  expenses: ExpenseDefaults;
  debts: DebtItem[];
  assets: AssetDefaults;
  net_worth: NetWorthDefaults;
  recurring: SDRecurringItem[];
  equity: EquityDefaults;
  tax: TaxDefaults;
  benefits: BenefitsDefaults;
  goals: GoalItem[];
  businesses: BusinessItem[];
  data_sources: DataSourceFlags;
}

export interface HouseholdDefaults {
  id?: number;
  filing_status?: string;
  state?: string;
  spouse_a_name?: string;
  spouse_a_income?: number;
  spouse_a_employer?: string;
  spouse_b_name?: string;
  spouse_b_income?: number;
  spouse_b_employer?: string;
  combined_income?: number;
  other_income_annual?: number;
  dependents?: Array<{ name: string; relationship: string }>;
}

export interface AgeDefaults {
  current_age: number | null;
  date_of_birth: string | null;
}

export interface IncomeDefaults {
  w2_total: number;
  w2_fed_withheld: number;
  w2_state_withheld: number;
  w2_year: number | null;
  nec_total: number;
  combined: number;
  by_source: Array<{
    employer: string;
    wages: number;
    withheld: number;
  }>;
}

export interface RetirementDefaults {
  total_savings: number;
  monthly_contribution: number;
  annual_contribution: number;
  employer_match_pct: number;
  contribution_rate_pct: number;
}

export interface ExpenseDefaults {
  avg_monthly: number;
  median_monthly: number;
  annual_total: number;
  personal_annual_total: number;
  months_of_data: number;
  by_category: Record<string, number>;
}

export interface DebtItem {
  name: string;
  type: string;
  balance: number;
  institution: string | null;
  monthly_payment?: number;
  retirement_relevant?: boolean;
}

export interface AssetDefaults {
  real_estate_total: number;
  vehicle_total: number;
  investment_total: number;
  retirement_total: number;
  other_total: number;
  total: number;
}

export interface NetWorthDefaults {
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  as_of: string | null;
}

export interface SDRecurringItem {
  id: number;
  name: string;
  amount: number;
  frequency: string;
  category: string | null;
  segment: string;
}

export interface EquityDefaults {
  total_value: number;
  vested_value: number;
  unvested_value: number;
}

export interface TaxDefaults {
  total_withholding: number;
  federal_withholding: number;
  state_withholding: number;
  effective_rate: number;
  tax_year: number | null;
}

export interface BenefitsDefaults {
  has_401k: boolean;
  match_pct: number;
  match_limit_pct: number;
  has_hsa: boolean;
  has_espp: boolean;
  has_mega_backdoor: boolean;
  health_premium_monthly: number;
}

export interface GoalItem {
  id: number;
  name: string;
  target: number;
  current: number;
  monthly_contribution: number;
  progress_pct: number;
  account_id: number | null;
}

export interface BusinessItem {
  id: number;
  name: string;
  entity_type: string;
  tax_treatment: string;
}

export interface DataSourceFlags {
  has_w2: boolean;
  has_plaid: boolean;
  has_household: boolean;
  has_benefits: boolean;
  has_assets: boolean;
  has_recurring: boolean;
  has_equity: boolean;
  has_budget: boolean;
  w2_count: number;
  plaid_accounts: number;
}

// Household update suggestions (W-2 → Household sync)
export interface HouseholdUpdateSuggestion {
  field: string;
  label: string;
  current: number | string;
  suggested: number | string;
  source: string;
}

// Smart budget line
export interface SmartBudgetLine {
  category: string;
  segment: string;
  budget_amount: number;
  source: "recurring" | "goal" | string; // e.g. "3-month median"
  detail: string | null;
}

// Tax carry-forward item
export interface TaxCarryForwardItem {
  form_type: string;
  payer_name: string;
  payer_ein: string | null;
  prior_year_amount: number;
  from_year: number;
  to_year: number;
  status: "expected" | "received";
}

// Proactive insight
export interface ProactiveInsight {
  type: string;
  severity: "info" | "warning" | "action";
  title: string;
  message: string;
  link_to: string;
  value: number | null;
}

// Category rule (learned from user corrections)
export interface CategoryRule {
  id: number;
  merchant_pattern: string;
  category: string | null;
  tax_category: string | null;
  segment: string | null;
  business_entity_id: number | null;
  match_count: number;
  is_active: boolean;
  source: string;
}

// Document type detection result
export interface DocumentTypeDetection {
  detected_type: string;
  confidence: number;
  suggested_fields: Record<string, string>;
}
