export interface BusinessEntity {
  id: number;
  name: string;
  owner: string | null;
  entity_type: string;
  tax_treatment: string;
  ein: string | null;
  is_active: boolean;
  is_provisional: boolean;
  active_from: string | null;
  active_to: string | null;
  notes: string | null;
  description: string | null;
  expected_expenses: string | null;
  created_at: string;
}

export interface BusinessEntityCreateIn {
  name: string;
  owner?: string | null;
  entity_type?: string;
  tax_treatment?: string;
  ein?: string | null;
  is_provisional?: boolean;
  active_from?: string | null;
  active_to?: string | null;
  notes?: string | null;
  description?: string | null;
  expected_expenses?: string | null;
}

export interface EntityMonthlyTotal {
  month: number;
  month_name: string;
  total_expenses: number;
  transaction_count: number;
}

export interface EntityCategoryBreakdown {
  category: string;
  total: number;
  percentage: number;
}

export interface EntityExpenseReport {
  entity_id: number;
  entity_name: string;
  year: number;
  monthly_totals: EntityMonthlyTotal[];
  category_breakdown: EntityCategoryBreakdown[];
  year_total_expenses: number;
  prior_year_total_expenses: number | null;
  year_over_year_change_pct: number | null;
}

export interface VendorEntityRule {
  id: number;
  vendor_pattern: string;
  business_entity_id: number;
  segment_override: string | null;
  effective_from: string | null;
  effective_to: string | null;
  priority: number;
  is_active: boolean;
  created_at: string;
}

export interface EntityReassignIn {
  from_entity_id: number;
  to_entity_id: number;
  date_from?: string | null;
  date_to?: string | null;
}

export interface ReimbursementMonthly {
  month: string;
  expenses: number;
  expense_count: number;
  reimbursed: number;
  reimbursement_count: number;
  net: number;
  running_balance: number;
}

export interface ReimbursementReport {
  entity_id: number;
  entity_name: string;
  linked_accounts: { id: number; name: string; institution: string }[];
  monthly: ReimbursementMonthly[];
  total_expenses: number;
  total_reimbursed: number;
  balance: number;
}

export interface EntityTransaction {
  date: string;
  description: string;
  amount: number;
  category: string;
  tax_category: string;
  account: string;
  segment: string;
  notes: string;
}

export interface VendorEntityRuleCreateIn {
  vendor_pattern: string;
  business_entity_id: number;
  segment_override?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  priority?: number;
}
