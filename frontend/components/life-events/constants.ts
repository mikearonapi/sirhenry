// ---------------------------------------------------------------------------
// Life Events — Shared constants and configuration
// ---------------------------------------------------------------------------

export interface EventTypeConfig {
  value: string;
  label: string;
  color: string;
  icon: string;
  subtypes: string[];
}

export const EVENT_TYPES: EventTypeConfig[] = [
  { value: "real_estate", label: "Real Estate", color: "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400", icon: "🏠",
    subtypes: ["purchase", "sale", "rental", "refinance"] },
  { value: "vehicle", label: "Vehicle", color: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-400", icon: "🚗",
    subtypes: ["purchase", "sale"] },
  { value: "family", label: "Family", color: "bg-pink-100 text-pink-700 dark:bg-pink-950/40 dark:text-pink-400", icon: "👨‍👩‍👧",
    subtypes: ["birth", "adoption", "marriage", "divorce", "dependent_change"] },
  { value: "employment", label: "Employment", color: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400", icon: "💼",
    subtypes: ["job_change", "layoff", "promotion", "start_business", "retirement"] },
  { value: "medical", label: "Major Medical", color: "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400", icon: "🏥",
    subtypes: ["major", "disability", "chronic_diagnosis"] },
  { value: "education", label: "Education", color: "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400", icon: "🎓",
    subtypes: ["college", "529_open", "tuition_payment", "student_loan"] },
  { value: "estate", label: "Estate & Gift", color: "bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400", icon: "📜",
    subtypes: ["inheritance", "gift", "will_update", "trust_creation"] },
  { value: "business", label: "Business", color: "bg-orange-100 text-orange-700 dark:bg-orange-950/40 dark:text-orange-400", icon: "🏢",
    subtypes: ["asset_sale", "equity_sale", "entity_formation", "acquisition"] },
];

export const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400",
  upcoming: "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
  needs_documentation: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400",
};

export const STATUS_LABELS: Record<string, string> = {
  completed: "Completed",
  upcoming: "Upcoming",
  needs_documentation: "Needs Docs",
};

// Structured financial amount fields per event type:subtype
export const AMOUNT_FIELDS: Record<string, { key: string; label: string; placeholder: string }[]> = {
  "real_estate:purchase": [
    { key: "purchase_price", label: "Purchase Price", placeholder: "e.g. 500000" },
    { key: "down_payment", label: "Down Payment", placeholder: "e.g. 100000" },
    { key: "loan_amount", label: "Loan Amount", placeholder: "e.g. 400000" },
    { key: "closing_costs", label: "Closing Costs", placeholder: "e.g. 8000" },
  ],
  "real_estate:sale": [
    { key: "sale_price", label: "Sale Price", placeholder: "e.g. 600000" },
    { key: "original_cost", label: "Original Purchase Price", placeholder: "e.g. 400000" },
    { key: "capital_gain", label: "Capital Gain (estimated)", placeholder: "e.g. 200000" },
  ],
  "real_estate:refinance": [
    { key: "new_rate", label: "New Interest Rate (%)", placeholder: "e.g. 6.5" },
    { key: "cash_out", label: "Cash-Out Amount", placeholder: "0 if rate-and-term" },
    { key: "closing_costs", label: "Closing Costs", placeholder: "e.g. 5000" },
  ],
  "real_estate:rental": [
    { key: "monthly_rent", label: "Monthly Rent Income", placeholder: "e.g. 2500" },
    { key: "purchase_price", label: "Property Value", placeholder: "e.g. 350000" },
  ],
  "vehicle:purchase": [
    { key: "purchase_price", label: "Purchase Price", placeholder: "e.g. 45000" },
    { key: "loan_amount", label: "Loan Amount", placeholder: "e.g. 35000" },
    { key: "trade_in_value", label: "Trade-In Value", placeholder: "Optional" },
  ],
  "vehicle:sale": [
    { key: "sale_price", label: "Sale Price", placeholder: "e.g. 20000" },
    { key: "original_cost", label: "Original Purchase Price", placeholder: "e.g. 35000" },
  ],
  "employment:job_change": [
    { key: "new_annual_salary", label: "New Annual Salary", placeholder: "e.g. 150000" },
    { key: "old_annual_salary", label: "Previous Annual Salary", placeholder: "Optional" },
    { key: "signing_bonus", label: "Signing Bonus", placeholder: "Optional" },
  ],
  "employment:start_business": [
    { key: "startup_costs", label: "Startup / Formation Costs", placeholder: "e.g. 10000" },
    { key: "initial_investment", label: "Initial Capital Investment", placeholder: "Optional" },
  ],
  "employment:retirement": [
    { key: "final_salary", label: "Final Annual Salary", placeholder: "Optional" },
    { key: "pension_annual", label: "Annual Pension Income", placeholder: "Optional" },
  ],
  "medical:major": [
    { key: "total_cost", label: "Total Medical Cost", placeholder: "e.g. 25000" },
    { key: "insurance_paid", label: "Insurance Paid", placeholder: "e.g. 20000" },
    { key: "out_of_pocket", label: "Your Out-of-Pocket", placeholder: "e.g. 5000" },
  ],
  "education:college": [
    { key: "annual_tuition", label: "Annual Tuition", placeholder: "e.g. 55000" },
    { key: "scholarship_amount", label: "Scholarship / Aid", placeholder: "Optional" },
    { key: "529_withdrawal", label: "529 Withdrawal Used", placeholder: "Optional" },
  ],
  "education:529_open": [
    { key: "initial_contribution", label: "Initial Contribution", placeholder: "e.g. 5000" },
  ],
  "education:student_loan": [
    { key: "loan_amount", label: "Total Loan Amount", placeholder: "e.g. 30000" },
    { key: "interest_rate", label: "Interest Rate (%)", placeholder: "e.g. 5.5" },
  ],
  "estate:inheritance": [
    { key: "amount_received", label: "Cash Received", placeholder: "e.g. 100000" },
    { key: "fmv_of_assets", label: "FMV of Non-Cash Assets", placeholder: "Optional" },
  ],
  "estate:gift": [
    { key: "gift_amount", label: "Gift Amount", placeholder: "e.g. 18000" },
  ],
  "business:asset_sale": [
    { key: "sale_price", label: "Sale Price", placeholder: "e.g. 500000" },
    { key: "cost_basis", label: "Cost Basis", placeholder: "e.g. 200000" },
  ],
  "business:equity_sale": [
    { key: "sale_price", label: "Sale Price", placeholder: "e.g. 1000000" },
    { key: "cost_basis", label: "Cost Basis / Strike Price", placeholder: "e.g. 100000" },
  ],
  "business:entity_formation": [
    { key: "startup_costs", label: "Formation / Legal Costs", placeholder: "e.g. 2500" },
  ],
};

export interface CascadeSuggestion {
  section: "tax" | "insurance" | "goals" | "reminders";
  label: string;
  detail: string;
  href: string;
}

export const SECTION_COLORS: Record<string, string> = {
  tax: "bg-red-50 border-red-100 text-red-700",
  insurance: "bg-blue-50 border-blue-100 text-blue-700",
  goals: "bg-green-50 border-green-100 text-green-700",
  reminders: "bg-purple-50 border-purple-100 text-purple-700",
};

export const SECTION_LABELS: Record<string, string> = {
  tax: "Tax",
  insurance: "Policies",
  goals: "Goals",
  reminders: "Reminders",
};

export const CASCADE_MAP: Record<string, CascadeSuggestion[]> = {
  "real_estate:purchase": [
    { section: "tax", label: "Mortgage interest deduction", detail: "Log your mortgage interest paid (Form 1098) — deductible if you itemize.", href: "/tax-strategy" },
    { section: "tax", label: "Property tax deduction", detail: "Add property taxes paid to your itemized deductions (up to $10k SALT cap).", href: "/tax-strategy" },
    { section: "insurance", label: "Homeowner's insurance required", detail: "Add a Home policy to your Policies page — required by lenders.", href: "/insurance" },
    { section: "goals", label: "Mortgage payoff goal", detail: "Create a goal to track extra payments and projected payoff date.", href: "/goals" },
    { section: "reminders", label: "Annual property tax deadline", detail: "Set a reminder for property tax due dates in your state.", href: "/admin" },
  ],
  "real_estate:sale": [
    { section: "tax", label: "Capital gains exclusion ($250k/$500k)", detail: "If primary residence held 2+ years, up to $500k gain is excluded. Verify eligibility in Tax Strategy.", href: "/tax-strategy" },
    { section: "tax", label: "Depreciation recapture (if rental)", detail: "If property was ever rented, depreciation taken must be recaptured at ordinary rates.", href: "/tax-strategy" },
    { section: "reminders", label: "File amended return if needed", detail: "Review if your sale creates estimated tax liability requiring a quarterly payment.", href: "/admin" },
  ],
  "real_estate:refinance": [
    { section: "tax", label: "Points deductible over loan life", detail: "Refinance points are amortized over the loan term, not deducted all at once.", href: "/tax-strategy" },
    { section: "goals", label: "Recalculate payoff timeline", detail: "Update your mortgage payoff goal with the new rate and payment.", href: "/goals" },
  ],
  "real_estate:rental": [
    { section: "tax", label: "Rental income is taxable", detail: "Report rental income on Schedule E. Track depreciation, repairs, and management fees.", href: "/tax-strategy" },
    { section: "insurance", label: "Landlord / rental property insurance", detail: "Standard homeowner's doesn't cover tenants. Add a landlord policy.", href: "/insurance" },
  ],
  "vehicle:purchase": [
    { section: "tax", label: "Sales tax deduction (if itemizing)", detail: "Vehicle sales tax can be added to your state & local tax deduction.", href: "/tax-strategy" },
    { section: "tax", label: "Business use deduction", detail: "If vehicle is used for business, track mileage or actual expenses for Schedule C.", href: "/tax-strategy" },
    { section: "insurance", label: "Auto insurance required", detail: "Add auto policy to your Policies page with coverage amounts and renewal date.", href: "/insurance" },
    { section: "goals", label: "Car loan payoff goal", detail: "Track extra payments toward your auto loan to save on interest.", href: "/goals" },
  ],
  "vehicle:sale": [
    { section: "tax", label: "Loss on personal vehicle is not deductible", detail: "Capital losses on personal-use vehicles cannot be deducted. Business vehicles are different.", href: "/tax-strategy" },
    { section: "insurance", label: "Remove or update auto policy", detail: "Update your auto insurance policy in Policies — remove old vehicle.", href: "/insurance" },
  ],
  "family:birth": [
    { section: "tax", label: "New dependent — update W-4", detail: "Adding a dependent reduces your withholding. File a new W-4 with your employer.", href: "/household" },
    { section: "tax", label: "Child tax credit ($2,000/child)", detail: "Claim the child tax credit on your return. Review in Tax Strategy.", href: "/tax-strategy" },
    { section: "tax", label: "Dependent care FSA or credit", detail: "Childcare expenses may qualify for a $3,000–$6,000 dependent care credit or FSA.", href: "/tax-strategy" },
    { section: "insurance", label: "Add child to health insurance", detail: "Enroll child within 30 days of birth (qualifying life event). Update Policies.", href: "/insurance" },
    { section: "insurance", label: "Increase life insurance coverage", detail: "Review life insurance coverage — a new dependent increases your needs.", href: "/insurance" },
    { section: "goals", label: "Open 529 college savings account", detail: "Start saving early — compound growth over 18 years is significant.", href: "/goals" },
    { section: "reminders", label: "Annual gifting to 529", detail: "Set a reminder to fund the 529 each year — up to $19,000/year per beneficiary.", href: "/admin" },
  ],
  "family:adoption": [
    { section: "tax", label: "Adoption tax credit (up to $16,810)", detail: "Federal adoption credit covers qualified adoption expenses. Review in Tax Strategy.", href: "/tax-strategy" },
    { section: "insurance", label: "Add child to health insurance", detail: "Adoption is a qualifying life event — enroll within 30 days.", href: "/insurance" },
  ],
  "family:marriage": [
    { section: "tax", label: "Update filing status to MFJ or MFS", detail: "Review married filing jointly vs. separately to find the optimal strategy.", href: "/household" },
    { section: "tax", label: "Update beneficiaries and W-4", detail: "File new W-4s reflecting married status. Review withholding with combined income.", href: "/household" },
    { section: "insurance", label: "Consolidate insurance policies", detail: "Combine or update health, auto, home, and life policies. Review Policies page.", href: "/insurance" },
    { section: "goals", label: "Set joint financial goals", detail: "Create shared goals for home purchase, retirement, and emergency fund.", href: "/goals" },
  ],
  "family:divorce": [
    { section: "tax", label: "Filing status changes to Single/HoH", detail: "Review head of household eligibility and update withholding (W-4).", href: "/household" },
    { section: "tax", label: "Alimony tax treatment (post-2018)", detail: "Post-2018 divorce: alimony is not deductible for payer, not taxable for recipient.", href: "/tax-strategy" },
    { section: "insurance", label: "Update beneficiaries immediately", detail: "Remove ex-spouse from life, retirement, and other policy beneficiaries.", href: "/insurance" },
  ],
  "family:dependent_change": [
    { section: "tax", label: "Update dependency exemption", detail: "Custody changes affect who claims the child. Review in Tax Strategy.", href: "/tax-strategy" },
    { section: "tax", label: "File new W-4", detail: "Adjust withholding in Household → Tax Coordination after dependent change.", href: "/household" },
  ],
  "employment:job_change": [
    { section: "tax", label: "File new W-4 with new employer", detail: "Update withholding based on new salary — review in Household → Tax Coordination.", href: "/household" },
    { section: "tax", label: "Roll over old 401k", detail: "Roll over employer retirement account to IRA or new employer plan within 60 days.", href: "/tax-strategy" },
    { section: "insurance", label: "COBRA or new health coverage", detail: "Enroll in new employer health plan within 30 days. Update Policies page.", href: "/insurance" },
    { section: "reminders", label: "Benefits enrollment deadline", detail: "New employer open enrollment window is typically 30 days from start date.", href: "/admin" },
    { section: "goals", label: "Update retirement contribution rate", detail: "Maximize new employer's 401k match immediately.", href: "/goals" },
  ],
  "employment:layoff": [
    { section: "tax", label: "Severance and unemployment are taxable", detail: "Withhold taxes on severance; unemployment benefits are taxable federal income.", href: "/tax-strategy" },
    { section: "insurance", label: "COBRA continuation coverage", detail: "Elect COBRA within 60 days. Add to Policies page with renewal date.", href: "/insurance" },
    { section: "reminders", label: "COBRA deadline — 60 days", detail: "Set a reminder: COBRA must be elected within 60 days of coverage loss.", href: "/admin" },
    { section: "goals", label: "Emergency fund drawdown plan", detail: "Review your emergency fund goal and runway in Goals.", href: "/goals" },
  ],
  "employment:start_business": [
    { section: "tax", label: "Schedule C or S-Corp return", detail: "Business income is reported on Schedule C. Consider S-Corp election at $40k+ profit.", href: "/tax-strategy" },
    { section: "tax", label: "QBI deduction up to 20%", detail: "Qualified Business Income deduction can reduce effective tax rate significantly.", href: "/tax-strategy" },
    { section: "tax", label: "Self-employment tax (15.3%)", detail: "Pay quarterly estimated taxes to avoid underpayment penalty.", href: "/tax-strategy" },
    { section: "tax", label: "Home office deduction", detail: "Dedicated workspace qualifies — track square footage and home expenses.", href: "/tax-strategy" },
    { section: "insurance", label: "Business liability insurance", detail: "Add business liability / E&O policy to Policies page.", href: "/insurance" },
    { section: "reminders", label: "Quarterly estimated tax payments", detail: "Q1: Apr 15 | Q2: Jun 15 | Q3: Sep 15 | Q4: Jan 15. Set reminders.", href: "/admin" },
  ],
  "employment:retirement": [
    { section: "tax", label: "RMD planning (age 73+)", detail: "Required minimum distributions start at 73. Plan withdrawals to minimize tax bracket impact.", href: "/tax-strategy" },
    { section: "tax", label: "Social Security timing strategy", detail: "Delaying SS to 70 increases benefit by 8%/year. Review in Tax Strategy.", href: "/tax-strategy" },
    { section: "insurance", label: "Medicare enrollment — age 65", detail: "Enroll in Medicare within 3 months of 65th birthday to avoid penalties.", href: "/insurance" },
  ],
  "medical:major": [
    { section: "tax", label: "Medical expense deduction (7.5% AGI threshold)", detail: "Unreimbursed medical expenses exceeding 7.5% of AGI are deductible if itemizing.", href: "/tax-strategy" },
    { section: "insurance", label: "Review disability coverage adequacy", detail: "Major medical events highlight disability risk. Review coverage in Policies.", href: "/insurance" },
    { section: "reminders", label: "FSA/HSA deadline to claim expenses", detail: "FSA grace period or runout period varies by plan. File claims before deadline.", href: "/admin" },
  ],
  "medical:disability": [
    { section: "tax", label: "Disability payments may be taxable", detail: "If employer paid premiums, benefits are taxable. If you paid, they may not be.", href: "/tax-strategy" },
    { section: "insurance", label: "Long-term disability coverage review", detail: "Review LTD benefit amount and elimination period in Policies.", href: "/insurance" },
  ],
  "education:college": [
    { section: "tax", label: "American Opportunity / Lifetime Learning Credit", detail: "Up to $2,500 AOTC per student for first 4 years, or Lifetime Learning Credit.", href: "/tax-strategy" },
    { section: "tax", label: "529 withdrawals — qualified expenses only", detail: "Only tuition, fees, and room/board are qualified. Track in Import.", href: "/tax-strategy" },
    { section: "goals", label: "Track 529 balance vs. remaining tuition", detail: "Update your college savings goal with years remaining and annual cost.", href: "/goals" },
  ],
  "education:529_open": [
    { section: "tax", label: "State income tax deduction (varies)", detail: "Many states offer deductions for 529 contributions. Check your state.", href: "/tax-strategy" },
    { section: "reminders", label: "Annual 529 contribution reminder", detail: "Set annual reminder to fund 529 — up to $19,000/year per beneficiary tax-free.", href: "/admin" },
    { section: "goals", label: "Set college savings goal", detail: "Create a goal tracking 529 balance vs. estimated college cost.", href: "/goals" },
  ],
  "estate:inheritance": [
    { section: "tax", label: "Stepped-up cost basis on inherited assets", detail: "Inherited investments get a new cost basis at date of death — reduces capital gains.", href: "/tax-strategy" },
    { section: "tax", label: "Inherited IRAs — 10-year distribution rule", detail: "Non-spouse beneficiaries must empty inherited IRAs within 10 years.", href: "/tax-strategy" },
    { section: "goals", label: "Update net worth and goals", detail: "Add inherited assets to Accounts and revise financial goals accordingly.", href: "/goals" },
  ],
  "estate:gift": [
    { section: "tax", label: "Annual exclusion — $19,000/person in 2025", detail: "Gifts up to $19,000 per recipient are excluded from gift tax reporting.", href: "/tax-strategy" },
    { section: "tax", label: "File Form 709 if over annual exclusion", detail: "Gifts over $19,000 to one person require Form 709 — reduces lifetime exemption.", href: "/tax-strategy" },
  ],
  "estate:will_update": [
    { section: "insurance", label: "Update beneficiary designations", detail: "Beneficiaries on life insurance and retirement accounts override your will. Review Policies.", href: "/insurance" },
    { section: "reminders", label: "Annual estate plan review", detail: "Set an annual reminder to review will, POA, and beneficiaries.", href: "/admin" },
  ],
  "business:equity_sale": [
    { section: "tax", label: "Long-term vs. short-term capital gains", detail: "Equity held 1+ year qualifies for preferential long-term rates (0/15/20%). Check holding period.", href: "/tax-strategy" },
    { section: "tax", label: "QSBS exclusion (Section 1202)", detail: "Qualified small business stock may be eligible for up to 100% capital gain exclusion.", href: "/tax-strategy" },
    { section: "reminders", label: "Estimated tax payment on proceeds", detail: "Large capital gain events may require immediate estimated tax payment.", href: "/admin" },
  ],
  "business:entity_formation": [
    { section: "tax", label: "Entity structure impacts self-employment tax", detail: "LLC → Schedule C. S-Corp → payroll + distributions. Choose based on net income.", href: "/tax-strategy" },
    { section: "insurance", label: "Business liability / E&O insurance", detail: "Add business insurance policy to Policies page.", href: "/insurance" },
    { section: "reminders", label: "Quarterly estimated tax payments", detail: "Set up quarterly payment reminders starting with next due date.", href: "/admin" },
  ],
  "business:asset_sale": [
    { section: "tax", label: "Section 1231 gain treatment", detail: "Business asset sales may qualify as Section 1231 gains — taxed at capital rates with recapture rules.", href: "/tax-strategy" },
    { section: "tax", label: "Installment sale option", detail: "Spreading payments over multiple years can reduce your annual tax burden.", href: "/tax-strategy" },
  ],
};

// ── Helper functions ────────────────────────────────────────────────────────

export function getAmountFields(type: string, subtype: string) {
  return AMOUNT_FIELDS[`${type}:${subtype}`] || [];
}

export function getCascadeSuggestions(type: string, subtype: string): CascadeSuggestion[] {
  const key = subtype ? `${type}:${subtype}` : type;
  return CASCADE_MAP[key] || CASCADE_MAP[type] || [];
}

export function getEventConfig(type: string): EventTypeConfig {
  return EVENT_TYPES.find((e) => e.value === type) || {
    value: type, label: type, color: "bg-stone-100 text-stone-600", icon: "📌", subtypes: [],
  };
}

export function parseAmounts(json: string | null): Record<string, string> {
  try { return json ? JSON.parse(json) : {}; } catch { return {}; }
}
