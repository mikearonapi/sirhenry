"use client";
import { useEffect, useState } from "react";
import {
  Loader2, TrendingUp, CheckCircle2, Circle, Lock, Info,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { updateHouseholdProfile } from "@/lib/api";
import type { HouseholdProfile } from "@/types/api";
import Card from "@/components/ui/Card";
import { FOO_STEPS, ESTATE_STATUS_OPTIONS, ESTATE_STATUS_BADGE } from "./constants";

// ---------------------------------------------------------------------------
// WealthTab
// ---------------------------------------------------------------------------

export interface WealthTabProps {
  profile: HouseholdProfile | null;
}

export default function WealthTab({ profile }: WealthTabProps) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localProfile, setLocalProfile] = useState<HouseholdProfile | null>(profile);
  const [estateReviewDates, setEstateReviewDates] = useState<Record<string, string>>({});

  useEffect(() => { setLocalProfile(profile); }, [profile]);

  useEffect(() => {
    if (!profile?.id) return;
    try {
      const saved = localStorage.getItem(`estate_dates_${profile.id}`);
      if (saved) setEstateReviewDates(JSON.parse(saved));
    } catch {}
  }, [profile?.id]);

  function setEstateDate(key: string, date: string) {
    setEstateReviewDates((prev) => {
      const updated = { ...prev, [key]: date };
      try { localStorage.setItem(`estate_dates_${profile?.id}`, JSON.stringify(updated)); } catch {}
      return updated;
    });
  }

  async function saveEstate() {
    if (!localProfile) return;
    setSaving(true);
    setError(null);
    try {
      await updateHouseholdProfile(localProfile.id, {
        estate_will_status: localProfile.estate_will_status,
        estate_poa_status: localProfile.estate_poa_status,
        estate_hcd_status: localProfile.estate_hcd_status,
        estate_trust_status: localProfile.estate_trust_status,
        beneficiaries_reviewed: localProfile.beneficiaries_reviewed,
        beneficiaries_reviewed_date: localProfile.beneficiaries_reviewed_date,
      });
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(false); }
  }

  if (!profile || !localProfile) {
    return (
      <div className="text-center py-12">
        <TrendingUp size={32} className="mx-auto text-stone-300 mb-3" />
        <p className="text-sm text-stone-500">Create a household profile on the Profile tab first.</p>
      </div>
    );
  }

  const ssEstimate = (income: number) => {
    const aime = Math.min(income / 12, 12_000);
    if (aime <= 1_115) return aime * 0.9;
    if (aime <= 6_721) return 1_115 * 0.9 + (aime - 1_115) * 0.32;
    return 1_115 * 0.9 + (6_721 - 1_115) * 0.32 + (aime - 6_721) * 0.15;
  };
  const ssA = ssEstimate(profile.spouse_a_income);
  const ssB = ssEstimate(profile.spouse_b_income);

  const combined = profile.combined_income;
  const rothPhaseStart = 236_000;
  const rothPhaseEnd = 246_000;
  const rothStatus = combined >= rothPhaseEnd ? "ineligible" : combined >= rothPhaseStart ? "partial" : "eligible";

  const estateDocs = [
    { key: "estate_will_status" as const, label: "Last Will & Testament", desc: "Specifies asset distribution and guardianship" },
    { key: "estate_poa_status" as const, label: "Financial Power of Attorney", desc: "Who manages finances if incapacitated" },
    { key: "estate_hcd_status" as const, label: "Healthcare Directive / Living Will", desc: "Medical decision-making instructions" },
    { key: "estate_trust_status" as const, label: "Revocable Living Trust", desc: "Avoids probate; recommended when net worth grows" },
  ];

  return (
    <div className="space-y-6">
      {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{error}</div>}

      <Card padding="lg">
        <h3 className="text-sm font-semibold text-stone-900 mb-1">Account Contribution Priority</h3>
        <p className="text-xs text-stone-500 mb-4">
          Financial Order of Operations for {profile.spouse_a_name || "Spouse A"} &amp; {profile.spouse_b_name || "Spouse B"} at {formatCurrency(combined, true)} combined income.
        </p>
        <div className="space-y-2">
          {FOO_STEPS.map((step, i) => {
            let relevance: "relevant" | "check" | "locked" = "relevant";
            if (step.key === "hsa") relevance = "check";
            if (step.key === "roth" && rothStatus === "ineligible") relevance = "locked";
            if (step.key === "529") {
              try { relevance = (JSON.parse(profile.dependents_json || "[]") as unknown[]).length > 0 ? "relevant" : "check"; } catch { relevance = "check"; }
            }

            const icon = relevance === "locked" ? <Lock size={14} className="text-stone-400" /> :
              relevance === "check" ? <Info size={14} className="text-amber-500" /> :
              <CheckCircle2 size={14} className="text-green-500" />;

            const bg = relevance === "locked" ? "bg-stone-50 border-stone-100 opacity-60" :
              relevance === "check" ? "bg-amber-50 border-amber-100" :
              i === 0 ? "bg-green-50 border-green-200" : "bg-white border-stone-100";

            return (
              <div key={step.key} className={`p-3 rounded-xl border ${bg} flex items-start gap-3`}>
                <div className="w-6 h-6 rounded-full bg-stone-100 flex items-center justify-center text-xs font-bold text-stone-500 shrink-0 mt-0.5">
                  {step.step}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    {icon}
                    <p className="text-sm font-medium text-stone-900">{step.label}</p>
                  </div>
                  <p className="text-xs text-stone-500 mt-0.5">{step.description}</p>
                  {step.key === "roth" && rothStatus !== "eligible" && (
                    <p className="text-xs text-amber-600 mt-1">
                      {rothStatus === "ineligible"
                        ? "Over income limit — use Backdoor Roth IRA strategy instead."
                        : "Partially phased out — contribute reduced amount or use Backdoor Roth."}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card padding="lg">
        <h3 className="text-sm font-semibold text-stone-900 mb-1">Social Security Outlook</h3>
        <p className="text-xs text-stone-500 mb-4">
          Rough estimated monthly benefit based on current income levels (simplified bend-point formula).
          For precise projections, create an account at ssa.gov/myaccount.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {([["a", profile.spouse_a_name, profile.spouse_a_income, ssA], ["b", profile.spouse_b_name, profile.spouse_b_income, ssB]] as [string, string | null, number, number][]).map(([s, name, income, est]) => (
            <div key={s} className="p-4 bg-stone-50 rounded-xl border border-stone-100">
              <p className="text-xs font-semibold text-stone-500 uppercase tracking-wide">{name || `Spouse ${s.toUpperCase()}`}</p>
              <p className="text-xs text-stone-400 mt-0.5">Income: {formatCurrency(income, true)}</p>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-sm font-bold text-stone-700">{formatCurrency(est * 0.7)}/mo</p>
                  <p className="text-xs text-stone-400">At 62</p>
                </div>
                <div>
                  <p className="text-sm font-bold text-stone-900">{formatCurrency(est)}/mo</p>
                  <p className="text-xs text-stone-400">At 67 (FRA)</p>
                </div>
                <div>
                  <p className="text-sm font-bold text-green-700">{formatCurrency(est * 1.24)}/mo</p>
                  <p className="text-xs text-stone-400">At 70</p>
                </div>
              </div>
              <p className="text-xs text-stone-400 mt-2 italic">
                Delaying from 67→70 increases benefit by 24% permanently.
              </p>
            </div>
          ))}
        </div>
      </Card>

      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-stone-900">Estate Planning Checklist</h3>
            <p className="text-xs text-stone-500 mt-0.5">Track the status of essential estate documents.</p>
          </div>
          <button onClick={saveEstate} disabled={saving}
            className="flex items-center gap-2 bg-stone-800 text-white px-3 py-2 rounded-lg text-xs font-medium hover:bg-stone-700 disabled:opacity-60">
            {saving && <Loader2 size={12} className="animate-spin" />} Save
          </button>
        </div>

        <div className="space-y-4">
          {estateDocs.map((doc) => {
            const val = localProfile[doc.key] || "";
            const badge = val ? ESTATE_STATUS_BADGE[val] : "bg-stone-100 text-stone-500";
            const reviewDate = estateReviewDates[doc.key] || "";
            return (
              <div key={doc.key} className="p-3 rounded-xl border border-stone-100 bg-stone-50">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-stone-900">{doc.label}</p>
                    <p className="text-xs text-stone-500">{doc.desc}</p>
                  </div>
                  <select
                    value={val}
                    onChange={(e) => setLocalProfile((p) => p ? { ...p, [doc.key]: e.target.value } : p)}
                    className={`text-xs px-2 py-1.5 rounded-lg border font-medium ${badge} focus:outline-none shrink-0`}
                  >
                    {ESTATE_STATUS_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <label className="text-[10px] text-stone-400 whitespace-nowrap">Last reviewed:</label>
                  <input
                    type="date"
                    value={reviewDate}
                    onChange={(e) => setEstateDate(doc.key, e.target.value)}
                    className="text-[11px] border border-stone-200 rounded px-2 py-0.5 text-stone-600 focus:outline-none focus:ring-1 focus:ring-[#16A34A]/20"
                  />
                  {!reviewDate && val === "complete" && (
                    <span className="text-[10px] text-amber-600 italic">Add a review date</span>
                  )}
                  {reviewDate && (() => {
                    const months = Math.floor((Date.now() - new Date(reviewDate).getTime()) / (1000 * 60 * 60 * 24 * 30));
                    return months > 24 ? (
                      <span className="text-[10px] text-red-500 font-medium">Review overdue ({months}mo ago)</span>
                    ) : months > 12 ? (
                      <span className="text-[10px] text-amber-600">Review soon ({months}mo ago)</span>
                    ) : (
                      <span className="text-[10px] text-green-600">{months}mo ago</span>
                    );
                  })()}
                </div>
              </div>
            );
          })}

          <div className="pt-3 border-t border-stone-100">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <p className="text-sm font-medium text-stone-900">Beneficiary Review</p>
                <p className="text-xs text-stone-500">Review beneficiary designations on all retirement accounts, life insurance, and bank accounts annually.</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setLocalProfile((p) => p ? { ...p, beneficiaries_reviewed: !p.beneficiaries_reviewed, beneficiaries_reviewed_date: !p.beneficiaries_reviewed ? new Date().toISOString().split("T")[0] : p.beneficiaries_reviewed_date } : p)}
                  className={`p-1 rounded ${localProfile.beneficiaries_reviewed ? "text-green-500" : "text-stone-300 hover:text-stone-400"}`}
                >
                  {localProfile.beneficiaries_reviewed ? <CheckCircle2 size={20} /> : <Circle size={20} />}
                </button>
                <span className="text-xs text-stone-500">
                  {localProfile.beneficiaries_reviewed
                    ? `Reviewed ${localProfile.beneficiaries_reviewed_date || ""}`
                    : "Not yet reviewed"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {combined > 500_000 && (
          <div className="mt-4 p-3 bg-purple-50 border border-purple-100 rounded-xl">
            <p className="text-xs font-semibold text-purple-700 mb-1">Estate Planning Note</p>
            <p className="text-xs text-purple-600">
              The federal estate tax exemption is $13.6M per person (2025) but is set to sunset at ~$7M in 2026 absent Congressional action.
              Consider consulting an estate attorney if your net worth is approaching $5M+.
              A revocable living trust can also help avoid probate for your heirs.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
