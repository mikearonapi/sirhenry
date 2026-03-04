"use client";
import { useState, useEffect } from "react";
import { Briefcase, Check, Heart, PiggyBank, Shield } from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData } from "./SetupWizard";
import { getHouseholdBenefits, upsertHouseholdBenefits } from "@/lib/api-household";
import { getErrorMessage } from "@/lib/errors";
import type { BenefitPackageType } from "@/types/household";

const INPUT = "w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white";

interface Props {
  data: SetupData;
  onRefresh: () => void;
}

interface BenefitForm {
  employer_name: string;
  has_401k: boolean;
  employer_match_pct: string;
  has_hsa: boolean;
  has_espp: boolean;
  life_insurance_coverage: string;
  has_health: boolean;
}

const EMPTY_FORM: BenefitForm = {
  employer_name: "",
  has_401k: false,
  employer_match_pct: "",
  has_hsa: false,
  has_espp: false,
  life_insurance_coverage: "",
  has_health: false,
};

export default function StepBenefits({ data, onRefresh }: Props) {
  const household = data.household;
  const married = household?.filing_status === "mfj" || household?.filing_status === "mfs";
  const [activeSpouse, setActiveSpouse] = useState<"a" | "b">("a");
  const [formA, setFormA] = useState<BenefitForm>({ ...EMPTY_FORM });
  const [formB, setFormB] = useState<BenefitForm>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!household) return;
    getHouseholdBenefits(household.id)
      .then((benefits: BenefitPackageType[]) => {
        for (const bp of benefits) {
          const f: BenefitForm = {
            employer_name: bp.employer_name || "",
            has_401k: bp.has_401k,
            employer_match_pct: bp.employer_match_pct?.toString() || "",
            has_hsa: bp.has_hsa,
            has_espp: bp.has_espp,
            life_insurance_coverage: bp.life_insurance_coverage?.toString() || "",
            has_health: (bp.health_premium_monthly ?? 0) > 0,
          };
          if (bp.spouse === "a") setFormA(f);
          else setFormB(f);
        }
        // Pre-fill employer from household if benefit record doesn't have one
        setFormA((prev) => ({
          ...prev,
          employer_name: prev.employer_name || household?.spouse_a_employer || "",
        }));
        if (married) {
          setFormB((prev) => ({
            ...prev,
            employer_name: prev.employer_name || household?.spouse_b_employer || "",
          }));
        }
        setLoaded(true);
      })
      .catch(() => {
        // No saved benefits yet — pre-fill from household data
        if (household?.spouse_a_employer) {
          setFormA((prev) => ({ ...prev, employer_name: prev.employer_name || household.spouse_a_employer || "" }));
        }
        if (married && household?.spouse_b_employer) {
          setFormB((prev) => ({ ...prev, employer_name: prev.employer_name || household.spouse_b_employer || "" }));
        }
        setLoaded(true);
      });
  }, [household, married]);

  const form = activeSpouse === "a" ? formA : formB;
  const setForm = activeSpouse === "a" ? setFormA : setFormB;

  function updateField<K extends keyof BenefitForm>(key: K, value: BenefitForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  async function handleSave() {
    if (!household) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      // Save spouse A
      await upsertHouseholdBenefits(household.id, {
        spouse: "a",
        employer_name: formA.employer_name || null,
        has_401k: formA.has_401k,
        employer_match_pct: formA.employer_match_pct ? parseFloat(formA.employer_match_pct) : null,
        has_hsa: formA.has_hsa,
        has_espp: formA.has_espp,
        life_insurance_coverage: formA.life_insurance_coverage ? parseFloat(formA.life_insurance_coverage) : null,
        health_premium_monthly: formA.has_health ? 1 : null, // flag only
      } as Partial<BenefitPackageType> & { spouse: string });
      // Save spouse B if married
      if (married) {
        await upsertHouseholdBenefits(household.id, {
          spouse: "b",
          employer_name: formB.employer_name || null,
          has_401k: formB.has_401k,
          employer_match_pct: formB.employer_match_pct ? parseFloat(formB.employer_match_pct) : null,
          has_hsa: formB.has_hsa,
          has_espp: formB.has_espp,
          life_insurance_coverage: formB.life_insurance_coverage ? parseFloat(formB.life_insurance_coverage) : null,
          health_premium_monthly: formB.has_health ? 1 : null,
        } as Partial<BenefitPackageType> & { spouse: string });
      }
      setSaved(true);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  if (!household) {
    return (
      <Card padding="md">
        <p className="text-sm text-stone-500">Complete the Household step first to set up benefits.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 font-display">Employer benefits</h2>
        <p className="text-sm text-stone-500 mt-0.5">
          Knowing your benefits helps optimize retirement contributions, HSA strategy, and insurance coverage.
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: 401k Optimization &middot; HSA Strategy &middot; Retirement Projections
        </p>
      </div>

      {/* Spouse toggle */}
      {married && (
        <div className="flex gap-2">
          <button
            onClick={() => setActiveSpouse("a")}
            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
              activeSpouse === "a"
                ? "bg-[#16A34A] text-white"
                : "bg-stone-100 text-stone-600 hover:bg-stone-200"
            }`}
          >
            {household.spouse_a_name || "Spouse A"}
          </button>
          <button
            onClick={() => setActiveSpouse("b")}
            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
              activeSpouse === "b"
                ? "bg-[#16A34A] text-white"
                : "bg-stone-100 text-stone-600 hover:bg-stone-200"
            }`}
          >
            {household.spouse_b_name || "Spouse B"}
          </button>
        </div>
      )}

      {/* Employer */}
      <div>
        <label className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-1.5 block">
          Employer Name
        </label>
        <input
          type="text"
          value={form.employer_name}
          onChange={(e) => updateField("employer_name", e.target.value)}
          placeholder="e.g. Google, JPMorgan"
          className={INPUT}
        />
      </div>

      {/* Quick toggles */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-stone-600 uppercase tracking-wide">
          Available Benefits
        </p>
        <p className="text-[11px] text-stone-400 mb-1">
          Select all that your employer offers.
        </p>

        {/* 401k */}
        <ToggleCard
          icon={PiggyBank}
          label="401(k) / 403(b)"
          desc="Employer-sponsored retirement plan"
          whyItMatters="Drives retirement contribution optimization and employer match capture."
          checked={form.has_401k}
          onChange={(v) => updateField("has_401k", v)}
        >
          {form.has_401k && (
            <div className="mt-3 ml-8">
              <label className="text-xs text-stone-500 mb-1 block">Employer match %</label>
              <input
                type="number"
                value={form.employer_match_pct}
                onChange={(e) => updateField("employer_match_pct", e.target.value)}
                placeholder="e.g. 4"
                className={`${INPUT} max-w-[120px]`}
              />
            </div>
          )}
        </ToggleCard>

        <ToggleCard
          icon={Heart}
          label="HSA (Health Savings Account)"
          desc="Triple tax advantage — pre-tax, tax-free growth, tax-free withdrawals"
          whyItMatters="HSA contributions reduce taxable income and build a healthcare reserve."
          checked={form.has_hsa}
          onChange={(v) => updateField("has_hsa", v)}
        />

        <ToggleCard
          icon={Briefcase}
          label="ESPP (Employee Stock Purchase Plan)"
          desc="Buy company stock at a discount"
          whyItMatters="ESPP discount is essentially free money — tracking helps optimize sell timing."
          checked={form.has_espp}
          onChange={(v) => updateField("has_espp", v)}
        />

        <ToggleCard
          icon={Shield}
          label="Employer Health Insurance"
          desc="Employer-provided medical coverage"
          whyItMatters="Affects insurance gap analysis and premium deduction eligibility."
          checked={form.has_health}
          onChange={(v) => updateField("has_health", v)}
        />
      </div>

      {/* Employer life insurance */}
      <div>
        <label className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-1.5 block">
          Employer Life Insurance Coverage
        </label>
        <p className="text-[11px] text-stone-400 mb-2">
          Often 1-2x salary. This reduces your personal life insurance gap.
        </p>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
          <input
            type="number"
            value={form.life_insurance_coverage}
            onChange={(e) => updateField("life_insurance_coverage", e.target.value)}
            placeholder="e.g. 300,000"
            className="w-full rounded-lg border border-stone-200 pl-7 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white"
          />
        </div>
      </div>

      {/* Save */}
      {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full flex items-center justify-center gap-2 bg-[#16A34A] text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm disabled:opacity-50 transition-colors"
      >
        {saving ? "Saving..." : saved ? <><Check size={14} /> Saved</> : "Save Benefits"}
      </button>
    </div>
  );
}

// Toggle card sub-component
function ToggleCard({
  icon: Icon,
  label,
  desc,
  whyItMatters,
  checked,
  onChange,
  children,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  desc: string;
  whyItMatters: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={`p-3 rounded-lg border transition-all ${
        checked
          ? "border-[#16A34A]/30 bg-green-50/50"
          : "border-stone-200 bg-white"
      }`}
    >
      <button
        onClick={() => onChange(!checked)}
        className="flex items-start gap-3 w-full text-left"
      >
        <div
          className={`w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 transition-colors flex-shrink-0 ${
            checked
              ? "bg-[#16A34A] border-[#16A34A]"
              : "border-stone-300 bg-white"
          }`}
        >
          {checked && <Check size={12} className="text-white" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Icon size={14} className={checked ? "text-[#16A34A]" : "text-stone-400"} />
            <span className={`text-sm font-medium ${checked ? "text-stone-800" : "text-stone-600"}`}>
              {label}
            </span>
          </div>
          <p className="text-[11px] text-stone-400 mt-0.5">{desc}</p>
          {checked && (
            <p className="text-[11px] text-[#16A34A]/70 mt-1 italic">{whyItMatters}</p>
          )}
        </div>
      </button>
      {children}
    </div>
  );
}
