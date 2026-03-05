/** Shared goal constants used by GoalsPage, GoalCard, and GoalTemplates. */

export const GOAL_TYPES = [
  { value: "savings", label: "Savings" },
  { value: "debt_payoff", label: "Debt Payoff" },
  { value: "investment", label: "Investment" },
  { value: "emergency_fund", label: "Emergency Fund" },
  { value: "purchase", label: "Major Purchase" },
  { value: "tax", label: "Tax Reserve" },
  { value: "other", label: "Other" },
] as const;

export const COLORS = [
  "#6366f1",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
] as const;

export const GRADIENTS = [
  "from-stone-600 to-stone-800",
  "from-blue-600 to-indigo-800",
  "from-emerald-600 to-teal-800",
  "from-amber-500 to-orange-700",
  "from-rose-500 to-pink-700",
  "from-purple-600 to-violet-800",
  "from-cyan-500 to-sky-700",
] as const;
