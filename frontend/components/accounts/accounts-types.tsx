import {
  Home, Car, TrendingUp, DollarSign, PiggyBank, Package,
  Landmark, CreditCard, Briefcase,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { ManualAsset, ManualAssetType, InvestmentSubtype, Account, EquityDashboard, BusinessEntity } from "@/types/api";

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

// ---------------------------------------------------------------------------
// Build unified groups from accounts, manual assets, and equity data.
// Pure data transformation — no side effects.
// ---------------------------------------------------------------------------
interface BuildGroupsInput {
  accounts: Account[];
  manualAssets: ManualAsset[];
  equityDashboard: EquityDashboard | null;
  bizEntities: BusinessEntity[];
  onEditAsset: (asset: ManualAsset) => void;
  onDeleteAsset: (asset: ManualAsset) => void;
}

export function buildUnifiedGroups({
  accounts, manualAssets, equityDashboard, bizEntities,
  onEditAsset, onDeleteAsset,
}: BuildGroupsInput): UnifiedGroup[] {
  const entityNameMap = new Map<number, string>();
  bizEntities.forEach((e) => entityNameMap.set(e.id, e.name));

  const groupMap = new Map<string, UnifiedGroup>();
  function ensureGroup(key: string): UnifiedGroup {
    let g = groupMap.get(key);
    if (!g) {
      const meta = GROUP_META[key] ?? GROUP_META.other_assets;
      g = { key, label: meta.label, icon: meta.icon, isLiability: meta.isLiability, total: 0, sortOrder: SORT_ORDER[key] ?? 99, items: [] };
      groupMap.set(key, g);
    }
    return g;
  }

  accounts.forEach((acct) => {
    let gk: string;
    if (acct.data_source === "plaid" && acct.plaid_type) {
      gk = plaidTypeToGroupKey(acct.plaid_type, acct.plaid_subtype ?? null);
    } else if (acct.subtype === "credit_card" || acct.subtype === "credit card") {
      gk = "credit_cards";
    } else if (acct.subtype === "savings" || acct.subtype === "money market" || acct.subtype === "cd") {
      gk = "savings";
    } else if (acct.subtype === "brokerage" || acct.account_type === "investment") {
      gk = "investments";
    } else if (acct.subtype === "mortgage" || acct.subtype === "loan" || acct.subtype === "auto" || acct.subtype === "student") {
      gk = "loans";
    } else {
      gk = "checking";
    }
    const g = ensureGroup(gk);
    const val = Math.abs(acct.balance ?? 0);
    g.total += val;

    const sourceBadge = acct.data_source === "plaid" ? "Plaid" : acct.data_source === "csv" ? "CSV" : acct.data_source === "monarch" ? "Monarch" : "";
    const mask = acct.plaid_mask ?? acct.last_four;
    const displayName = `${acct.name}${mask ? ` (...${mask})` : ""}`;
    const subtitleParts: string[] = [];
    if (acct.plaid_subtype ?? acct.subtype) subtitleParts.push(acct.plaid_subtype ?? acct.subtype ?? "");
    if (acct.institution) subtitleParts.push(acct.institution);
    if (sourceBadge) subtitleParts.push(sourceBadge);

    let detail: string | undefined;
    if (acct.data_source === "plaid" && acct.plaid_last_synced) {
      detail = `Synced ${new Date(acct.plaid_last_synced).toLocaleDateString()}`;
    }
    if (acct.transaction_count && acct.transaction_count > 0) {
      const txnLabel = `${acct.transaction_count} txns`;
      detail = detail ? `${detail} · ${txnLabel}` : txnLabel;
    }

    const entityBadge = acct.default_business_entity_id
      ? entityNameMap.get(acct.default_business_entity_id)
      : undefined;

    g.items.push({
      id: `account-${acct.id}`,
      name: displayName,
      subtitle: subtitleParts.join(" · ") || acct.account_type,
      value: val,
      detail,
      badge: entityBadge,
    });
  });

  manualAssets.forEach((asset) => {
    const gk = manualAssetTypeToGroupKey(asset.asset_type);
    const g = ensureGroup(gk);
    g.total += asset.current_value;

    let subtitle = "";
    let detail: string | undefined;
    if (asset.asset_type === "investment") {
      const parts: string[] = [];
      if (asset.account_subtype) {
        const found = INVESTMENT_SUBTYPES.find((s) => s.value === asset.account_subtype);
        parts.push(found?.label ?? asset.account_subtype);
      }
      if (asset.custodian) parts.push(asset.custodian);
      else if (asset.institution) parts.push(asset.institution);
      if (asset.owner) parts.push(asset.owner);
      subtitle = parts.join(" · ") || "Investment";
      const details: string[] = [];
      if (asset.annual_return_pct != null) details.push(`${asset.annual_return_pct >= 0 ? "+" : ""}${asset.annual_return_pct.toFixed(1)}% return`);
      if (asset.as_of_date) details.push(`as of ${new Date(asset.as_of_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`);
      detail = details.length > 0 ? details.join(" · ") : undefined;
    } else {
      subtitle = `${asset.institution ? `${asset.institution} · ` : ""}${asset.address ?? asset.description ?? MANUAL_ASSET_CONFIG[asset.asset_type]?.label ?? ""}`;
      detail = asset.purchase_price != null ? `Purchased ${formatCurrency(asset.purchase_price)}` : undefined;
    }

    g.items.push({
      id: `manual-${asset.id}`,
      name: asset.name,
      subtitle,
      value: asset.current_value,
      detail,
      canEdit: true,
      onEdit: () => onEditAsset(asset),
      onDelete: () => onDeleteAsset(asset),
    });
  });

  const equityTotal = equityDashboard?.total_equity_value ?? 0;
  if (equityTotal > 0 && equityDashboard && equityDashboard.grants.length > 0) {
    const g = ensureGroup("equity_comp");
    g.total += equityTotal;
    for (const grant of equityDashboard.grants) {
      const vestedLabel = `${grant.vested_shares.toLocaleString()} vested`;
      const unvestedLabel = grant.unvested_shares > 0 ? ` · ${grant.unvested_shares.toLocaleString()} unvested` : "";
      const fmvLabel = grant.current_fmv > 0 ? ` · $${grant.current_fmv.toFixed(2)} FMV` : "";
      g.items.push({
        id: `equity-${grant.id}`,
        name: `${grant.employer} — ${grant.grant_type.toUpperCase()}`,
        subtitle: `${vestedLabel}${unvestedLabel}${fmvLabel}`,
        value: grant.total_value,
        detail: grant.unvested_shares > 0 ? `${grant.total_shares.toLocaleString()} total shares` : undefined,
      });
    }
  }

  return Array.from(groupMap.values())
    .filter((g) => g.items.length > 0)
    .sort((a, b) => a.sortOrder - b.sortOrder);
}
