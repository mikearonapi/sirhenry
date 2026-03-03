export type OutlierClassification = "recurring" | "one_time" | "not_outlier";

export interface OutlierFeedback {
  id: number;
  transaction_id: number;
  classification: OutlierClassification;
  user_note: string | null;
  description_pattern: string | null;
  category: string | null;
  apply_to_future: boolean;
  year: number;
  created_at: string;
}

export interface OutlierFeedbackIn {
  transaction_id: number;
  classification: OutlierClassification;
  user_note?: string | null;
  apply_to_future?: boolean;
  year: number;
}

export interface OutlierReviewSummary {
  total_outliers: number;
  reviewed: number;
  recurring: number;
  one_time: number;
  not_outlier: number;
}

export interface OutlierTransaction {
  id: number;
  date: string | null;
  description: string;
  amount: number;
  category: string;
  segment: string | null;
  typical_amount: number;
  threshold: number;
  excess_pct: number;
  reason: string;
  feedback: OutlierFeedback | null;
}

export interface InsightsSummary {
  total_outlier_expenses: number;
  total_outlier_income: number;
  expense_outlier_count: number;
  income_outlier_count: number;
  normalized_monthly_budget: number;
  actual_monthly_average: number;
  normalization_savings: number;
}

export interface NormalizedCategory {
  category: string;
  normalized_monthly: number;
  mean_monthly: number;
  min_monthly: number;
  max_monthly: number;
  months_active: number;
}

export interface NormalizedBudget {
  normalized_monthly_total: number;
  mean_monthly_total: number;
  min_month: number;
  max_month: number;
  by_category: NormalizedCategory[];
}

export interface CategoryAmount {
  category: string;
  amount: number;
}

export interface MonthlyAnalysis {
  month: number;
  month_name: string;
  total_expenses: number;
  expenses_excl_outliers: number;
  total_income: number;
  outlier_expense_total: number;
  outlier_count: number;
  classification: string;
  deviation_pct: number;
  top_categories: CategoryAmount[];
  explanation: string | null;
}

export interface SeasonalCategory {
  category: string;
  avg_amount: number;
}

export interface SeasonalPattern {
  month: number;
  month_name: string;
  average_expenses: number;
  seasonal_index: number;
  label: string;
  years_of_data: number;
  top_categories: SeasonalCategory[];
}

export interface CategoryTrend {
  category: string;
  trend: string;
  total_annual: number;
  monthly_average: number;
  monthly_median: number;
  volatility: number;
  budget_share_pct: number;
  months_active: number;
  monthly_amounts: Record<string, number>;
}

export interface IncomeSource {
  source: string;
  total: number;
}

export interface IrregularIncomeItem {
  date: string | null;
  description: string;
  amount: number;
  category: string;
}

export interface IncomeAnalysis {
  regular_monthly_median: number;
  regular_monthly_mean: number;
  total_regular: number;
  total_irregular: number;
  irregular_items: IrregularIncomeItem[];
  by_source: IncomeSource[];
}

export interface MonthlyComparison {
  month: number;
  month_name: string;
  current_expenses: number;
  prior_expenses: number;
  current_income: number;
  prior_income: number;
  prior_2_expenses?: number;
  prior_2_income?: number;
}

export interface CategoryYoY {
  category: string;
  current_year: number;
  prior_year: number;
  change_pct: number;
}

export interface YearOverYear {
  current_year_income: number;
  prior_year_income: number;
  income_change_pct: number;
  current_year_expenses: number;
  prior_year_expenses: number;
  expense_change_pct: number;
  current_year_net: number;
  prior_year_net: number;
  monthly_comparison: MonthlyComparison[];
  category_changes: CategoryYoY[];
  prior_year_2?: number | null;
  prior_year_2_income?: number | null;
  prior_year_2_expenses?: number | null;
}

export interface Insights {
  year: number;
  transaction_count: number;
  summary: InsightsSummary;
  expense_outliers: OutlierTransaction[];
  income_outliers: OutlierTransaction[];
  outlier_review: OutlierReviewSummary | null;
  normalized_budget: NormalizedBudget;
  monthly_analysis: MonthlyAnalysis[];
  seasonal_patterns: SeasonalPattern[];
  category_trends: CategoryTrend[];
  income_analysis: IncomeAnalysis;
  year_over_year: YearOverYear | null;
}
