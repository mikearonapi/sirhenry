// ─── Synthetic Data for Landing Page Mockups ─────────────────────────
// Single source of truth for all landing page feature showcases.
// Persona: Sarah (SWE, $220K) & Alex (PM, $160K) — a HENRY couple, age 34.
// All numbers are internally consistent.
// Last synced with app features: March 2026.

// ─── Dashboard ────────────────────────────────────────────────────────
export const DEMO_DASHBOARD = {
  netWorth: 347_000,
  netWorthDelta90d: 12_400,
  savingsRate: 18.2,
  targetSavingsRate: 20,
  retireByAge: 54,
  retireConfidence: 84,
  currentMonthIncome: 31_667,
  currentMonthExpenses: 23_200,
  currentMonthTaxEstimate: 4_800,
  currentMonthSavings: 3_667,
};

export const DEMO_ACTION_PLAN = [
  { name: "Max out backdoor Roth IRA", status: "done" as const, value: "+$14,000/yr" },
  { name: "Fund HSA to maximum", status: "next" as const, value: "+$8,300/yr" },
  { name: "Diversify RSU concentration", status: "pending" as const, value: "Reduce risk" },
  { name: "Open 529 for college savings", status: "pending" as const, value: "+$10K/yr tax benefit" },
];

// ─── Retirement / Trajectory ──────────────────────────────────────────
export const DEMO_RETIREMENT = {
  fireNumber: 3_200_000,
  coastFireNumber: 890_000,
  projectedNestEgg: 3_450_000,
  earliestRetirementAge: 52,
  retirementReadinessPct: 84,
  monteCarlo: {
    p10: 2_100_000,
    p50: 3_450_000,
    p90: 5_100_000,
    runs: 10_000,
  },
  yearlyProjection: [
    { age: 34, balance: 347_000 },
    { age: 38, balance: 620_000 },
    { age: 42, balance: 1_050_000 },
    { age: 46, balance: 1_680_000 },
    { age: 50, balance: 2_500_000 },
    { age: 54, balance: 3_450_000 },
    { age: 58, balance: 4_100_000 },
    { age: 62, balance: 4_500_000 },
    { age: 64, balance: 4_200_000 },
  ],
};

// ─── Portfolio & Investments ──────────────────────────────────────────
export const DEMO_PORTFOLIO = {
  totalValue: 285_000,
  totalGainLoss: 34_200,
  totalGainLossPct: 13.6,
  allocation: [
    { name: "US Stocks", pct: 52, color: "#22C55E" },
    { name: "Int'l Stocks", pct: 18, color: "#3B82F6" },
    { name: "Bonds", pct: 15, color: "#8B5CF6" },
    { name: "REITs", pct: 8, color: "#F59E0B" },
    { name: "Cash", pct: 4, color: "#6B7280" },
    { name: "Crypto", pct: 3, color: "#EC4899" },
  ],
  topHoldings: [
    { ticker: "VTI", name: "Vanguard Total Stock", value: 98_000, gainPct: 18.2 },
    { ticker: "VXUS", name: "Vanguard Int'l Stock", value: 42_000, gainPct: 8.1 },
    { ticker: "BND", name: "Vanguard Total Bond", value: 38_000, gainPct: 2.4 },
    { ticker: "AAPL", name: "Apple (RSU)", value: 32_000, gainPct: 24.5 },
    { ticker: "VNQ", name: "Vanguard Real Estate", value: 22_000, gainPct: 5.7 },
  ],
  taxLossHarvesting: {
    harvestableAmount: 4_200,
    estimatedTaxSavings: 1_470,
    candidates: 3,
  },
};

// ─── Tax Strategy ─────────────────────────────────────────────────────
export const DEMO_TAX = {
  taxYear: 2025,
  estimatedAGI: 392_000,
  effectiveRate: 28.4,
  marginalRate: 35,
  estimatedTotalTax: 108_600,
  strategies: [
    { title: "Mega Backdoor Roth", savings: "$8,400 – $12,600", complexity: "medium" as const },
    { title: "Tax Loss Harvest Q4", savings: "$1,200 – $1,800", complexity: "low" as const },
    { title: "Donor Advised Fund", savings: "$3,500 – $5,200", complexity: "low" as const },
    { title: "RSU Timing Optimization", savings: "$2,800 – $4,100", complexity: "medium" as const },
  ],
  checklist: { completed: 6, total: 9 },
};

// ─── Budget & Forecasting ─────────────────────────────────────────────
export const DEMO_BUDGET = {
  month: "March",
  year: 2026,
  totalBudgeted: 18_500,
  totalSpent: 14_200,
  groups: [
    { group: "Food & Dining", icon: "\u{1F37D}\u{FE0F}", budget: 2_200, spent: 1_840 },
    { group: "Home & Services", icon: "\u{1F3E0}", budget: 5_800, spent: 5_800 },
    { group: "Bills & Utilities", icon: "\u{1F4A1}", budget: 950, spent: 720 },
    { group: "Family & Children", icon: "\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}\u{200D}\u{1F466}", budget: 1_800, spent: 1_200 },
    { group: "Health & Wellness", icon: "\u{1F48A}", budget: 800, spent: 450 },
    { group: "Travel & Lifestyle", icon: "\u{2708}\u{FE0F}", budget: 1_500, spent: 980 },
  ],
  forecast: { predictedTotal: 19_100, confidence: 82 },
};

// ─── Goals ────────────────────────────────────────────────────────────
export const DEMO_GOALS = [
  { name: "Emergency Fund", target: 50_000, current: 32_000, pct: 64, onTrack: true, monthly: 2_000, gradient: "from-emerald-600 to-teal-800" },
  { name: "House Down Payment", target: 150_000, current: 48_000, pct: 32, onTrack: true, monthly: 3_000, gradient: "from-blue-600 to-indigo-800" },
  { name: "Pay Off Student Loans", target: 82_000, current: 52_000, pct: 63, onTrack: false, monthly: 2_500, gradient: "from-stone-600 to-stone-800" },
  { name: "Max Tax-Advantaged", target: 30_500, current: 22_875, pct: 75, onTrack: true, monthly: 2_542, gradient: "from-amber-500 to-orange-700" },
];

// ─── Household Optimization ───────────────────────────────────────────
export const DEMO_HOUSEHOLD = {
  primary: { name: "Sarah", employer: "Tech Corp", income: 220_000 },
  spouse: { name: "Alex", employer: "MedTech Inc", income: 160_000 },
  filingStatus: "Married Filing Jointly",
  recommendations: [
    { area: "Filing Status", action: "MFJ saves $4,200 vs MFS", savings: 4_200 },
    { area: "401(k) Coordination", action: "Max both 401(k)s \u2014 $46K combined", savings: 16_100 },
    { area: "Health Insurance", action: "Use Tech Corp HDHP + HSA", savings: 3_200 },
    { area: "Childcare FSA", action: "Elect Dependent Care FSA ($5K)", savings: 1_750 },
  ],
  totalAnnualSavings: 25_250,
};

// ─── Recurring & Subscriptions ────────────────────────────────────────
export const DEMO_RECURRING = {
  totalMonthly: 2_847,
  totalAnnual: 34_164,
  count: 18,
  byCategory: [
    { category: "Housing & HOA", monthly: 4_200, count: 2, color: "#22C55E" },
    { category: "Insurance", monthly: 1_240, count: 4, color: "#3B82F6" },
    { category: "Utilities", monthly: 310, count: 2, color: "#F59E0B" },
    { category: "Fitness & Wellness", monthly: 180, count: 2, color: "#EC4899" },
    { category: "Software & AI", monthly: 95, count: 3, color: "#8B5CF6" },
    { category: "Streaming", monthly: 89, count: 5, color: "#EF4444" },
  ],
  items: [
    { name: "Mortgage", amount: 3_800, frequency: "monthly" as const },
    { name: "Auto Insurance", amount: 420, frequency: "monthly" as const },
    { name: "Equinox", amount: 120, frequency: "monthly" as const },
    { name: "Netflix", amount: 22.99, frequency: "monthly" as const },
    { name: "Claude Pro", amount: 20, frequency: "monthly" as const },
    { name: "Spotify Family", amount: 16.99, frequency: "monthly" as const },
  ],
};

// ─── Accounts / Bank Sync ─────────────────────────────────────────────
export const DEMO_ACCOUNTS = {
  totalNetWorth: 347_000,
  byType: [
    { type: "Investments", value: 285_000, accounts: 4, color: "#22C55E" },
    { type: "Checking & Savings", value: 42_000, accounts: 3, color: "#3B82F6" },
    { type: "Real Estate (equity)", value: 120_000, accounts: 1, color: "#F59E0B" },
    { type: "Liabilities", value: -100_000, accounts: 2, color: "#EF4444" },
  ],
  connections: [
    { institution: "Chase", accounts: 3, lastSynced: "2 min ago" },
    { institution: "Fidelity", accounts: 2, lastSynced: "1 hour ago" },
    { institution: "Vanguard", accounts: 2, lastSynced: "1 hour ago" },
  ],
};

// ─── AI Chat Exchanges ────────────────────────────────────────────────
export const DEMO_CHAT_EXCHANGES = [
  {
    question: "Can I afford a $1.4M house on our combined $380K income?",
    tools: ["retirement_impact", "budget_snapshot"],
    answer: "Yes \u2014 but it delays retirement from 54 to 59. Your savings rate drops from 18% to 11%, pushing your trajectory outside the confidence band. Here\u2019s the scenario comparison.",
  },
  {
    question: "My RSUs vest next month. What should I do?",
    tools: ["equity_vest_lookup", "tax_estimate"],
    answer: "Your March vest is $62K. At your 35% marginal rate, that\u2019s a $21,700 tax event \u2014 withholding only covers $13,640. Set aside $8,060. I\u2019d recommend selling on vest to reduce concentration risk.",
  },
  {
    question: "How are we doing on our goals this month?",
    tools: ["goal_progress", "budget_velocity"],
    answer: "3 of 4 goals are on track. Student loans are $800 behind \u2014 redirect the Travel budget surplus ($520) to catch up. Emergency fund hits 64% this month.",
  },
  {
    question: "Should we do MFJ or MFS this year?",
    tools: ["filing_status_compare", "household_optimization"],
    answer: "MFJ saves you $4,200 this year. MFS only makes sense for income-driven student loan repayment \u2014 at your income, that won\u2019t qualify. Stick with MFJ.",
  },
];
