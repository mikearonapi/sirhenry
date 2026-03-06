"use client";
import { useState } from "react";
import {
  Heart, Shield, Activity, Car, Home, Umbrella,
  Eye, SmilePlus, Clock, PawPrint, HelpCircle,
  Check, Plus, MessageCircle,
} from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData } from "./SetupWizard";
import { createInsurancePolicy } from "@/lib/api-insurance";
import { getErrorMessage } from "@/lib/errors";
import SirHenryName from "@/components/ui/SirHenryName";
import type { InsurancePolicyType } from "@/types/insurance";

const INPUT = "w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

const POLICY_TYPES: {
  type: InsurancePolicyType;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  why: string;
}[] = [
  { type: "health", label: "Health", icon: Heart, why: "Gap analysis, HSA/FSA coordination, premium tracking" },
  { type: "life", label: "Life", icon: Shield, why: "Coverage adequacy vs income replacement needs" },
  { type: "disability", label: "Disability", icon: Activity, why: "Income protection gap, STD/LTD coordination" },
  { type: "auto", label: "Auto", icon: Car, why: "Liability coverage, renewal tracking" },
  { type: "home", label: "Home / Renters", icon: Home, why: "Property protection, liability coverage" },
  { type: "umbrella", label: "Umbrella", icon: Umbrella, why: "Excess liability — recommended when net worth > $300k" },
  { type: "vision", label: "Vision", icon: Eye, why: "Premium tracking, FSA-eligible expenses" },
  { type: "dental", label: "Dental", icon: SmilePlus, why: "Premium tracking, FSA-eligible expenses" },
  { type: "ltc", label: "Long-Term Care", icon: Clock, why: "Retirement healthcare planning" },
  { type: "pet", label: "Pet", icon: PawPrint, why: "Premium tracking" },
  { type: "other", label: "Other", icon: HelpCircle, why: "E&O, business liability, etc." },
];

interface Props {
  data: SetupData;
  onRefresh: () => void;
}

interface QuickPolicy {
  type: InsurancePolicyType;
  provider: string;
}

export default function StepInsurance({ data, onRefresh }: Props) {
  const [selected, setSelected] = useState<Set<InsurancePolicyType>>(() => {
    const existing = new Set<InsurancePolicyType>();
    for (const p of data.policies) {
      if (p.is_active) existing.add(p.policy_type);
    }
    return existing;
  });
  const [expandedType, setExpandedType] = useState<InsurancePolicyType | null>(null);
  const [provider, setProvider] = useState("");
  const [savedPolicies, setSavedPolicies] = useState<QuickPolicy[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleType(type: InsurancePolicyType) {
    const next = new Set(selected);
    if (next.has(type)) {
      next.delete(type);
    } else {
      next.add(type);
    }
    setSelected(next);
  }

  const alreadySaved = (type: InsurancePolicyType) =>
    data.policies.some((p) => p.policy_type === type && p.is_active) ||
    savedPolicies.some((p) => p.type === type);

  async function handleSavePolicy(type: InsurancePolicyType) {
    setSaving(true);
    setError(null);
    try {
      await createInsurancePolicy({
        policy_type: type,
        provider: provider || null,
        household_id: data.household?.id ?? null,
        is_active: true,
      });
      setSavedPolicies([...savedPolicies, { type, provider }]);
      setProvider("");
      setExpandedType(null);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 font-display">Insurance coverage</h2>
        <p className="text-sm text-stone-500 mt-0.5">
          Select which policies you have. This powers gap analysis to find where you may be under- or over-insured.
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: Coverage Gap Analysis &middot; Premium Optimization
        </p>
      </div>

      <div className="space-y-2">
        {POLICY_TYPES.map((pt) => {
          const Icon = pt.icon;
          const isSelected = selected.has(pt.type);
          const isSaved = alreadySaved(pt.type);
          const isExpanded = expandedType === pt.type;

          return (
            <div key={pt.type}>
              <button
                onClick={() => {
                  toggleType(pt.type);
                  if (!isSelected && !isSaved) {
                    setExpandedType(pt.type);
                    setProvider("");
                  } else if (isExpanded) {
                    setExpandedType(null);
                  }
                }}
                className={`w-full p-3 rounded-lg border transition-all text-left flex items-center gap-3 ${
                  isSelected || isSaved
                    ? "border-[#16A34A]/30 bg-green-50/50"
                    : "border-stone-200 bg-white hover:border-stone-300"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                    isSelected || isSaved
                      ? "bg-[#16A34A] border-[#16A34A]"
                      : "border-stone-300 bg-white"
                  }`}
                >
                  {(isSelected || isSaved) && <Check size={12} className="text-white" />}
                </div>
                <Icon size={16} className={isSelected || isSaved ? "text-[#16A34A]" : "text-stone-400"} />
                <div className="flex-1 min-w-0">
                  <span className={`text-sm font-medium ${isSelected || isSaved ? "text-stone-800" : "text-stone-600"}`}>
                    {pt.label}
                  </span>
                  <p className="text-[11px] text-stone-400">{pt.why}</p>
                </div>
                {isSaved && (
                  <span className="text-[10px] text-[#16A34A] font-medium bg-green-100 px-1.5 py-0.5 rounded">
                    Saved
                  </span>
                )}
              </button>

              {/* Inline add provider */}
              {isExpanded && !isSaved && (
                <div className="ml-8 mt-2 mb-1 flex items-center gap-2">
                  <input
                    type="text"
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    placeholder="Provider name (optional)"
                    className={`${INPUT} flex-1`}
                    autoFocus
                  />
                  <button
                    onClick={() => handleSavePolicy(pt.type)}
                    disabled={saving}
                    className="flex items-center gap-1 bg-[#16A34A] text-white px-3 py-2 rounded-lg text-xs font-medium hover:bg-[#15803d] disabled:opacity-50 whitespace-nowrap transition-colors"
                  >
                    <Plus size={12} /> Add
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={() => askHenry("Based on my income, dependents, and assets, do I have adequate insurance coverage? What gaps should I address?")}
        className="flex items-center gap-1 text-[11px] text-[#16A34A] hover:underline"
      >
        <MessageCircle size={10} />
        Want a coverage review? Ask <SirHenryName />
      </button>

      {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

      <Card padding="sm" className="bg-stone-50 border-stone-100">
        <p className="text-[11px] text-stone-500">
          You can add full details (coverage amounts, premiums, renewal dates) on the{" "}
          <a href="/insurance" className="text-[#16A34A] hover:underline">Insurance page</a> anytime.
          For now, just tell us what you have.
        </p>
      </Card>
    </div>
  );
}
