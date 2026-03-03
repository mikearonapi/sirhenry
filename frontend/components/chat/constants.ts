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
    label: "Goals & Subscriptions",
    icon: Target,
    color: "text-purple-600",
    bgColor: "bg-purple-50 hover:bg-purple-100 border-purple-100",
    suggestions: [
      "What recurring subscriptions am I paying for?",
      "How much am I spending on subscriptions annually?",
      "Am I on track with my budget this month?",
      "What's my overall financial health looking like?",
    ],
  },
];

export const SUGGESTION_CATEGORIES_DARK: SuggestionCategory[] = [
  { ...SUGGESTION_CATEGORIES[0], bgColor: "bg-green-900/30 hover:bg-green-900/50 border-green-800/50", color: "text-green-400" },
  { ...SUGGESTION_CATEGORIES[1], bgColor: "bg-green-900/30 hover:bg-green-900/50 border-green-800/50", color: "text-green-400" },
  { ...SUGGESTION_CATEGORIES[2], bgColor: "bg-amber-900/30 hover:bg-amber-900/50 border-amber-800/50", color: "text-amber-400" },
  { ...SUGGESTION_CATEGORIES[3], bgColor: "bg-zinc-800 hover:bg-zinc-700 border-zinc-700", color: "text-zinc-300" },
];
