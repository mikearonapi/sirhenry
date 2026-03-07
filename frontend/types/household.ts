export type OtherIncomeType =
  | "trust_k1"
  | "partnership_k1"
  | "scorp_k1"
  | "rental"
  | "dividends_1099"
  | "business_1099"
  | "alimony"
  | "social_security"
  | "pension"
  | "other";

export interface OtherIncomeSource {
  label: string;
  type: OtherIncomeType;
  amount: number;
  notes?: string;
}

export type FamilyMemberRelationship = "self" | "spouse" | "child" | "other_dependent" | "parent" | "other";

export interface FamilyMember {
  id: number;
  household_id: number;
  name: string;
  relationship: FamilyMemberRelationship;
  date_of_birth: string | null;
  ssn_last4: string | null;
  is_earner: boolean;
  income: number | null;
  employer: string | null;
  work_state: string | null;
  employer_start_date: string | null;
  grade_level: string | null;
  school_name: string | null;
  care_cost_annual: number | null;
  college_start_year: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FamilyMemberIn {
  household_id: number;
  name: string;
  relationship: FamilyMemberRelationship;
  date_of_birth?: string | null;
  ssn_last4?: string | null;
  is_earner?: boolean;
  income?: number | null;
  employer?: string | null;
  work_state?: string | null;
  employer_start_date?: string | null;
  grade_level?: string | null;
  school_name?: string | null;
  care_cost_annual?: number | null;
  college_start_year?: number | null;
  notes?: string | null;
}

export interface FamilyMilestone {
  member_id: number;
  member_name: string;
  relationship: FamilyMemberRelationship;
  type: string;
  label: string;
  years_away: number;
  target_year: number;
  age_at_event: number;
  action: string;
  category: "retirement" | "healthcare" | "education" | "insurance" | "tax" | string;
}

export interface HouseholdProfile {
  id: number;
  name: string;
  filing_status: string;
  state: string | null;
  dependents_json: string | null;
  spouse_a_name: string | null;
  spouse_a_preferred_name: string | null;
  spouse_a_income: number;
  spouse_a_employer: string | null;
  spouse_a_work_state: string | null;
  spouse_a_start_date: string | null;
  spouse_b_name: string | null;
  spouse_b_income: number;
  spouse_b_employer: string | null;
  spouse_b_work_state: string | null;
  spouse_b_start_date: string | null;
  combined_income: number;
  estate_will_status: string | null;
  estate_poa_status: string | null;
  estate_hcd_status: string | null;
  estate_trust_status: string | null;
  beneficiaries_reviewed: boolean | null;
  beneficiaries_reviewed_date: string | null;
  other_income_annual: number | null;
  other_income_sources_json: string | null;
  is_primary: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface HouseholdProfileIn {
  name?: string;
  filing_status?: string;
  state?: string | null;
  dependents_json?: string | null;
  spouse_a_name?: string | null;
  spouse_a_preferred_name?: string | null;
  spouse_a_income?: number;
  spouse_a_employer?: string | null;
  spouse_a_work_state?: string | null;
  spouse_a_start_date?: string | null;
  spouse_b_name?: string | null;
  spouse_b_income?: number;
  spouse_b_employer?: string | null;
  spouse_b_work_state?: string | null;
  spouse_b_start_date?: string | null;
  estate_will_status?: string | null;
  estate_poa_status?: string | null;
  estate_hcd_status?: string | null;
  estate_trust_status?: string | null;
  beneficiaries_reviewed?: boolean | null;
  beneficiaries_reviewed_date?: string | null;
  other_income_annual?: number | null;
  other_income_sources_json?: string | null;
  notes?: string | null;
}

export interface BenefitPackageType {
  id: number;
  household_id: number;
  spouse: "a" | "b";
  employer_name: string | null;
  has_401k: boolean;
  employer_match_pct: number | null;
  employer_match_limit_pct: number | null;
  has_roth_401k: boolean;
  has_mega_backdoor: boolean;
  annual_401k_limit: number | null;
  mega_backdoor_limit: number | null;
  annual_401k_contribution: number | null;
  has_hsa: boolean;
  hsa_employer_contribution: number | null;
  has_fsa: boolean;
  has_dep_care_fsa: boolean;
  health_premium_monthly: number | null;
  dental_vision_monthly: number | null;
  health_plan_options_json: string | null;
  life_insurance_coverage: number | null;
  life_insurance_cost_monthly: number | null;
  std_coverage_pct: number | null;
  std_waiting_days: number | null;
  ltd_coverage_pct: number | null;
  ltd_waiting_days: number | null;
  commuter_monthly_limit: number | null;
  tuition_reimbursement_annual: number | null;
  has_espp: boolean;
  espp_discount_pct: number | null;
  open_enrollment_start: string | null;
  open_enrollment_end: string | null;
  other_benefits_json: string | null;
  notes: string | null;
}

export interface HouseholdOptimizationResult {
  household_id: number;
  tax_year: number;
  optimal_filing_status: string;
  mfj_tax: number;
  mfs_tax: number;
  filing_savings: number;
  retirement_strategy: Record<string, unknown>;
  insurance_selection: string;
  childcare_strategy: Record<string, unknown>;
  total_annual_savings: number;
  recommendations: Array<{ area: string; action: string; savings: number }>;
}

export interface W4OptimizationResult {
  spouse_a_income: number;
  spouse_b_income: number;
  combined_income: number;
  estimated_mfj_tax: number;
  estimated_withheld_a: number;
  estimated_withheld_b: number;
  total_estimated_withheld: number;
  estimated_shortfall: number;
  extra_per_paycheck_a: number;
  extra_per_paycheck_b: number;
  marginal_rate: number;
  effective_rate: number;
  recommendation: string;
  recommendation_lines: string[];
}

export interface TaxThreshold {
  id: string;
  label: string;
  threshold: number;
  threshold_end?: number;
  current_magi: number;
  exposure: number;
  tax_impact: number;
  proximity_pct: number;
  exceeded: boolean;
  partially_exceeded?: boolean;
  description: string;
  actions: string[];
}

export interface TaxThresholdResult {
  combined_income: number;
  magi_estimate: number;
  filing_status: string;
  thresholds: TaxThreshold[];
  exceeded_count: number;
  total_estimated_additional_tax: number;
  note: string;
}
