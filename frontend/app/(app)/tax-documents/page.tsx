"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Loader2, AlertCircle, Info, Printer, MessageCircle, ArrowLeftRight, TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  getTaxSummary, getTaxItems, getTaxEstimate, getTaxChecklist, getDocuments,
} from "@/lib/api";
import type {
  TaxSummary, TaxItem, TaxEstimate, TaxChecklist, Document as DocType,
} from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import {
  TaxEstimateSection,
  IncomeSummaryGrid,
  DocumentCoverage,
  FormDetailsSection,
  FilingChecklist,
} from "@/components/tax";
import { formatCurrency } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2];

export default function TaxDocumentsPage() {
  const [year, setYear] = useState(currentYear - 1);
  const [summary, setSummary] = useState<TaxSummary | null>(null);
  const [items, setItems] = useState<TaxItem[]>([]);
  const [estimate, setEstimate] = useState<TaxEstimate | null>(null);
  const [checklist, setChecklist] = useState<TaxChecklist | null>(null);
  const [documents, setDocuments] = useState<DocType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Year-over-year comparison
  const [showCompare, setShowCompare] = useState(false);
  const [prevSummary, setPrevSummary] = useState<TaxSummary | null>(null);
  const [prevEstimate, setPrevEstimate] = useState<TaxEstimate | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  const load = useCallback(async (y: number, signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [s, i, e, cl, docs] = await Promise.all([
        getTaxSummary(y).catch(() => null),
        getTaxItems(y).catch(() => []),
        getTaxEstimate(y).catch(() => null),
        getTaxChecklist(y).catch(() => null),
        getDocuments({ status: "completed", limit: 500 }).catch(() => ({ items: [], total: 0 })),
      ]);
      if (signal?.aborted) return;
      setSummary(s);
      setItems(i);
      setEstimate(e);
      setChecklist(cl);
      setDocuments(docs.items ?? []);
    } catch (err: unknown) {
      if (!signal?.aborted) setError(getErrorMessage(err));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(year, controller.signal);
    setShowCompare(false);
    setPrevSummary(null);
    setPrevEstimate(null);
    return () => controller.abort();
  }, [year, load]);

  const handleUploadComplete = useCallback(() => {
    load(year);
  }, [year, load]);

  const handleToggleCompare = useCallback(async () => {
    if (showCompare) {
      setShowCompare(false);
      return;
    }
    setCompareLoading(true);
    const prevYear = year - 1;
    try {
      const [ps, pe] = await Promise.all([
        getTaxSummary(prevYear).catch(() => null),
        getTaxEstimate(prevYear).catch(() => null),
      ]);
      setPrevSummary(ps);
      setPrevEstimate(pe);
      setShowCompare(true);
    } catch {
      // silently fail
    } finally {
      setCompareLoading(false);
    }
  }, [showCompare, year]);

  return (
    <div className="space-y-8 print:space-y-4">
      <PageHeader
        title="Tax Documents"
        subtitle="Upload, track, and prepare your tax documents"
        actions={
          <div className="flex items-center gap-3 print:hidden">
            <Link
              href="/tax-strategy"
              className="flex items-center gap-2 text-sm text-stone-600 border border-stone-200 rounded-lg px-4 py-2 hover:bg-stone-50"
            >
              Tax Strategy
            </Link>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
            >
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button
              onClick={handleToggleCompare}
              disabled={compareLoading}
              className={`flex items-center gap-2 text-sm border rounded-lg px-4 py-2 transition-colors ${
                showCompare
                  ? "bg-[#DCFCE7] border-[#16A34A]/30 text-[#16A34A]"
                  : "text-stone-600 border-stone-200 hover:bg-stone-50"
              }`}
            >
              {compareLoading ? <Loader2 size={14} className="animate-spin" /> : <ArrowLeftRight size={14} />}
              {showCompare ? `vs ${year - 1}` : "Compare Years"}
            </button>
            <button
              onClick={() => window.print()}
              className="flex items-center gap-2 text-sm text-stone-600 border border-stone-200 rounded-lg px-4 py-2 hover:bg-stone-50"
            >
              <Printer size={14} /> Print / PDF
            </button>
          </div>
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
              <div>
                <p className="font-semibold">Failed to load data</p>
                <p className="text-sm mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {estimate?.data_source === "setup_profile" && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-3 flex items-center gap-3 print:hidden">
              <Info size={16} className="text-blue-500 flex-shrink-0" />
              <p className="text-sm text-blue-700">
                Estimates based on your household profile. Upload your actual W-2s and 1099s below for accurate CPA-ready data.
              </p>
            </div>
          )}
          {estimate?.data_source === "none" && (
            <div className="bg-amber-50 border border-amber-100 rounded-xl px-5 py-3 flex items-center gap-3 print:hidden">
              <Info size={16} className="text-amber-500 flex-shrink-0" />
              <p className="text-sm text-amber-700">
                No income data yet. Complete your{" "}
                <Link href="/setup" className="font-medium underline">household profile</Link> or upload tax documents below to see estimates.
              </p>
            </div>
          )}

          {/* Year-over-Year Comparison */}
          {showCompare && prevSummary && prevEstimate && estimate && summary && (
            <YearOverYearComparison
              currentYear={year}
              currentSummary={summary}
              currentEstimate={estimate}
              prevSummary={prevSummary}
              prevEstimate={prevEstimate}
            />
          )}

          {/* Tax Estimate */}
          {estimate && <TaxEstimateSection estimate={estimate} year={year} />}

          {/* Income Summary */}
          {summary && <IncomeSummaryGrid summary={summary} year={year} />}

          {/* Document Coverage + Upload Zone */}
          {checklist && (
            <DocumentCoverage
              checklist={checklist}
              year={year}
              onUploadComplete={handleUploadComplete}
            />
          )}

          {/* Form Details */}
          <FormDetailsSection items={items} summary={summary} year={year} />

          {/* Documents on File + Filing Readiness */}
          {checklist && (
            <FilingChecklist
              checklist={checklist}
              documents={documents}
              year={year}
            />
          )}

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
                  your original W-2, 1099, K-1, and other tax documents to your CPA or tax preparer.
                </p>
                <button
                  type="button"
                  onClick={() => askHenry(`Based on my ${year} tax report, what should I discuss with my CPA? What are the key things to flag?`)}
                  className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:underline mt-2"
                >
                  <MessageCircle size={12} /> Ask Sir Henry what to discuss with your CPA
                </button>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

/** Year-over-year comparison panel */
function YearOverYearComparison({
  currentYear,
  currentSummary,
  currentEstimate,
  prevSummary,
  prevEstimate,
}: {
  currentYear: number;
  currentSummary: TaxSummary;
  currentEstimate: TaxEstimate;
  prevSummary: TaxSummary;
  prevEstimate: TaxEstimate;
}) {
  const prevYear = currentYear - 1;

  const comparisons = [
    { label: "W-2 Wages", current: currentSummary.w2_total_wages, prev: prevSummary.w2_total_wages },
    { label: "1099-NEC", current: currentSummary.nec_total, prev: prevSummary.nec_total },
    { label: "Dividends", current: currentSummary.div_ordinary, prev: prevSummary.div_ordinary },
    { label: "Capital Gains", current: currentSummary.capital_gains_long + currentSummary.capital_gains_short, prev: prevSummary.capital_gains_long + prevSummary.capital_gains_short },
    { label: "Interest", current: currentSummary.interest_income, prev: prevSummary.interest_income },
    { label: "K-1 Income", current: currentSummary.k1_ordinary_income + currentSummary.k1_guaranteed_payments, prev: prevSummary.k1_ordinary_income + prevSummary.k1_guaranteed_payments },
  ];

  const taxComparisons = [
    { label: "Estimated Adjusted Gross Income", current: currentEstimate.estimated_agi, prev: prevEstimate.estimated_agi },
    { label: "Total Tax", current: currentEstimate.total_estimated_tax, prev: prevEstimate.total_estimated_tax },
    { label: "Effective Rate", current: currentEstimate.effective_rate, prev: prevEstimate.effective_rate, isRate: true },
    { label: "Balance Due", current: currentEstimate.estimated_balance_due, prev: prevEstimate.estimated_balance_due },
  ];

  return (
    <Card padding="lg">
      <div className="flex items-center gap-2 mb-4">
        <ArrowLeftRight size={18} className="text-[#16A34A]" />
        <h3 className="text-sm font-semibold text-stone-800">
          Year-over-Year: {currentYear} vs {prevYear}
        </h3>
      </div>

      {/* Income comparison */}
      <div className="mb-4">
        <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">Income</h4>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
          {comparisons.filter((c) => c.current !== 0 || c.prev !== 0).map((c) => (
            <CompareCell key={c.label} label={c.label} current={c.current} prev={c.prev} currentYear={currentYear} prevYear={prevYear} />
          ))}
        </div>
      </div>

      {/* Tax comparison */}
      <div>
        <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">Tax Summary</h4>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {taxComparisons.map((c) => (
            <CompareCell key={c.label} label={c.label} current={c.current} prev={c.prev} currentYear={currentYear} prevYear={prevYear} isRate={c.isRate} invertColor={c.label === "Total Tax" || c.label === "Balance Due"} />
          ))}
        </div>
      </div>
    </Card>
  );
}

function CompareCell({
  label, current, prev, currentYear, prevYear, isRate, invertColor,
}: {
  label: string;
  current: number;
  prev: number;
  currentYear: number;
  prevYear: number;
  isRate?: boolean;
  invertColor?: boolean;
}) {
  const diff = current - prev;
  const pctChange = prev !== 0 ? ((current - prev) / Math.abs(prev)) * 100 : 0;
  const isUp = diff > 0;
  const isFlat = Math.abs(diff) < 1;

  // For taxes/balance due, up is bad (red), down is good (green)
  // For income, up is good (green), down is neutral
  const diffColorClass = isFlat
    ? "text-stone-400"
    : invertColor
      ? (isUp ? "text-red-600" : "text-green-600")
      : (isUp ? "text-green-600" : "text-red-600");

  return (
    <div className="bg-stone-50 rounded-lg p-3">
      <p className="text-xs text-stone-500 mb-1">{label}</p>
      <div className="flex items-end justify-between gap-2">
        <div>
          <p className="text-sm font-semibold font-mono tabular-nums text-stone-800">
            {isRate ? `${current}%` : formatCurrency(current)}
          </p>
          <p className="text-[10px] text-stone-400">
            {currentYear}: {isRate ? `${current}%` : formatCurrency(current, true)}
          </p>
          <p className="text-[10px] text-stone-400">
            {prevYear}: {isRate ? `${prev}%` : formatCurrency(prev, true)}
          </p>
        </div>
        {!isFlat && (
          <div className={`flex items-center gap-0.5 text-xs font-medium ${diffColorClass}`}>
            {isUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
            <span className="font-mono tabular-nums">
              {isRate ? `${Math.abs(diff).toFixed(1)}pp` : formatCurrency(Math.abs(diff), true)}
            </span>
            {!isRate && pctChange !== 0 && (
              <span className="text-[10px] opacity-70">({Math.abs(pctChange).toFixed(0)}%)</span>
            )}
          </div>
        )}
        {isFlat && (
          <div className="flex items-center gap-0.5 text-xs text-stone-400">
            <Minus size={10} />
            <span>No change</span>
          </div>
        )}
      </div>
    </div>
  );
}
