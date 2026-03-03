export interface BenchmarkData {
  user_age: number;
  income: number;
  net_worth: number;
  savings_rate: number;
  nw_percentile: number;
  savings_percentile: number;
  nw_for_age_median: number;
  nw_for_age_75th: number;
  required_savings_rate?: number;
}

export interface FOOStep {
  step: number;
  name: string;
  description: string;
  status: "done" | "in_progress" | "next" | "locked";
  current_value: number | null;
  target_value: number | null;
  link: string;
}
