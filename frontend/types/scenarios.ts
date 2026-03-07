export interface ScenarioTemplate {
  label: string;
  icon: string;
  description: string;
  parameters: Record<string, {
    label: string;
    type: string;
    default: number | string;
  }>;
}

/** Scenario-specific parameters (varies per scenario_type). */
export type ScenarioParameters = Record<string, number | string>;

/** Input for creating a new life scenario. */
export interface ScenarioCreateInput {
  name: string;
  scenario_type: string;
  parameters: ScenarioParameters;
  annual_income: number;
  monthly_take_home: number;
  current_monthly_expenses: number;
  current_monthly_debt_payments?: number;
  current_savings?: number;
  current_investments?: number;
}

/** Input for stateless scenario calculation (no save). */
export interface ScenarioCalcInput {
  scenario_type: string;
  parameters: ScenarioParameters;
  annual_income: number;
  monthly_take_home: number;
  current_monthly_expenses: number;
  current_monthly_debt_payments?: number;
  current_savings?: number;
  current_investments?: number;
}

export interface LifeScenarioType {
  id: number;
  name: string;
  scenario_type: string;
  parameters: Record<string, number | string>;
  annual_income: number | null;
  monthly_take_home: number | null;
  current_monthly_expenses: number | null;
  total_cost: number | null;
  new_monthly_payment: number | null;
  monthly_surplus_after: number | null;
  savings_rate_before_pct: number | null;
  savings_rate_after_pct: number | null;
  dti_before_pct: number | null;
  dti_after_pct: number | null;
  affordability_score: number | null;
  verdict: string | null;
  results_detail: Record<string, unknown> | null;
  ai_analysis: string | null;
  status: string;
  is_favorite: boolean;
  notes: string | null;
  created_at: string;
}

export interface ScenarioCalcResult {
  total_cost: number;
  new_monthly_payment: number;
  monthly_surplus_after: number;
  savings_rate_before_pct: number;
  savings_rate_after_pct: number;
  dti_before_pct: number;
  dti_after_pct: number;
  affordability_score: number;
  verdict: string;
  breakdown: Record<string, number>;
  [key: string]: unknown;
}

export interface CompositeScenarioResult {
  combined_monthly_impact: number;
  combined_savings_rate_after: number;
  combined_dti_after: number;
  combined_affordability_score: number;
  combined_verdict: string;
  scenarios: Array<{ id: number; name: string; monthly_impact: number }>;
}

export interface MultiYearProjection {
  years: Array<{
    year: number;
    net_worth: number;
    savings: number;
    expenses: number;
    cash_flow: number;
  }>;
}

export interface ScenarioComparison {
  scenario_a: { id: number; name: string; metrics: Record<string, number> };
  scenario_b: { id: number; name: string; metrics: Record<string, number> };
  differences: Record<string, number>;
}
