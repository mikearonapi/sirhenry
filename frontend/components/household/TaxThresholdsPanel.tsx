"use client";
import { useState } from "react";
import { Loader2, Target, ChevronDown } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { getTaxThresholds } from "@/lib/api";
import type { HouseholdProfile, TaxThresholdResult } from "@/types/api";
import Card from "@/components/ui/Card";

// ---------------------------------------------------------------------------
// TaxThresholdsPanel — Tax threshold monitor
// ---------------------------------------------------------------------------

export interface TaxThresholdsPanelProps {
  profile: HouseholdProfile;
  onError: (msg: string) => void;
}

export default function TaxThresholdsPanel({ profile, onError }: TaxThresholdsPanelProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TaxThresholdResult | null>(null);
  const [capGains, setCapGains] = useState(0);
  const [dividends, setDividends] = useState(0);
  const [preTax, setPreTax] = useState(0);

  const incomeA = profile.spouse_a_income || 0;
  const incomeB = profile.spouse_b_income || 0;

  async function runThresholds() {
    setLoading(true);
    try {
      const deps = (() => {
        try { return (JSON.parse(profile.dependents_json || "[]") as unknown[]).length; } catch { return 0; }
      })();
      const r = await getTaxThresholds({
        spouse_a_income: incomeA,
        spouse_b_income: incomeB,
        capital_gains: capGains,
        qualified_dividends: dividends,
        pre_tax_deductions: preTax,
        filing_status: profile.filing_status || "mfj",
        dependents: deps,
      });
      setResult(r);
    } catch (e: unknown) { onError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-4">
      <Card padding="lg">
        <h3 className="text-sm font-semibold text-stone-900 mb-1">Tax Threshold Monitor</h3>
        <p className="text-xs text-stone-500 mb-4">
          See how close you are to key HENRY tax thresholds and what actions to take.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="text-xs text-stone-400">Capital Gains (annual)</label>
            <input type="number" value={capGains || ""} onChange={(e) => setCapGains(Number(e.target.value) || 0)}
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
          </div>
          <div>
            <label className="text-xs text-stone-400">Qualified Dividends (annual)</label>
            <input type="number" value={dividends || ""} onChange={(e) => setDividends(Number(e.target.value) || 0)}
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
          </div>
          <div>
            <label className="text-xs text-stone-400">Total Pre-tax Deductions</label>
            <input type="number" value={preTax || ""} onChange={(e) => setPreTax(Number(e.target.value) || 0)}
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
          </div>
        </div>
        <button onClick={runThresholds} disabled={loading}
          className="flex items-center gap-2 bg-stone-800 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-stone-700 disabled:opacity-60">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Target size={14} />} Analyze Thresholds
        </button>
      </Card>

      {result && (
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <p className="text-xs text-stone-500">
              Estimated MAGI: <span className="font-semibold text-stone-800">{formatCurrency(result.magi_estimate)}</span>
            </p>
            {result.exceeded_count > 0 && (
              <span className="text-xs bg-red-50 text-red-600 px-2 py-1 rounded-full border border-red-100">
                {result.exceeded_count} threshold{result.exceeded_count > 1 ? "s" : ""} exceeded
              </span>
            )}
            {result.total_estimated_additional_tax > 0 && (
              <span className="text-xs text-stone-500">
                Est. additional tax: <span className="font-medium text-red-600">{formatCurrency(result.total_estimated_additional_tax)}</span>
              </span>
            )}
          </div>

          {result.thresholds.map((t) => {
            const statusColor = t.exceeded
              ? "border-red-200 bg-red-50"
              : t.proximity_pct >= 85
              ? "border-amber-200 bg-amber-50"
              : "border-stone-200 bg-stone-50";
            const barColor = t.exceeded ? "bg-red-500" : t.proximity_pct >= 85 ? "bg-amber-400" : "bg-green-400";

            return (
              <Card key={t.id} padding="md">
                <div className={`rounded-xl border p-4 ${statusColor}`}>
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="text-sm font-semibold text-stone-900">{t.label}</p>
                      {t.exceeded && t.tax_impact > 0 && (
                        <p className="text-xs text-red-600 mt-0.5">Est. tax impact: {formatCurrency(t.tax_impact)}</p>
                      )}
                    </div>
                    <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                      t.exceeded ? "bg-red-100 text-red-700" :
                      t.proximity_pct >= 85 ? "bg-amber-100 text-amber-700" :
                      "bg-green-100 text-green-700"
                    }`}>
                      {t.exceeded ? "Exceeded" : `${t.proximity_pct.toFixed(0)}% of limit`}
                    </span>
                  </div>

                  <div className="mb-2">
                    <div className="h-1.5 bg-stone-200 rounded-full">
                      <div className={`h-1.5 rounded-full ${barColor}`} style={{ width: `${Math.min(100, t.proximity_pct)}%` }} />
                    </div>
                    <div className="flex justify-between text-xs text-stone-400 mt-1">
                      <span>$0</span>
                      <span>{formatCurrency(t.threshold)}</span>
                    </div>
                  </div>

                  <p className="text-xs text-stone-600 mb-2">{t.description}</p>

                  <details className="group">
                    <summary className="text-xs text-[#16A34A] cursor-pointer hover:text-[#15803d] list-none flex items-center gap-1">
                      <span>Actions to consider</span>
                      <ChevronDown size={12} className="group-open:rotate-180 transition-transform" />
                    </summary>
                    <ul className="mt-2 space-y-1">
                      {t.actions.map((a, i) => (
                        <li key={i} className="text-xs text-stone-600 flex items-start gap-1.5">
                          <span className="text-stone-400 mt-0.5">&#8226;</span> {a}
                        </li>
                      ))}
                    </ul>
                  </details>
                </div>
              </Card>
            );
          })}

          <p className="text-xs text-stone-400 italic">{result.note}</p>
        </div>
      )}
    </div>
  );
}
