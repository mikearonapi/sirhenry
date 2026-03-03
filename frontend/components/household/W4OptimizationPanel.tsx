"use client";
import { useCallback, useEffect, useState } from "react";
import { Loader2, Calculator, CheckCircle2, RefreshCw } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { w4Optimization, getHouseholdBenefits } from "@/lib/api";
import type { HouseholdProfile, BenefitPackageType, W4OptimizationResult } from "@/types/api";
import Card from "@/components/ui/Card";
import StatCard from "@/components/ui/StatCard";
import { PAY_PERIODS } from "./constants";

// ---------------------------------------------------------------------------
// W4OptimizationPanel — W-4 withholding optimization UI
// ---------------------------------------------------------------------------

export interface W4OptimizationPanelProps {
  profile: HouseholdProfile;
  onError: (msg: string) => void;
}

export default function W4OptimizationPanel({ profile, onError }: W4OptimizationPanelProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<W4OptimizationResult | null>(null);
  const [payA, setPayA] = useState(26);
  const [payB, setPayB] = useState(26);
  const [preTaxA, setPreTaxA] = useState(0);
  const [preTaxB, setPreTaxB] = useState(0);
  const [otherIncome, setOtherIncome] = useState(0);
  const [benefitsLoaded, setBenefitsLoaded] = useState(false);

  const incomeA = profile.spouse_a_income || 0;
  const incomeB = profile.spouse_b_income || 0;

  const autoFillFromBenefits = useCallback(async () => {
    try {
      const bens = await getHouseholdBenefits(profile.id);
      const benA = Array.isArray(bens) ? bens.find((b: BenefitPackageType) => b.spouse === "a") : undefined;
      const benB = Array.isArray(bens) ? bens.find((b: BenefitPackageType) => b.spouse === "b") : undefined;
      const calcPreTax = (b: BenefitPackageType | undefined) =>
        (b?.annual_401k_contribution || 0)
        + (b?.health_premium_monthly || 0) * 12
        + (b?.dental_vision_monthly || 0) * 12
        + (b?.commuter_monthly_limit || 0) * 12;
      setPreTaxA(calcPreTax(benA));
      setPreTaxB(calcPreTax(benB));
      if (profile.other_income_annual) {
        setOtherIncome(profile.other_income_annual);
      }
      setBenefitsLoaded(true);
    } catch { /* non-fatal */ }
  }, [profile]);

  useEffect(() => { autoFillFromBenefits(); }, [autoFillFromBenefits]);

  async function runW4() {
    setLoading(true);
    try {
      const r = await w4Optimization({
        spouse_a_income: incomeA,
        spouse_b_income: incomeB,
        spouse_a_pay_periods: payA,
        spouse_b_pay_periods: payB,
        pre_tax_deductions_a: preTaxA,
        pre_tax_deductions_b: preTaxB,
        other_income: otherIncome,
        filing_status: profile.filing_status || "mfj",
      });
      setResult(r);
    } catch (e: unknown) { onError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  return (
    <Card padding="lg">
      <h3 className="text-sm font-semibold text-stone-900 mb-1">W-4 Withholding Optimization</h3>
      <p className="text-xs text-stone-500 mb-2">
        Dual-income couples systematically under-withhold. Each employer treats the other spouse&apos;s income as $0,
        pushing the combined income into a higher bracket than either spouse&apos;s withholding accounts for.
      </p>
      <div className="flex items-center gap-2 mb-4">
        {benefitsLoaded ? (
          <div className="flex items-center gap-1.5 text-xs text-green-700 bg-green-50 px-3 py-1.5 rounded-lg border border-green-100">
            <CheckCircle2 size={12} />
            Pre-tax deductions auto-filled from Benefits tab (401k + health + dental + commuter)
          </div>
        ) : (
          <button onClick={autoFillFromBenefits}
            className="flex items-center gap-1.5 text-xs text-[#16A34A] bg-[#16A34A]/5 hover:bg-[#16A34A]/10 px-3 py-1.5 rounded-lg border border-[#16A34A]/20 font-medium transition-colors">
            <RefreshCw size={12} /> Auto-fill from Benefits
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs font-semibold text-stone-600 mb-2">{profile.spouse_a_name || "Spouse A"}</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-stone-400">Pay Frequency</label>
              <select value={payA} onChange={(e) => setPayA(Number(e.target.value))}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20">
                {PAY_PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-400">Pre-tax Deductions — annual (401k + health + dental + commuter)</label>
              <input type="number" value={preTaxA || ""} onChange={(e) => setPreTaxA(Number(e.target.value) || 0)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
            </div>
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold text-stone-600 mb-2">{profile.spouse_b_name || "Spouse B"}</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-stone-400">Pay Frequency</label>
              <select value={payB} onChange={(e) => setPayB(Number(e.target.value))}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20">
                {PAY_PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-400">Pre-tax Deductions — annual (401k + health + dental + commuter)</label>
              <input type="number" value={preTaxB || ""} onChange={(e) => setPreTaxB(Number(e.target.value) || 0)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
            </div>
          </div>
        </div>
      </div>
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <label className="text-xs text-stone-400">Other Income — Trust K-1, rental, 1099 (annual, no W-2 withholding)</label>
          {profile.other_income_annual ? (
            <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full border border-purple-200">
              Auto-filled from profile
            </span>
          ) : null}
        </div>
        <input type="number" value={otherIncome || ""} onChange={(e) => setOtherIncome(Number(e.target.value) || 0)}
          className="w-36 mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
        {!profile.other_income_annual && (
          <p className="text-[11px] text-stone-400 mt-1">
            Save trust/rental income on the Profile tab to auto-fill this field every time.
          </p>
        )}
      </div>
      <button onClick={runW4} disabled={loading}
        className="flex items-center gap-2 bg-stone-800 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-stone-700 disabled:opacity-60">
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Calculator size={14} />} Calculate W-4
      </button>

      {result && (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Estimated Tax Owed" value={formatCurrency(result.estimated_mfj_tax)} sub={`${(result.effective_rate * 100).toFixed(1)}% effective rate`} />
            <StatCard label="Estimated Withheld" value={formatCurrency(result.total_estimated_withheld)} sub="Combined both W-2s" />
            <StatCard
              label="Estimated Shortfall"
              value={formatCurrency(Math.abs(result.estimated_shortfall))}
              sub={result.estimated_shortfall > 0 ? "Under-withheld" : "Over-withheld"}
              trend={result.estimated_shortfall > 500 ? "down" : "up"}
              trendValue={result.estimated_shortfall > 500 ? "Adjust W-4" : "On track"}
            />
            <StatCard label="Marginal Rate" value={`${(result.marginal_rate * 100).toFixed(0)}%`} sub="Federal bracket" />
          </div>

          {result.estimated_shortfall > 500 && (
            <div className="p-4 bg-amber-50 border border-amber-100 rounded-xl">
              <p className="text-sm font-semibold text-amber-800 mb-2">Recommended W-4 Adjustments (Step 4c)</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3 bg-white rounded-lg border border-amber-100">
                  <p className="text-xs text-stone-500">{profile.spouse_a_name || "Spouse A"} — Additional Per Paycheck</p>
                  <p className="text-xl font-bold text-amber-700">{formatCurrency(result.extra_per_paycheck_a)}</p>
                </div>
                <div className="p-3 bg-white rounded-lg border border-amber-100">
                  <p className="text-xs text-stone-500">{profile.spouse_b_name || "Spouse B"} — Additional Per Paycheck</p>
                  <p className="text-xl font-bold text-amber-700">{formatCurrency(result.extra_per_paycheck_b)}</p>
                </div>
              </div>
              <p className="text-xs text-amber-700 mt-3">
                Add these amounts to W-4 Step 4c &quot;Extra withholding&quot; at each employer. Use the IRS Withholding Estimator for a precise calculation.
              </p>
            </div>
          )}

          {result.estimated_shortfall <= 0 && (
            <div className="p-4 bg-green-50 border border-green-100 rounded-xl flex items-center gap-3">
              <CheckCircle2 size={16} className="text-green-600" />
              <p className="text-sm text-green-800">{result.recommendation}</p>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
