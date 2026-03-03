export interface DebtPayoff {
  name: string;
  monthly_payment: number;
  payoff_age: number;
}

export interface RetirementProfile {
  id: number;
  name: string;
  current_age: number;
  retirement_age: number;
  life_expectancy: number;
  current_annual_income: number;
  expected_income_growth_pct: number;
  expected_social_security_monthly: number;
  social_security_start_age: number;
  pension_monthly: number;
  other_retirement_income_monthly: number;
  current_retirement_savings: number;
  current_other_investments: number;
  monthly_retirement_contribution: number;
  employer_match_pct: number;
  employer_match_limit_pct: number;
  desired_annual_retirement_income: number | null;
  income_replacement_pct: number;
  healthcare_annual_estimate: number;
  additional_annual_expenses: number;
  inflation_rate_pct: number;
  pre_retirement_return_pct: number;
  post_retirement_return_pct: number;
  tax_rate_in_retirement_pct: number;
  current_annual_expenses: number | null;
  debt_payoffs: DebtPayoff[];
  target_nest_egg: number | null;
  projected_nest_egg_at_retirement: number | null;
  monthly_savings_needed: number | null;
  retirement_readiness_pct: number | null;
  years_money_will_last: number | null;
  projected_monthly_retirement_income: number | null;
  savings_gap: number | null;
  fire_number: number | null;
  coast_fire_number: number | null;
  earliest_retirement_age: number | null;
  is_primary: boolean;
  last_computed_at: string | null;
  notes: string | null;
}

export interface RetirementResults {
  years_to_retirement: number;
  years_in_retirement: number;
  annual_income_needed_today: number;
  annual_income_needed_at_retirement: number;
  monthly_income_needed_at_retirement: number;
  target_nest_egg: number;
  fire_number: number;
  coast_fire_number: number;
  lean_fire_number: number;
  projected_nest_egg: number;
  projected_monthly_income: number;
  savings_gap: number;
  monthly_savings_needed: number;
  retirement_readiness_pct: number;
  years_money_will_last: number;
  on_track: boolean;
  current_savings_rate_pct: number;
  recommended_savings_rate_pct: number;
  total_monthly_contribution: number;
  employer_match_monthly: number;
  social_security_annual: number;
  pension_annual: number;
  other_income_annual: number;
  total_guaranteed_income_annual: number;
  portfolio_income_needed_annual: number;
  debt_payoff_savings_annual: number;
  earliest_retirement_age: number;
  yearly_projection: Array<{
    age: number;
    year: number;
    phase: string;
    balance: number;
    growth: number;
    contribution: number;
    withdrawal: number;
  }>;
}

export interface RetirementImpact {
  current_retirement_age: number;
  new_retirement_age: number;
  years_delayed: number;
  current_fire_number: number;
  new_fire_number: number;
}

export interface MonteCarloResult {
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  runs: number;
}
