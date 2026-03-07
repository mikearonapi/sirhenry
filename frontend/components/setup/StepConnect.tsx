"use client";
import { useState, useCallback, useEffect } from "react";
import {
  CreditCard, Briefcase, Building2, Plus, Check, Landmark, Home, Car,
  PiggyBank, ExternalLink, CheckCircle, Loader2, AlertCircle, X,
  SkipForward, ArrowRight, ChevronDown, ChevronUp,
} from "lucide-react";
import { usePlaidLink } from "react-plaid-link";
import type { PlaidLinkOnSuccessMetadata, PlaidLinkError } from "react-plaid-link";
import Card from "@/components/ui/Card";
import ConnectEmployer from "@/components/accounts/ConnectEmployer";
import type { SetupData } from "./SetupWizard";
import { createManualAsset, getPlaidLinkToken, exchangePlaidPublicToken, getPlaidSyncStatus } from "@/lib/api";
import { getIncomeConnections, getIncomeCascadeSummary } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import type { ManualAssetType } from "@/types/portfolio";
import type { IncomeCascadeSummary } from "@/types/income";
import { OB_INPUT, OB_DOLLAR, OB_HEADING, OB_SUBTITLE, OB_LABEL } from "./styles";

const QUICK_ASSETS = [
  { type: "real_estate", label: "Home / Property", icon: Home, placeholder: "e.g. 500,000" },
  { type: "vehicle", label: "Vehicle", icon: Car, placeholder: "e.g. 35,000" },
  { type: "investment", label: "Investment Account", icon: PiggyBank, placeholder: "e.g. 250,000" },
  { type: "other_asset", label: "Other Asset", icon: Landmark, placeholder: "e.g. 10,000" },
];

interface QuickAsset { type: string; name: string; value: string; }

interface Props {
  data: SetupData;
  onRefresh: () => void;
  onSyncStateChange?: (syncing: boolean) => void;
}

export default function StepConnect({ data, onRefresh, onSyncStateChange }: Props) {
  // ── Plaid Bank state ──
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [connectingPlaid, setConnectingPlaid] = useState(false);
  const [plaidSuccess, setPlaidSuccess] = useState<string | null>(null);
  const [plaidError, setPlaidError] = useState<string | null>(null);
  const [syncPhase, setSyncPhase] = useState<string | null>(null);
  const [pollingItemId, setPollingItemId] = useState<number | null>(null);

  // ── Employer state ──
  const [employerConnected, setEmployerConnected] = useState(false);
  const [cascadeSummary, setCascadeSummary] = useState<IncomeCascadeSummary | null>(null);

  // ── Manual assets ──
  const [quickAssets, setQuickAssets] = useState<QuickAsset[]>([]);
  const [showManual, setShowManual] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addType, setAddType] = useState("");
  const [addName, setAddName] = useState("");
  const [addValue, setAddValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check for existing employer connection
  useEffect(() => {
    getIncomeConnections()
      .then((conns) => {
        const active = conns.find((c) => c.status === "active");
        if (active) {
          setEmployerConnected(true);
          loadCascade(active.id);
        }
      })
      .catch(() => {});
  }, []);

  async function loadCascade(connectionId: number) {
    try {
      const summary = await getIncomeCascadeSummary(connectionId);
      setCascadeSummary(summary);
    } catch {
      // Non-critical
    }
  }

  // ── Plaid sync polling ──
  useEffect(() => {
    onSyncStateChange?.(!!pollingItemId);
  }, [pollingItemId, onSyncStateChange]);

  useEffect(() => {
    if (!pollingItemId) return;
    const interval = setInterval(async () => {
      try {
        const status = await getPlaidSyncStatus(pollingItemId);
        setSyncPhase(status.sync_phase);
        if (status.sync_phase === "complete" || status.sync_phase === "error") {
          clearInterval(interval);
          setPollingItemId(null);
          onRefresh();
          if (status.sync_phase === "complete") setSyncPhase(null);
        }
      } catch {
        clearInterval(interval);
        setPollingItemId(null);
        setSyncPhase(null);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [pollingItemId, onRefresh]);

  const onPlaidSuccess = useCallback(
    async (publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => {
      setConnectingPlaid(false);
      const institutionName = metadata?.institution?.name ?? "Unknown Institution";
      try {
        const result = await exchangePlaidPublicToken(publicToken, institutionName);
        const matchMsg = result.accounts_matched
          ? ` (${result.accounts_matched} account${result.accounts_matched > 1 ? "s" : ""} linked)`
          : "";
        setPlaidSuccess(`Connected to ${institutionName}!${matchMsg}`);
        setLinkToken(null);
        setSyncPhase("syncing");
        setPollingItemId(result.id);
        onRefresh();
      } catch (e: unknown) {
        setPlaidError(`Failed to connect ${institutionName}: ${getErrorMessage(e)}`);
      }
    },
    [onRefresh],
  );

  const onPlaidExit = useCallback((err: PlaidLinkError | null) => {
    setConnectingPlaid(false);
    setLinkToken(null);
    if (err) {
      setPlaidError(err.display_message || err.error_message || "Bank connection was cancelled.");
    }
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: onPlaidSuccess,
    onExit: onPlaidExit,
  });

  useEffect(() => {
    if (linkToken && ready) open();
  }, [linkToken, ready, open]);

  async function handleConnectBank() {
    setConnectingPlaid(true);
    setPlaidError(null);
    setPlaidSuccess(null);
    try {
      const tokenData = await getPlaidLinkToken();
      setLinkToken(tokenData.link_token);
    } catch {
      setConnectingPlaid(false);
      setPlaidError("Failed to initialize Plaid Link. Check that PLAID_CLIENT_ID and PLAID_SECRET are set.");
    }
  }

  function handleEmployerComplete() {
    setEmployerConnected(true);
    onRefresh();
    getIncomeConnections()
      .then((conns) => {
        const active = conns.filter((c) => c.status === "active");
        if (active.length > 0) loadCascade(active[active.length - 1].id);
      })
      .catch(() => {});
  }

  async function handleAddAsset() {
    if (!addType || !addName || !addValue) return;
    setSaving(true);
    setError(null);
    try {
      await createManualAsset({
        name: addName,
        asset_type: addType as ManualAssetType,
        current_value: parseFloat(addValue) || 0,
      });
      setQuickAssets([...quickAssets, { type: addType, name: addName, value: addValue }]);
      setAddType(""); setAddName(""); setAddValue("");
      setShowAddForm(false);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  function getAssetIcon(type: string) {
    switch (type) {
      case "real_estate": return Home;
      case "vehicle": return Car;
      case "investment": return PiggyBank;
      default: return Landmark;
    }
  }

  const existingAccounts = data.accounts.filter((a) => a.is_active);

  return (
    <div className="space-y-8">
      <div>
        <h2 className={OB_HEADING}>Connect your accounts</h2>
        <p className={OB_SUBTITLE}>
          Link bank accounts and payroll to auto-import transactions, income, and benefits.
        </p>
      </div>

      {/* ── Bank Accounts Card ── */}
      <div className="rounded-2xl border-2 border-border bg-card overflow-hidden">
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center flex-shrink-0">
              <CreditCard size={24} className="text-accent" />
            </div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-text-primary">Bank Accounts</h3>
              <p className="text-sm text-text-secondary mt-0.5">
                Auto-import transactions, balances, and spending patterns via Plaid
              </p>
            </div>
          </div>

          {/* Existing accounts */}
          {existingAccounts.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {existingAccounts.slice(0, 6).map((a) => (
                <div key={a.id} className="flex items-center justify-between py-1.5">
                  <div className="flex items-center gap-2">
                    <Building2 size={14} className="text-text-muted" />
                    <span className="text-sm text-text-secondary">{a.name}</span>
                    {a.institution && <span className="text-xs text-text-muted">{a.institution}</span>}
                  </div>
                  <Check size={14} className="text-accent" />
                </div>
              ))}
              {existingAccounts.length > 6 && (
                <p className="text-xs text-text-muted">+{existingAccounts.length - 6} more</p>
              )}
            </div>
          )}

          {/* Plaid status banners */}
          {plaidSuccess && (
            <div className="mt-4 bg-green-50 text-green-700 rounded-xl p-3 flex items-start gap-2 border border-green-100">
              <CheckCircle size={16} className="flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium">{plaidSuccess}</p>
                {syncPhase && syncPhase !== "error" && (
                  <div className="flex items-center gap-2 mt-1.5">
                    <Loader2 size={12} className="animate-spin text-accent" />
                    <p className="text-xs text-text-secondary">
                      {syncPhase === "syncing" && "Syncing transactions..."}
                      {syncPhase === "categorizing" && "AI is categorizing your transactions..."}
                    </p>
                  </div>
                )}
              </div>
              <button onClick={() => setPlaidSuccess(null)} className="text-green-400 hover:text-green-600">
                <X size={14} />
              </button>
            </div>
          )}
          {plaidError && (
            <div className="mt-4 bg-red-50 text-red-700 rounded-xl p-3 flex items-center gap-2 border border-red-100">
              <AlertCircle size={16} className="flex-shrink-0" />
              <p className="text-xs flex-1">{plaidError}</p>
              <button onClick={() => setPlaidError(null)} className="text-red-400 hover:text-red-600">
                <X size={14} />
              </button>
            </div>
          )}

          <button
            onClick={handleConnectBank}
            disabled={connectingPlaid}
            className="mt-4 w-full bg-text-primary text-white dark:text-black py-3 rounded-xl text-sm font-semibold hover:bg-text-primary/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {connectingPlaid ? (
              <><Loader2 size={16} className="animate-spin" /> Opening Plaid Link...</>
            ) : existingAccounts.length > 0 ? (
              <><Plus size={16} /> Connect Another Bank</>
            ) : (
              <><CreditCard size={16} /> Connect Bank Accounts</>
            )}
          </button>
        </div>
      </div>

      {/* ── Employer Payroll Card ── */}
      <div className="rounded-2xl border-2 border-border bg-card overflow-hidden">
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-surface flex items-center justify-center flex-shrink-0">
              <Briefcase size={24} className="text-text-secondary" />
            </div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-text-primary">Employer Payroll</h3>
              <p className="text-sm text-text-secondary mt-0.5">
                Auto-fill income, benefits, and tax withholdings from your payroll provider
              </p>
            </div>
          </div>

          {/* Employer connection or cascade */}
          {employerConnected && cascadeSummary ? (
            <div className="mt-4 bg-green-50/50 border border-accent/20 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2">
                <CheckCircle size={16} className="text-accent" />
                <p className="text-sm font-medium text-text-primary">
                  Imported from {cascadeSummary.employer ?? "your employer"}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {cascadeSummary.annual_income != null && cascadeSummary.annual_income > 0 && (
                  <CascadeItem label="Annual Income" value={formatCurrency(cascadeSummary.annual_income, true)} destination="Household" />
                )}
                {cascadeSummary.pay_stubs_imported > 0 && (
                  <CascadeItem label="Pay Stubs" value={`${cascadeSummary.pay_stubs_imported} imported`} destination="Tax Documents" />
                )}
                {cascadeSummary.benefits_detected.length > 0 && (
                  <CascadeItem label="Benefits" value={cascadeSummary.benefits_detected.join(", ")} destination="Benefits" />
                )}
              </div>
            </div>
          ) : employerConnected ? (
            <div className="mt-4 bg-green-50/50 border border-accent/20 rounded-xl p-3 flex items-center gap-2">
              <CheckCircle size={16} className="text-accent" />
              <p className="text-sm font-medium text-text-primary">Employer connected — syncing data...</p>
            </div>
          ) : (
            <div className="mt-4">
              <ConnectEmployer onConnectionComplete={handleEmployerComplete} />
            </div>
          )}
        </div>
      </div>

      {/* ── Manual Assets (collapsible) ── */}
      <div>
        <button
          onClick={() => setShowManual(!showManual)}
          className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-secondary transition-colors"
        >
          {showManual ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          <span className="font-medium">Add assets manually</span>
          <span className="text-xs text-text-muted">(home, car, investments)</span>
        </button>

        {showManual && (
          <div className="mt-4 space-y-3">
            {/* Added assets */}
            {quickAssets.map((a, i) => {
              const Icon = getAssetIcon(a.type);
              return (
                <div key={i} className="flex items-center gap-2 py-2 border-b border-border-light last:border-0">
                  <Icon size={14} className="text-accent" />
                  <span className="text-sm text-text-secondary flex-1">{a.name}</span>
                  <span className="text-sm font-mono text-text-secondary">${parseFloat(a.value).toLocaleString()}</span>
                  <Check size={14} className="text-accent" />
                </div>
              );
            })}

            {showAddForm ? (
              <Card padding="md" className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  {QUICK_ASSETS.map((opt) => {
                    const Icon = opt.icon;
                    const selected = addType === opt.type;
                    return (
                      <button
                        key={opt.type}
                        onClick={() => setAddType(opt.type)}
                        className={`p-3 rounded-xl text-left transition-all flex items-center gap-2 ${
                          selected
                            ? "border-2 border-accent bg-green-50 ring-1 ring-accent/20"
                            : "border-2 border-border hover:border-border"
                        }`}
                      >
                        <Icon size={14} className={selected ? "text-accent" : "text-text-muted"} />
                        <span className={`text-xs font-medium ${selected ? "text-accent" : "text-text-secondary"}`}>
                          {opt.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
                <input
                  type="text"
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  placeholder="Asset name (e.g. Primary Residence)"
                  className={OB_INPUT}
                />
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
                  <input
                    type="number"
                    value={addValue}
                    onChange={(e) => setAddValue(e.target.value)}
                    placeholder={QUICK_ASSETS.find((a) => a.type === addType)?.placeholder || "Current value"}
                    className={OB_DOLLAR}
                  />
                </div>
                {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}
                <div className="flex gap-2">
                  <button
                    onClick={handleAddAsset}
                    disabled={!addType || !addName || !addValue || saving}
                    className="flex items-center gap-1.5 bg-accent text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors"
                  >
                    {saving ? "Saving..." : "Add Asset"}
                  </button>
                  <button
                    onClick={() => { setShowAddForm(false); setError(null); }}
                    className="px-4 py-2.5 text-sm text-text-secondary hover:text-text-secondary transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </Card>
            ) : (
              <button
                onClick={() => setShowAddForm(true)}
                className="flex items-center gap-2 w-full p-4 rounded-xl border-2 border-dashed border-border text-sm text-text-secondary hover:border-border hover:text-text-secondary transition-colors"
              >
                <Plus size={14} />
                Add a manual asset
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CascadeItem({ label, value, destination }: { label: string; value: string; destination: string }) {
  return (
    <div className="bg-card rounded-lg border border-card-border p-3">
      <p className="text-xs font-medium text-text-muted uppercase tracking-wide">{label}</p>
      <p className="text-sm font-medium text-text-primary mt-0.5 font-mono">{value}</p>
      <div className="flex items-center gap-1 mt-1.5">
        <ArrowRight size={9} className="text-accent" />
        <span className="text-xs text-accent font-medium">{destination}</span>
      </div>
    </div>
  );
}
