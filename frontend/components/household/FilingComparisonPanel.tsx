"use client";
import { useState } from "react";
import { Loader2, Calculator } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { compareFilingStatus } from "@/lib/api";
import type { HouseholdProfile } from "@/types/api";
import Card from "@/components/ui/Card";

// ---------------------------------------------------------------------------
// FilingComparisonPanel — MFJ vs MFS filing status comparison
// ---------------------------------------------------------------------------

export interface FilingComparisonPanelProps {
  profile: HouseholdProfile;
  onError: (msg: string) => void;
}

export default function FilingComparisonPanel({ profile, onError }: FilingComparisonPanelProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ mfj_tax: number; mfs_tax: number; savings: number; recommendation: string } | null>(null);
  const [compA, setCompA] = useState(profile.spouse_a_income || 0);
  const [compB, setCompB] = useState(profile.spouse_b_income || 0);

  async function runFiling() {
    setLoading(true);
    try {
      const r = await compareFilingStatus({ spouse_a_income: compA, spouse_b_income: compB });
      setResult(r);
    } catch (e: unknown) { onError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  return (
    <Card padding="lg">
      <h3 className="text-sm font-semibold text-stone-900 mb-2">MFJ vs MFS Comparison</h3>
      <p className="text-xs text-stone-500 mb-4">Compare Married Filing Jointly vs Married Filing Separately to find the optimal strategy.</p>
      <div className="flex flex-wrap items-end gap-4 mb-4">
        <div>
          <label className="text-xs text-stone-500">{profile.spouse_a_name || "Spouse A"} Income</label>
          <input type="number" value={compA || ""} onChange={(e) => setCompA(Number(e.target.value) || 0)}
            className="w-36 mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
        </div>
        <div>
          <label className="text-xs text-stone-500">{profile.spouse_b_name || "Spouse B"} Income</label>
          <input type="number" value={compB || ""} onChange={(e) => setCompB(Number(e.target.value) || 0)}
            className="w-36 mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
        </div>
        <button onClick={runFiling} disabled={loading}
          className="flex items-center gap-2 bg-stone-800 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-stone-700 disabled:opacity-60">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Calculator size={14} />} Compare
        </button>
      </div>
      {result && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-stone-50 rounded-xl border border-stone-100">
          <div><p className="text-xs text-stone-400">MFJ Tax</p><p className="text-lg font-bold text-stone-900">{formatCurrency(result.mfj_tax)}</p></div>
          <div><p className="text-xs text-stone-400">MFS Tax</p><p className="text-lg font-bold text-stone-900">{formatCurrency(result.mfs_tax)}</p></div>
          <div><p className="text-xs text-stone-400">Savings (MFJ)</p>
            <p className={`text-lg font-bold ${result.savings >= 0 ? "text-green-600" : "text-red-600"}`}>
              {formatCurrency(result.savings)}</p></div>
          <div><p className="text-xs text-stone-400">Recommendation</p><p className="text-sm font-semibold text-stone-800">{result.recommendation}</p></div>
        </div>
      )}
    </Card>
  );
}
