"use client";
import { useState, useEffect } from "react";
import {
  Briefcase, Check, Heart, PiggyBank, Shield, Plus, MessageCircle,
  Car, Home, Umbrella, Eye, SmilePlus, Clock, PawPrint, HelpCircle, Activity,
} from "lucide-react";
import Card from "@/components/ui/Card";
import { AutoFilledIndicator } from "@/components/ui/AutoFilledIndicator";
import type { SetupData, RegisterSaveFn } from "./SetupWizard";
import { getHouseholdBenefits, upsertHouseholdBenefits } from "@/lib/api-household";
import { getSmartDefaults } from "@/lib/api";
import { createInsurancePolicy } from "@/lib/api-insurance";
import { getErrorMessage } from "@/lib/errors";
import SirHenryName from "@/components/ui/SirHenryName";
import type { BenefitPackageType } from "@/types/household";
import type { BenefitsDefaults } from "@/types/smart-defaults";
import type { InsurancePolicyType } from "@/types/insurance";
import { OB_INPUT, OB_HEADING, OB_SUBTITLE, OB_LABEL } from "./styles";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

// ── Benefits types ──
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
  employer_name: "", has_401k: false, employer_match_pct: "",
  has_hsa: false, has_espp: false, life_insurance_coverage: "", has_health: false,
};

// ── Insurance types ──
const POLICY_TYPES: {
  type: InsurancePolicyType;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}[] = [
  { type: "health", label: "Health", icon: Heart },
  { type: "life", label: "Life", icon: Shield },
  { type: "disability", label: "Disability", icon: Activity },
  { type: "auto", label: "Auto", icon: Car },
  { type: "home", label: "Home / Renters", icon: Home },
  { type: "umbrella", label: "Umbrella", icon: Umbrella },
  { type: "vision", label: "Vision", icon: Eye },
  { type: "dental", label: "Dental", icon: SmilePlus },
  { type: "ltc", label: "Long-Term Care", icon: Clock },
  { type: "pet", label: "Pet", icon: PawPrint },
  { type: "other", label: "Other", icon: HelpCircle },
];

interface Props {
  data: SetupData;
  onRefresh: () => void;
  registerSave?: RegisterSaveFn;
}

export default function StepBenefitsCoverage({ data, onRefresh, registerSave }: Props) {
  const household = data.household;
  const married = household?.filing_status === "mfj" || household?.filing_status === "mfs";

  // ── Benefits state ──
  const [activeSpouse, setActiveSpouse] = useState<"a" | "b">("a");
  const [formA, setFormA] = useState<BenefitForm>({ ...EMPTY_FORM });
  const [formB, setFormB] = useState<BenefitForm>({ ...EMPTY_FORM });
  const [autoFilledFields, setAutoFilledFields] = useState<Set<keyof BenefitForm>>(new Set());
  const [benefitsLoaded, setBenefitsLoaded] = useState(false);

  // ── Insurance state ──
  const [selectedPolicies, setSelectedPolicies] = useState<Set<InsurancePolicyType>>(() => {
    const existing = new Set<InsurancePolicyType>();
    for (const p of data.policies) { if (p.is_active) existing.add(p.policy_type); }
    return existing;
  });
  const [expandedType, setExpandedType] = useState<InsurancePolicyType | null>(null);
  const [provider, setProvider] = useState("");
  const [savedPolicies, setSavedPolicies] = useState<{ type: InsurancePolicyType; provider: string }[]>([]);
  const [insuranceSaving, setInsuranceSaving] = useState(false);

  // ── Shared state ──
  const [error, setError] = useState<string | null>(null);

  // Fetch smart defaults
  useEffect(() => {
    getSmartDefaults()
      .then((sd) => {
        const benefits: BenefitsDefaults = sd.benefits;
        const hasPayrollData = benefits.has_401k || benefits.has_hsa || benefits.has_espp || benefits.match_pct > 0;
        if (!hasPayrollData) return;
        const filled = new Set<keyof BenefitForm>();
        setFormA((prev) => {
          const updated = { ...prev };
          if (benefits.has_401k && !prev.has_401k) { updated.has_401k = true; filled.add("has_401k"); }
          if (benefits.match_pct > 0 && !prev.employer_match_pct) { updated.employer_match_pct = benefits.match_pct.toString(); filled.add("employer_match_pct"); }
          if (benefits.has_hsa && !prev.has_hsa) { updated.has_hsa = true; filled.add("has_hsa"); }
          if (benefits.has_espp && !prev.has_espp) { updated.has_espp = true; filled.add("has_espp"); }
          if (benefits.health_premium_monthly > 0 && !prev.has_health) { updated.has_health = true; filled.add("has_health"); }
          return updated;
        });
        setAutoFilledFields(filled);
      })
      .catch(() => {});
  }, []);

  // Load existing benefits
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
        setFormA((prev) => ({ ...prev, employer_name: prev.employer_name || household?.spouse_a_employer || "" }));
        if (married) {
          setFormB((prev) => ({ ...prev, employer_name: prev.employer_name || household?.spouse_b_employer || "" }));
        }
        setBenefitsLoaded(true);
      })
      .catch(() => {
        if (household?.spouse_a_employer) setFormA((prev) => ({ ...prev, employer_name: prev.employer_name || household.spouse_a_employer || "" }));
        if (married && household?.spouse_b_employer) setFormB((prev) => ({ ...prev, employer_name: prev.employer_name || household.spouse_b_employer || "" }));
        setBenefitsLoaded(true);
      });
  }, [household, married]);

  const form = activeSpouse === "a" ? formA : formB;
  const setForm = activeSpouse === "a" ? setFormA : setFormB;

  function updateField<K extends keyof BenefitForm>(key: K, value: BenefitForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (autoFilledFields.has(key)) {
      setAutoFilledFields((prev) => { const next = new Set(prev); next.delete(key); return next; });
    }
  }

  // Combined save: benefits + new insurance policies
  async function handleSave() {
    if (!household) return;
    setError(null);
    try {
      // Save benefits
      await upsertHouseholdBenefits(household.id, {
        spouse: "a",
        employer_name: formA.employer_name || null,
        has_401k: formA.has_401k,
        employer_match_pct: formA.employer_match_pct ? parseFloat(formA.employer_match_pct) : null,
        has_hsa: formA.has_hsa, has_espp: formA.has_espp,
        life_insurance_coverage: formA.life_insurance_coverage ? parseFloat(formA.life_insurance_coverage) : null,
        health_premium_monthly: formA.has_health ? 1 : null,
      } as Partial<BenefitPackageType> & { spouse: string });
      if (married) {
        await upsertHouseholdBenefits(household.id, {
          spouse: "b",
          employer_name: formB.employer_name || null,
          has_401k: formB.has_401k,
          employer_match_pct: formB.employer_match_pct ? parseFloat(formB.employer_match_pct) : null,
          has_hsa: formB.has_hsa, has_espp: formB.has_espp,
          life_insurance_coverage: formB.life_insurance_coverage ? parseFloat(formB.life_insurance_coverage) : null,
          health_premium_monthly: formB.has_health ? 1 : null,
        } as Partial<BenefitPackageType> & { spouse: string });
      }
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
      throw e;
    }
  }

  useEffect(() => {
    if (registerSave) registerSave(household ? handleSave : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registerSave, household, formA, formB, married]);

  // Insurance inline save
  const alreadySaved = (type: InsurancePolicyType) =>
    data.policies.some((p) => p.policy_type === type && p.is_active) ||
    savedPolicies.some((p) => p.type === type);

  async function handleSavePolicy(type: InsurancePolicyType) {
    setInsuranceSaving(true);
    setError(null);
    try {
      await createInsurancePolicy({
        policy_type: type,
        provider: provider || null,
        household_id: household?.id ?? null,
        is_active: true,
      });
      setSavedPolicies([...savedPolicies, { type, provider }]);
      setProvider(""); setExpandedType(null);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setInsuranceSaving(false);
    }
  }

  if (!household) {
    return (
      <Card padding="md">
        <p className="text-sm text-text-secondary">Complete the About You step first to set up benefits.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className={OB_HEADING}>Benefits & coverage</h2>
        <p className={OB_SUBTITLE}>
          Employer benefits and insurance drive retirement optimization, HSA strategy, and coverage gap analysis.
        </p>
      </div>

      {/* ── Section 1: Employer Benefits ── */}
      <div className="space-y-5">
        <h3 className="text-base font-semibold text-text-primary flex items-center gap-2">
          <Briefcase size={16} className="text-text-secondary" />
          Employer Benefits
        </h3>

        {/* Spouse toggle */}
        {married && (
          <div className="flex gap-2">
            {(["a", "b"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setActiveSpouse(s)}
                className={`flex-1 py-2.5 px-3 rounded-xl text-sm font-medium transition-colors ${
                  activeSpouse === s
                    ? "bg-text-primary text-white dark:text-black"
                    : "bg-surface text-text-secondary hover:bg-surface-hover"
                }`}
              >
                {s === "a" ? (household.spouse_a_name || "Spouse A") : (household.spouse_b_name || "Spouse B")}
              </button>
            ))}
          </div>
        )}

        {/* Employer name */}
        <div>
          <label className={OB_LABEL}>Employer Name</label>
          <input
            type="text"
            value={form.employer_name}
            onChange={(e) => updateField("employer_name", e.target.value)}
            placeholder="e.g. Google, JPMorgan"
            className={OB_INPUT}
          />
        </div>

        {/* Benefits toggles */}
        <div className="space-y-2">
          <ToggleCard icon={PiggyBank} label="401(k) / 403(b)" desc="Employer-sponsored retirement plan"
            checked={form.has_401k} onChange={(v) => updateField("has_401k", v)} autoFilled={autoFilledFields.has("has_401k")}>
            {form.has_401k && (
              <div className="mt-3 ml-8">
                <div className="flex items-center gap-2 mb-1">
                  <label className="text-xs text-text-secondary">Employer match %</label>
                  {autoFilledFields.has("employer_match_pct") && <AutoFilledIndicator source="payroll connection" />}
                </div>
                <input type="number" value={form.employer_match_pct}
                  onChange={(e) => updateField("employer_match_pct", e.target.value)}
                  placeholder="e.g. 4" className={`${OB_INPUT} max-w-[140px]`} />
              </div>
            )}
          </ToggleCard>
          <ToggleCard icon={Heart} label="HSA" desc="Triple tax advantage — pre-tax, tax-free growth & withdrawals"
            checked={form.has_hsa} onChange={(v) => updateField("has_hsa", v)} autoFilled={autoFilledFields.has("has_hsa")} />
          <ToggleCard icon={Briefcase} label="ESPP" desc="Buy company stock at a discount"
            checked={form.has_espp} onChange={(v) => updateField("has_espp", v)} autoFilled={autoFilledFields.has("has_espp")} />
          <ToggleCard icon={Shield} label="Health Insurance" desc="Employer-provided medical coverage"
            checked={form.has_health} onChange={(v) => updateField("has_health", v)} autoFilled={autoFilledFields.has("has_health")} />
        </div>

        {/* Life insurance */}
        <div>
          <label className={OB_LABEL}>Employer Life Insurance Coverage</label>
          <p className="text-xs text-text-muted mb-2">Often 1-2x salary. Reduces your personal life insurance gap.</p>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
            <input type="number" value={form.life_insurance_coverage}
              onChange={(e) => updateField("life_insurance_coverage", e.target.value)}
              placeholder="e.g. 300,000"
              className="w-full rounded-xl border-2 border-border pl-8 pr-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent bg-card" />
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* ── Section 2: Personal Insurance ── */}
      <div className="space-y-5">
        <h3 className="text-base font-semibold text-text-primary flex items-center gap-2">
          <Shield size={16} className="text-text-secondary" />
          Personal Insurance
        </h3>
        <p className="text-sm text-text-secondary -mt-2">
          Select policies you have for coverage gap analysis.
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {POLICY_TYPES.map((pt) => {
            const Icon = pt.icon;
            const isSelected = selectedPolicies.has(pt.type);
            const isSaved = alreadySaved(pt.type);
            const isExpanded = expandedType === pt.type;

            return (
              <div key={pt.type} className={isExpanded ? "col-span-2 sm:col-span-3" : ""}>
                <button
                  onClick={() => {
                    const next = new Set(selectedPolicies);
                    if (next.has(pt.type)) next.delete(pt.type);
                    else next.add(pt.type);
                    setSelectedPolicies(next);
                    if (!isSelected && !isSaved) { setExpandedType(pt.type); setProvider(""); }
                    else if (isExpanded) setExpandedType(null);
                  }}
                  className={`w-full p-3 rounded-xl transition-all text-left flex items-center gap-2 ${
                    isSelected || isSaved
                      ? "border-2 border-accent bg-green-50"
                      : "border-2 border-border bg-card hover:border-border"
                  }`}
                >
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                    isSelected || isSaved ? "bg-accent border-accent" : "border-text-muted bg-card"
                  }`}>
                    {(isSelected || isSaved) && <Check size={10} className="text-white" />}
                  </div>
                  <Icon size={14} className={isSelected || isSaved ? "text-accent" : "text-text-muted"} />
                  <span className={`text-xs font-medium ${isSelected || isSaved ? "text-text-primary" : "text-text-secondary"}`}>
                    {pt.label}
                  </span>
                  {isSaved && (
                    <span className="text-xs text-accent font-medium bg-green-100 px-1.5 py-0.5 rounded ml-auto">
                      Saved
                    </span>
                  )}
                </button>
                {isExpanded && !isSaved && (
                  <div className="mt-2 mb-1 flex items-center gap-2">
                    <input type="text" value={provider} onChange={(e) => setProvider(e.target.value)}
                      placeholder="Provider name (optional)" className={`${OB_INPUT} flex-1`} autoFocus />
                    <button onClick={() => handleSavePolicy(pt.type)} disabled={insuranceSaving}
                      className="flex items-center gap-1 bg-accent text-white px-3 py-2.5 rounded-xl text-xs font-medium hover:bg-accent-hover disabled:opacity-50 whitespace-nowrap transition-colors">
                      <Plus size={12} /> Add
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <button type="button"
          onClick={() => askHenry("Based on my income, dependents, and assets, do I have adequate insurance coverage? What gaps should I address?")}
          className="flex items-center gap-1 text-xs text-accent hover:underline">
          <MessageCircle size={10} />
          Want a coverage review? Ask <SirHenryName />
        </button>
      </div>

      {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{error}</p>}
    </div>
  );
}

// ── Toggle Card sub-component ──
function ToggleCard({
  icon: Icon, label, desc, checked, onChange, children, autoFilled = false,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string; desc: string; checked: boolean;
  onChange: (v: boolean) => void; children?: React.ReactNode; autoFilled?: boolean;
}) {
  return (
    <div className={`p-4 rounded-xl border-2 transition-all ${
      checked ? "border-accent/30 bg-green-50/50" : "border-border bg-card"
    }`}>
      <button onClick={() => onChange(!checked)} className="flex items-start gap-3 w-full text-left">
        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 transition-colors flex-shrink-0 ${
          checked ? "bg-accent border-accent" : "border-text-muted bg-card"
        }`}>
          {checked && <Check size={12} className="text-white" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Icon size={14} className={checked ? "text-accent" : "text-text-muted"} />
            <span className={`text-sm font-medium ${checked ? "text-text-primary" : "text-text-secondary"}`}>{label}</span>
            {autoFilled && <AutoFilledIndicator source="payroll connection" />}
          </div>
          <p className="text-xs text-text-muted mt-0.5">{desc}</p>
        </div>
      </button>
      {children}
    </div>
  );
}
