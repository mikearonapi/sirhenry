import type { Transaction } from "./transactions";

export interface FinancialPeriod {
  id: number;
  year: number;
  month: number | null;
  segment: string;
  total_income: number;
  total_expenses: number;
  net_cash_flow: number;
  w2_income: number;
  investment_income: number;
  board_income: number;
  business_expenses: number;
  personal_expenses: number;
  expense_breakdown: string | null;
  income_breakdown: string | null;
  computed_at: string;
}

export interface MonthlyReport {
  period: FinancialPeriod;
  top_expense_categories: Array<{ category: string; amount: number }>;
  top_income_sources: Array<{ source: string; amount: number }>;
  vs_prior_month: {
    income_delta: number;
    expense_delta: number;
    net_delta: number;
  } | null;
  ai_insights: string | null;
}

export interface Dashboard {
  current_year: number;
  current_month: number;
  ytd_income: number;
  ytd_expenses: number;
  ytd_net: number;
  ytd_tax_estimate: number;
  current_month_income: number;
  current_month_expenses: number;
  current_month_net: number;
  current_month_tax_estimate: number;
  recent_transactions: Transaction[];
  monthly_trend: FinancialPeriod[];
  top_strategies_count: number;
}
