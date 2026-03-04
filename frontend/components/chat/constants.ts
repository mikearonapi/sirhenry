import {
  Search,
  FileEdit,
  BarChart3,
  Wallet,
  Receipt,
  Target,
  RotateCcw,
  TrendingUp,
  ShieldCheck,
  Sparkles,
  PieChart,
  Landmark,
  Compass,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Tool display constants
// ---------------------------------------------------------------------------

export const TOOL_ICONS: Record<string, typeof Search> = {
  search_transactions: Search,
  get_transaction_detail: Search,
  recategorize_transaction: FileEdit,
  get_spending_summary: BarChart3,
  get_account_balances: Wallet,
  get_tax_info: Receipt,
  get_budget_status: Target,
  get_recurring_expenses: RotateCcw,
  get_setup_status: Sparkles,
  get_household_summary: Wallet,
  get_goals_summary: Target,
  get_portfolio_overview: PieChart,
  get_retirement_status: Landmark,
  get_life_scenarios: Compass,
};

export const TOOL_LABELS: Record<string, string> = {
  search_transactions: "Searching transactions",
  get_transaction_detail: "Looking up transaction details",
  recategorize_transaction: "Updating transaction",
  get_spending_summary: "Analyzing spending",
  get_account_balances: "Checking accounts",
  get_tax_info: "Pulling tax data",
  get_budget_status: "Reviewing budget",
  get_recurring_expenses: "Scanning subscriptions",
  get_setup_status: "Checking setup progress",
  get_household_summary: "Loading household profile",
  get_goals_summary: "Reviewing your goals",
  get_portfolio_overview: "Analyzing portfolio",
  get_retirement_status: "Checking retirement readiness",
  get_life_scenarios: "Loading life scenarios",
};

export const TOOL_DONE_LABELS: Record<string, string> = {
  search_transactions: "Found transactions",
  get_transaction_detail: "Retrieved details",
  recategorize_transaction: "Transaction updated",
  get_spending_summary: "Spending analyzed",
  get_account_balances: "Accounts checked",
  get_tax_info: "Tax data loaded",
  get_budget_status: "Budget reviewed",
  get_recurring_expenses: "Subscriptions scanned",
  get_setup_status: "Setup status loaded",
  get_household_summary: "Household data loaded",
  get_goals_summary: "Goals reviewed",
  get_portfolio_overview: "Portfolio analyzed",
  get_retirement_status: "Retirement status loaded",
  get_life_scenarios: "Scenarios loaded",
};

// ---------------------------------------------------------------------------
// Suggestion categories
// ---------------------------------------------------------------------------

export interface SuggestionCategory {
  label: string;
  icon: typeof Search;
  color: string;
  bgColor: string;
  suggestions: string[];
}

export const SUGGESTION_CATEGORIES: SuggestionCategory[] = [
  {
    label: "Spending",
    icon: TrendingUp,
    color: "text-blue-600",
    bgColor: "bg-blue-50 hover:bg-blue-100 border-blue-100",
    suggestions: [
      "What did I spend the most on last month?",
      "Show me unusual or large charges this year",
      "How does my spending this month compare to last month?",
      "Where can I cut back to save more?",
    ],
  },
  {
    label: "Taxes",
    icon: Receipt,
    color: "text-emerald-600",
    bgColor: "bg-emerald-50 hover:bg-emerald-100 border-emerald-100",
    suggestions: [
      "What tax strategies should I focus on right now?",
      "Are there any business expenses I might be missing?",
      "How much have I spent on deductible categories this year?",
      "Review my business expenses for AutoRev",
    ],
  },
  {
    label: "Accuracy",
    icon: ShieldCheck,
    color: "text-amber-600",
    bgColor: "bg-amber-50 hover:bg-amber-100 border-amber-100",
    suggestions: [
      "Are there any transactions that look miscategorized?",
      "Show me low-confidence AI categorizations",
      "Find any personal expenses tagged as business",
      "Check if reimbursable expenses are properly marked",
    ],
  },
  {
    label: "Goals & Planning",
    icon: Target,
    color: "text-purple-600",
    bgColor: "bg-purple-50 hover:bg-purple-100 border-purple-100",
    suggestions: [
      "Am I on track with my financial goals?",
      "How does my portfolio allocation look? Any rebalancing needed?",
      "Am I on track for retirement? What should I change?",
      "Can I afford to buy a house in the next 2 years?",
    ],
  },
  {
    label: "Wealth Building",
    icon: TrendingUp,
    color: "text-indigo-600",
    bgColor: "bg-indigo-50 hover:bg-indigo-100 border-indigo-100",
    suggestions: [
      "Should I pay off loans faster or invest more?",
      "How should I handle my RSU vesting and taxes?",
      "What's my net worth trajectory looking like?",
      "Help me optimize my 401k and retirement contributions",
    ],
  },
];

// Setup-specific suggestions (shown on /setup pages)
export const SETUP_SUGGESTION_CATEGORY: SuggestionCategory = {
  label: "Setup",
  icon: Sparkles,
  color: "text-[#16A34A]",
  bgColor: "bg-green-50 hover:bg-green-100 border-green-100",
  suggestions: [
    "What filing status would save me the most in taxes?",
    "Help me decide how to structure my business — LLC, S-Corp, or sole prop?",
    "What insurance coverage does my family need?",
    "Which life events should I be tracking for tax purposes?",
  ],
};

export const SUGGESTION_CATEGORIES_DARK: SuggestionCategory[] = [
  { ...SUGGESTION_CATEGORIES[0], bgColor: "bg-green-900/30 hover:bg-green-900/50 border-green-800/50", color: "text-green-400" },
  { ...SUGGESTION_CATEGORIES[1], bgColor: "bg-green-900/30 hover:bg-green-900/50 border-green-800/50", color: "text-green-400" },
  { ...SUGGESTION_CATEGORIES[2], bgColor: "bg-amber-900/30 hover:bg-amber-900/50 border-amber-800/50", color: "text-amber-400" },
  { ...SUGGESTION_CATEGORIES[3], bgColor: "bg-purple-900/30 hover:bg-purple-900/50 border-purple-800/50", color: "text-purple-400" },
  { ...SUGGESTION_CATEGORIES[4], bgColor: "bg-indigo-900/30 hover:bg-indigo-900/50 border-indigo-800/50", color: "text-indigo-400" },
];

export const SETUP_SUGGESTION_CATEGORY_DARK: SuggestionCategory = {
  ...SETUP_SUGGESTION_CATEGORY,
  bgColor: "bg-green-900/30 hover:bg-green-900/50 border-green-800/50",
  color: "text-green-400",
};
