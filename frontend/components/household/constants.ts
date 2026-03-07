import {
  Users, Briefcase, Calculator, Shield, TrendingUp,
} from "lucide-react";
import type { OtherIncomeType, FamilyMemberIn } from "@/types/api";

export const FILING_OPTIONS = [
  { value: "mfj", label: "Married Filing Jointly" },
  { value: "mfs", label: "Married Filing Separately" },
  { value: "single", label: "Single" },
  { value: "hoh", label: "Head of Household" },
];

export const ESTATE_STATUS_OPTIONS = [
  { value: "", label: "— Not set —" },
  { value: "none", label: "None / Not started" },
  { value: "draft", label: "Draft in progress" },
  { value: "complete", label: "Complete" },
];

export const ESTATE_STATUS_BADGE: Record<string, string> = {
  none: "bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400",
  draft: "bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400",
  complete: "bg-green-50 text-green-600 dark:bg-green-950/30 dark:text-green-400",
};

export const PAY_PERIODS = [
  { value: 52, label: "Weekly (52/yr)" },
  { value: 26, label: "Bi-weekly (26/yr)" },
  { value: 24, label: "Semi-monthly (24/yr)" },
  { value: 12, label: "Monthly (12/yr)" },
];

export const TABS = [
  {
    id: "profile", label: "Profile", icon: Users,
    subtitle: "Your household's legal and tax identity",
    connects: "Feeds filing status and income to Tax Strategy, W-4 optimization, and all personalized recommendations.",
  },
  {
    id: "benefits", label: "Benefits", icon: Briefcase,
    subtitle: "Employer-provided financial tools and plan comparison",
    connects: "Drives 401k/HSA contribution limits shown in Tax Strategy and helps optimize tax-advantaged account prioritization.",
  },
  {
    id: "tax", label: "Tax Coordination", icon: Calculator,
    subtitle: "Optimize withholding and multi-state filing",
    connects: "W-4 changes affect paycheck withholding. Filing status comparison feeds directly into Tax Strategy projections.",
  },
  {
    id: "insurance", label: "Benefits Insurance", icon: Shield,
    subtitle: "Employer health, dental, and vision coverage gap analysis",
    connects: "Analyzes employer-provided coverage against your household's needs. For personal policies (life, auto, home), see Policies.",
  },
  {
    id: "wealth", label: "Wealth Coordination", icon: TrendingUp,
    subtitle: "Financial Order of Operations and estate planning status",
    connects: "Prioritization steps guide Goals and Portfolio decisions. Estate planning status connects to beneficiary management in Policies.",
  },
];

export const FOO_STEPS = [
  { step: 1, label: "401k to employer match", description: "Free money — capture 100% of employer match first", key: "match" },
  { step: 2, label: "HSA (if on HDHP)", description: "Triple tax advantage: pre-tax, tax-free growth, tax-free withdrawals for medical", key: "hsa" },
  { step: 3, label: "Emergency fund (3–6 months)", description: "Before investing beyond the match", key: "emergency" },
  { step: 4, label: "Roth IRA (if income eligible)", description: "$7,000/person in 2025. Use Backdoor Roth if over income limit", key: "roth" },
  { step: 5, label: "Max 401k ($23,500/person)", description: "Pre-tax or Roth — reduces taxable income significantly", key: "401k_max" },
  { step: 6, label: "Mega Backdoor Roth (if available)", description: "After-tax 401k → in-plan Roth conversion, up to $46,000 additional", key: "mega_backdoor" },
  { step: 7, label: "529 for dependents", description: "Tax-free college savings, $18,000/yr gift-tax-free per beneficiary", key: "529" },
  { step: 8, label: "Taxable brokerage", description: "After all tax-advantaged accounts are maxed", key: "taxable" },
];

export const RECIPROCITY_PAIRS: [string, string][] = [
  ["AZ","CA"],["AZ","IN"],["AZ","OR"],["AZ","VA"],
  ["DC","MD"],["DC","VA"],
  ["IL","IA"],["IL","KY"],["IL","MI"],["IL","WI"],
  ["IN","KY"],["IN","MI"],["IN","OH"],["IN","PA"],["IN","WI"],
  ["KY","MI"],["KY","OH"],["KY","VA"],["KY","WV"],["KY","WI"],
  ["MD","PA"],["MD","VA"],["MD","WV"],
  ["MI","MN"],["MI","OH"],["MI","WI"],
  ["MN","ND"],["MT","ND"],
  ["NJ","PA"],
  ["OH","PA"],["OH","WV"],
  ["PA","VA"],["PA","WV"],
  ["VA","WV"],
];

export function hasReciprocity(a: string, b: string): boolean {
  const ua = a.toUpperCase();
  const ub = b.toUpperCase();
  return RECIPROCITY_PAIRS.some(([x, y]) => (x === ua && y === ub) || (x === ub && y === ua));
}

export interface PlanOption {
  id: string;
  name: string;
  type: "hdhp" | "ppo" | "hmo";
  premium_monthly: number;
  deductible: number;
  oop_max: number;
  hsa_eligible: boolean;
  employer_hsa_contribution: number;
}

export const UTILIZATION_SCENARIOS = [
  { label: "Low", value: 500, desc: "Healthy year, minimal care" },
  { label: "Medium", value: 3_000, desc: "A few visits, minor procedure" },
  { label: "High", value: 8_000, desc: "Significant care or surgery" },
];

// TODO: These contribution limits should be fetched from the backend
// `/tax/constants` endpoint to stay in sync with pipeline/tax/constants.py
// and automatically update for future tax years.
export const LIMITS_2025 = {
  k401: 23_500,
  k401_catchup: 31_000,
  k401_total: 70_000,
  hsa_self: 4_300,
  hsa_family: 8_550,
  hsa_catchup: 5_300,
  fsa: 3_300,
  dep_care_fsa: 5_000,
  roth_ira: 7_000,
  roth_ira_catchup: 8_000,
  gift_tax_exclusion: 18_000,
};

export const MARGINAL_RATE_EST = 0.28;

export function calcPlanCost(plan: PlanOption, utilization: number): number {
  const annualPremium = plan.premium_monthly * 12;
  const oop = Math.min(utilization, plan.deductible)
    + Math.max(0, Math.min(utilization - plan.deductible, plan.oop_max - plan.deductible) * 0.2);
  const rawCost = annualPremium + oop;
  if (!plan.hsa_eligible) return rawCost;
  const employeeHsa = Math.max(0, LIMITS_2025.hsa_family - plan.employer_hsa_contribution);
  return rawCost - employeeHsa * MARGINAL_RATE_EST;
}

export const OTHER_INCOME_TYPES: { value: OtherIncomeType; label: string; hint: string }[] = [
  { value: "trust_k1",       label: "Family Trust K-1 (Form 1041)",  hint: "Distributions from a family/estate trust. No SE tax. Report on Sch E." },
  { value: "partnership_k1", label: "Partnership K-1 (Form 1065)",   hint: "Income from a partnership (LP, LLC taxed as partnership). SE tax applies to general partners / active members. Report on Sch E." },
  { value: "scorp_k1",       label: "S-Corp K-1 (Form 1120-S)",      hint: "Distributions/income from an S-corp. SE tax generally does NOT apply to K-1 distributions (only to W-2 salary from the S-corp). Report on Sch E." },
  { value: "rental",         label: "Rental Income (Sch E)",         hint: "Net rental income from investment properties. No SE tax. May be subject to NIIT if passive." },
  { value: "dividends_1099", label: "1099-DIV / Interest",           hint: "Brokerage dividends and interest not on a W-2. Qualified dividends taxed at capital gains rates." },
  { value: "business_1099",  label: "1099-NEC / Self-employment",    hint: "Consulting, freelance, or side income. SE tax of 15.3% applies. Report on Sch C." },
  { value: "alimony",        label: "Alimony Received",              hint: "Alimony taxable under pre-2019 divorce decrees only." },
  { value: "social_security", label: "Social Security",              hint: "SS benefits (up to 85% may be taxable depending on combined income)." },
  { value: "pension",        label: "Pension / Annuity",             hint: "Taxable pension or annuity distributions (1099-R)." },
  { value: "other",          label: "Other Non-W2 Income",           hint: "Any other income not captured above. No withholding — plan for estimated taxes." },
];

export const RELATIONSHIP_OPTIONS = [
  { value: "self",             label: "Me (Self)" },
  { value: "spouse",           label: "Spouse / Partner" },
  { value: "child",            label: "Child" },
  { value: "other_dependent",  label: "Other Dependent" },
  { value: "parent",           label: "Parent" },
  { value: "other",            label: "Other" },
];

export const REL_ICON: Record<string, string> = {
  self: "👤", spouse: "👤", child: "🧒", other_dependent: "👥", parent: "👴", other: "👥",
};

export const REL_COLOR: Record<string, string> = {
  self:            "bg-accent/10 border-accent/20",
  spouse:          "bg-blue-50 border-blue-100 dark:bg-blue-950/20 dark:border-blue-900",
  child:           "bg-green-50 border-green-100 dark:bg-green-950/20 dark:border-green-900",
  other_dependent: "bg-purple-50 border-purple-100 dark:bg-purple-950/20 dark:border-purple-900",
  parent:          "bg-amber-50 border-amber-100 dark:bg-amber-950/20 dark:border-amber-900",
  other:           "bg-surface border-border",
};

export const MILESTONE_CATEGORY_COLOR: Record<string, string> = {
  retirement: "bg-purple-50 text-purple-700 border-purple-100 dark:bg-purple-950/30 dark:text-purple-400 dark:border-purple-900",
  healthcare:  "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-950/30 dark:text-blue-400 dark:border-blue-900",
  education:   "bg-green-50 text-green-700 border-green-100 dark:bg-green-950/30 dark:text-green-400 dark:border-green-900",
  insurance:   "bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-900",
  tax:         "bg-red-50 text-red-700 border-red-100 dark:bg-red-950/30 dark:text-red-400 dark:border-red-900",
};

export function calcAge(dob: string | null): number | null {
  if (!dob) return null;
  const d = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - d.getFullYear();
  if (today.getMonth() < d.getMonth() || (today.getMonth() === d.getMonth() && today.getDate() < d.getDate())) age--;
  return age;
}

export const emptyMemberForm = (): Omit<FamilyMemberIn, "household_id"> => ({
  name: "",
  relationship: "child",
  date_of_birth: null,
  ssn_last4: null,
  is_earner: false,
  income: null,
  employer: null,
  work_state: null,
  employer_start_date: null,
  grade_level: null,
  school_name: null,
  care_cost_annual: null,
  college_start_year: null,
  notes: null,
});
