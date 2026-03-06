import {
  Home, Car, TrendingUp, DollarSign, PiggyBank, Package,
  Landmark, CreditCard, Briefcase,
} from "lucide-react";
import type { ManualAsset, ManualAssetType, InvestmentSubtype } from "@/types/api";

// ---------------------------------------------------------------------------
// Unified group model — every group (Plaid, CSV, manual, portfolio, equity)
// is normalized into this shape so we can render one sorted list.
// ---------------------------------------------------------------------------
export interface UnifiedItem {
  id: string;
  name: string;
  subtitle: string;
  value: number;
  detail?: string;
  badge?: string;          // e.g. business entity name
  canEdit?: boolean;
  onEdit?: () => void;
  onDelete?: () => void;
}

export interface UnifiedGroup {
  key: string;
  label: string;
  icon: React.ReactNode;
  isLiability: boolean;
  total: number;
  sortOrder: number;
  items: UnifiedItem[];
}

// ---------------------------------------------------------------------------
// Asset form model
// ---------------------------------------------------------------------------
export interface AssetFormState {
  name: string;
  asset_type: ManualAssetType;
  current_value: string;
  purchase_price: string;
  institution: string;
  address: string;
  description: string;
  notes: string;
  owner: string;
  account_subtype: string;
  custodian: string;
  employer: string;
  tax_treatment: string;
  is_retirement_account: boolean;
  contribution_type: string;
  contribution_rate_pct: string;
  employee_contribution_ytd: string;
  employer_contribution_ytd: string;
  employer_match_pct: string;
  employer_match_limit_pct: string;
  annual_return_pct: string;
  beneficiary: string;
  as_of_date: string;
}

export const EMPTY_FORM: AssetFormState = {
  name: "",
  asset_type: "real_estate",
  current_value: "",
  purchase_price: "",
  institution: "",
  address: "",
  description: "",
  notes: "",
  owner: "",
  account_subtype: "",
  custodian: "",
  employer: "",
  tax_treatment: "",
  is_retirement_account: false,
  contribution_type: "",
  contribution_rate_pct: "",
  employee_contribution_ytd: "",
  employer_contribution_ytd: "",
  employer_match_pct: "",
  employer_match_limit_pct: "",
  annual_return_pct: "",
  beneficiary: "",
  as_of_date: "",
};

// ---------------------------------------------------------------------------
// Admin health / completeness
// ---------------------------------------------------------------------------
export interface AdminHealthSection {
  label: string;
  href: string;
  count: number;
  status: "complete" | "partial" | "empty";
  action: string;
}

export interface SetupItem {
  label: string;
  href: string;
  count: number;
  status: "complete" | "partial" | "empty";
  action: string;
}

export type AddFlowStep = "choose" | "manual-form";

export interface CompletenessStep {
  label: string;
  count: number;
  action: string;
}

// ---------------------------------------------------------------------------
// Canonical display order & group metadata
// ---------------------------------------------------------------------------
export const SORT_ORDER: Record<string, number> = {
  real_estate: 1,
  investments: 2,
  equity_comp: 3,
  checking: 4,
  savings: 5,
  vehicles: 6,
  other_assets: 7,
  loans: 8,
  credit_cards: 9,
  other_liabilities: 10,
};

export const GROUP_META: Record<string, { label: string; icon: React.ReactNode; isLiability: boolean }> = {
  real_estate:        { label: "Real Estate",          icon: <Home size={18} className="text-blue-500" />,       isLiability: false },
  investments:        { label: "Investments",           icon: <TrendingUp size={18} className="text-indigo-500" />, isLiability: false },
  equity_comp:        { label: "Equity Compensation",   icon: <Briefcase size={18} className="text-violet-500" />, isLiability: false },
  checking:           { label: "Checking",              icon: <DollarSign size={18} className="text-green-500" />, isLiability: false },
  savings:            { label: "Savings",               icon: <PiggyBank size={18} className="text-blue-500" />,  isLiability: false },
  vehicles:           { label: "Vehicles",              icon: <Car size={18} className="text-cyan-500" />,        isLiability: false },
  other_assets:       { label: "Other Assets",          icon: <Package size={18} className="text-emerald-500" />, isLiability: false },
  loans:              { label: "Loans",                 icon: <Landmark size={18} className="text-red-400" />,    isLiability: true },
  credit_cards:       { label: "Credit Cards",          icon: <CreditCard size={18} className="text-orange-500" />, isLiability: true },
  other_liabilities:  { label: "Other Liabilities",     icon: <Landmark size={18} className="text-red-300" />,   isLiability: true },
};

export const MANUAL_ASSET_CONFIG: Record<ManualAssetType, { label: string; groupLabel: string; icon: React.ReactNode; isLiability: boolean }> = {
  real_estate:      { label: "Real Estate",       groupLabel: "Real Estate",          icon: <Home size={18} className="text-blue-500" />,       isLiability: false },
  vehicle:          { label: "Vehicle",           groupLabel: "Vehicles",             icon: <Car size={18} className="text-cyan-500" />,        isLiability: false },
  investment:       { label: "Investment",        groupLabel: "Investments (Manual)",  icon: <TrendingUp size={18} className="text-indigo-500" />, isLiability: false },
  other_asset:      { label: "Other Asset",       groupLabel: "Other Assets",         icon: <Package size={18} className="text-emerald-500" />, isLiability: false },
  mortgage:         { label: "Mortgage",          groupLabel: "Mortgages",            icon: <Home size={18} className="text-red-400" />,        isLiability: true },
  loan:             { label: "Loan",              groupLabel: "Loans",                icon: <Landmark size={18} className="text-red-400" />,    isLiability: true },
  other_liability:  { label: "Other Liability",   groupLabel: "Other Liabilities",    icon: <Landmark size={18} className="text-red-300" />,   isLiability: true },
};

export const INVESTMENT_SUBTYPES: { value: InvestmentSubtype; label: string }[] = [
  { value: "401k_traditional", label: "401(k) Traditional" },
  { value: "401k_roth", label: "401(k) Roth" },
  { value: "traditional_ira", label: "Traditional IRA" },
  { value: "roth_ira", label: "Roth IRA" },
  { value: "rollover_ira", label: "Rollover IRA" },
  { value: "brokerage", label: "Brokerage" },
  { value: "trust", label: "Trust" },
  { value: "espp", label: "ESPP" },
  { value: "rsu", label: "RSU" },
  { value: "hsa", label: "HSA" },
  { value: "529", label: "529 Plan" },
  { value: "other", label: "Other" },
];

// ---------------------------------------------------------------------------
// Asset → form state mapper (pure data transformation)
// ---------------------------------------------------------------------------
export function assetToFormState(asset: ManualAsset): AssetFormState {
  return {
    name: asset.name,
    asset_type: asset.asset_type,
    current_value: String(asset.current_value),
    purchase_price: asset.purchase_price != null ? String(asset.purchase_price) : "",
    institution: asset.institution ?? "",
    address: asset.address ?? "",
    description: asset.description ?? "",
    notes: asset.notes ?? "",
    owner: asset.owner ?? "",
    account_subtype: asset.account_subtype ?? "",
    custodian: asset.custodian ?? "",
    employer: asset.employer ?? "",
    tax_treatment: asset.tax_treatment ?? "",
    is_retirement_account: asset.is_retirement_account ?? false,
    contribution_type: asset.contribution_type ?? "",
    contribution_rate_pct: asset.contribution_rate_pct != null ? String(asset.contribution_rate_pct) : "",
    employee_contribution_ytd: asset.employee_contribution_ytd != null ? String(asset.employee_contribution_ytd) : "",
    employer_contribution_ytd: asset.employer_contribution_ytd != null ? String(asset.employer_contribution_ytd) : "",
    employer_match_pct: asset.employer_match_pct != null ? String(asset.employer_match_pct) : "",
    employer_match_limit_pct: asset.employer_match_limit_pct != null ? String(asset.employer_match_limit_pct) : "",
    annual_return_pct: asset.annual_return_pct != null ? String(asset.annual_return_pct) : "",
    beneficiary: asset.beneficiary ?? "",
    as_of_date: asset.as_of_date ? asset.as_of_date.split("T")[0] : "",
  };
}

// ---------------------------------------------------------------------------
// Plaid / manual-asset → unified group key mappers
// ---------------------------------------------------------------------------
export function plaidTypeToGroupKey(type: string, subtype: string | null): string {
  switch (type) {
    case "depository":
      if (subtype === "savings" || subtype === "money market" || subtype === "cd") return "savings";
      return "checking";
    case "credit": return "credit_cards";
    case "investment": return "investments";
    case "loan": return "loans";
    case "mortgage": return "loans";
    default: return "other_assets";
  }
}

export function manualAssetTypeToGroupKey(type: ManualAssetType): string {
  switch (type) {
    case "real_estate": return "real_estate";
    case "vehicle": return "vehicles";
    case "investment": return "investments";
    case "other_asset": return "other_assets";
    case "mortgage": return "loans";
    case "loan": return "loans";
    case "other_liability": return "other_liabilities";
  }
}
