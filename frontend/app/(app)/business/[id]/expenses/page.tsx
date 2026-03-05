"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  ArrowLeft, Download, Printer, Loader2, AlertCircle,
  ChevronLeft, ChevronRight, TrendingUp, TrendingDown, Minus,
  Calendar,
} from "lucide-react";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import { getEntityExpenseReport, getEntityExpenseCsvUrl, getBusinessEntities } from "@/lib/api";
import { formatCurrency, monthName } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import type { EntityExpenseReport, BusinessEntity } from "@/types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CHART_COLORS = [
  "#16A34A", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899",
  "#06b6d4", "#ef4444", "#64748b", "#a855f7", "#14b8a6",
];

const now = new Date();

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EntityExpensesPage() {
  const params = useParams();
  const entityId = Number(params.id);
  const [year, setYear] = useState(now.getFullYear());
  const [report, setReport] = useState<EntityExpenseReport | null>(null);
  const [entity, setEntity] = useState<BusinessEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterMonth, setFilterMonth] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, entities] = await Promise.all([
        getEntityExpenseReport(entityId, year),
        getBusinessEntities(true),
      ]);
      setReport(data);
      setEntity(entities.find((e) => e.id === entityId) ?? null);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [entityId, year]);

  useEffect(() => { load(); }, [load]);

  // Chart data — fill all 12 months
  const chartData = useMemo(() => {
    if (!report) return [];
    return Array.from({ length: 12 }, (_, i) => {
      const month = i + 1;
      const found = report.monthly_totals.find((m) => m.month === month);
      return {
        month,
        name: monthName(month).slice(0, 3),
        total: found ? Math.abs(found.total_expenses) : 0,
        count: found?.transaction_count ?? 0,
      };
    });
  }, [report]);

  // Category data for pie chart
  const categoryData = useMemo(() => {
    if (!report) return [];
    return report.category_breakdown
      .filter((c) => c.total !== 0)
      .map((c) => ({
        name: c.category,
        value: Math.abs(c.total),
        percentage: c.percentage,
      }))
      .sort((a, b) => b.value - a.value);
  }, [report]);

  // Summary stats
  const ytdTotal = report?.year_total_expenses ?? 0;
  const priorTotal = report?.prior_year_total_expenses ?? null;
  const yoyChange = report?.year_over_year_change_pct ?? null;
  const monthlyAvg = ytdTotal && chartData.filter((d) => d.total > 0).length > 0
    ? Math.abs(ytdTotal) / chartData.filter((d) => d.total > 0).length
    : 0;

  function handleExportCsv() {
    const url = getEntityExpenseCsvUrl(entityId, year, filterMonth ?? undefined);
    window.open(url, "_blank");
  }

  function handlePrint() {
    window.print();
  }

  return (
    <div className="space-y-6 print:space-y-4">
      {/* Header — hidden print, shows clean version */}
      <div className="print:hidden">
        <PageHeader
          title={entity?.name ? `${entity.name} — Expenses` : "Business Expenses"}
          subtitle={`${year} expense breakdown and transaction detail`}
          actions={
            <div className="flex items-center gap-2">
              <a
                href={`/business/${entityId}`}
                className="flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-700 border border-stone-200 rounded-lg px-3 py-2"
              >
                <ArrowLeft size={14} /> Back
              </a>
              <button
                onClick={handleExportCsv}
                className="flex items-center gap-1.5 text-sm text-stone-600 border border-stone-200 rounded-lg px-3 py-2 hover:bg-stone-50"
              >
                <Download size={14} /> Export CSV
              </button>
              <button
                onClick={handlePrint}
                className="flex items-center gap-1.5 text-sm text-stone-600 border border-stone-200 rounded-lg px-3 py-2 hover:bg-stone-50"
              >
                <Printer size={14} /> Print
              </button>
            </div>
          }
        />
      </div>

      {/* Print-only header */}
      <div className="hidden print:block">
        <h1 className="text-xl font-bold text-stone-900">
          {entity?.name ?? "Business"} — {year} Expense Report
        </h1>
        <p className="text-sm text-stone-500 mt-1">
          Generated {new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100 print:hidden">
          <AlertCircle size={18} />
          <p className="text-sm flex-1">{error}</p>
        </div>
      )}

      {/* Year selector */}
      <div className="flex items-center gap-3 print:hidden">
        <button
          onClick={() => setYear((y) => y - 1)}
          className="p-1.5 rounded-lg border border-stone-200 text-stone-500 hover:bg-stone-50"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm font-semibold text-stone-800 min-w-[4rem] text-center">{year}</span>
        <button
          onClick={() => setYear((y) => y + 1)}
          disabled={year >= now.getFullYear()}
          className="p-1.5 rounded-lg border border-stone-200 text-stone-500 hover:bg-stone-50 disabled:opacity-40"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-stone-500 text-sm py-12 justify-center">
          <Loader2 size={16} className="animate-spin" /> Loading expense data...
        </div>
      ) : !report ? (
        <Card padding="lg">
          <p className="text-sm text-stone-500 text-center py-8">No expense data found for this entity in {year}.</p>
        </Card>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card padding="md">
              <p className="text-xs text-stone-500 uppercase tracking-wider">YTD Expenses</p>
              <p className="text-2xl font-bold font-mono text-stone-900 mt-1">
                {formatCurrency(Math.abs(ytdTotal))}
              </p>
            </Card>
            <Card padding="md">
              <p className="text-xs text-stone-500 uppercase tracking-wider">Monthly Average</p>
              <p className="text-2xl font-bold font-mono text-stone-900 mt-1">
                {formatCurrency(monthlyAvg)}
              </p>
            </Card>
            <Card padding="md">
              <p className="text-xs text-stone-500 uppercase tracking-wider">vs Prior Year</p>
              <div className="flex items-center gap-2 mt-1">
                {yoyChange !== null ? (
                  <>
                    {yoyChange > 0 ? (
                      <TrendingUp size={18} className="text-red-500" />
                    ) : yoyChange < 0 ? (
                      <TrendingDown size={18} className="text-green-600" />
                    ) : (
                      <Minus size={18} className="text-stone-400" />
                    )}
                    <span className={`text-2xl font-bold font-mono ${
                      yoyChange > 0 ? "text-red-600" : yoyChange < 0 ? "text-green-600" : "text-stone-900"
                    }`}>
                      {yoyChange > 0 ? "+" : ""}{yoyChange.toFixed(1)}%
                    </span>
                  </>
                ) : (
                  <span className="text-lg text-stone-400">No prior data</span>
                )}
              </div>
              {priorTotal !== null && (
                <p className="text-xs text-stone-400 mt-1">{year - 1}: {formatCurrency(Math.abs(priorTotal))}</p>
              )}
            </Card>
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            {/* Monthly bar chart */}
            <Card padding="md" className="lg:col-span-3">
              <h3 className="text-sm font-semibold text-stone-900 mb-4">Monthly Expenses</h3>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#78716c" }} />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#78716c" }}
                      tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      formatter={(v) => typeof v === "number" ? [formatCurrency(v), "Expenses"] : String(v ?? "")}
                      labelFormatter={(label) => `${String(label)} ${year}`}
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    />
                    <Bar
                      dataKey="total"
                      fill="#16A34A"
                      radius={[4, 4, 0, 0]}
                      cursor="pointer"
                      onClick={(_data, index) => {
                        const month = (index ?? 0) + 1;
                        setFilterMonth(filterMonth === month ? null : month);
                      }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {filterMonth && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-stone-500">
                    Filtered to: <strong>{monthName(filterMonth)}</strong>
                  </span>
                  <button
                    onClick={() => setFilterMonth(null)}
                    className="text-xs text-[#16A34A] hover:underline"
                  >
                    Clear
                  </button>
                </div>
              )}
            </Card>

            {/* Category breakdown */}
            <Card padding="md" className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-stone-900 mb-4">By Category</h3>
              {categoryData.length > 0 ? (
                <>
                  <div className="h-[200px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={categoryData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={45}
                          outerRadius={75}
                          paddingAngle={2}
                        >
                          {categoryData.map((_, i) => (
                            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")}
                          contentStyle={{ fontSize: 12, borderRadius: 8 }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-1.5 mt-2 max-h-[200px] overflow-y-auto">
                    {categoryData.map((cat, i) => (
                      <div key={cat.name} className="flex items-center gap-2 text-xs">
                        <span
                          className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                        />
                        <span className="text-stone-700 flex-1 truncate">{cat.name}</span>
                        <span className="font-mono text-stone-500">{formatCurrency(cat.value)}</span>
                        <span className="text-stone-400 w-10 text-right">{cat.percentage.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-xs text-stone-400 py-8 text-center">No category data</p>
              )}
            </Card>
          </div>

          {/* Monthly detail table */}
          <Card padding="md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-stone-900">Monthly Detail</h3>
              <div className="flex items-center gap-2 print:hidden">
                <Calendar size={14} className="text-stone-400" />
                <select
                  value={filterMonth ?? ""}
                  onChange={(e) => setFilterMonth(e.target.value ? Number(e.target.value) : null)}
                  className="text-xs border border-stone-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
                >
                  <option value="">All Months</option>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                    <option key={m} value={m}>{monthName(m)}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-stone-100">
                    <th className="text-left text-xs font-medium text-stone-500 pb-2 pr-4">Month</th>
                    <th className="text-right text-xs font-medium text-stone-500 pb-2 pr-4">Transactions</th>
                    <th className="text-right text-xs font-medium text-stone-500 pb-2 pr-4">Total</th>
                    <th className="text-right text-xs font-medium text-stone-500 pb-2">% of Year</th>
                  </tr>
                </thead>
                <tbody>
                  {chartData
                    .filter((d) => !filterMonth || d.month === filterMonth)
                    .filter((d) => d.total > 0 || d.count > 0)
                    .map((d) => {
                      const pct = Math.abs(ytdTotal) > 0 ? (d.total / Math.abs(ytdTotal)) * 100 : 0;
                      return (
                        <tr key={d.month} className="border-b border-stone-50 hover:bg-stone-50">
                          <td className="py-2 pr-4 text-stone-800 font-medium">{monthName(d.month)}</td>
                          <td className="py-2 pr-4 text-right font-mono text-stone-500">{d.count}</td>
                          <td className="py-2 pr-4 text-right font-mono text-stone-900">{formatCurrency(d.total)}</td>
                          <td className="py-2 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <div className="w-16 bg-stone-100 rounded-full h-1.5">
                                <div
                                  className="bg-[#16A34A] h-1.5 rounded-full"
                                  style={{ width: `${Math.min(pct, 100)}%` }}
                                />
                              </div>
                              <span className="text-xs text-stone-500 w-10 text-right">{pct.toFixed(1)}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
                {!filterMonth && (
                  <tfoot>
                    <tr className="border-t border-stone-200">
                      <td className="py-2 pr-4 font-semibold text-stone-900">Total</td>
                      <td className="py-2 pr-4 text-right font-mono text-stone-500">
                        {chartData.reduce((s, d) => s + d.count, 0)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono font-semibold text-stone-900">
                        {formatCurrency(Math.abs(ytdTotal))}
                      </td>
                      <td className="py-2 text-right text-xs text-stone-400">100%</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </Card>

          {/* Entity description — print only */}
          {entity?.description && (
            <div className="hidden print:block text-xs text-stone-500 mt-4">
              <strong>About:</strong> {entity.description}
            </div>
          )}
        </>
      )}

      {/* Print styles */}
      <style jsx global>{`
        @media print {
          nav, aside, header, [data-sidebar], .print\\:hidden {
            display: none !important;
          }
          body {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          .print\\:block {
            display: block !important;
          }
        }
      `}</style>
    </div>
  );
}
