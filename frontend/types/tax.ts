export interface TaxItem {
  id: number;
  source_document_id: number;
  tax_year: number;
  form_type: "w2" | "1099_nec" | "1099_div" | "1099_b" | "1099_int" | "k1" | "1099_r" | "1099_g" | "1099_k" | "1098";
  payer_name: string | null;
  payer_ein: string | null;
  // W-2
  w2_wages: number | null;
  w2_federal_tax_withheld: number | null;
  w2_state: string | null;
  w2_state_wages: number | null;
  w2_state_income_tax: number | null;
  w2_state_allocations: string | null;
  // 1099-NEC
  nec_nonemployee_compensation: number | null;
  nec_federal_tax_withheld: number | null;
  // 1099-DIV
  div_total_ordinary: number | null;
  div_qualified: number | null;
  div_total_capital_gain: number | null;
  // 1099-B
  b_proceeds: number | null;
  b_cost_basis: number | null;
  b_gain_loss: number | null;
  b_term: string | null;
  // 1099-INT
  int_interest: number | null;
  // K-1
  k1_ordinary_income: number | null;
  k1_rental_income: number | null;
  k1_other_rental_income: number | null;
  k1_guaranteed_payments: number | null;
  k1_interest_income: number | null;
  k1_dividends: number | null;
  k1_qualified_dividends: number | null;
  k1_short_term_capital_gain: number | null;
  k1_long_term_capital_gain: number | null;
  k1_section_179: number | null;
  k1_distributions: number | null;
  // 1099-R (retirement)
  r_gross_distribution: number | null;
  r_taxable_amount: number | null;
  r_federal_tax_withheld: number | null;
  r_distribution_code: string | null;
  r_state_tax_withheld: number | null;
  r_state: string | null;
  // 1099-G (government)
  g_unemployment_compensation: number | null;
  g_state_tax_refund: number | null;
  g_federal_tax_withheld: number | null;
  g_state: string | null;
  // 1099-K (payment platforms)
  k_gross_amount: number | null;
  k_federal_tax_withheld: number | null;
  k_state: string | null;
  // 1098 (mortgage)
  m_mortgage_interest: number | null;
  m_points_paid: number | null;
  m_property_tax: number | null;
  // Raw
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
  k1_ordinary_income: number;
  k1_rental_income: number;
  k1_guaranteed_payments: number;
  k1_interest_income: number;
  k1_dividends: number;
  k1_capital_gains: number;
  retirement_distributions: number;
  retirement_taxable: number;
  unemployment_income: number;
  state_tax_refund: number;
  payment_platform_income: number;
  mortgage_interest_deduction: number;
  property_tax_deduction: number;
  data_source?: "documents" | "setup_profile" | "none";
}

export interface TaxStrategy {
  id: number;
  tax_year: number;
  priority: number;
  title: string;
  description: string;
  strategy_type: "bracket" | "deduction" | "credit" | "structure" | "timing" | "retirement" | "investment" | "state";
  estimated_savings_low: number | null;
  estimated_savings_high: number | null;
  action_required: string | null;
  deadline: string | null;
  is_dismissed: boolean;
  generated_at: string;
  // Enhanced AI analysis fields
  confidence: number | null;
  confidence_reasoning: string | null;
  category: "quick_win" | "this_year" | "big_move" | "long_term" | null;
  complexity: "low" | "medium" | "high" | null;
  prerequisites_json: string | null;
  who_its_for: string | null;
  related_simulator: string | null;
}

export interface TaxStrategyProfile {
  income_type: "w2" | "self_employed" | "mixed";
  combined_income: number;
  investment_income: number;
  filing_status: string;
  owed_or_refund: "owed" | "refund" | "unsure";
  itemizes: boolean;
  multi_state: boolean;
  age_over_50: boolean;
  has_rental_property: boolean;
  has_investment_accounts: boolean;
  has_equity_comp: boolean;
  has_traditional_ira: boolean;
  employer_allows_after_tax_401k: boolean;
  priorities: ("reduce_now" | "build_wealth" | "simplify")[];
  complexity_preference: "low" | "medium" | "high";
  open_to_business: boolean;
  open_to_real_estate: boolean;
  has_student_loans: boolean;
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
  data_source: "documents" | "setup_profile" | "none";
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
  data_source: "documents" | "setup_profile" | "none";
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

export interface MegaBackdoorResult {
  available: boolean;
  available_space: number;
  employee_contributions: number;
  employer_contributions: number;
  plan_limit: number;
  tax_free_growth_value_20yr: number;
  explanation: string;
}

export interface DefinedBenefitResult {
  viable: boolean;
  max_annual_contribution: number;
  sep_ira_contribution: number;
  additional_contribution: number;
  annual_tax_savings: number;
  sep_annual_tax_savings: number;
  additional_annual_savings: number;
  projected_accumulation: number;
  sep_projected_accumulation: number;
  years_to_retirement: number;
  marginal_rate: number;
  explanation: string;
}

export interface Section179Result {
  qualifies_section_179: boolean;
  equipment_cost: number;
  business_use_pct: number;
  deductible_cost: number;
  section_179_deduction: number;
  bonus_depreciation: number;
  year_one_total_deduction: number;
  year_one_tax_savings: number;
  marginal_rate: number;
  rental_analysis: {
    equipment_name: string;
    monthly_rental_rate: number;
    utilization_rate: number;
    demand_level: "high" | "medium" | "low";
    annual_rental_gross: number;
    annual_expenses: number;
    annual_net_rental: number;
    expense_breakdown: {
      maintenance: number;
      insurance: number;
      storage: number;
      transport: number;
    };
    resale_value_5yr: number;
    total_return_5yr: number;
  } | null;
  five_year_projection: Array<{
    year: number;
    rental_income: number;
    depreciation_deduction: number;
    tax_savings: number;
    net_cash_flow: number;
    cumulative_cash: number;
  }>;
  exit_strategies: Array<{
    strategy: string;
    description: string;
    applicable: boolean;
  }>;
  recommended_equipment: Array<{
    category: string;
    name: string;
    cost_range: string;
    monthly_rental: number;
    demand: "high" | "medium" | "low";
    utilization: number;
  }>;
  qualification_notes: string[];
}

export interface FilingStatusCompareResult {
  mfj: {
    federal_tax: number;
    niit: number;
    state_tax: number;
    fica: number;
    student_loan_benefit: number;
    total_tax: number;
    effective_rate: number;
    deduction_used: number;
    itemizing: boolean;
  };
  mfs: {
    federal_tax: number;
    niit: number;
    state_tax: number;
    fica: number;
    student_loan_benefit: number;
    total_tax: number;
    effective_rate: number;
    deduction_used: number;
    itemizing: boolean;
  };
  difference: number;
  better: "mfj" | "mfs";
  recommendation: string;
  idr_benefit: number;
  idr_note: string;
  mfs_limitations: string[];
}

export interface QBIDeductionResult {
  qbi_income: number;
  taxable_income: number;
  filing_status: string;
  is_sstb: boolean;
  basic_20pct_deduction: number;
  w2_wage_limit: number;
  taxable_income_cap: number;
  final_deduction: number;
  tax_savings: number;
  marginal_rate: number;
  phaseout_start: number;
  phaseout_end: number;
  in_phaseout: boolean;
  above_phaseout: boolean;
  sstb_eliminated: boolean;
  warnings: string[];
  recommendation: string;
}

export interface StateComparisonResult {
  income: number;
  filing_status: string;
  current_state: string;
  federal_tax: number;
  fica: number;
  current_state_tax: number;
  current_total_tax: number;
  states: Array<{
    state: string;
    state_name: string;
    state_tax: number;
    state_rate: number;
    total_tax: number;
    effective_total_rate: number;
    savings_vs_current: number;
    is_current: boolean;
    is_no_tax: boolean;
  }>;
  best_state: string;
  max_savings: number;
  recommendation: string;
}

export interface RealEstateSTRResult {
  qualifies_str: boolean;
  material_participation: boolean;
  can_offset_w2: boolean;
  property_value: number;
  depreciable_basis: number;
  standard_annual_depreciation: number;
  cost_seg_year_one_depreciation: number;
  annual_rental_income: number;
  operating_expenses: number;
  standard_net_income: number;
  cost_seg_net_income_year_one: number;
  w2_offset_year_one: number;
  tax_savings_year_one: number;
  standard_tax_savings: number;
  marginal_rate: number;
  qualification_notes: string[];
}
