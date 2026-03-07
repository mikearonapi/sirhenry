"use client";
import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, AlertCircle } from "lucide-react";
import { getPeriods } from "@/lib/api";
import { monthName, safeJsonParse } from "@/lib/utils";
import type { FinancialPeriod } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import PageHeader from "@/components/ui/PageHeader";
import TabBar from "@/components/ui/TabBar";
import { useTabState } from "@/hooks/useTabState";
import { useInsights } from "@/hooks/useInsights";
import { TABS } from "@/components/cashflow/constants";
import OverviewTab from "@/components/cashflow/OverviewTab";
import TrendsTab from "@/components/cashflow/TrendsTab";
import SeasonalTab from "@/components/cashflow/SeasonalTab";
import YearOverYearTab from "@/components/cashflow/YearOverYearTab";

const now = new Date();

type TimeFrame = "monthly" | "quarterly" | "yearly";

export default function CashFlowPage() {
  const [year, setYear] = useState(now.getFullYear());
  const [periods, setPeriods] = useState<FinancialPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<TimeFrame>("monthly");
  const [activeTab, setTab] = useTabState(TABS, "overview");

  const insights = useInsights(year);

  useEffect(() => {
    setLoading(true);
    getPeriods(year)
      .then(setPeriods)
      .catch((e: unknown) => setError(getErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [year]);

  /* ── Derived data ─────────────────────────────────────── */

  const monthly = periods
    .filter((p) => p.month !== null)
    .sort((a, b) => (a.month ?? 0) - (b.month ?? 0));

  const annual = periods.find((p) => p.month === null);

  const totalIncome = annual?.total_income ?? monthly.reduce((s, p) => s + p.total_income, 0);
  const totalExpenses = annual?.total_expenses ?? monthly.reduce((s, p) => s + p.total_expenses, 0);
  const totalSavings = totalIncome - totalExpenses;
  const savingsRate = totalIncome > 0 ? (totalSavings / totalIncome) * 100 : 0;

  const quarterlyData = [1, 2, 3, 4].map((q) => {
    const months = monthly.filter((p) => Math.ceil((p.month ?? 1) / 3) === q);
    return {
      name: `Q${q}`,
      Income: Math.round(months.reduce((s, p) => s + p.total_income, 0)),
      Expenses: Math.round(months.reduce((s, p) => s + p.total_expenses, 0)),
      Net: Math.round(months.reduce((s, p) => s + p.net_cash_flow, 0)),
    };
  });

  const [allPeriods, setAllPeriods] = useState<FinancialPeriod[]>([]);
  useEffect(() => {
    if (timeframe === "yearly") {
      getPeriods(undefined)
        .then(setAllPeriods)
        .catch(() => {});
    }
  }, [timeframe]);

  const yearlyData = (() => {
    const byYear = new Map<number, { income: number; expenses: number; net: number }>();
    allPeriods
      .filter((p) => p.month === null)
      .forEach((p) => byYear.set(p.year, { income: p.total_income, expenses: p.total_expenses, net: p.net_cash_flow }));
    return Array.from(byYear.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([yr, d]) => ({ name: String(yr), Income: Math.round(d.income), Expenses: Math.round(d.expenses), Net: Math.round(d.net) }));
  })();

  const chartData = timeframe === "yearly"
    ? yearlyData
    : timeframe === "quarterly"
      ? quarterlyData
      : monthly.map((p) => ({
          name: monthName(p.month ?? 1).slice(0, 3),
          Income: Math.round(p.total_income),
          Expenses: Math.round(p.total_expenses),
          Net: Math.round(p.net_cash_flow),
        }));

  const topExpenseCategories = useMemo(() => {
    const all: Record<string, number> = {};
    monthly.forEach((p) => {
      const breakdown = safeJsonParse<Record<string, number>>(p.expense_breakdown, {});
      Object.entries(breakdown).forEach(([cat, amt]) => {
        all[cat] = (all[cat] ?? 0) + amt;
      });
    });
    return Object.entries(all).sort((a, b) => b[1] - a[1]).slice(0, 12);
  }, [monthly]);

  const incomeEntries = useMemo(() => {
    const all: Record<string, number> = {};
    monthly.forEach((p) => {
      const breakdown = safeJsonParse<Record<string, number>>(p.income_breakdown, {});
      Object.entries(breakdown).forEach(([cat, amt]) => {
        all[cat] = (all[cat] ?? 0) + amt;
      });
    });
    return Object.entries(all).sort((a, b) => b[1] - a[1]);
  }, [monthly]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cash Flow"
        subtitle="Income, expenses, and net cash flow over time"
        actions={
          <div className="flex items-center gap-2">
            {activeTab === "overview" && (
              <div className="flex bg-surface rounded-lg p-0.5">
                {(["monthly", "quarterly", "yearly"] as TimeFrame[]).map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      timeframe === tf ? "bg-card text-text-primary shadow-sm" : "text-text-secondary hover:text-text-secondary"
                    }`}
                  >
                    {tf.charAt(0).toUpperCase() + tf.slice(1)}
                  </button>
                ))}
              </div>
            )}
            <div className="flex items-center gap-1 border border-border rounded-lg">
              <button onClick={() => setYear(year - 1)} className="p-2 hover:bg-surface rounded-l-lg">
                <ChevronLeft size={14} className="text-text-secondary" />
              </button>
              <span className="text-sm font-medium text-text-secondary px-2">{year}</span>
              <button onClick={() => setYear(year + 1)} disabled={year >= now.getFullYear()} className="p-2 hover:bg-surface rounded-r-lg disabled:opacity-30">
                <ChevronRight size={14} className="text-text-secondary" />
              </button>
            </div>
          </div>
        }
      />

      <TabBar tabs={TABS} activeTab={activeTab} onChange={setTab} />

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-text-muted" size={24} /></div>
      ) : (
        <>
          {error && (
            <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
              <AlertCircle size={18} />
              <p className="text-sm">{error}</p>
            </div>
          )}

          {activeTab === "overview" && (
            <OverviewTab
              totalIncome={totalIncome}
              totalExpenses={totalExpenses}
              totalSavings={totalSavings}
              savingsRate={savingsRate}
              chartData={chartData}
              topExpenseCategories={topExpenseCategories}
              incomeEntries={incomeEntries}
              year={year}
            />
          )}

          {activeTab === "trends" && <TrendsTab insights={insights} />}

          {activeTab === "seasonal" && <SeasonalTab insights={insights} />}

          {activeTab === "yoy" && <YearOverYearTab insights={insights} year={year} />}
        </>
      )}
    </div>
  );
}
