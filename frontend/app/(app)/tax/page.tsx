"use client";
import { useEffect, useState } from "react";
import {
  AlertCircle, Loader2, CheckCircle, Circle, CircleDot, MinusCircle,
} from "lucide-react";
import {
  getTaxChecklist, getTaxEstimate, getTaxItems, getTaxSummary,
} from "@/lib/api";
import { formatCurrency, safeJsonParse } from "@/lib/utils";
import type { TaxChecklist, TaxEstimate, TaxItem, TaxSummary } from "@/types/api";
import StatCard from "@/components/ui/StatCard";
import ProgressBar from "@/components/ui/ProgressBar";
import PageHeader from "@/components/ui/PageHeader";

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2];

const CHECKLIST_CATEGORY_LABELS: Record<string, string> = {
  documents: "Document Collection",
  preparation: "Tax Preparation",
  filing: "Filing",
  payments: "Payments",
};

export default function TaxChecklistPage() {
  const [year, setYear] = useState(currentYear - 1);
  const [summary, setSummary] = useState<TaxSummary | null>(null);
  const [items, setItems] = useState<TaxItem[]>([]);
  const [estimate, setEstimate] = useState<TaxEstimate | null>(null);
  const [checklist, setChecklist] = useState<TaxChecklist | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(y: number, signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    try {
      const [s, i, e, cl] = await Promise.all([
        getTaxSummary(y).catch((err: any) => { if (!signal?.aborted) setError(err.message); return null; }),
        getTaxItems(y).catch((err: any) => { if (!signal?.aborted) setError(err.message); return []; }),
        getTaxEstimate(y).catch((err: any) => { if (!signal?.aborted) setError(err.message); return null; }),
        getTaxChecklist(y).catch(() => null),
      ]);
      if (signal?.aborted) return;
      setSummary(s);
      setItems(i);
      setEstimate(e);
      setChecklist(cl);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    load(year, controller.signal);
    return () => controller.abort();
  }, [year]);

  const w2Items = items.filter((i) => i.form_type === "w2");
  const necItems = items.filter((i) => i.form_type === "1099_nec");
  const divItems = items.filter((i) => i.form_type === "1099_div");

  return (
    <div className="space-y-8">
      <PageHeader
        title="Tax Checklist"
        subtitle="Everything you need for your tax filing — documents, estimates, and progress"
        actions={
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
          >
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        }
      />

      {loading ? (
        <div className="flex items-center gap-3 text-stone-400 justify-center h-48">
          <Loader2 className="animate-spin" size={20} /> Loading tax data...
        </div>
      ) : (
        <>
          {error && (
            <div className="bg-red-50 text-red-700 rounded-xl p-5 flex items-center gap-3">
              <AlertCircle size={20} />
              <div><p className="font-semibold">Failed to load data</p><p className="text-sm mt-0.5">{error}</p></div>
            </div>
          )}

          {/* Tax Estimate */}
          {estimate && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-3">
                {year} Tax Estimate
                <span className="ml-2 text-stone-300 font-normal normal-case">(rough estimate — not professional advice)</span>
              </h2>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Estimated AGI" value={formatCurrency(estimate.estimated_agi, true)} />
                <StatCard label="Total Tax Estimate" value={formatCurrency(estimate.total_estimated_tax, true)} />
                <StatCard label="Effective Rate" value={`${estimate.effective_rate}%`} />
                <StatCard label="Est. Balance Due" value={formatCurrency(estimate.estimated_balance_due, true)} trend={estimate.estimated_balance_due > 0 ? "down" : "up"} sub={estimate.estimated_balance_due > 0 ? "May owe" : "Possible refund"} />
              </div>
              <div className="mt-4 bg-white rounded-xl border border-stone-100 shadow-sm p-5">
                <h3 className="text-sm font-semibold text-stone-700 mb-3">Tax Breakdown</h3>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                  {[
                    { label: "Federal Income Tax", value: estimate.federal_income_tax },
                    { label: "Self-Employment Tax", value: estimate.self_employment_tax },
                    { label: "Net Investment Income (3.8%)", value: estimate.niit },
                    { label: "Additional Medicare (0.9%)", value: estimate.additional_medicare_tax },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-stone-50 rounded-lg p-3">
                      <p className="text-xs text-stone-500">{label}</p>
                      <p className="font-semibold text-stone-800 mt-1">{formatCurrency(value)}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-3 grid grid-cols-2 gap-4 text-sm border-t border-stone-100 pt-3">
                  <div><p className="text-xs text-stone-500">W-2 Already Withheld</p><p className="font-semibold text-green-600">{formatCurrency(estimate.w2_federal_already_withheld)}</p></div>
                  <div><p className="text-xs text-stone-500">Ordinary Income</p><p className="font-semibold text-stone-800">{formatCurrency(estimate.ordinary_income)}</p></div>
                </div>
              </div>
            </div>
          )}

          {/* Filing Checklist */}
          {checklist && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400">{year} Tax Filing Checklist</h2>
                <span className="text-sm font-semibold text-stone-600">{checklist.completed}/{checklist.total} complete</span>
              </div>
              <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-stone-600">Overall Progress</span>
                    <span className="text-sm font-semibold text-stone-800">{checklist.progress_pct}%</span>
                  </div>
                  <ProgressBar value={checklist.progress_pct} size="md" />
                </div>
                {(["documents", "preparation", "filing", "payments"] as const).map((cat) => {
                  const catItems = checklist.items.filter((ci) => ci.category === cat);
                  if (catItems.length === 0) return null;
                  const catComplete = catItems.filter((ci) => ci.status === "complete").length;
                  return (
                    <div key={cat} className="mb-4 last:mb-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">{CHECKLIST_CATEGORY_LABELS[cat]}</h3>
                        <span className="text-xs text-stone-400">({catComplete}/{catItems.length})</span>
                      </div>
                      <div className="space-y-1.5">
                        {catItems.map((ci) => (
                          <div key={ci.id} className={`flex items-start gap-3 rounded-lg px-3 py-2 text-sm ${
                            ci.status === "complete" ? "bg-green-50/50" : ci.status === "partial" ? "bg-amber-50/50" : ci.status === "not_applicable" ? "bg-stone-50/50 opacity-50" : "bg-stone-50/30"
                          }`}>
                            <div className="mt-0.5 flex-shrink-0">
                              {ci.status === "complete" ? <CheckCircle size={16} className="text-green-500" /> : ci.status === "partial" ? <CircleDot size={16} className="text-amber-500" /> : ci.status === "not_applicable" ? <MinusCircle size={16} className="text-stone-300" /> : <Circle size={16} className="text-stone-300" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className={`font-medium ${ci.status === "complete" ? "text-green-800" : ci.status === "not_applicable" ? "text-stone-400" : "text-stone-700"}`}>{ci.label}</p>
                              {ci.detail && <p className="text-xs text-stone-400 mt-0.5">{ci.detail}</p>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Income Summary */}
          {summary && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-3">Income Summary — {year}</h2>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="W-2 Wages" value={formatCurrency(summary.w2_total_wages, true)} />
                <StatCard label="Board / 1099-NEC" value={formatCurrency(summary.nec_total, true)} />
                <StatCard label="Dividends" value={formatCurrency(summary.div_ordinary, true)} sub={`${formatCurrency(summary.div_qualified, true)} qualified`} />
                <StatCard label="Capital Gains" value={formatCurrency(summary.capital_gains_long + summary.capital_gains_short, true)} sub={`LT: ${formatCurrency(summary.capital_gains_long, true)} · ST: ${formatCurrency(summary.capital_gains_short, true)}`} />
              </div>
            </div>
          )}

          {/* W-2 Multi-State */}
          {w2Items.length > 0 && (
            <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
              <h2 className="text-sm font-semibold text-stone-700 mb-4">W-2 — Multi-State Allocation</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="sr-only">W-2 multi-state wage and withholding allocation</caption>
                  <thead className="bg-stone-50">
                    <tr>
                      <th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">Employer</th>
                      <th className="text-right px-3 py-2 text-xs font-semibold text-stone-500">Wages (Box 1)</th>
                      <th className="text-right px-3 py-2 text-xs font-semibold text-stone-500">Federal W/H</th>
                      <th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">State Allocations</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {w2Items.map((item) => {
                      const allocations = safeJsonParse<Array<{ state: string; wages: number; tax: number }>>(item.w2_state_allocations, []);
                      return (
                        <tr key={item.id}>
                          <td className="px-3 py-3 font-medium text-stone-800">{item.payer_name ?? "—"}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{item.w2_wages != null ? formatCurrency(item.w2_wages) : "—"}</td>
                          <td className="px-3 py-3 text-right tabular-nums">{item.w2_federal_tax_withheld != null ? formatCurrency(item.w2_federal_tax_withheld) : "—"}</td>
                          <td className="px-3 py-3">
                            {allocations.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {allocations.map((a, i) => (
                                  <span key={i} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded">
                                    <strong>{a.state}</strong>: {formatCurrency(a.wages, true)} / {formatCurrency(a.tax, true)} withheld
                                  </span>
                                ))}
                              </div>
                            ) : <span className="text-stone-400 text-xs">Single state or not extracted</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 1099s */}
          {(necItems.length > 0 || divItems.length > 0) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {necItems.length > 0 && (
                <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
                  <h2 className="text-sm font-semibold text-stone-700 mb-3">1099-NEC (Board / Director Income)</h2>
                  {necItems.map((item) => (
                    <div key={item.id} className="flex items-center justify-between text-sm py-2 border-b border-stone-50 last:border-0">
                      <div><p className="font-medium text-stone-800">{item.payer_name ?? "Unknown payer"}</p><p className="text-xs text-stone-400">EIN: {item.payer_ein ?? "N/A"}</p></div>
                      <div className="text-right"><p className="font-semibold">{formatCurrency(item.nec_nonemployee_compensation ?? 0)}</p><p className="text-xs text-stone-400">W/H: {formatCurrency(item.nec_federal_tax_withheld ?? 0)}</p></div>
                    </div>
                  ))}
                </div>
              )}
              {divItems.length > 0 && (
                <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
                  <h2 className="text-sm font-semibold text-stone-700 mb-3">1099-DIV (Dividends)</h2>
                  {divItems.map((item) => (
                    <div key={item.id} className="flex items-center justify-between text-sm py-2 border-b border-stone-50 last:border-0">
                      <p className="font-medium text-stone-800">{item.payer_name ?? "Unknown"}</p>
                      <div className="text-right text-xs space-y-0.5">
                        <p><span className="text-stone-400">Ordinary:</span> {formatCurrency(item.div_total_ordinary ?? 0)}</p>
                        <p><span className="text-stone-400">Qualified:</span> {formatCurrency(item.div_qualified ?? 0)}</p>
                        <p><span className="text-stone-400">Cap. Gain:</span> {formatCurrency(item.div_total_capital_gain ?? 0)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
