"use client";
import { useEffect, useState } from "react";
import {
  Loader2, AlertCircle, Download, FileText, Printer,
  Building2, DollarSign, Receipt, Package,
} from "lucide-react";
import { getTaxSummary, getTaxItems, getTaxEstimate, getDocuments } from "@/lib/api";
import { formatCurrency, safeJsonParse } from "@/lib/utils";
import type { TaxSummary, TaxItem, TaxEstimate, Document as DocType } from "@/types/api";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2];

export default function TaxReportsPage() {
  const [year, setYear] = useState(currentYear - 1);
  const [summary, setSummary] = useState<TaxSummary | null>(null);
  const [items, setItems] = useState<TaxItem[]>([]);
  const [estimate, setEstimate] = useState<TaxEstimate | null>(null);
  const [documents, setDocuments] = useState<DocType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(y: number, signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    try {
      const [s, i, e, docs] = await Promise.all([
        getTaxSummary(y).catch(() => null),
        getTaxItems(y).catch(() => []),
        getTaxEstimate(y).catch(() => null),
        getDocuments({ document_type: "tax" }).catch(() => ({ items: [], total: 0 })),
      ]);
      if (signal?.aborted) return;
      setSummary(s);
      setItems(i);
      setEstimate(e);
      setDocuments(docs.items ?? []);
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
  const bItems = items.filter((i) => i.form_type === "1099_b");
  const totalW2Wages = w2Items.reduce((s, i) => s + (i.w2_wages ?? 0), 0);
  const totalW2Withheld = w2Items.reduce((s, i) => s + (i.w2_federal_tax_withheld ?? 0), 0);
  const totalNEC = necItems.reduce((s, i) => s + (i.nec_nonemployee_compensation ?? 0), 0);

  function handlePrint() {
    window.print();
  }

  return (
    <div className="space-y-8 print:space-y-4">
      <PageHeader
        title="Tax Reports"
        subtitle="CPA-ready summaries and documents for your tax preparer"
        actions={
          <div className="flex items-center gap-3 print:hidden">
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
            >
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button
              onClick={handlePrint}
              className="flex items-center gap-2 text-sm text-stone-600 border border-stone-200 rounded-lg px-4 py-2 hover:bg-stone-50"
            >
              <Printer size={14} /> Print / PDF
            </button>
          </div>
        }
      />

      {loading ? (
        <div className="flex items-center gap-3 text-stone-400 justify-center h-48">
          <Loader2 className="animate-spin" size={20} /> Loading...
        </div>
      ) : error ? (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle size={18} /><p className="text-sm">{error}</p>
        </div>
      ) : (
        <>
          {/* Summary for CPA */}
          <Card padding="lg">
            <div className="flex items-center gap-2 mb-4">
              <Receipt size={18} className="text-[#16A34A]" />
              <h2 className="text-sm font-semibold text-stone-800">{year} Tax Year Summary</h2>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              <SummaryItem label="Total W-2 Wages" value={formatCurrency(totalW2Wages)} />
              <SummaryItem label="Federal Withheld (W-2)" value={formatCurrency(totalW2Withheld)} color="green" />
              <SummaryItem label="1099-NEC Income" value={formatCurrency(totalNEC)} />
              <SummaryItem label="Estimated AGI" value={estimate ? formatCurrency(estimate.estimated_agi) : "—"} />
              <SummaryItem label="Dividend Income" value={summary ? formatCurrency(summary.div_ordinary) : "—"} />
              <SummaryItem label="Capital Gains" value={summary ? formatCurrency(summary.capital_gains_long + summary.capital_gains_short) : "—"} />
              <SummaryItem label="Estimated Total Tax" value={estimate ? formatCurrency(estimate.total_estimated_tax) : "—"} color="red" />
              <SummaryItem label="Effective Rate" value={estimate ? `${estimate.effective_rate}%` : "—"} />
            </div>
          </Card>

          {/* W-2 Details */}
          {w2Items.length > 0 && (
            <Card padding="lg">
              <div className="flex items-center gap-2 mb-4">
                <Building2 size={18} className="text-indigo-500" />
                <h2 className="text-sm font-semibold text-stone-800">W-2 Forms ({w2Items.length})</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="sr-only">W-2 forms for {year}</caption>
                  <thead className="bg-stone-50">
                    <tr>
                      <th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">Employer</th>
                      <th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">EIN</th>
                      <th className="text-right px-3 py-2 text-xs font-semibold text-stone-500">Wages</th>
                      <th className="text-right px-3 py-2 text-xs font-semibold text-stone-500">Fed W/H</th>
                      <th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">States</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {w2Items.map((item) => {
                      const allocs = safeJsonParse<Array<{ state: string; wages: number; tax: number }>>(item.w2_state_allocations, []);
                      return (
                        <tr key={item.id}>
                          <td className="px-3 py-2 font-medium text-stone-800">{item.payer_name ?? "—"}</td>
                          <td className="px-3 py-2 text-stone-500">{item.payer_ein ?? "—"}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(item.w2_wages ?? 0)}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(item.w2_federal_tax_withheld ?? 0)}</td>
                          <td className="px-3 py-2">
                            {allocs.length > 0 ? allocs.map((a, i) => (
                              <span key={i} className="inline-flex mr-2 text-xs">{a.state}: {formatCurrency(a.wages, true)} / {formatCurrency(a.tax, true)} w/h</span>
                            )) : <span className="text-xs text-stone-400">—</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* 1099 Details */}
          {(necItems.length > 0 || divItems.length > 0 || bItems.length > 0) && (
            <Card padding="lg">
              <div className="flex items-center gap-2 mb-4">
                <DollarSign size={18} className="text-green-500" />
                <h2 className="text-sm font-semibold text-stone-800">1099 Forms</h2>
              </div>
              <div className="space-y-4">
                {necItems.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">1099-NEC</h3>
                    {necItems.map((item) => (
                      <div key={item.id} className="flex justify-between text-sm py-1.5 border-b border-stone-50 last:border-0">
                        <span className="text-stone-700">{item.payer_name ?? "Unknown"} <span className="text-stone-400 text-xs">({item.payer_ein ?? "N/A"})</span></span>
                        <span className="font-semibold tabular-nums">{formatCurrency(item.nec_nonemployee_compensation ?? 0)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {divItems.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">1099-DIV</h3>
                    {divItems.map((item) => (
                      <div key={item.id} className="flex justify-between text-sm py-1.5 border-b border-stone-50 last:border-0">
                        <span className="text-stone-700">{item.payer_name ?? "Unknown"}</span>
                        <div className="text-right text-xs space-x-3">
                          <span>Ordinary: <strong>{formatCurrency(item.div_total_ordinary ?? 0)}</strong></span>
                          <span>Qualified: <strong>{formatCurrency(item.div_qualified ?? 0)}</strong></span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {bItems.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">1099-B (Capital Gains)</h3>
                    <p className="text-sm text-stone-600">{bItems.length} form(s) on file — {summary ? formatCurrency(summary.capital_gains_long + summary.capital_gains_short) : "—"} total</p>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Documents on file */}
          <Card padding="lg">
            <div className="flex items-center gap-2 mb-4">
              <Package size={18} className="text-amber-500" />
              <h2 className="text-sm font-semibold text-stone-800">Documents on File</h2>
            </div>
            {documents.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="mx-auto text-stone-200 mb-3" size={36} />
                <p className="text-stone-500 text-sm">No tax documents uploaded yet.</p>
                <p className="text-stone-400 text-xs mt-1">Import W-2s, 1099s, and other tax documents via the Import page.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-stone-50 text-sm">
                    <div className="flex items-center gap-3">
                      <FileText size={16} className="text-stone-400" />
                      <div>
                        <p className="font-medium text-stone-700">{doc.filename}</p>
                        <p className="text-xs text-stone-400 capitalize">{doc.document_type} · {doc.status}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* CPA sharing note */}
          <Card padding="lg" className="print:hidden">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#DCFCE7] flex items-center justify-center flex-shrink-0">
                <Printer size={20} className="text-[#16A34A]" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-stone-800">Share with your Tax Preparer</h3>
                <p className="text-sm text-stone-500 mt-1">
                  Use the &quot;Print / PDF&quot; button above to save this report as a PDF. Send it along with
                  your original W-2, 1099, and other tax documents to your CPA or tax preparer.
                </p>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function SummaryItem({ label, value, color }: { label: string; value: string; color?: "green" | "red" }) {
  const colorCls = color === "green" ? "text-green-600" : color === "red" ? "text-red-600" : "text-stone-800";
  return (
    <div className="bg-stone-50 rounded-lg p-3">
      <p className="text-xs text-stone-500">{label}</p>
      <p className={`font-semibold mt-0.5 tabular-nums ${colorCls}`}>{value}</p>
    </div>
  );
}
