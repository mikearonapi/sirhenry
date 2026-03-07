"use client";
import { useCallback, useEffect, useState } from "react";
import { Loader2, AlertTriangle, Briefcase } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import {
  getHouseholdBenefits, upsertHouseholdBenefits,
  getFamilyMembers, getManualAssets,
} from "@/lib/api";
import type {
  HouseholdProfile, BenefitPackageType, FamilyMember, ManualAsset,
} from "@/types/api";
import BenefitsPlanForm from "./BenefitsPlanForm";
import BenefitsPlanComparison from "./BenefitsPlanComparison";
import ContributionHeadroomCard from "./ContributionHeadroomCard";

// ---------------------------------------------------------------------------
// BenefitsTab — main orchestrator
// ---------------------------------------------------------------------------

export interface BenefitsTabProps {
  profile: HouseholdProfile | null;
}

export default function BenefitsTab({ profile }: BenefitsTabProps) {
  const [benefits, setBenefits] = useState<BenefitPackageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<"a" | "b" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeSpouse, setActiveSpouse] = useState<"a" | "b">("a");
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [assets, setAssets] = useState<ManualAsset[]>([]);

  const loadBenefits = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    try {
      const [data, mems, assetData] = await Promise.all([
        getHouseholdBenefits(profile.id),
        getFamilyMembers(profile.id),
        getManualAssets().catch(() => []),
      ]);
      setBenefits(Array.isArray(data) ? data : []);
      setFamilyMembers(Array.isArray(mems) ? mems : []);
      setAssets(Array.isArray(assetData) ? assetData : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [profile]);

  useEffect(() => { loadBenefits(); }, [loadBenefits]);

  const initForm = (spouse: "a" | "b") => {
    const existing = benefits.find((b) => b.spouse === spouse);
    return {
      employer_name: existing?.employer_name || "",
      has_401k: existing?.has_401k || false,
      employer_match_pct: existing?.employer_match_pct || 0,
      employer_match_limit_pct: existing?.employer_match_limit_pct || 6,
      has_roth_401k: existing?.has_roth_401k || false,
      has_mega_backdoor: existing?.has_mega_backdoor || false,
      annual_401k_contribution: existing?.annual_401k_contribution || 0,
      has_hsa: existing?.has_hsa || false,
      hsa_employer_contribution: existing?.hsa_employer_contribution || 0,
      has_fsa: existing?.has_fsa || false,
      has_dep_care_fsa: existing?.has_dep_care_fsa || false,
      health_premium_monthly: existing?.health_premium_monthly || 0,
      dental_vision_monthly: existing?.dental_vision_monthly || 0,
      life_insurance_coverage: existing?.life_insurance_coverage || 0,
      std_coverage_pct: existing?.std_coverage_pct || null,
      ltd_coverage_pct: existing?.ltd_coverage_pct || null,
      commuter_monthly_limit: existing?.commuter_monthly_limit || 0,
      tuition_reimbursement_annual: existing?.tuition_reimbursement_annual || 0,
      has_espp: existing?.has_espp || false,
      espp_discount_pct: existing?.espp_discount_pct || 15,
      open_enrollment_start: existing?.open_enrollment_start || "",
      open_enrollment_end: existing?.open_enrollment_end || "",
      notes: existing?.notes || "",
    };
  };

  const [formA, setFormA] = useState(() => initForm("a"));
  const [formB, setFormB] = useState(() => initForm("b"));

  useEffect(() => {
    setFormA(initForm("a"));
    setFormB(initForm("b"));
  }, [benefits]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave(spouse: "a" | "b") {
    if (!profile) return;
    setSaving(spouse);
    setError(null);
    try {
      const form = spouse === "a" ? formA : formB;
      await upsertHouseholdBenefits(profile.id, { ...form, spouse });
      await loadBenefits();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(null);
    }
  }

  if (!profile) {
    return (
      <div className="text-center py-12">
        <Briefcase size={32} className="mx-auto text-text-muted mb-3" />
        <p className="text-sm text-text-secondary">Create a household profile on the Profile tab first.</p>
      </div>
    );
  }

  const spouseName = (s: "a" | "b") => {
    const rel = s === "a" ? "self" : "spouse";
    const fromFamily = familyMembers.find((m) => m.relationship === rel)?.name;
    if (fromFamily) return fromFamily;
    return s === "a" ? (profile.spouse_a_name || "Earner A") : (profile.spouse_b_name || "Earner B");
  };

  const benA = benefits.find((b) => b.spouse === "a");
  const benB = benefits.find((b) => b.spouse === "b");
  const hsaFsaConflict = (benA?.has_hsa && benB?.has_fsa) || (benB?.has_hsa && benA?.has_fsa);

  const calcHiddenSalary = (ben: BenefitPackageType | undefined) => {
    if (!ben) return 0;
    return (ben.health_premium_monthly || 0) * 12
      + (ben.dental_vision_monthly || 0) * 12
      + (ben.hsa_employer_contribution || 0)
      + (ben.employer_match_pct || 0) / 100 * Math.min(ben.employer_match_limit_pct || 6, 6) / 100 * (ben.spouse === "a" ? profile.spouse_a_income : profile.spouse_b_income)
      + (ben.commuter_monthly_limit || 0) * 12
      + (ben.tuition_reimbursement_annual || 0);
  };

  const hiddenA = calcHiddenSalary(benA);
  const hiddenB = calcHiddenSalary(benB);

  const hasDependents = (() => {
    try { return (JSON.parse(profile?.dependents_json || "[]") as unknown[]).length > 0; } catch { return false; }
  })();

  return (
    <div className="space-y-6">
      {loading && <div className="flex items-center gap-2 text-text-secondary text-sm"><Loader2 size={14} className="animate-spin" />Loading benefits...</div>}
      {error && <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 p-3 rounded-lg">{error}</div>}

      {/* Alerts: HSA/FSA conflict + hidden salary */}
      {(hsaFsaConflict || hiddenA > 0 || hiddenB > 0) && (
        <div className="space-y-3">
          {hsaFsaConflict && (
            <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-900 rounded-xl flex items-start gap-3">
              <AlertTriangle size={16} className="text-red-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-red-800 dark:text-red-400">HSA + FSA Conflict Detected</p>
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                  One spouse has an HSA while the other has an FSA. Being on a spouse&apos;s FSA disqualifies HSA contributions
                  unless the FSA is a Limited-Purpose FSA (dental/vision only). Verify your FSA type.
                </p>
              </div>
            </div>
          )}
          {(hiddenA > 0 || hiddenB > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {hiddenA > 0 && (
                <div className="p-4 bg-green-50 dark:bg-green-950/40 border border-green-100 dark:border-green-900 rounded-xl">
                  <p className="text-xs text-green-600 dark:text-green-400 font-semibold uppercase tracking-wide mb-1">{spouseName("a")} Hidden Salary</p>
                  <p className="text-xl font-bold text-green-700 dark:text-green-400">{formatCurrency(hiddenA)}/yr</p>
                  <p className="text-xs text-green-600 dark:text-green-400 mt-1">Estimated value of employer benefits</p>
                </div>
              )}
              {hiddenB > 0 && (
                <div className="p-4 bg-green-50 dark:bg-green-950/40 border border-green-100 dark:border-green-900 rounded-xl">
                  <p className="text-xs text-green-600 dark:text-green-400 font-semibold uppercase tracking-wide mb-1">{spouseName("b")} Hidden Salary</p>
                  <p className="text-xl font-bold text-green-700 dark:text-green-400">{formatCurrency(hiddenB)}/yr</p>
                  <p className="text-xs text-green-600 dark:text-green-400 mt-1">Estimated value of employer benefits</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Contribution headroom */}
      <ContributionHeadroomCard benA={benA} benB={benB} assets={assets} hasDependents={hasDependents} />

      {/* Spouse tabs */}
      <div className="flex gap-2 border-b border-border pb-0">
        {(["a", "b"] as const).map((s) => (
          <button key={s} onClick={() => setActiveSpouse(s)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
              activeSpouse === s
                ? "border-accent text-accent"
                : "border-transparent text-text-secondary hover:text-text-secondary"
            }`}>
            {spouseName(s)}
          </button>
        ))}
      </div>

      {/* Benefits form for the active spouse */}
      <BenefitsPlanForm
        spouseName={spouseName(activeSpouse)}
        form={activeSpouse === "a" ? formA : formB}
        setForm={activeSpouse === "a" ? setFormA : setFormB}
        saving={saving === activeSpouse}
        onSave={() => handleSave(activeSpouse)}
      />

      {/* Health plan comparison */}
      <BenefitsPlanComparison spouseAName={spouseName("a")} spouseBName={spouseName("b")} />
    </div>
  );
}
