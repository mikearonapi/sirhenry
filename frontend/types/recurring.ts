export interface RecurringItem {
  id: number;
  name: string;
  amount: number;
  frequency: "monthly" | "quarterly" | "annual" | "weekly" | "bi-weekly";
  category: string | null;
  segment: string;
  status: "active" | "cancelled" | "paused";
  last_seen_date: string | null;
  next_expected_date: string | null;
  is_auto_detected: boolean;
  annual_cost: number;
}

export interface RecurringSummary {
  total_monthly_cost: number;
  total_annual_cost: number;
  subscription_count: number;
  by_category: Record<string, number>;
}
