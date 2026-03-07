"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Building2, RefreshCw, Loader2, CheckCircle, AlertCircle, Plus, X,
} from "lucide-react";
import { usePlaidLink } from "react-plaid-link";
import type { PlaidLinkOnSuccessMetadata, PlaidLinkError } from "react-plaid-link";
import type { InvestmentSubtype, TaxTreatment, ContributionType } from "@/types/portfolio";
import {
  getAccounts, getPlaidItems,
  syncPlaid, getPlaidLinkToken, exchangePlaidPublicToken,
  getManualAssets, createManualAsset, updateManualAsset, deleteManualAsset,
  getEquityDashboard,
  getHouseholdProfiles, getLifeEvents, getInsurancePolicies, getBusinessEntities,
} from "@/lib/api";
import { getIncomeConnections } from "@/lib/api-income";
import type {
  Account, PlaidItem, ManualAsset, ManualAssetType,
  EquityDashboard, BusinessEntity,
} from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import {
  GettingStartedChecklist,
  NetWorthHeader, AccountGroupList, SummarySidebar, AddAccountModal,
  SetupBanner,
} from "@/components/accounts";
import {
  EMPTY_FORM, buildUnifiedGroups, assetToFormState,
} from "@/components/accounts/accounts-types";
import type {
  AdminHealthSection, AddFlowStep, CompletenessStep, SetupItem, AssetFormState,
} from "@/components/accounts/accounts-types";
import { getErrorMessage } from "@/lib/errors";
import { LINK_TOKEN_KEY, INSTITUTION_KEY } from "@/app/oauth-redirect/page";

export default function AccountsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-48 gap-3 text-text-muted">
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
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [connectingPlaid, setConnectingPlaid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [manualAssets, setManualAssets] = useState<ManualAsset[]>([]);
  const [equityDashboard, setEquityDashboard] = useState<EquityDashboard | null>(null);
  const [addFlowStep, setAddFlowStep] = useState<AddFlowStep | null>(null);
  const [editingAsset, setEditingAsset] = useState<ManualAsset | null>(null);
  const [assetForm, setAssetForm] = useState<AssetFormState>(EMPTY_FORM);
  const [savingAsset, setSavingAsset] = useState(false);
  const [bizEntities, setBizEntities] = useState<BusinessEntity[]>([]);
  const [hasEmployerConnection, setHasEmployerConnection] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [items, allAccounts, assets, equity, entities, incomeConns] = await Promise.all([
        getPlaidItems(),
        getAccounts(),
        getManualAssets(),
        getEquityDashboard().catch(() => null),
        getBusinessEntities(true).catch(() => [] as BusinessEntity[]),
        getIncomeConnections().catch(() => []),
      ]);
      setPlaidItems(items);
      setAccounts(allAccounts);
      setManualAssets(assets);
      setEquityDashboard(equity);
      setBizEntities(entities);
      setHasEmployerConnection(incomeConns.length > 0);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

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
        const [profiles, lifeEvts, policies] = await Promise.allSettled([
          getHouseholdProfiles(), getLifeEvents(), getInsurancePolicies(),
        ]);
        const healthOf = (label: string, href: string, action: string, r: PromiseSettledResult<unknown>) => {
          const arr = r.status === "fulfilled" ? (r.value as unknown[]) : [];
          return { label, href, count: arr.length, status: (arr.length > 0 ? "complete" : "empty") as "complete" | "empty", action };
        };
        const bizResult: PromiseSettledResult<unknown> = { status: "fulfilled", value: bizEntities };
        setAdminHealth([
          healthOf("Household", "/household", "Add household profile", profiles),
          healthOf("Life Events", "/life-events", "Log a life event", lifeEvts),
          healthOf("Policies", "/insurance", "Add insurance policies", policies),
          healthOf("Business", "/business", "Add business entity (if applicable)", bizResult),
        ]);
      } catch { /* Health check is non-critical */ } finally { setHealthLoading(false); }
    }
    checkAdminHealth();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSync() {
    setSyncing(true);
    setSuccessMsg(null);
    try {
      await syncPlaid();
      setTimeout(() => { load(); setSyncing(false); setSuccessMsg("Sync complete — accounts and transactions updated."); setTimeout(() => setSuccessMsg(null), 5000); }, 3000);
    } catch (e: unknown) { setError(getErrorMessage(e)); setSyncing(false); }
  }

  const onPlaidSuccess = useCallback(async (publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => {
    setConnectingPlaid(false);
    const institutionName = metadata?.institution?.name ?? "Unknown Institution";
    sessionStorage.removeItem(LINK_TOKEN_KEY);
    sessionStorage.removeItem(INSTITUTION_KEY);
    try {
      const result = await exchangePlaidPublicToken(publicToken, institutionName);
      const matchMsg = result.accounts_matched ? ` (${result.accounts_matched} existing account${result.accounts_matched > 1 ? "s" : ""} linked)` : "";
      setSuccessMsg(`Connected to ${institutionName}!${matchMsg} Syncing transactions...`);
      setLinkToken(null);
      await load();
      setTimeout(async () => { await load(); setSuccessMsg(`${institutionName} synced — transactions imported.`); setTimeout(() => setSuccessMsg(null), 5000); }, 10000);
    } catch (e: unknown) { setError(`Failed to connect ${institutionName}: ${getErrorMessage(e)}`); }
  }, []);

  const onPlaidExit = useCallback((err: PlaidLinkError | null) => {
    setConnectingPlaid(false);
    setLinkToken(null);
    sessionStorage.removeItem(LINK_TOKEN_KEY);
    sessionStorage.removeItem(INSTITUTION_KEY);
    if (err) setError(err.display_message || err.error_message || "Plaid connection was cancelled.");
  }, []);

  const { open, ready } = usePlaidLink({ token: linkToken, onSuccess: onPlaidSuccess, onExit: onPlaidExit });
  useEffect(() => { if (linkToken && ready) open(); }, [linkToken, ready, open]);

  async function handleConnectPlaid() {
    setAddFlowStep(null); setConnectingPlaid(true); setError(null); setSuccessMsg(null);
    try {
      const data = await getPlaidLinkToken();
      sessionStorage.setItem(LINK_TOKEN_KEY, data.link_token);
      setLinkToken(data.link_token);
    } catch { setConnectingPlaid(false); setError("Failed to initialize Plaid Link. Make sure PLAID_CLIENT_ID and PLAID_SECRET are set in .env"); }
  }

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => { const next = new Set(prev); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  }

  function openAddFlow() { setEditingAsset(null); setAssetForm(EMPTY_FORM); setAddFlowStep("choose"); }
  function pickManualType(type: ManualAssetType) { setAssetForm({ ...EMPTY_FORM, asset_type: type }); setAddFlowStep("manual-form"); }
  function openEditAsset(asset: ManualAsset) { setEditingAsset(asset); setAssetForm(assetToFormState(asset)); setAddFlowStep("manual-form"); }
  function closeModal() { setAddFlowStep(null); setEditingAsset(null); }

  async function handleSaveAsset() {
    setSavingAsset(true);
    try {
      const val = parseFloat(assetForm.current_value);
      if (isNaN(val) || val < 0) throw new Error("Enter a valid value");
      if (!assetForm.name.trim()) throw new Error("Name is required");
      const investmentFields = assetForm.asset_type === "investment" ? {
        owner: assetForm.owner || null,
        account_subtype: (assetForm.account_subtype || null) as InvestmentSubtype | null,
        custodian: assetForm.custodian || null, employer: assetForm.employer || null,
        tax_treatment: (assetForm.tax_treatment || null) as TaxTreatment | null,
        is_retirement_account: assetForm.is_retirement_account,
        contribution_type: (assetForm.contribution_type || null) as ContributionType | null,
        contribution_rate_pct: assetForm.contribution_rate_pct ? parseFloat(assetForm.contribution_rate_pct) : null,
        employee_contribution_ytd: assetForm.employee_contribution_ytd ? parseFloat(assetForm.employee_contribution_ytd) : null,
        employer_contribution_ytd: assetForm.employer_contribution_ytd ? parseFloat(assetForm.employer_contribution_ytd) : null,
        employer_match_pct: assetForm.employer_match_pct ? parseFloat(assetForm.employer_match_pct) : null,
        employer_match_limit_pct: assetForm.employer_match_limit_pct ? parseFloat(assetForm.employer_match_limit_pct) : null,
        annual_return_pct: assetForm.annual_return_pct ? parseFloat(assetForm.annual_return_pct) : null,
        beneficiary: assetForm.beneficiary || null, as_of_date: assetForm.as_of_date || null,
      } : {};
      const shared = {
        name: assetForm.name.trim(), current_value: val,
        purchase_price: assetForm.purchase_price ? parseFloat(assetForm.purchase_price) : null,
        institution: assetForm.institution || null, address: assetForm.address || null,
        description: assetForm.description || null, notes: assetForm.notes || null,
        ...investmentFields,
      };
      if (editingAsset) { await updateManualAsset(editingAsset.id, shared); }
      else { await createManualAsset({ ...shared, asset_type: assetForm.asset_type }); }
      closeModal();
      setSuccessMsg(editingAsset ? "Asset updated." : "Asset added to net worth.");
      setTimeout(() => setSuccessMsg(null), 4000);
      await load();
    } catch (e: unknown) { setError(getErrorMessage(e)); } finally { setSavingAsset(false); }
  }

  async function handleDeleteAsset(asset: ManualAsset) {
    if (!confirm(`Delete "${asset.name}"? This cannot be undone.`)) return;
    try { await deleteManualAsset(asset.id); setSuccessMsg(`Deleted ${asset.name}.`); setTimeout(() => setSuccessMsg(null), 4000); await load(); }
    catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  // Build unified groups from all data sources
  const unifiedGroups = buildUnifiedGroups({
    accounts, manualAssets, equityDashboard, bizEntities,
    onEditAsset: openEditAsset, onDeleteAsset: handleDeleteAsset,
  });
  const equityTotal = equityDashboard?.total_equity_value ?? 0;
  const totalAssets = unifiedGroups.filter((g) => !g.isLiability).reduce((s, g) => s + g.total, 0);
  const totalLiabilities = unifiedGroups.filter((g) => g.isLiability).reduce((s, g) => s + g.total, 0);
  const netWorth = totalAssets - totalLiabilities;
  const hasAnyAccounts = accounts.length > 0 || manualAssets.length > 0 || equityTotal > 0;

  const investCount = accounts.filter((a) => a.account_type === "investment").length + manualAssets.filter((a) => a.asset_type === "investment").length + (equityTotal > 0 ? 1 : 0);
  const completenessSteps: CompletenessStep[] = [
    { label: "Bank Accounts", count: accounts.filter((a) => a.account_type === "personal").length, action: "Connect via Plaid or add manually" },
    { label: "Investments", count: investCount, action: "Link brokerage, 401k, or IRA" },
    { label: "Real Estate", count: manualAssets.filter((a) => a.asset_type === "real_estate").length, action: "Add your home or property value" },
    { label: "Liabilities", count: manualAssets.filter((a) => a.is_liability).length, action: "Add mortgage, auto loans, credit cards" },
  ];
  const setupItems: SetupItem[] = [
    ...adminHealth,
    ...completenessSteps.map((s): SetupItem => ({ label: s.label, href: "/accounts", count: s.count, status: s.count > 0 ? "complete" : "empty", action: s.action })),
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        subtitle="Manage all accounts, assets, and liabilities — your single source of truth"
        actions={
          <>
            <button onClick={handleSync} disabled={syncing} className="flex items-center gap-2 text-sm text-text-secondary border border-border rounded-lg px-4 py-2 hover:bg-surface disabled:opacity-60">
              <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
              {syncing ? "Syncing..." : "Refresh all"}
            </button>
            <button onClick={openAddFlow} className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm">
              <Plus size={14} /> Add account
            </button>
          </>
        }
      />

      {!loading && !healthLoading && (
        <SetupBanner items={setupItems} hasEmployerConnection={hasEmployerConnection} loading={false} onConnectionComplete={() => load()} />
      )}

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} /><p className="text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600"><X size={16} /></button>
        </div>
      )}
      {successMsg && (
        <div className="bg-green-50 text-green-700 rounded-xl p-4 flex items-center gap-3 border border-green-100">
          <CheckCircle size={18} /><p className="text-sm font-medium">{successMsg}</p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 gap-3 text-text-muted">
          <Loader2 className="animate-spin" size={20} /> Loading accounts...
        </div>
      ) : !hasAnyAccounts ? (
        <>
          <GettingStartedChecklist onAddAccount={openAddFlow} />
          <EmptyState
            icon={<Building2 size={40} />}
            title="No accounts yet"
            description="Connect your banks via Plaid or manually add your assets, investments, and liabilities."
            action={<button onClick={openAddFlow} className="flex items-center gap-2 bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm"><Plus size={15} /> Add your first account</button>}
          />
        </>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-4">
            <NetWorthHeader netWorth={netWorth} />
            <AccountGroupList groups={unifiedGroups} collapsedGroups={collapsedGroups} onToggleGroup={toggleGroup} />
          </div>
          <div className="space-y-4">
            <SummarySidebar totalAssets={totalAssets} totalLiabilities={totalLiabilities} groups={unifiedGroups} />
          </div>
        </div>
      )}

      <AddAccountModal
        addFlowStep={addFlowStep} editingAsset={editingAsset} assetForm={assetForm} savingAsset={savingAsset} connectingPlaid={connectingPlaid}
        onSetAssetForm={setAssetForm} onPickManualType={pickManualType} onConnectPlaid={handleConnectPlaid}
        onSave={handleSaveAsset} onClose={closeModal} onBack={() => setAddFlowStep("choose")}
      />
    </div>
  );
}
