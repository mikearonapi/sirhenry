"use client";
import { useState, useCallback, useEffect } from "react";
import {
  Building2, Plus, Check, Landmark, CreditCard, Home, Car,
  PiggyBank, ExternalLink, CheckCircle, Loader2, AlertCircle, X,
} from "lucide-react";
import { usePlaidLink } from "react-plaid-link";
import type { PlaidLinkOnSuccessMetadata, PlaidLinkError } from "react-plaid-link";
import Card from "@/components/ui/Card";
import type { SetupData } from "./SetupWizard";
import { createManualAsset, getPlaidLinkToken, exchangePlaidPublicToken } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import type { ManualAssetType } from "@/types/portfolio";

const INPUT = "w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white";
const DOLLAR = "w-full rounded-lg border border-stone-200 pl-7 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white";

const QUICK_ASSETS = [
  { type: "real_estate", label: "Home / Property", icon: Home, placeholder: "e.g. 500,000" },
  { type: "vehicle", label: "Vehicle", icon: Car, placeholder: "e.g. 35,000" },
  { type: "investment", label: "Investment Account", icon: PiggyBank, placeholder: "e.g. 250,000" },
  { type: "other_asset", label: "Other Asset", icon: Landmark, placeholder: "e.g. 10,000" },
];

interface Props {
  data: SetupData;
  onRefresh: () => void;
}

interface QuickAsset {
  type: string;
  name: string;
  value: string;
}

export default function StepAccounts({ data, onRefresh }: Props) {
  const [quickAssets, setQuickAssets] = useState<QuickAsset[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addType, setAddType] = useState("");
  const [addName, setAddName] = useState("");
  const [addValue, setAddValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Plaid Link state
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [connectingPlaid, setConnectingPlaid] = useState(false);
  const [plaidSuccess, setPlaidSuccess] = useState<string | null>(null);
  const [plaidError, setPlaidError] = useState<string | null>(null);

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

  const existingAccounts = data.accounts.filter((a) => a.is_active);
  const hasAccounts = existingAccounts.length > 0 || quickAssets.length > 0;

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
      setAddType("");
      setAddName("");
      setAddValue("");
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

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 font-display">Your accounts & assets</h2>
        <p className="text-sm text-stone-500 mt-0.5">
          These form your net worth picture and help track cash flow, investments, and debt.
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: Cash Flow Tracking &middot; Budget Insights &middot; Net Worth Dashboard
        </p>
      </div>

      {/* Existing accounts */}
      {existingAccounts.length > 0 && (
        <Card padding="md">
          <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-3">
            Already connected ({existingAccounts.length})
          </p>
          <div className="space-y-2">
            {existingAccounts.slice(0, 6).map((a) => (
              <div key={a.id} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2">
                  <Building2 size={14} className="text-stone-400" />
                  <span className="text-sm text-stone-700">{a.name}</span>
                  {a.institution && (
                    <span className="text-xs text-stone-400">{a.institution}</span>
                  )}
                </div>
                <Check size={14} className="text-[#16A34A]" />
              </div>
            ))}
            {existingAccounts.length > 6 && (
              <p className="text-xs text-stone-400">+{existingAccounts.length - 6} more</p>
            )}
          </div>
        </Card>
      )}

      {/* Plaid Link inline */}
      {plaidSuccess && (
        <div className="bg-green-50 text-green-700 rounded-xl p-3 flex items-center gap-2 border border-green-100">
          <CheckCircle size={16} className="flex-shrink-0" />
          <p className="text-sm font-medium flex-1">{plaidSuccess}</p>
          <button onClick={() => setPlaidSuccess(null)} className="text-green-400 hover:text-green-600">
            <X size={14} />
          </button>
        </div>
      )}
      {plaidError && (
        <div className="bg-red-50 text-red-700 rounded-xl p-3 flex items-center gap-2 border border-red-100">
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
        className="w-full block"
      >
        <Card padding="md" hover className="border-dashed border-[#16A34A]/30 bg-green-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#16A34A]/10 flex items-center justify-center">
              {connectingPlaid ? (
                <Loader2 size={20} className="text-[#16A34A] animate-spin" />
              ) : (
                <CreditCard size={20} className="text-[#16A34A]" />
              )}
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-stone-800">
                {connectingPlaid ? "Opening Plaid Link..." : "Connect bank accounts via Plaid"}
              </p>
              <p className="text-xs text-stone-500 mt-0.5">
                Automatically imports transactions, balances, and account details
              </p>
            </div>
          </div>
        </Card>
      </button>

      {/* Secondary link to full Accounts page */}
      <a
        href="/accounts"
        className="flex items-center justify-center gap-1.5 text-xs text-stone-400 hover:text-stone-600 transition-colors"
      >
        <ExternalLink size={11} />
        Or manage accounts on the full Accounts page
      </a>

      {/* Quick add section */}
      <div>
        <p className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-3">
          Quick-add manual assets
        </p>
        <p className="text-[11px] text-stone-400 mb-3">
          Add assets not in a bank (home, car, 401k, crypto). These complete your net worth picture.
        </p>

        {/* Added assets */}
        {quickAssets.map((a, i) => {
          const Icon = getAssetIcon(a.type);
          return (
            <div key={i} className="flex items-center gap-2 py-2 border-b border-stone-50 last:border-0">
              <Icon size={14} className="text-[#16A34A]" />
              <span className="text-sm text-stone-700 flex-1">{a.name}</span>
              <span className="text-sm font-mono text-stone-600">
                ${parseFloat(a.value).toLocaleString()}
              </span>
              <Check size={14} className="text-[#16A34A]" />
            </div>
          );
        })}

        {/* Add form */}
        {showAddForm ? (
          <Card padding="md" className="space-y-3 mt-2">
            <div className="grid grid-cols-2 gap-2">
              {QUICK_ASSETS.map((opt) => {
                const Icon = opt.icon;
                const selected = addType === opt.type;
                return (
                  <button
                    key={opt.type}
                    onClick={() => setAddType(opt.type)}
                    className={`p-2.5 rounded-lg border text-left transition-all flex items-center gap-2 ${
                      selected
                        ? "border-[#16A34A] bg-green-50 ring-1 ring-[#16A34A]/20"
                        : "border-stone-200 hover:border-stone-300"
                    }`}
                  >
                    <Icon size={14} className={selected ? "text-[#16A34A]" : "text-stone-400"} />
                    <span className={`text-xs font-medium ${selected ? "text-[#16A34A]" : "text-stone-600"}`}>
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
              className={INPUT}
            />
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
              <input
                type="number"
                value={addValue}
                onChange={(e) => setAddValue(e.target.value)}
                placeholder={QUICK_ASSETS.find((a) => a.type === addType)?.placeholder || "Current value"}
                className={DOLLAR}
              />
            </div>
            {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={handleAddAsset}
                disabled={!addType || !addName || !addValue || saving}
                className="flex items-center gap-1.5 bg-[#16A34A] text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-[#15803d] disabled:opacity-50 transition-colors"
              >
                {saving ? "Saving..." : "Add Asset"}
              </button>
              <button
                onClick={() => { setShowAddForm(false); setError(null); }}
                className="px-3 py-2 text-sm text-stone-500 hover:text-stone-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </Card>
        ) : (
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 w-full p-3 rounded-lg border border-dashed border-stone-200 text-sm text-stone-500 hover:border-stone-300 hover:text-stone-600 transition-colors mt-2"
          >
            <Plus size={14} />
            Add a manual asset
          </button>
        )}
      </div>
    </div>
  );
}
