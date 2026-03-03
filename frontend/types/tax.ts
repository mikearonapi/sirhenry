export interface TaxItem {
  id: number;
  source_document_id: number;
  tax_year: number;
  form_type: "w2" | "1099_nec" | "1099_div" | "1099_b" | "1099_int" | "k1";
  payer_name: string | null;
  payer_ein: string | null;
  w2_wages: number | null;
  w2_federal_tax_withheld: number | null;
  w2_state: string | null;
  w2_state_wages: number | null;
  w2_state_income_tax: number | null;
  w2_state_allocations: string | null;
  nec_nonemployee_compensation: number | null;
  nec_federal_tax_withheld: number | null;
  div_total_ordinary: number | null;
  div_qualified: number | null;
  div_total_capital_gain: number | null;
  b_proceeds: number | null;
  b_cost_basis: number | null;
  b_gain_loss: number | null;
  b_term: string | null;
  int_interest: number | null;
  raw_fields: string | null;
}

export interface TaxSummary {
  tax_year: number;
  w2_total_wages: number;
  w2_federal_withheld: number;
  w2_state_allocations: Array<{ state: string; wages: number; tax: number }>;
  nec_total: number;
  div_ordinary: number;
  div_qualified: number;
  div_capital_gain: number;
  capital_gains_short: number;
  capital_gains_long: number;
  interest_income: number;
}

export interface TaxStrategy {
  id: number;
  tax_year: number;
  priority: number;
  title: string;
  description: string;
  strategy_type: "bracket" | "deduction" | "credit" | "structure" | "timing" | "retirement" | "investment";
  estimated_savings_low: number | null;
  estimated_savings_high: number | null;
  action_required: string | null;
  deadline: string | null;
  is_dismissed: boolean;
  generated_at: string;
}

export interface TaxEstimate {
  tax_year: number;
  estimated_agi: number;
  estimated_taxable_income: number;
  ordinary_income: number;
  qualified_dividends_and_ltcg: number;
  self_employment_income: number;
  federal_income_tax: number;
  self_employment_tax: number;
  niit: number;
  additional_medicare_tax: number;
  total_estimated_tax: number;
  effective_rate: number;
  marginal_rate: number;
  w2_federal_already_withheld: number;
  estimated_balance_due: number;
  disclaimer: string;
}

export interface TaxChecklistItem {
  id: string;
  label: string;
  description: string;
  status: "complete" | "partial" | "incomplete" | "not_applicable";
  detail: string | null;
  category: "documents" | "preparation" | "filing" | "payments";
}

export interface TaxChecklist {
  tax_year: number;
  items: TaxChecklistItem[];
  completed: number;
  total: number;
  progress_pct: number;
}

export interface DeductionOpportunity {
  id: string;
  title: string;
  description: string;
  category: string;
  estimated_tax_savings_low: number;
  estimated_tax_savings_high: number;
  estimated_cost: number | null;
  net_benefit_explanation: string;
  urgency: "high" | "medium" | "low";
  deadline: string | null;
  applicable: boolean;
}

export interface TaxDeductionInsights {
  tax_year: number;
  estimated_balance_due: number;
  effective_rate: number;
  marginal_rate: number;
  opportunities: DeductionOpportunity[];
  summary: string;
}

export interface RothConversionResult {
  year_by_year: Array<{
    year: number;
    conversion_amount: number;
    tax_on_conversion: number;
    marginal_rate: number;
    remaining_traditional: number;
    roth_balance: number;
  }>;
  total_converted: number;
  total_tax_paid: number;
  projected_roth_at_retirement: number;
}

export interface SCorpAnalysisResult {
  schedule_c_tax: number;
  scorp_tax: number;
  se_tax_savings: number;
  reasonable_salary: number;
  total_savings: number;
}

export interface MultiYearTaxProjection {
  years: Array<{
    year: number;
    income: number;
    federal_tax: number;
    state_tax: number;
    fica: number;
    total_tax: number;
    effective_rate: number;
  }>;
}

export interface StudentLoanResult {
  strategies: Array<{
    name: string;
    monthly_payment: number;
    total_paid: number;
    total_interest: number;
    payoff_years: number;
    forgiveness_amount: number;
  }>;
  recommendation: string;
}
