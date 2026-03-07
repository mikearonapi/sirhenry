"use client";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import { request } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";

interface ESPPResult {
  is_qualifying: boolean;
  ordinary_income: number;
  capital_gain: number;
  total_tax: number;
  net_proceeds: number;
  effective_tax_rate: number;
  holding_period_days: number;
  days_until_qualifying: number;
  recommendation: string;
}

interface ESPPAnalysisProps {
  defaultIncome?: number;
  defaultFilingStatus?: string;
}

export default function ESPPAnalysis({ defaultIncome = 200000, defaultFilingStatus = "mfj" }: ESPPAnalysisProps) {
  const [form, setForm] = useState({
    purchase_price: 0,
    fmv_at_purchase: 0,
    fmv_at_sale: 0,
    shares: 0,
    purchase_date: "",
    sale_date: "",
    offering_date: "",
    discount_pct: 15,
    other_income: defaultIncome,
    filing_status: defaultFilingStatus,
  });
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qualifying, setQualifying] = useState<ESPPResult | null>(null);
  const [disqualifying, setDisqualifying] = useState<ESPPResult | null>(null);

  async function runAnalysis() {
    if (!form.purchase_date || !form.offering_date || form.shares <= 0) return;
    setAnalyzing(true);
    setError(null);
    try {
      // Run qualifying scenario (sale after holding period)
      const qResult = await request<ESPPResult>("/equity-comp/espp-analysis", {
        method: "POST",
        body: JSON.stringify(form),
      });

      // Run disqualifying scenario (sell now)
      const today = new Date().toISOString().split("T")[0];
      const dqResult = await request<ESPPResult>("/equity-comp/espp-analysis", {
        method: "POST",
        body: JSON.stringify({ ...form, sale_date: today }),
      });

      setQualifying(qResult);
      setDisqualifying(dqResult);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setAnalyzing(false);
  }

  const fmt = formatCurrency;

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-secondary">
        Compare qualifying vs disqualifying dispositions for ESPP shares. A qualifying disposition (2+ years from offering, 1+ year from purchase) typically saves you money on taxes.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Purchase Price / Share</label>
          <input type="number" step="0.01" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.purchase_price || ""} onChange={e => setForm({ ...form, purchase_price: Number(e.target.value) })} placeholder="0.00" />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">FMV at Purchase</label>
          <input type="number" step="0.01" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.fmv_at_purchase || ""} onChange={e => setForm({ ...form, fmv_at_purchase: Number(e.target.value) })} placeholder="0.00" />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Current FMV / Sale Price</label>
          <input type="number" step="0.01" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.fmv_at_sale || ""} onChange={e => setForm({ ...form, fmv_at_sale: Number(e.target.value) })} placeholder="0.00" />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Shares</label>
          <input type="number" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.shares || ""} onChange={e => setForm({ ...form, shares: Number(e.target.value) })} placeholder="0" />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Offering Date</label>
          <input type="date" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.offering_date} onChange={e => setForm({ ...form, offering_date: e.target.value })} />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Purchase Date</label>
          <input type="date" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.purchase_date} onChange={e => setForm({ ...form, purchase_date: e.target.value })} />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Planned Sale Date</label>
          <input type="date" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.sale_date} onChange={e => setForm({ ...form, sale_date: e.target.value })} />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Discount %</label>
          <input type="number" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.discount_pct} onChange={e => setForm({ ...form, discount_pct: Number(e.target.value) })} />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Other Income</label>
          <input type="number" className="w-full border border-text-muted rounded-lg px-3 py-2 text-sm" value={form.other_income} onChange={e => setForm({ ...form, other_income: Number(e.target.value) })} />
        </div>
      </div>

      <button onClick={runAnalysis} disabled={analyzing || form.shares <= 0} className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50">
        {analyzing ? <><Loader2 size={13} className="animate-spin inline mr-2" />Analyzing...</> : "Compare Dispositions"}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {qualifying && disqualifying && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Qualifying */}
          <Card padding="lg" className={qualifying.is_qualifying ? "border-green-200 bg-green-50/30" : "border-border"}>
            <div className="flex items-center gap-2 mb-3">
              <span className={`text-xs px-2 py-0.5 rounded ${qualifying.is_qualifying ? "bg-green-100 text-green-700" : "bg-surface text-text-secondary"}`}>
                {qualifying.is_qualifying ? "Qualifying" : "Not Yet Qualifying"}
              </span>
              <span className="text-xs text-text-muted">Planned sale date</span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm"><span className="text-text-secondary">Ordinary Income</span><span className="font-mono tabular-nums">{fmt(qualifying.ordinary_income)}</span></div>
              <div className="flex justify-between text-sm"><span className="text-text-secondary">Capital Gain</span><span className="font-mono tabular-nums">{fmt(qualifying.capital_gain)}</span></div>
              <div className="flex justify-between text-sm border-t border-border pt-2"><span className="text-text-secondary">Total Tax</span><span className="font-mono tabular-nums text-red-600">{fmt(qualifying.total_tax)}</span></div>
              <div className="flex justify-between text-sm font-semibold"><span className="text-text-secondary">Net Proceeds</span><span className="font-mono tabular-nums text-green-600">{fmt(qualifying.net_proceeds)}</span></div>
              <div className="flex justify-between text-xs"><span className="text-text-muted">Effective Tax Rate</span><span className="tabular-nums">{qualifying.effective_tax_rate.toFixed(1)}%</span></div>
              {qualifying.days_until_qualifying > 0 && (
                <p className="text-xs text-amber-600 mt-2">{qualifying.days_until_qualifying} days until qualifying disposition</p>
              )}
            </div>
          </Card>

          {/* Disqualifying */}
          <Card padding="lg" className="border-border">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700">Disqualifying</span>
              <span className="text-xs text-text-muted">Sell today</span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm"><span className="text-text-secondary">Ordinary Income</span><span className="font-mono tabular-nums">{fmt(disqualifying.ordinary_income)}</span></div>
              <div className="flex justify-between text-sm"><span className="text-text-secondary">Capital Gain</span><span className="font-mono tabular-nums">{fmt(disqualifying.capital_gain)}</span></div>
              <div className="flex justify-between text-sm border-t border-border pt-2"><span className="text-text-secondary">Total Tax</span><span className="font-mono tabular-nums text-red-600">{fmt(disqualifying.total_tax)}</span></div>
              <div className="flex justify-between text-sm font-semibold"><span className="text-text-secondary">Net Proceeds</span><span className="font-mono tabular-nums">{fmt(disqualifying.net_proceeds)}</span></div>
              <div className="flex justify-between text-xs"><span className="text-text-muted">Effective Tax Rate</span><span className="tabular-nums">{disqualifying.effective_tax_rate.toFixed(1)}%</span></div>
            </div>
          </Card>
        </div>
      )}

      {qualifying && disqualifying && (
        <Card padding="lg" className="bg-blue-50/50 border-blue-100">
          <p className="text-sm text-blue-800">{qualifying.recommendation}</p>
          {qualifying.net_proceeds > disqualifying.net_proceeds && (
            <p className="text-sm text-green-700 font-semibold mt-2">
              Waiting saves you {fmt(qualifying.net_proceeds - disqualifying.net_proceeds)} in taxes.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
