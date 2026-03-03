export type InsurancePolicyType =
  | "health" | "life" | "disability" | "auto" | "home"
  | "umbrella" | "pet" | "vision" | "dental" | "ltc" | "other";

export interface InsurancePolicy {
  id: number;
  household_id: number | null;
  owner_spouse: "a" | "b" | null;
  policy_type: InsurancePolicyType;
  provider: string | null;
  policy_number: string | null;
  coverage_amount: number | null;
  deductible: number | null;
  oop_max: number | null;
  annual_premium: number | null;
  monthly_premium: number | null;
  renewal_date: string | null;
  beneficiaries_json: string | null;
  employer_provided: boolean;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface InsurancePolicyIn {
  household_id?: number | null;
  owner_spouse?: "a" | "b" | null;
  policy_type: InsurancePolicyType;
  provider?: string | null;
  policy_number?: string | null;
  coverage_amount?: number | null;
  deductible?: number | null;
  oop_max?: number | null;
  annual_premium?: number | null;
  monthly_premium?: number | null;
  renewal_date?: string | null;
  beneficiaries_json?: string | null;
  employer_provided?: boolean;
  is_active?: boolean;
  notes?: string | null;
}

export interface InsuranceGapItem {
  type: string;
  label: string;
  current_coverage: number;
  recommended_coverage: number;
  gap: number;
  severity: "high" | "medium" | "low";
  note: string;
}

export interface InsuranceGapAnalysis {
  total_policies: number;
  total_annual_premium: number;
  total_monthly_premium: number;
  gaps: InsuranceGapItem[];
  high_severity_gaps: number;
  medium_severity_gaps: number;
  renewing_soon: Array<{
    id: number;
    label: string;
    renewal_date: string;
    days_until: number;
  }>;
  recommendations: string[];
}
