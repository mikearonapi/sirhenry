// ─── Synthetic Data for Landing Page Mockups ─────────────────────────
// Single source of truth for all landing page feature showcases.
// Persona: Michael Chen (Sr. SWE, $245K) & Jessica Chen (Finance Mgr, $165K)
// — a HENRY couple, age 33/32. Side consulting LLC. One child (Ethan, 3).
// All numbers are internally consistent with the demo seeder.
// Last synced with app features: March 2026.

// ─── Dashboard ────────────────────────────────────────────────────────
export const DEMO_DASHBOARD = {
  netWorth: 395_000,
  netWorthDelta90d: 33_000,
  savingsRate: 19.5,
  targetSavingsRate: 20,
  retireByAge: 52,
  retireConfidence: 87,
  currentMonthIncome: 35_500,
  currentMonthExpenses: 24_800,
  currentMonthTaxEstimate: 5_200,
  currentMonthSavings: 5_500,
};

export const DEMO_ACTION_PLAN = [
  { name: "Max out backdoor Roth IRA", status: "done" as const, value: "+$14,000/yr" },
  { name: "Fund HSA to maximum", status: "done" as const, value: "+$8,300/yr" },
  { name: "Set up mega backdoor Roth", status: "next" as const, value: "+$22,500/yr" },
  { name: "Diversify RSU concentration", status: "pending" as const, value: "Reduce risk" },
  { name: "Max 529 for NY deduction", status: "pending" as const, value: "+$685 state tax" },
];

// ─── Retirement / Trajectory ──────────────────────────────────────────
export const DEMO_RETIREMENT = {
  fireNumber: 3_500_000,
  coastFireNumber: 920_000,
  projectedNestEgg: 3_800_000,
  earliestRetirementAge: 50,
  retirementReadinessPct: 87,
  monteCarlo: {
    p10: 2_300_000,
    p50: 3_800_000,
    p90: 5_600_000,
    runs: 10_000,
  },
  yearlyProjection: [
    { age: 33, balance: 395_000 },
    { age: 37, balance: 720_000 },
    { age: 41, balance: 1_200_000 },
    { age: 45, balance: 1_900_000 },
    { age: 49, balance: 2_800_000 },
    { age: 52, balance: 3_800_000 },
    { age: 56, balance: 4_500_000 },
    { age: 60, balance: 5_000_000 },
    { age: 64, balance: 4_800_000 },
  ],
};

// ─── Portfolio & Investments ──────────────────────────────────────────
export const DEMO_PORTFOLIO = {
  totalValue: 364_000,
  totalGainLoss: 42_500,
  totalGainLossPct: 13.2,
  allocation: [
    { name: "US Stocks", pct: 45, color: "#22C55E" },
    { name: "Int'l Stocks", pct: 18, color: "#3B82F6" },
    { name: "Bonds", pct: 14, color: "#8B5CF6" },
    { name: "REITs", pct: 8, color: "#F59E0B" },
    { name: "Crypto", pct: 5, color: "#EC4899" },
    { name: "Cash", pct: 10, color: "#6B7280" },
  ],
  topHoldings: [
    { ticker: "VTI", name: "Vanguard Total Stock", value: 108_168, gainPct: 23.8 },
    { ticker: "VGT", name: "Vanguard Info Tech", value: 46_070, gainPct: 12.9 },
    { ticker: "BND", name: "Vanguard Total Bond", value: 44_080, gainPct: 3.4 },
    { ticker: "AAPL", name: "Apple (RSU)", value: 36_414, gainPct: 28.3 },
    { ticker: "VNQ", name: "Vanguard Real Estate", value: 24_640, gainPct: 7.3 },
  ],
  taxLossHarvesting: {
    harvestableAmount: 4_800,
    estimatedTaxSavings: 1_680,
    candidates: 3,
  },
};

// ─── Tax Strategy ─────────────────────────────────────────────────────
export const DEMO_TAX = {
  taxYear: 2025,
  estimatedAGI: 452_000,
  effectiveRate: 29.4,
  marginalRate: 35,
  estimatedTotalTax: 142_200,
  strategies: [
    { title: "Mega Backdoor Roth", savings: "$9,200 – $13,800", complexity: "medium" as const },
    { title: "Tax Loss Harvest Q4", savings: "$1,400 – $2,100", complexity: "low" as const },
    { title: "Donor Advised Fund", savings: "$3,800 – $5,600", complexity: "low" as const },
    { title: "RSU Timing Optimization", savings: "$3,000 – $4,500", complexity: "medium" as const },
    { title: "529 NY State Deduction", savings: "$685", complexity: "low" as const },
  ],
  checklist: { completed: 6, total: 10 },
};

// ─── Budget & Forecasting ─────────────────────────────────────────────
export const DEMO_BUDGET = {
  month: "March",
  year: 2026,
  totalBudgeted: 20_000,
  totalSpent: 15_800,
  groups: [
    { group: "Food & Dining", icon: "\u{1F37D}\u{FE0F}", budget: 2_500, spent: 2_050 },
    { group: "Home & Services", icon: "\u{1F3E0}", budget: 5_500, spent: 5_500 },
    { group: "Bills & Utilities", icon: "\u{1F4A1}", budget: 1_075, spent: 820 },
    { group: "Family & Children", icon: "\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}\u{200D}\u{1F466}", budget: 2_520, spent: 1_800 },
    { group: "Health & Wellness", icon: "\u{1F48A}", budget: 850, spent: 520 },
    { group: "Travel & Lifestyle", icon: "\u{2708}\u{FE0F}", budget: 1_500, spent: 1_100 },
  ],
  forecast: { predictedTotal: 20_400, confidence: 84 },
};

// ─── Goals ────────────────────────────────────────────────────────────
export const DEMO_GOALS = [
  { name: "Emergency Fund", target: 60_000, current: 38_000, pct: 63, onTrack: true, monthly: 2_000, gradient: "from-emerald-600 to-teal-800" },
  { name: "Pay Off Student Loans", target: 76_000, current: 52_000, pct: 68, onTrack: true, monthly: 2_500, gradient: "from-indigo-600 to-violet-800" },
  { name: "Max Tax-Advantaged", target: 55_300, current: 41_500, pct: 75, onTrack: true, monthly: 4_608, gradient: "from-amber-500 to-orange-700" },
  { name: "Sabbatical Fund", target: 80_000, current: 22_000, pct: 28, onTrack: false, monthly: 1_500, gradient: "from-blue-600 to-sky-800" },
];

// ─── Household Optimization ───────────────────────────────────────────
export const DEMO_HOUSEHOLD = {
  primary: { name: "Michael", employer: "Meridian Technologies", income: 245_000 },
  spouse: { name: "Jessica", employer: "BlackRock", income: 165_000 },
  filingStatus: "Married Filing Jointly",
  recommendations: [
    { area: "Filing Status", action: "MFJ saves $5,200 vs MFS", savings: 5_200 },
    { area: "401(k) Coordination", action: "Max both 401(k)s \u2014 $47K combined", savings: 16_450 },
    { area: "Health Insurance", action: "Use Meridian HDHP + HSA ($8,300)", savings: 3_200 },
    { area: "Childcare FSA", action: "Elect Dependent Care FSA ($5K)", savings: 1_750 },
    { area: "529 NY Deduction", action: "Contribute $10K to NY 529", savings: 685 },
    { area: "Mega Backdoor Roth", action: "After-tax 401(k) \u2192 Roth conversion", savings: 2_365 },
  ],
  totalAnnualSavings: 29_650,
};

// ─── Recurring & Subscriptions ────────────────────────────────────────
export const DEMO_RECURRING = {
  totalMonthly: 7_350,
  totalAnnual: 88_200,
  count: 19,
  byCategory: [
    { category: "Housing & HOA", monthly: 5_075, count: 3, color: "#22C55E" },
    { category: "Insurance", monthly: 660, count: 4, color: "#3B82F6" },
    { category: "Utilities", monthly: 415, count: 3, color: "#F59E0B" },
    { category: "Fitness & Wellness", monthly: 164, count: 2, color: "#EC4899" },
    { category: "Software & AI", monthly: 25, count: 2, color: "#8B5CF6" },
    { category: "Streaming", monthly: 110, count: 5, color: "#EF4444" },
  ],
  items: [
    { name: "Mortgage", amount: 3_800, frequency: "monthly" as const },
    { name: "Property Tax Escrow", amount: 850, frequency: "monthly" as const },
    { name: "HOA Dues", amount: 425, frequency: "monthly" as const },
    { name: "Auto Insurance", amount: 380, frequency: "monthly" as const },
    { name: "Equinox", amount: 120, frequency: "monthly" as const },
    { name: "Netflix", amount: 22.99, frequency: "monthly" as const },
    { name: "Claude Pro", amount: 20, frequency: "monthly" as const },
  ],
};

// ─── Accounts / Bank Sync ─────────────────────────────────────────────
export const DEMO_ACCOUNTS = {
  totalNetWorth: 395_000,
  byType: [
    { type: "Investments", value: 364_000, accounts: 6, color: "#22C55E" },
    { type: "Checking & Savings", value: 68_000, accounts: 3, color: "#3B82F6" },
    { type: "Real Estate (equity)", value: 188_000, accounts: 1, color: "#F59E0B" },
    { type: "Crypto", value: 41_000, accounts: 1, color: "#EC4899" },
    { type: "Liabilities", value: -266_000, accounts: 3, color: "#EF4444" },
  ],
  connections: [
    { institution: "Chase", accounts: 4, lastSynced: "2 min ago" },
    { institution: "Fidelity", accounts: 2, lastSynced: "1 hour ago" },
    { institution: "Vanguard", accounts: 2, lastSynced: "1 hour ago" },
    { institution: "Schwab", accounts: 1, lastSynced: "1 hour ago" },
    { institution: "Coinbase", accounts: 1, lastSynced: "3 hours ago" },
  ],
};

// ─── AI Chat Exchanges ────────────────────────────────────────────────
export const DEMO_CHAT_EXCHANGES = [
  {
    question: "Can I afford a $1.2M house on our combined $410K income?",
    tools: ["retirement_impact", "budget_snapshot"],
    answer: "Yes \u2014 but it delays retirement from 52 to 57. Your savings rate drops from 19.5% to 6%, pushing your trajectory outside the confidence band. Here\u2019s the scenario comparison.",
  },
  {
    question: "My RSUs vest next month. What should I do?",
    tools: ["equity_vest_lookup", "tax_estimate"],
    answer: "Your March vest is 38 shares at ~$220.69. At your 35% marginal rate, that\u2019s $2,935 in taxes \u2014 withholding only covers $1,845. Set aside $1,090. I\u2019d recommend selling on vest to reduce concentration risk.",
  },
  {
    question: "How are we doing on our goals this month?",
    tools: ["goal_progress", "budget_velocity"],
    answer: "3 of 4 goals are on track. Sabbatical fund is behind \u2014 you need $1,500/mo but only saved $800 this month. Consider redirecting the Travel budget surplus ($400) to catch up.",
  },
  {
    question: "Should we file MFJ or MFS this year?",
    tools: ["filing_status_compare", "household_optimization"],
    answer: "MFJ saves you $5,200 this year. MFS only makes sense for income-driven student loan repayment \u2014 at your income, that won\u2019t qualify. Your consulting Schedule C income makes MFJ even more beneficial. Stick with MFJ.",
  },
];
