"use client";
import { useState } from "react";
import { Building2, Plus, Check, Landmark, CreditCard, Home, Car, PiggyBank, ExternalLink } from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData } from "./SetupWizard";
import { createManualAsset } from "@/lib/api-assets";
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

      {/* Plaid link CTA */}
      <a
        href="/accounts"
        className="block"
      >
        <Card padding="md" hover className="border-dashed border-[#16A34A]/30 bg-green-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#16A34A]/10 flex items-center justify-center">
              <CreditCard size={20} className="text-[#16A34A]" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-stone-800">
                Connect bank accounts via Plaid
              </p>
              <p className="text-xs text-stone-500 mt-0.5">
                Automatically imports transactions, balances, and account details. Go to Accounts page to connect.
              </p>
            </div>
            <ExternalLink size={14} className="text-stone-400" />
          </div>
        </Card>
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
            {error && <p className="text-xs text-red-600">{error}</p>}
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
