export interface BudgetItem {
  id: number;
  year: number;
  month: number;
  category: string;
  segment: string;
  budget_amount: number;
  actual_amount: number;
  variance: number;
  utilization_pct: number;
  notes: string | null;
}

export interface BudgetSummary {
  total_budgeted: number;
  total_actual: number;
  variance: number;
  utilization_pct: number;
  over_budget_categories: Array<{ category: string; budgeted: number; actual: number }>;
  year_over_year: Array<{ year: number; total_expenses: number }>;
}

export interface UnbudgetedCategory {
  category: string;
  actual_amount: number;
}

export interface BudgetSnapshot {
  annual_expenses: number;
  monthly_expenses: number;
  categories: Array<{ category: string; monthly: number; annual: number }>;
  liabilities: Array<{ name: string; type: string; balance: number; institution: string | null }>;
}

export interface BudgetForecast {
  month: number;
  year: number;
  categories: Array<{
    category: string;
    predicted_amount: number;
    confidence: number;
    historical_avg: number;
  }>;
  total_predicted: number;
}

export interface BudgetForecastResponse {
  forecast: BudgetForecast;
  seasonal: Record<string, { monthly_averages?: Record<number, number>; peaks?: Record<number, number> }>;
  target_month: number;
  target_year: number;
}

export interface SpendVelocity {
  category: string;
  budget: number;
  spent_so_far: number;
  projected_total: number;
  on_track: boolean;
  status: "on_track" | "watch" | "over_budget";
}
