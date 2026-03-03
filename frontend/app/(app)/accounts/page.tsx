"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Building2, RefreshCw, Loader2, CheckCircle, AlertCircle, Plus, X,
} from "lucide-react";
import { usePlaidLink } from "react-plaid-link";
import {
  getAccounts, getPlaidItems, getPlaidAccounts,
  syncPlaid, getPlaidLinkToken, exchangePlaidPublicToken,
  getManualAssets, createManualAsset, updateManualAsset, deleteManualAsset,
  getPortfolioSummary, getEquityDashboard,
  getHouseholdProfiles, getLifeEvents, getInsurancePolicies, getBusinessEntities,
} from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type {
  Account, PlaidItem, PlaidAccount, ManualAsset, ManualAssetType,
  PortfolioSummary, EquityDashboard,
} from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import {
  AdminHealthBar, CompletenessTracker, GettingStartedChecklist,
  NetWorthHeader, AccountGroupList, SummarySidebar, AddAccountModal,
} from "@/components/accounts";
import {
  EMPTY_FORM, SORT_ORDER, GROUP_META, MANUAL_ASSET_CONFIG, INVESTMENT_SUBTYPES,
  plaidTypeToGroupKey, manualAssetTypeToGroupKey, assetToFormState,
} from "@/components/accounts/accounts-types";
import type {
  UnifiedGroup, AdminHealthSection, AddFlowStep, CompletenessStep, AssetFormState,
} from "@/components/accounts/accounts-types";
import { getErrorMessage } from "@/lib/errors";
import { LINK_TOKEN_KEY, INSTITUTION_KEY } from "@/app/oauth-redirect/page";

export default function AccountsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-48 gap-3 text-stone-400">
        <Loader2 className="animate-spin" size={20} />
        Loading accounts...
      </div>
    }>
      <AccountsPageContent />
    </Suspense>
  );
}

function AccountsPageContent() {
  const searchParams = useSearchParams();
  const [adminHealth, setAdminHealth] = useState<AdminHealthSection[]>([]);
  const [healthLoading, setHealthLoading] = useState(true);
  const [plaidItems, setPlaidItems] = useState<PlaidItem[]>([]);
  const [plaidAccounts, setPlaidAccounts] = useState<PlaidAccount[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [connectingPlaid, setConnectingPlaid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [manualAssets, setManualAssets] = useState<ManualAsset[]>([]);
  const [portfolioSummary, setPortfolioSummary] = useState<PortfolioSummary | null>(null);
  const [equityDashboard, setEquityDashboard] = useState<EquityDashboard | null>(null);
  const [addFlowStep, setAddFlowStep] = useState<AddFlowStep | null>(null);
  const [editingAsset, setEditingAsset] = useState<ManualAsset | null>(null);
  const [assetForm, setAssetForm] = useState<AssetFormState>(EMPTY_FORM);
  const [savingAsset, setSavingAsset] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [items, accts, manualAccts, assets, portfolio, equity] = await Promise.all([
        getPlaidItems(),
        getPlaidAccounts(),
        getAccounts(),
        getManualAssets(),
        getPortfolioSummary().catch(() => null),
        getEquityDashboard().catch(() => null),
      ]);
      setPlaidItems(items);
      setPlaidAccounts(accts);
      setAccounts(manualAccts);
      setManualAssets(assets);
      setPortfolioSummary(portfolio);
      setEquityDashboard(equity);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  // Show success message when returning from Plaid OAuth redirect
  useEffect(() => {
    if (searchParams.get("connected") === "1") {
      setSuccessMsg("Bank connected! Accounts are loading...");
      setTimeout(() => setSuccessMsg(null), 5000);
    }
  }, [searchParams]);

  useEffect(() => {
    async function checkAdminHealth() {
      setHealthLoading(true);
      try {
        const [profiles, lifeEvts, policies, bizEntities] = await Promise.allSettled([
          getHouseholdProfiles(),
          getLifeEvents(),
          getInsurancePolicies(),
          getBusinessEntities(false),
        ]);
        const healthOf = (label: string, href: string, action: string, r: PromiseSettledResult<any>) => {
          const arr = r.status === "fulfilled" ? (r.value as unknown[]) : [];
          return { label, href, count: arr.length, status: (arr.length > 0 ? "complete" : "empty") as "complete" | "empty", action };
        };
        setAdminHealth([
          healthOf("Household", "/household", "Add household profile", profiles),
          healthOf("Life Events", "/life-events", "Log a life event", lifeEvts),
          healthOf("Policies", "/insurance", "Add insurance policies", policies),
          healthOf("Business", "/business", "Add business entity (if applicable)", bizEntities),
        ]);
      } catch {
        // Health check is non-critical
      } finally {
        setHealthLoading(false);
      }
    }
    checkAdminHealth();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSync() {
    setSyncing(true);
    setSuccessMsg(null);
    try {
      await syncPlaid();
      setTimeout(() => {
        load();
        setSyncing(false);
        setSuccessMsg("Sync complete — accounts and transactions updated.");
        setTimeout(() => setSuccessMsg(null), 5000);
      }, 3000);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
      setSyncing(false);
    }
  }

  const onPlaidSuccess = useCallback(async (publicToken: string, metadata: any) => {
    setConnectingPlaid(false);
    const institutionName = metadata?.institution?.name ?? "Unknown Institution";
    // Clear OAuth session storage in case the user completed via non-OAuth path
    sessionStorage.removeItem(LINK_TOKEN_KEY);
    sessionStorage.removeItem(INSTITUTION_KEY);
    try {
      await exchangePlaidPublicToken(publicToken, institutionName);
      setSuccessMsg(`Connected to ${institutionName}! Fetching accounts...`);
      setLinkToken(null);
      await load();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (e: unknown) {
      setError(`Failed to connect ${institutionName}: ${getErrorMessage(e)}`);
    }
  }, []);

  const onPlaidExit = useCallback((err: any) => {
    setConnectingPlaid(false);
    setLinkToken(null);
    sessionStorage.removeItem(LINK_TOKEN_KEY);
    sessionStorage.removeItem(INSTITUTION_KEY);
    if (err) setError(err.display_message || err.error_message || "Plaid connection was cancelled.");
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: onPlaidSuccess,
    onExit: onPlaidExit,
  });

  useEffect(() => {
    if (linkToken && ready) open();
  }, [linkToken, ready, open]);

  async function handleConnectPlaid() {
    setAddFlowStep(null);
    setConnectingPlaid(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const data = await getPlaidLinkToken();
      // Persist token so the oauth-redirect page can re-initialize Link after
      // the bank redirects back (OAuth flow: Capital One, Chase, etc.)
      sessionStorage.setItem(LINK_TOKEN_KEY, data.link_token);
      setLinkToken(data.link_token);
    } catch {
      setConnectingPlaid(false);
      setError("Failed to initialize Plaid Link. Make sure PLAID_CLIENT_ID and PLAID_SECRET are set in .env");
    }
  }

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function openAddFlow() {
    setEditingAsset(null);
    setAssetForm(EMPTY_FORM);
    setAddFlowStep("choose");
  }

  function pickManualType(type: ManualAssetType) {
    setAssetForm({ ...EMPTY_FORM, asset_type: type });
    setAddFlowStep("manual-form");
  }

  function openEditAsset(asset: ManualAsset) {
    setEditingAsset(asset);
    setAssetForm(assetToFormState(asset));
    setAddFlowStep("manual-form");
  }

  function closeModal() {
    setAddFlowStep(null);
    setEditingAsset(null);
  }

  async function handleSaveAsset() {
    setSavingAsset(true);
    try {
      const val = parseFloat(assetForm.current_value);
      if (isNaN(val) || val < 0) throw new Error("Enter a valid value");
      if (!assetForm.name.trim()) throw new Error("Name is required");

      const investmentFields = assetForm.asset_type === "investment" ? {
        owner: assetForm.owner || null,
        account_subtype: (assetForm.account_subtype || null) as any,
        custodian: assetForm.custodian || null,
        employer: assetForm.employer || null,
        tax_treatment: (assetForm.tax_treatment || null) as any,
        is_retirement_account: assetForm.is_retirement_account,
        contribution_type: (assetForm.contribution_type || null) as any,
        contribution_rate_pct: assetForm.contribution_rate_pct ? parseFloat(assetForm.contribution_rate_pct) : null,
        employee_contribution_ytd: assetForm.employee_contribution_ytd ? parseFloat(assetForm.employee_contribution_ytd) : null,
        employer_contribution_ytd: assetForm.employer_contribution_ytd ? parseFloat(assetForm.employer_contribution_ytd) : null,
        employer_match_pct: assetForm.employer_match_pct ? parseFloat(assetForm.employer_match_pct) : null,
        employer_match_limit_pct: assetForm.employer_match_limit_pct ? parseFloat(assetForm.employer_match_limit_pct) : null,
        annual_return_pct: assetForm.annual_return_pct ? parseFloat(assetForm.annual_return_pct) : null,
        beneficiary: assetForm.beneficiary || null,
        as_of_date: assetForm.as_of_date || null,
      } : {};

      if (editingAsset) {
        await updateManualAsset(editingAsset.id, {
          name: assetForm.name.trim(),
          current_value: val,
          purchase_price: assetForm.purchase_price ? parseFloat(assetForm.purchase_price) : null,
          institution: assetForm.institution || null,
          address: assetForm.address || null,
          description: assetForm.description || null,
          notes: assetForm.notes || null,
          ...investmentFields,
        });
      } else {
        await createManualAsset({
          name: assetForm.name.trim(),
          asset_type: assetForm.asset_type,
          current_value: val,
          purchase_price: assetForm.purchase_price ? parseFloat(assetForm.purchase_price) : null,
          institution: assetForm.institution || null,
          address: assetForm.address || null,
          description: assetForm.description || null,
          notes: assetForm.notes || null,
          ...investmentFields,
        });
      }
      closeModal();
      setSuccessMsg(editingAsset ? "Asset updated." : "Asset added to net worth.");
      setTimeout(() => setSuccessMsg(null), 4000);
      await load();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSavingAsset(false);
    }
  }

  async function handleDeleteAsset(asset: ManualAsset) {
    if (!confirm(`Delete "${asset.name}"? This cannot be undone.`)) return;
    try {
      await deleteManualAsset(asset.id);
      setSuccessMsg(`Deleted ${asset.name}.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await load();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
  }

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

  plaidAccounts.forEach((acct) => {
    const gk = plaidTypeToGroupKey(acct.type, acct.subtype);
    const g = ensureGroup(gk);
    const val = Math.abs(acct.current_balance ?? 0);
    g.total += val;
    g.items.push({
      id: `plaid-${acct.id}`,
      name: `${acct.name}${acct.mask ? ` (...${acct.mask})` : ""}`,
      subtitle: acct.subtype ?? acct.type,
      value: val,
      detail: acct.last_updated ? new Date(acct.last_updated).toLocaleDateString() : undefined,
    });
  });

  accounts.forEach((acct) => {
    let gk: string;
    if (acct.subtype === "credit_card") gk = "credit_cards";
    else if (acct.subtype === "savings") gk = "savings";
    else gk = "checking";
    const g = ensureGroup(gk);
    const val = Math.abs(acct.balance ?? 0);
    g.total += val;
    g.items.push({
      id: `csv-${acct.id}`,
      name: acct.name,
      subtitle: `${acct.subtype ?? acct.account_type}${acct.institution ? ` · ${acct.institution}` : ""}`,
      value: val,
      detail: `${acct.transaction_count ?? 0} txns`,
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
      onEdit: () => openEditAsset(asset),
      onDelete: () => handleDeleteAsset(asset),
    });
  });

  const portfolioTotal = portfolioSummary?.total_value ?? 0;
  if (portfolioTotal > 0 && portfolioSummary) {
    const g = ensureGroup("investments");
    g.total += portfolioTotal;
    const parts: string[] = [];
    if (portfolioSummary.stock_value > 0) parts.push(`Stocks ${formatCurrency(portfolioSummary.stock_value)}`);
    if (portfolioSummary.etf_value > 0) parts.push(`ETFs ${formatCurrency(portfolioSummary.etf_value)}`);
    if (portfolioSummary.crypto_value > 0) parts.push(`Crypto ${formatCurrency(portfolioSummary.crypto_value)}`);
    if (portfolioSummary.other_value > 0) parts.push(`Other ${formatCurrency(portfolioSummary.other_value)}`);
    g.items.push({
      id: "portfolio-total",
      name: "Portfolio Holdings",
      subtitle: parts.join(" · ") || `${portfolioSummary.holdings_count} holdings`,
      value: portfolioTotal,
      detail: portfolioSummary.total_gain_loss !== 0
        ? `${portfolioSummary.total_gain_loss >= 0 ? "+" : ""}${formatCurrency(portfolioSummary.total_gain_loss)} (${portfolioSummary.total_gain_loss_pct >= 0 ? "+" : ""}${portfolioSummary.total_gain_loss_pct.toFixed(1)}%)`
        : undefined,
    });
  }

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

  const unifiedGroups = Array.from(groupMap.values())
    .filter((g) => g.items.length > 0)
    .sort((a, b) => a.sortOrder - b.sortOrder);

  const totalAssets = unifiedGroups.filter((g) => !g.isLiability).reduce((s, g) => s + g.total, 0);
  const totalLiabilities = unifiedGroups.filter((g) => g.isLiability).reduce((s, g) => s + g.total, 0);
  const netWorth = totalAssets - totalLiabilities;

  const hasAnyAccounts = plaidItems.length > 0 || accounts.length > 0 || manualAssets.length > 0
    || portfolioTotal > 0 || equityTotal > 0;

  const investCountForTracker = plaidAccounts.filter((a) => a.type === "investment").length
    + manualAssets.filter((a) => ["investment_account", "brokerage", "ira", "401k"].includes(a.asset_type)).length
    + (portfolioTotal > 0 ? 1 : 0) + (equityTotal > 0 ? 1 : 0);
  const completenessSteps: CompletenessStep[] = [
    { label: "Bank Accounts", count: plaidItems.length + accounts.filter((a) => a.account_type === "personal").length, action: "Connect via Plaid or add manually" },
    { label: "Investments", count: investCountForTracker, action: "Link brokerage, 401k, or IRA" },
    { label: "Real Estate", count: manualAssets.filter((a) => a.asset_type === "real_estate").length, action: "Add your home or property value" },
    { label: "Liabilities", count: manualAssets.filter((a) => a.is_liability).length, action: "Add mortgage, auto loans, credit cards" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        subtitle="Manage all accounts, assets, and liabilities — your single source of truth"
        actions={
          <>
            <button
              onClick={handleSync}
              disabled={syncing}
              className="flex items-center gap-2 text-sm text-stone-600 border border-stone-200 rounded-lg px-4 py-2 hover:bg-stone-50 disabled:opacity-60"
            >
              <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
              {syncing ? "Syncing..." : "Refresh all"}
            </button>
            <button
              onClick={openAddFlow}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
            >
              <Plus size={14} />
              Add account
            </button>
          </>
        }
      />

      {!healthLoading && adminHealth.length > 0 && (
        <AdminHealthBar
          adminHealth={adminHealth}
          accountsCount={plaidItems.length + accounts.length + manualAssets.length}
        />
      )}

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600"><X size={16} /></button>
        </div>
      )}
      {successMsg && (
        <div className="bg-green-50 text-green-700 rounded-xl p-4 flex items-center gap-3 border border-green-100">
          <CheckCircle size={18} />
          <p className="text-sm font-medium">{successMsg}</p>
        </div>
      )}

      {!loading && <CompletenessTracker steps={completenessSteps} />}

      {loading ? (
        <div className="flex items-center justify-center h-48 gap-3 text-stone-400">
          <Loader2 className="animate-spin" size={20} />
          Loading accounts...
        </div>
      ) : !hasAnyAccounts ? (
        <>
          <GettingStartedChecklist onAddAccount={openAddFlow} />
          <EmptyState
            icon={<Building2 size={40} />}
            title="No accounts yet"
            description="Connect your banks via Plaid or manually add your assets, investments, and liabilities."
            action={
              <button
                onClick={openAddFlow}
                className="flex items-center gap-2 bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
              >
                <Plus size={15} />
                Add your first account
              </button>
            }
          />
        </>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-4">
            <NetWorthHeader netWorth={netWorth} />
            <AccountGroupList
              groups={unifiedGroups}
              collapsedGroups={collapsedGroups}
              onToggleGroup={toggleGroup}
            />
          </div>
          <div className="space-y-4">
            <SummarySidebar
              totalAssets={totalAssets}
              totalLiabilities={totalLiabilities}
              groups={unifiedGroups}
            />
          </div>
        </div>
      )}

      <AddAccountModal
        addFlowStep={addFlowStep}
        editingAsset={editingAsset}
        assetForm={assetForm}
        savingAsset={savingAsset}
        connectingPlaid={connectingPlaid}
        onSetAssetForm={setAssetForm}
        onPickManualType={pickManualType}
        onConnectPlaid={handleConnectPlaid}
        onSave={handleSaveAsset}
        onClose={closeModal}
        onBack={() => setAddFlowStep("choose")}
      />
    </div>
  );
}
