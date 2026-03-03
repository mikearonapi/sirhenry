export interface Goal {
  id: number;
  name: string;
  description: string | null;
  goal_type: "savings" | "debt_payoff" | "investment" | "emergency_fund" | "purchase" | "tax" | "other";
  target_amount: number;
  current_amount: number;
  target_date: string | null;
  status: "active" | "completed" | "paused" | "cancelled";
  color: string;
  monthly_contribution: number | null;
  progress_pct: number;
  months_remaining: number | null;
  on_track: boolean | null;
}

export interface Reminder {
  id: number;
  title: string;
  description: string | null;
  reminder_type: "bill" | "tax" | "subscription" | "goal" | "custom";
  due_date: string;
  amount: number | null;
  advance_notice: "none" | "1_day" | "3_days" | "7_days" | "14_days";
  status: "pending" | "completed" | "snoozed" | "dismissed";
  is_recurring: boolean;
  recurrence_rule: string | null;
  days_until_due: number;
  is_overdue: boolean;
}
