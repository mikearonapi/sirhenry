"use client";
import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, LineChart, Line, Legend,
} from "recharts";
import { Loader2, TrendingUp, TrendingDown, AlertCircle } from "lucide-react";
import { getMonthlyReport, getPeriods } from "@/lib/api";
import { formatCurrency, monthName, safeJsonParse } from "@/lib/utils";
import type { FinancialPeriod, MonthlyReport } from "@/types/api";
import StatCard from "@/components/ui/StatCard";

const currentYear = new Date().getFullYear();
const currentMonth = new Date().getMonth() + 1;

type View = "income_statement" | "cash_flow";

export default function StatementsPage() {
  const [view, setView] = useState<View>("income_statement");
  const [segment, setSegment] = useState("all");
  const [year, setYear] = useState(currentYear);
  const [month, setMonth] = useState<number | null>(null);
  const [periods, setPeriods] = useState<FinancialPeriod[]>([]);
  const [monthly, setMonthly] = useState<MonthlyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiInsights, setAiInsights] = useState<string | null>(null);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPeriods(year, segment)
      .then(setPeriods)
      .catch((e: any) => { setError(e.message); setPeriods([]); })
      .finally(() => setLoading(false));
  }, [year, segment]);

  useEffect(() => {
    if (month) {
      getMonthlyReport(year, month)
        .then(setMonthly)
        .catch((e: any) => { setError(e.message); setMonthly(null); });
    } else {
      setMonthly(null);
    }
  }, [year, month]);

  async function loadAiInsights() {
    if (!month) return;
    setLoadingInsights(true);
    try {
      const res = await getMonthlyReport(year, month, true);
      setAiInsights(res.ai_insights ?? null);
    } finally {
      setLoadingInsights(false);
    }
  }

  const monthlyPeriods = periods.filter((p) => p.month !== null).sort((a, b) => (a.month ?? 0) - (b.month ?? 0));
  const annual = periods.find((p) => p.month === null);

  const chartData = monthlyPeriods.map((p) => ({
    name: monthName(p.month ?? 1).slice(0, 3),
    Income: Math.round(p.total_income),
    Expenses: Math.round(p.total_expenses),
    Net: Math.round(p.net_cash_flow),
    "W-2": Math.round(p.w2_income),
    "Investment": Math.round(p.investment_income),
    "Board": Math.round(p.board_income),
  }));

  const displayPeriod = month ? monthly?.period : annual;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Financial Statements</h1>
          <p className="text-stone-500 text-sm mt-0.5">Income statement and cash flow</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
            className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
          >
            <option value="all">All</option>
            <option value="personal">Personal</option>
            <option value="business">Business</option>
            <option value="investment">Investment</option>
          </select>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
          >
            {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select
            value={month ?? ""}
            onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : null)}
            className="text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
          >
            <option value="">Full Year</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>{monthName(m)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* View tabs */}
      <div className="flex gap-1 bg-stone-100 rounded-lg p-1 w-fit">
        {(["income_statement", "cash_flow"] as View[]).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              view === v ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-700"
            }`}
          >
            {v === "income_statement" ? "Income Statement" : "Cash Flow"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center gap-3 text-stone-400 justify-center h-48">
          <Loader2 className="animate-spin" size={20} />
          Loading…
        </div>
      ) : (
        <>
          {error && (
            <div className="bg-red-50 text-red-700 rounded-xl p-5 mb-6 flex items-center gap-3">
              <AlertCircle size={20} />
              <div>
                <p className="font-semibold">Failed to load data</p>
                <p className="text-sm mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* Summary cards */}
          {displayPeriod && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Total Income" value={formatCurrency(displayPeriod.total_income, true)} icon={<TrendingUp size={18} />} />
              <StatCard label="Total Expenses" value={formatCurrency(displayPeriod.total_expenses, true)} icon={<TrendingDown size={18} />} />
              <StatCard
                label="Net Cash Flow"
                value={formatCurrency(displayPeriod.net_cash_flow, true)}
                trend={displayPeriod.net_cash_flow >= 0 ? "up" : "down"}
              />
              <StatCard label="Business Expenses" value={formatCurrency(displayPeriod.business_expenses, true)} />
            </div>
          )}

          {/* Income sources */}
          {displayPeriod && (
            <div className="grid grid-cols-3 gap-4">
              <StatCard size="sm" label="W-2 Income" value={formatCurrency(displayPeriod.w2_income, true)} />
              <StatCard size="sm" label="Investment Income" value={formatCurrency(displayPeriod.investment_income, true)} />
              <StatCard size="sm" label="Board / Director Income" value={formatCurrency(displayPeriod.board_income, true)} />
            </div>
          )}

          {/* Chart */}
          {chartData.length > 0 && (
            <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-stone-700 mb-4">
                {view === "income_statement" ? "Monthly Income vs. Expenses" : "Monthly Cash Flow"} — {year}
              </h2>
              <ResponsiveContainer width="100%" height={280}>
                {view === "income_statement" ? (
                  <BarChart data={chartData} margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")} />
                    <Legend />
                    <Bar dataKey="Income" fill="#6366f1" radius={[3, 3, 0, 0]} stackId="income" />
                    <Bar dataKey="Expenses" fill="#f87171" radius={[3, 3, 0, 0]} />
                  </BarChart>
                ) : (
                  <LineChart data={chartData} margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")} />
                    <Legend />
                    <Line type="monotone" dataKey="Net" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="Income" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="Expenses" stroke="#f87171" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          )}

          {/* Expense breakdown */}
          {displayPeriod?.expense_breakdown && (
            <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-stone-700 mb-4">Expense Breakdown</h2>
              <div className="space-y-2">
                {Object.entries(safeJsonParse<Record<string, number>>(displayPeriod.expense_breakdown, {}))
                  .slice(0, 12)
                  .map(([cat, amount]) => {
                    const total = displayPeriod.total_expenses || 1;
                    const pct = Math.round((amount / total) * 100);
                    return (
                      <div key={cat} className="flex items-center gap-3 text-sm">
                        <span className="w-48 truncate text-stone-700">{cat}</span>
                        <div className="flex-1 bg-stone-100 rounded-full h-2">
                          <div
                            className="bg-indigo-400 h-2 rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-24 text-right tabular-nums text-stone-600">{formatCurrency(amount)}</span>
                        <span className="w-10 text-right text-stone-400 text-xs">{pct}%</span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* AI Monthly Insights */}
          {month && (
            <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-stone-700">
                  AI Insights — {monthName(month)} {year}
                </h2>
                <button
                  onClick={loadAiInsights}
                  disabled={loadingInsights}
                  className="flex items-center gap-2 text-sm text-[#16A34A] hover:underline disabled:opacity-60"
                >
                  {loadingInsights ? <Loader2 size={14} className="animate-spin" /> : null}
                  {aiInsights ? "Regenerate" : "Generate AI Insights"}
                </button>
              </div>
              {aiInsights ? (
                <pre className="whitespace-pre-wrap font-sans text-sm text-stone-700 leading-relaxed">{aiInsights}</pre>
              ) : (
                <p className="text-stone-400 text-sm">Click "Generate AI Insights" to get a Claude-written monthly financial review.</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
