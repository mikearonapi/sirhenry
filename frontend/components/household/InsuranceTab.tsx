"use client";
import { useState } from "react";
import {
  Loader2, AlertCircle, ShieldCheck, AlertTriangle, CheckCircle2, Info,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { getInsuranceGapAnalysis } from "@/lib/api";
import type { HouseholdProfile, InsuranceGapAnalysis } from "@/types/api";
import Card from "@/components/ui/Card";

// ---------------------------------------------------------------------------
// InsuranceTab
// ---------------------------------------------------------------------------

export interface InsuranceTabProps {
  profile: HouseholdProfile | null;
}

export default function InsuranceTab({ profile }: InsuranceTabProps) {
  const [gap, setGap] = useState<InsuranceGapAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const body = profile
        ? { household_id: profile.id, spouse_a_income: profile.spouse_a_income, spouse_b_income: profile.spouse_b_income }
        : {};
      const r = await getInsuranceGapAnalysis(body);
      setGap(r);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-4">
      {error && <div className="bg-red-50 text-red-700 rounded-xl p-3 text-sm flex items-center gap-2"><AlertCircle size={14} />{error}</div>}

      <Card padding="lg">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Insurance Coverage Snapshot</h3>
            <p className="text-xs text-text-muted mt-0.5">
              Pulls from your Insurance Hub. Analyzes coverage gaps and recommends actions.
            </p>
          </div>
          <button onClick={runAnalysis} disabled={loading}
            className="flex items-center gap-2 bg-stone-800 dark:bg-stone-700 text-white px-3 py-2 rounded-lg text-xs font-medium hover:bg-stone-700 dark:hover:bg-stone-600 disabled:opacity-60">
            {loading ? <Loader2 size={13} className="animate-spin" /> : <ShieldCheck size={13} />}
            Analyze
          </button>
        </div>

        <div className="p-3 bg-blue-50 border border-blue-100 rounded-xl flex items-start gap-2 mb-4">
          <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
          <p className="text-xs text-blue-700">
            Manage detailed policy records in <a href="/insurance" className="underline font-medium">Insurance &amp; Benefits Hub</a>.
            This tab shows the household coverage summary and gaps.
          </p>
        </div>

        {gap ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="text-center p-3 bg-surface rounded-xl border border-card-border">
                <p className="text-xl font-bold text-text-primary">{gap.total_policies}</p>
                <p className="text-xs text-text-muted">Active Policies</p>
              </div>
              <div className="text-center p-3 bg-surface rounded-xl border border-card-border">
                <p className="text-lg font-bold text-text-primary">{formatCurrency(gap.total_monthly_premium)}</p>
                <p className="text-xs text-text-muted">/mo premiums</p>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-xl border border-red-100">
                <p className="text-xl font-bold text-red-600">{gap.high_severity_gaps}</p>
                <p className="text-xs text-red-500">Critical Gaps</p>
              </div>
              <div className="text-center p-3 bg-amber-50 rounded-xl border border-amber-100">
                <p className="text-xl font-bold text-amber-600">{gap.medium_severity_gaps}</p>
                <p className="text-xs text-amber-500">Review Needed</p>
              </div>
            </div>

            {gap.renewing_soon.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl">
                <p className="text-xs font-semibold text-amber-700 mb-1">Renewing Within 60 Days</p>
                {gap.renewing_soon.map((r) => (
                  <p key={r.id} className="text-xs text-amber-600">{r.label} — {r.days_until} days ({r.renewal_date})</p>
                ))}
              </div>
            )}

            {gap.gaps.map((g) => {
              const sev = { high: "border-red-200 bg-red-50", medium: "border-amber-200 bg-amber-50", low: "border-green-100 bg-green-50" }[g.severity];
              const icon = g.severity === "high" ? <AlertTriangle size={14} className="text-red-500" /> :
                g.severity === "medium" ? <AlertCircle size={14} className="text-amber-500" /> :
                <CheckCircle2 size={14} className="text-green-500" />;
              return (
                <div key={g.type} className={`p-3 rounded-xl border ${sev} flex items-start gap-3`}>
                  {icon}
                  <div>
                    <p className="text-sm font-semibold text-text-primary">{g.label}</p>
                    <p className="text-xs text-text-secondary mt-0.5">{g.note}</p>
                    {g.gap > 0 && (
                      <p className="text-xs text-red-600 mt-1">
                        Coverage gap: {formatCurrency(g.gap)}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-text-muted text-center py-6">
            Click &quot;Analyze&quot; to see your household insurance coverage summary and gaps.
          </p>
        )}
      </Card>
    </div>
  );
}
