"use client";
import { useEffect, useMemo, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar, Legend, Cell, ComposedChart, Line,
} from "recharts";
import {
  Loader2, AlertCircle, ChevronLeft, ChevronRight, ChevronDown, ChevronUp,
  AlertTriangle, DollarSign, Zap, Activity,
  ArrowUpRight, ArrowDownRight, BarChart3,
} from "lucide-react";
import { getPeriods } from "@/lib/api";
import { formatCurrency, formatDate, monthName, safeJsonParse, CATEGORY_COLORS } from "@/lib/utils";
import type { FinancialPeriod, MonthlyAnalysis, CategoryTrend, OutlierTransaction } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import ProgressBar from "@/components/ui/ProgressBar";
import Badge from "@/components/ui/Badge";
import { useInsights } from "@/hooks/useInsights";
import { CLASSIFICATION_STYLES, TREND_ICONS, SEASONAL_COLORS } from "@/components/insights/constants";
import ExpenseOutlierReview from "@/components/insights/ExpenseOutlierReview";

function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <Card padding="lg">
      <div className="animate-pulse space-y-3">
        <div className="h-4 bg-stone-200 rounded w-1/3" />
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="h-3 bg-stone-100 rounded" style={{ width: `${80 - i * 10}%` }} />
        ))}
      </div>
    </Card>
  );
}

function SkeletonChart() {
  return (
    <Card padding="lg">
      <div className="animate-pulse">
        <div className="h-4 bg-stone-200 rounded w-2/5 mb-4" />
        <div className="h-[300px] bg-stone-50 rounded-lg flex items-end justify-around px-6 pb-4 gap-3">
          {[60, 80, 45, 90, 55, 70, 40, 65, 50, 75, 60, 85].map((h, i) => (
            <div key={i} className="bg-stone-200 rounded-t w-full" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    </Card>
  );
}

const now = new Date();

type TimeFrame = "monthly" | "quarterly" | "yearly";

const EXPENSE_COLORS = [
  "#16A34A", "#f59e0b", "#3b82f6", "#8b5cf6", "#ec4899",
  "#06b6d4", "#16a34a", "#64748b", "#ef4444", "#a855f7",
];

export default function CashFlowPage() {
  const [year, setYear] = useState(now.getFullYear());
  const [periods, setPeriods] = useState<FinancialPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<TimeFrame>("monthly");
  const [expandedCategories, setExpandedCategories] = useState(false);

  const insights = useInsights(year);

  useEffect(() => {
    setLoading(true);
    getPeriods(year)
      .then(setPeriods)
      .catch((e: unknown) => setError(getErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [year]);

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

  const INCOME_COLORS = ["#16a34a", "#22c55e", "#4ade80", "#86efac", "#bbf7d0"];

  // Insights-derived data
  const iData = insights.data;
  const monthlyChartData = iData?.monthly_analysis.map((m: MonthlyAnalysis) => ({
    name: m.month_name.slice(0, 3),
    "Total Expenses": Math.round(m.total_expenses),
    "Normalized Expenses": Math.round(m.expenses_excl_outliers),
    "Outlier Amount": Math.round(m.outlier_expense_total),
    Income: Math.round(m.total_income),
    classification: m.classification,
  })) ?? [];

  const seasonalChartData = iData?.seasonal_patterns.map((s) => ({
    name: s.month_name.slice(0, 3),
    index: s.seasonal_index,
    label: s.label,
    amount: Math.round(s.average_expenses),
  })) ?? [];

  const visibleCategories = iData
    ? (expandedCategories ? iData.category_trends : iData.category_trends.slice(0, 10))
    : [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cash Flow"
        subtitle="Income, expenses, and net cash flow over time"
        actions={
          <div className="flex items-center gap-2">
            <div className="flex bg-stone-100 rounded-lg p-0.5">
              {(["monthly", "quarterly", "yearly"] as TimeFrame[]).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    timeframe === tf ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-700"
                  }`}
                >
                  {tf.charAt(0).toUpperCase() + tf.slice(1)}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 border border-stone-200 rounded-lg">
              <button onClick={() => setYear(year - 1)} className="p-2 hover:bg-stone-50 rounded-l-lg">
                <ChevronLeft size={14} className="text-stone-500" />
              </button>
              <span className="text-sm font-medium text-stone-700 px-2">{year}</span>
              <button onClick={() => setYear(year + 1)} disabled={year >= now.getFullYear()} className="p-2 hover:bg-stone-50 rounded-r-lg disabled:opacity-30">
                <ChevronRight size={14} className="text-stone-500" />
              </button>
            </div>
          </div>
        }
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card padding="lg">
          <p className="text-xs font-medium text-stone-500 uppercase tracking-wider mb-1">Income</p>
          <p className="text-2xl font-bold text-stone-900 tracking-tight">{formatCurrency(totalIncome, true)}</p>
        </Card>
        <Card padding="lg">
          <p className="text-xs font-medium text-stone-500 uppercase tracking-wider mb-1">Expenses</p>
          <p className="text-2xl font-bold text-stone-900 tracking-tight">{formatCurrency(totalExpenses, true)}</p>
        </Card>
        <Card padding="lg">
          <p className="text-xs font-medium text-stone-500 uppercase tracking-wider mb-1">Total Savings</p>
          <p className={`text-2xl font-bold tracking-tight ${totalSavings >= 0 ? "text-green-600" : "text-red-600"}`}>
            {formatCurrency(totalSavings, true)}
          </p>
        </Card>
        <Card padding="lg" className={savingsRate >= 20 ? "ring-1 ring-green-200" : ""}>
          <p className="text-xs font-medium text-stone-500 uppercase tracking-wider mb-1">Savings Rate</p>
          <p className={`text-2xl font-bold tracking-tight ${savingsRate >= 20 ? "text-green-600" : savingsRate >= 0 ? "text-amber-600" : "text-red-600"}`}>
            {savingsRate.toFixed(1)}%
          </p>
        </Card>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      ) : (
        <>
          {error && (
            <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
              <AlertCircle size={18} />
              <p className="text-sm">{error}</p>
            </div>
          )}

          {/* Cash Flow Chart */}
          {chartData.length > 0 && (
            <Card padding="lg">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-sm font-semibold text-stone-700">Cash Flow — {year}</h2>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, border: "1px solid #e7e5e4", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                    formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Income" fill="#86efac" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Expenses" fill="#fca5a5" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Monthly Expenses: Actual vs Normalized (from Insights) */}
          {iData && monthlyChartData.length > 0 && (
            <Card padding="lg">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h2 className="text-sm font-semibold text-stone-700">Monthly Spending: Actual vs Normalized</h2>
                  <p className="text-xs text-stone-400 mt-0.5">
                    Orange bars show outlier spending that inflates your monthly totals
                  </p>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <ComposedChart data={monthlyChartData} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, border: "1px solid #e7e5e4", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                    formatter={(v, name) => [typeof v === "number" ? formatCurrency(v) : String(v ?? ""), String(name)]}
                  />
                  <Legend wrapperStyle={{ fontSize: 12, color: "#78716c" }} />
                  <Bar dataKey="Normalized Expenses" stackId="expenses" fill="#86efac" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="Outlier Amount" stackId="expenses" fill="#fdba74" radius={[4, 4, 0, 0]} />
                  <Line type="monotone" dataKey="Income" stroke="#16a34a" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                </ComposedChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-2 mt-4">
                {iData.monthly_analysis.map((m: MonthlyAnalysis) => {
                  const style = CLASSIFICATION_STYLES[m.classification] || CLASSIFICATION_STYLES.normal;
                  return (
                    <div key={m.month} className={`${style.bg} rounded-lg px-3 py-1.5`}>
                      <span className={`text-xs font-medium ${style.text}`}>
                        {m.month_name.slice(0, 3)}: {style.label}
                      </span>
                      {m.outlier_count > 0 && (
                        <span className="text-xs text-stone-400 ml-1">
                          ({m.outlier_count} outlier{m.outlier_count > 1 ? "s" : ""})
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {/* Income & Expense Breakdowns */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Income */}
            <Card padding="lg">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-stone-700">Income</h2>
                <span className="text-xs text-stone-400">By source</span>
              </div>
              {incomeEntries.length === 0 ? (
                <p className="text-stone-400 text-sm text-center py-6">No income data yet.</p>
              ) : (
                <div className="space-y-3">
                  {incomeEntries.map(([cat, amt], i) => {
                    const pct = totalIncome > 0 ? (amt / totalIncome) * 100 : 0;
                    const color = INCOME_COLORS[i % INCOME_COLORS.length];
                    return (
                      <div key={cat}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: color }} />
                            <span className="text-sm text-stone-700 truncate">{cat}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-semibold tabular-nums text-stone-900">{formatCurrency(amt, true)}</span>
                            <span className="text-xs text-stone-400 w-12 text-right tabular-nums">{pct.toFixed(1)}%</span>
                          </div>
                        </div>
                        <ProgressBar value={pct} color={color} size="xs" />
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            {/* Expenses */}
            <Card padding="lg">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-stone-700">Expenses</h2>
                <span className="text-xs text-stone-400">By category</span>
              </div>
              {topExpenseCategories.length === 0 ? (
                <p className="text-stone-400 text-sm text-center py-6">No expense data yet.</p>
              ) : (
                <div className="space-y-3">
                  {topExpenseCategories.map(([cat, amt], i) => {
                    const pct = totalExpenses > 0 ? (amt / totalExpenses) * 100 : 0;
                    const color = CATEGORY_COLORS[cat] ?? EXPENSE_COLORS[i % EXPENSE_COLORS.length];
                    return (
                      <div key={cat}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: color }} />
                            <span className="text-sm text-stone-700 truncate">{cat}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-semibold tabular-nums text-stone-900">{formatCurrency(amt, true)}</span>
                            <span className="text-xs text-stone-400 w-12 text-right tabular-nums">{pct.toFixed(1)}%</span>
                          </div>
                        </div>
                        <ProgressBar value={pct} color={color} size="xs" />
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </div>

          {/* ── Insights Sections ─────────────────────────────────── */}

          {/* Insights loading state */}
          {insights.loading && (
            <div className="space-y-5">
              <SkeletonChart />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <SkeletonCard rows={4} />
                <SkeletonCard rows={4} />
              </div>
            </div>
          )}

          {/* Expense Outlier Review */}
          {iData && (
            <ExpenseOutlierReview
              expenseOutliers={iData.expense_outliers}
              outlierReview={iData.outlier_review}
              onClassify={insights.classify}
              onUndo={insights.undoClassification}
              onError={(msg) => insights.setError(msg)}
            />
          )}

          {/* Income Windfalls & Bonuses */}
          {iData && (
            <Card padding="none">
              <div className="flex items-center justify-between px-5 pt-5 pb-3">
                <div>
                  <h2 className="text-sm font-semibold text-stone-700">Income Windfalls & Bonuses</h2>
                  <p className="text-xs text-stone-400 mt-0.5">
                    Income above your regular monthly pattern
                  </p>
                </div>
                <Badge variant="success">{iData.income_outliers.length}</Badge>
              </div>
              {iData.income_outliers.length === 0 ? (
                <p className="text-stone-400 text-sm text-center py-8 px-5">No income outliers detected.</p>
              ) : (
                <div className="divide-y divide-stone-50">
                  {iData.income_outliers.slice(0, 8).map((tx: OutlierTransaction) => (
                    <div key={tx.id} className="px-5 py-3 hover:bg-stone-50/50">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-stone-800 truncate">{tx.description}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[11px] text-stone-400">
                              {tx.date ? formatDate(tx.date) : "—"}
                            </span>
                            <Badge variant="default">{tx.category}</Badge>
                          </div>
                        </div>
                        <div className="text-right ml-3">
                          <p className="text-sm font-semibold text-green-600 tabular-nums">+{formatCurrency(tx.amount)}</p>
                          <p className="text-[11px] text-stone-400">typical: {formatCurrency(tx.typical_amount)}</p>
                        </div>
                      </div>
                      <p className="text-xs text-blue-600 mt-1.5 bg-blue-50/50 rounded px-2 py-1">
                        {tx.reason}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* Category Spending Trends */}
          {iData && iData.category_trends.length > 0 && (
            <Card padding="lg">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h2 className="text-sm font-semibold text-stone-700">Category Spending Trends</h2>
                  <p className="text-xs text-stone-400 mt-0.5">
                    Direction and volatility of spending by category (first half vs second half of year)
                  </p>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-stone-100">
                      <th className="text-left py-2 text-xs font-medium text-stone-400 uppercase">Category</th>
                      <th className="text-center py-2 text-xs font-medium text-stone-400 uppercase">Trend</th>
                      <th className="text-right py-2 text-xs font-medium text-stone-400 uppercase">Annual Total</th>
                      <th className="text-right py-2 text-xs font-medium text-stone-400 uppercase">Avg / Mo</th>
                      <th className="text-right py-2 text-xs font-medium text-stone-400 uppercase">Volatility</th>
                      <th className="text-right py-2 text-xs font-medium text-stone-400 uppercase">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleCategories.map((cat: CategoryTrend) => (
                      <tr key={cat.category} className="border-b border-stone-50 hover:bg-stone-50/50">
                        <td className="py-2.5 font-medium text-stone-700">{cat.category}</td>
                        <td className="py-2.5 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            {TREND_ICONS[cat.trend]}
                            <span className={`text-xs font-medium capitalize ${
                              cat.trend === "increasing" ? "text-red-500"
                              : cat.trend === "decreasing" ? "text-green-500"
                              : "text-stone-400"
                            }`}>
                              {cat.trend === "insufficient_data" ? "N/A" : cat.trend}
                            </span>
                          </div>
                        </td>
                        <td className="py-2.5 text-right tabular-nums font-semibold text-stone-800">
                          {formatCurrency(cat.total_annual)}
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-stone-500">
                          {formatCurrency(cat.monthly_average)}
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-stone-400">
                          ±{formatCurrency(cat.volatility)}
                        </td>
                        <td className="py-2.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 bg-stone-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-[#16A34A] rounded-full"
                                style={{ width: `${Math.min(cat.budget_share_pct, 100)}%` }}
                              />
                            </div>
                            <span className="text-xs tabular-nums text-stone-500 w-10 text-right">
                              {cat.budget_share_pct.toFixed(1)}%
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {iData.category_trends.length > 10 && (
                <button
                  onClick={() => setExpandedCategories(!expandedCategories)}
                  className="w-full py-2.5 mt-2 text-xs text-[#16A34A] font-medium hover:bg-stone-50 rounded-lg flex items-center justify-center gap-1"
                >
                  {expandedCategories ? (
                    <><ChevronUp size={14} /> Show top 10</>
                  ) : (
                    <><ChevronDown size={14} /> Show all {iData.category_trends.length} categories</>
                  )}
                </button>
              )}
            </Card>
          )}

          {/* Seasonal Spending Patterns */}
          {iData && seasonalChartData.length > 0 && (
            <Card padding="lg">
              <div className="mb-5">
                <h2 className="text-sm font-semibold text-stone-700">Seasonal Spending Patterns</h2>
                <p className="text-xs text-stone-400 mt-0.5">
                  Spending index relative to your annual average (100 = average). Higher values indicate months where you consistently spend more.
                </p>
              </div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={seasonalChartData} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v: number) => `${v}`} tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} domain={[0, "auto"]} />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, border: "1px solid #e7e5e4", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                    formatter={(v, name) => {
                      const val = typeof v === "number" ? v : 0;
                      if (name === "index") return [`${val.toFixed(1)}`, "Seasonal Index"];
                      return [formatCurrency(val), "Avg Expenses"];
                    }}
                  />
                  <Bar dataKey="index" radius={[4, 4, 0, 0]}>
                    {seasonalChartData.map((entry, i) => (
                      <Cell key={i} fill={SEASONAL_COLORS[entry.label] || "#22c55e"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-3 mt-4">
                {Object.entries(SEASONAL_COLORS).map(([label, color]) => (
                  <div key={label} className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
                    <span className="text-xs text-stone-500 capitalize">{label.replace("_", " ")}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Income Analysis + Year Over Year */}
          {iData && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <Card padding="lg">
                <h2 className="text-sm font-semibold text-stone-700 mb-4">Income Breakdown</h2>
                <div className="grid grid-cols-2 gap-4 mb-5">
                  <div className="bg-green-50 rounded-lg p-4 text-center">
                    <p className="text-xl font-bold text-green-700">
                      {formatCurrency(iData.income_analysis.regular_monthly_median, true)}
                    </p>
                    <p className="text-[11px] text-green-600 uppercase mt-1">Regular / Mo</p>
                  </div>
                  <div className="bg-amber-50 rounded-lg p-4 text-center">
                    <p className="text-xl font-bold text-amber-700">
                      {formatCurrency(iData.income_analysis.total_irregular, true)}
                    </p>
                    <p className="text-[11px] text-amber-600 uppercase mt-1">Irregular / Year</p>
                  </div>
                </div>
                <h3 className="text-xs font-medium text-stone-400 uppercase mb-3">Income Sources</h3>
                <div className="space-y-2">
                  {iData.income_analysis.by_source.map((src) => {
                    const total = iData.income_analysis.total_regular + iData.income_analysis.total_irregular;
                    const pct = total > 0 ? (src.total / total * 100) : 0;
                    return (
                      <div key={src.source} className="flex items-center gap-3">
                        <span className="text-sm text-stone-600 flex-1 truncate">{src.source}</span>
                        <div className="w-20 h-1.5 bg-stone-100 rounded-full overflow-hidden">
                          <div className="h-full bg-green-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                        </div>
                        <span className="text-sm font-semibold text-stone-800 tabular-nums w-20 text-right">
                          {formatCurrency(src.total, true)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>

              {iData.year_over_year ? (
                <Card padding="lg">
                  <h2 className="text-sm font-semibold text-stone-700 mb-4">
                    Year Over Year: {year} vs {year - 1}
                  </h2>
                  <div className="space-y-4 mb-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-stone-600">Income</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-stone-800 tabular-nums">
                          {formatCurrency(iData.year_over_year.current_year_income, true)}
                        </span>
                        <span className={`text-xs font-medium flex items-center gap-0.5 ${
                          iData.year_over_year.income_change_pct >= 0 ? "text-green-600" : "text-red-600"
                        }`}>
                          {iData.year_over_year.income_change_pct >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                          {Math.abs(iData.year_over_year.income_change_pct).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-stone-600">Expenses</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-stone-800 tabular-nums">
                          {formatCurrency(iData.year_over_year.current_year_expenses, true)}
                        </span>
                        <span className={`text-xs font-medium flex items-center gap-0.5 ${
                          iData.year_over_year.expense_change_pct <= 0 ? "text-green-600" : "text-red-600"
                        }`}>
                          {iData.year_over_year.expense_change_pct >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                          {Math.abs(iData.year_over_year.expense_change_pct).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between border-t border-stone-100 pt-3">
                      <span className="text-sm font-medium text-stone-700">Net Savings</span>
                      <span className={`text-sm font-bold tabular-nums ${
                        iData.year_over_year.current_year_net >= 0 ? "text-green-600" : "text-red-600"
                      }`}>
                        {formatCurrency(iData.year_over_year.current_year_net, true)}
                      </span>
                    </div>
                  </div>
                  <h3 className="text-xs font-medium text-stone-400 uppercase mb-3">Biggest Category Changes</h3>
                  <div className="space-y-2">
                    {iData.year_over_year.category_changes.slice(0, 6).map((cat) => (
                      <div key={cat.category} className="flex items-center gap-3">
                        <span className="text-xs text-stone-600 flex-1 truncate">{cat.category}</span>
                        <span className={`text-xs font-medium flex items-center gap-0.5 ${
                          cat.change_pct > 10 ? "text-red-500" : cat.change_pct < -10 ? "text-green-500" : "text-stone-400"
                        }`}>
                          {cat.change_pct > 0 ? "+" : ""}{cat.change_pct.toFixed(0)}%
                        </span>
                        <span className="text-xs tabular-nums text-stone-500 w-16 text-right">
                          {formatCurrency(cat.current_year, true)}
                        </span>
                      </div>
                    ))}
                  </div>
                </Card>
              ) : (
                <Card padding="lg">
                  <h2 className="text-sm font-semibold text-stone-700 mb-4">Year Over Year</h2>
                  <div className="text-center py-8">
                    <BarChart3 className="mx-auto text-stone-200 mb-2" size={32} />
                    <p className="text-stone-400 text-sm">No prior year data available for comparison.</p>
                    <p className="text-stone-300 text-xs mt-1">Import {year - 1} statements to enable YoY analysis.</p>
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* Monthly Expense Comparison (YoY chart) */}
          {iData?.year_over_year && iData.year_over_year.monthly_comparison.length > 0 && (() => {
            const yoy = iData.year_over_year;
            const hasPrior2 = yoy.prior_year_2 != null
              && yoy.monthly_comparison.some((m) => (m.prior_2_expenses ?? 0) > 0);
            const prior2Year = yoy.prior_year_2;
            const chartYears = hasPrior2
              ? `${year} vs ${year - 1} vs ${prior2Year}`
              : `${year} vs ${year - 1}`;
            return (
              <Card padding="lg">
                <div className="mb-5">
                  <h2 className="text-sm font-semibold text-stone-700">Monthly Expense Comparison: {chartYears}</h2>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={yoy.monthly_comparison.map((m) => {
                      const row: Record<string, string | number> = {
                        name: m.month_name.slice(0, 3),
                        [String(year)]: Math.round(m.current_expenses),
                        [String(year - 1)]: Math.round(m.prior_expenses),
                      };
                      if (hasPrior2 && prior2Year != null) {
                        row[String(prior2Year)] = Math.round(m.prior_2_expenses ?? 0);
                      }
                      return row;
                    })}
                    margin={{ top: 5, right: 5, left: 5, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" />
                    <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: 8, border: "1px solid #e7e5e4", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                      formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")}
                    />
                    <Legend wrapperStyle={{ fontSize: 12, color: "#78716c" }} />
                    <Bar dataKey={String(year)} fill="#16A34A" radius={[4, 4, 0, 0]} />
                    <Bar dataKey={String(year - 1)} fill="#d6d3d1" radius={[4, 4, 0, 0]} />
                    {hasPrior2 && prior2Year != null && (
                      <Bar dataKey={String(prior2Year)} fill="#a8a29e" radius={[4, 4, 0, 0]} />
                    )}
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            );
          })()}
        </>
      )}
    </div>
  );
}
