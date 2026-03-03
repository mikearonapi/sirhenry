"use client";
import { useState } from "react";
import { AlertCircle, Calculator, MapPin, Info } from "lucide-react";
import type { HouseholdProfile } from "@/types/api";
import Card from "@/components/ui/Card";
import { hasReciprocity } from "./constants";
import FilingComparisonPanel from "./FilingComparisonPanel";
import W4OptimizationPanel from "./W4OptimizationPanel";
import TaxThresholdsPanel from "./TaxThresholdsPanel";

// ---------------------------------------------------------------------------
// TaxCoordinationTab — main orchestrator
// ---------------------------------------------------------------------------

export interface TaxCoordinationTabProps {
  profile: HouseholdProfile | null;
}

export default function TaxCoordinationTab({ profile }: TaxCoordinationTabProps) {
  const [activeSection, setActiveSection] = useState<"filing" | "w4" | "thresholds" | "multistate">("filing");
  const [error, setError] = useState<string | null>(null);

  const multiStateSpouses = profile ? [
    profile.spouse_a_work_state && profile.state && profile.spouse_a_work_state !== profile.state
      ? { name: profile.spouse_a_name || "Spouse A", home: profile.state, work: profile.spouse_a_work_state, reciprocity: hasReciprocity(profile.state, profile.spouse_a_work_state) }
      : null,
    profile.spouse_b_work_state && profile.state && profile.spouse_b_work_state !== profile.state
      ? { name: profile.spouse_b_name || "Spouse B", home: profile.state, work: profile.spouse_b_work_state, reciprocity: hasReciprocity(profile.state, profile.spouse_b_work_state) }
      : null,
  ].filter(Boolean) as { name: string; home: string; work: string; reciprocity: boolean }[] : [];

  if (!profile) {
    return (
      <div className="text-center py-12">
        <Calculator size={32} className="mx-auto text-stone-300 mb-3" />
        <p className="text-sm text-stone-500">Create a household profile on the Profile tab first.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && <div className="bg-red-50 text-red-700 rounded-xl p-3 text-sm flex items-center gap-2"><AlertCircle size={14} />{error}</div>}

      {multiStateSpouses.length > 0 && (
        <div className="p-4 bg-blue-50 border border-blue-100 rounded-xl flex items-start gap-3">
          <MapPin size={16} className="text-blue-500 mt-0.5 shrink-0" />
          <div className="space-y-1 flex-1">
            <p className="text-sm font-semibold text-blue-800">Multi-State Tax Situation Detected</p>
            {multiStateSpouses.map((s) => (
              <div key={s.name} className="text-xs text-blue-700">
                <span className="font-medium">{s.name}</span> lives in <span className="font-medium">{s.home}</span> but works in <span className="font-medium">{s.work}</span>.
                {s.reciprocity
                  ? <span className="ml-1 text-green-700 font-medium">&#10003; {s.home}/{s.work} have a reciprocity agreement — typically one state return required.</span>
                  : <span className="ml-1 text-amber-700">File resident return in {s.home} + non-resident return in {s.work}. Claim credit on {s.home} return for taxes paid to {s.work}.</span>
                }
              </div>
            ))}
            <button
              onClick={() => setActiveSection("multistate")}
              className="text-xs text-blue-600 underline mt-1 hover:text-blue-800"
            >
              View detailed multi-state analysis →
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {[
          { id: "filing", label: "Filing Status" },
          { id: "w4", label: "W-4 Optimization" },
          { id: "thresholds", label: "Tax Thresholds" },
          ...(multiStateSpouses.length > 0 ? [{ id: "multistate", label: "Multi-State" }] : []),
        ].map((s) => (
          <button key={s.id} onClick={() => setActiveSection(s.id as typeof activeSection)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeSection === s.id
                ? "bg-stone-900 text-white"
                : "bg-stone-100 text-stone-600 hover:bg-stone-200"
            }`}>
            {s.label}
          </button>
        ))}
      </div>

      {activeSection === "filing" && (
        <FilingComparisonPanel profile={profile} onError={setError} />
      )}

      {activeSection === "w4" && (
        <W4OptimizationPanel profile={profile} onError={setError} />
      )}

      {activeSection === "thresholds" && (
        <TaxThresholdsPanel profile={profile} onError={setError} />
      )}

      {activeSection === "multistate" && (
        <div className="space-y-4">
          {multiStateSpouses.map((s) => (
            <Card key={s.name} padding="lg">
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={16} className="text-blue-500" />
                <h3 className="text-sm font-semibold text-stone-900">{s.name} — {s.home} Resident / {s.work} Nonresident</h3>
              </div>

              {s.reciprocity ? (
                <div className="p-3 bg-green-50 border border-green-100 rounded-xl mb-4">
                  <p className="text-sm font-semibold text-green-800">&#10003; Reciprocity Agreement in Effect</p>
                  <p className="text-xs text-green-700 mt-1">
                    {s.home} and {s.work} have a mutual tax reciprocity agreement. Typically, you only file one state
                    resident return ({s.home}) and are exempt from {s.work} income tax on wages. File a reciprocity
                    exemption certificate with your {s.work} employer to stop {s.work} withholding.
                  </p>
                </div>
              ) : (
                <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl mb-4">
                  <p className="text-sm font-semibold text-amber-800">Two State Returns Required</p>
                  <p className="text-xs text-amber-700 mt-1">
                    No reciprocity between {s.home} and {s.work}. You must file a <strong>resident return</strong> in {s.home}
                    (reporting all income) and a <strong>nonresident return</strong> in {s.work} (reporting only {s.work}-source wages).
                    Claim a credit on the {s.home} return for income taxes paid to {s.work} to avoid double taxation.
                  </p>
                </div>
              )}

              <div className="space-y-3">
                <p className="text-xs font-semibold text-stone-700 uppercase tracking-wide">Key Filing Checklist</p>
                {[
                  { label: `Determine if ${s.work} withholding is set up correctly on W-4` },
                  { label: `File Form ${s.work}-NR (nonresident) if no reciprocity` },
                  { label: `Claim resident credit on ${s.home} return for taxes paid to ${s.work}` },
                  { label: s.reciprocity ? `File reciprocity exemption with ${s.work} employer — stop double withholding` : `Review ${s.work} employer withholding for nonresident wages` },
                  { label: "Ensure both states are included in estimated tax payments if applicable" },
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-stone-700">
                    <Info size={13} className="text-blue-400 mt-0.5 shrink-0" />
                    {item.label}
                  </div>
                ))}
              </div>

              <div className="mt-4 p-3 bg-stone-50 rounded-xl border border-stone-100 text-xs text-stone-600">
                <strong>Note:</strong> State tax laws change. Confirm rules with a CPA licensed in both {s.home} and {s.work},
                especially if income is above $500k (some states impose additional surtaxes).
              </div>
            </Card>
          ))}

          {multiStateSpouses.length === 0 && (
            <Card padding="lg">
              <div className="text-center py-8">
                <MapPin size={28} className="mx-auto text-stone-300 mb-2" />
                <p className="text-sm text-stone-500">No multi-state situation detected. If a spouse works in a different state, add it to their profile on the Profile tab.</p>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
