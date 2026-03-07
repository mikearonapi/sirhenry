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
  Calendar, Receipt,
} from "lucide-react";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import { getEntityExpenseReport, getEntityExpenseCsvUrl, getBusinessEntities, getEntityTransactions } from "@/lib/api";
import { formatCurrency, monthName } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import type { EntityExpenseReport, EntityTransaction, BusinessEntity } from "@/types/api";

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
  const [transactions, setTransactions] = useState<EntityTransaction[]>([]);
  const [txLoading, setTxLoading] = useState(false);

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

  // Load transactions when year or filterMonth changes
  useEffect(() => {
    let cancelled = false;
    setTxLoading(true);
    getEntityTransactions(entityId, year, filterMonth ?? undefined)
      .then((data) => { if (!cancelled) setTransactions(data); })
      .catch(() => { if (!cancelled) setTransactions([]); })
      .finally(() => { if (!cancelled) setTxLoading(false); });
    return () => { cancelled = true; };
  }, [entityId, year, filterMonth]);

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

  // Category data for pie chart — recompute from transactions when month is filtered
  const categoryData = useMemo(() => {
    if (filterMonth && transactions.length > 0) {
      const byCategory: Record<string, number> = {};
      for (const tx of transactions) {
        if (tx.amount >= 0) continue; // only expenses
        const cat = tx.category || "Uncategorized";
        byCategory[cat] = (byCategory[cat] ?? 0) + Math.abs(tx.amount);
      }
      const total = Object.values(byCategory).reduce((s, v) => s + v, 0);
      return Object.entries(byCategory)
        .map(([name, value]) => ({
          name,
          value: Math.round(value * 100) / 100,
          percentage: total > 0 ? Math.round((value / total) * 1000) / 10 : 0,
        }))
        .sort((a, b) => b.value - a.value);
    }
    if (!report) return [];
    return report.category_breakdown
      .filter((c) => c.total !== 0)
      .map((c) => ({
        name: c.category,
        value: Math.abs(c.total),
        percentage: c.percentage,
      }))
      .sort((a, b) => b.value - a.value);
  }, [report, filterMonth, transactions]);

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
                className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-secondary border border-border rounded-lg px-3 py-2"
              >
                <ArrowLeft size={14} /> Back
              </a>
              <button
                onClick={handleExportCsv}
                className="flex items-center gap-1.5 text-sm text-text-secondary border border-border rounded-lg px-3 py-2 hover:bg-surface"
              >
                <Download size={14} /> Export CSV
              </button>
              <button
                onClick={handlePrint}
                className="flex items-center gap-1.5 text-sm text-text-secondary border border-border rounded-lg px-3 py-2 hover:bg-surface"
              >
                <Printer size={14} /> Print
              </button>
            </div>
          }
        />
      </div>

      {/* Print-only header */}
      <div className="hidden print:block">
        <h1 className="text-xl font-bold text-text-primary">
          {entity?.name ?? "Business"} — {year} Expense Report
        </h1>
        <p className="text-sm text-text-secondary mt-1">
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
          className="p-1.5 rounded-lg border border-border text-text-secondary hover:bg-surface"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm font-semibold text-text-primary min-w-[4rem] text-center">{year}</span>
        <button
          onClick={() => setYear((y) => y + 1)}
          disabled={year >= now.getFullYear()}
          className="p-1.5 rounded-lg border border-border text-text-secondary hover:bg-surface disabled:opacity-40"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-text-secondary text-sm py-12 justify-center">
          <Loader2 size={16} className="animate-spin" /> Loading expense data...
        </div>
      ) : !report ? (
        <Card padding="lg">
          <p className="text-sm text-text-secondary text-center py-8">No expense data found for this entity in {year}.</p>
        </Card>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card padding="md">
              <p className="text-xs text-text-secondary uppercase tracking-wider">YTD Expenses</p>
              <p className="text-2xl font-bold font-mono text-text-primary mt-1">
                {formatCurrency(Math.abs(ytdTotal))}
              </p>
            </Card>
            <Card padding="md">
              <p className="text-xs text-text-secondary uppercase tracking-wider">Monthly Average</p>
              <p className="text-2xl font-bold font-mono text-text-primary mt-1">
                {formatCurrency(monthlyAvg)}
              </p>
            </Card>
            <Card padding="md">
              <p className="text-xs text-text-secondary uppercase tracking-wider">vs Prior Year</p>
              <div className="flex items-center gap-2 mt-1">
                {yoyChange !== null ? (
                  <>
                    {yoyChange > 0 ? (
                      <TrendingUp size={18} className="text-red-500" />
                    ) : yoyChange < 0 ? (
                      <TrendingDown size={18} className="text-green-600" />
                    ) : (
                      <Minus size={18} className="text-text-muted" />
                    )}
                    <span className={`text-2xl font-bold font-mono ${
                      yoyChange > 0 ? "text-red-600" : yoyChange < 0 ? "text-green-600" : "text-text-primary"
                    }`}>
                      {yoyChange > 0 ? "+" : ""}{yoyChange.toFixed(1)}%
                    </span>
                  </>
                ) : (
                  <span className="text-lg text-text-muted">No prior data</span>
                )}
              </div>
              {priorTotal !== null && (
                <p className="text-xs text-text-muted mt-1">{year - 1}: {formatCurrency(Math.abs(priorTotal))}</p>
              )}
            </Card>
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            {/* Monthly bar chart */}
            <Card padding="md" className="lg:col-span-3">
              <h3 className="text-sm font-semibold text-text-primary mb-4">Monthly Expenses</h3>
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
                  <span className="text-xs text-text-secondary">
                    Filtered to: <strong>{monthName(filterMonth)}</strong>
                  </span>
                  <button
                    onClick={() => setFilterMonth(null)}
                    className="text-xs text-accent hover:underline"
                  >
                    Clear
                  </button>
                </div>
              )}
            </Card>

            {/* Category breakdown */}
            <Card padding="md" className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-text-primary mb-4">
                By Category{filterMonth ? ` — ${monthName(filterMonth)}` : ""}
              </h3>
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
                        <span className="text-text-secondary flex-1 truncate">{cat.name}</span>
                        <span className="font-mono text-text-secondary">{formatCurrency(cat.value)}</span>
                        <span className="text-text-muted w-10 text-right">{cat.percentage.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-xs text-text-muted py-8 text-center">No category data</p>
              )}
            </Card>
          </div>

          {/* Monthly detail table */}
          <Card padding="md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text-primary">Monthly Detail</h3>
              <div className="flex items-center gap-2 print:hidden">
                <Calendar size={14} className="text-text-muted" />
                <select
                  value={filterMonth ?? ""}
                  onChange={(e) => setFilterMonth(e.target.value ? Number(e.target.value) : null)}
                  className="text-xs border border-border rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-accent/20"
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
                  <tr className="border-b border-card-border">
                    <th className="text-left text-xs font-medium text-text-secondary pb-2 pr-4">Month</th>
                    <th className="text-right text-xs font-medium text-text-secondary pb-2 pr-4">Transactions</th>
                    <th className="text-right text-xs font-medium text-text-secondary pb-2 pr-4">Total</th>
                    <th className="text-right text-xs font-medium text-text-secondary pb-2">% of Year</th>
                  </tr>
                </thead>
                <tbody>
                  {chartData
                    .filter((d) => !filterMonth || d.month === filterMonth)
                    .filter((d) => d.total > 0 || d.count > 0)
                    .map((d) => {
                      const pct = Math.abs(ytdTotal) > 0 ? (d.total / Math.abs(ytdTotal)) * 100 : 0;
                      return (
                        <tr key={d.month} className="border-b border-border-light hover:bg-surface">
                          <td className="py-2 pr-4 text-text-primary font-medium">{monthName(d.month)}</td>
                          <td className="py-2 pr-4 text-right font-mono text-text-secondary">{d.count}</td>
                          <td className="py-2 pr-4 text-right font-mono text-text-primary">{formatCurrency(d.total)}</td>
                          <td className="py-2 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <div className="w-16 bg-surface rounded-full h-1.5">
                                <div
                                  className="bg-accent h-1.5 rounded-full"
                                  style={{ width: `${Math.min(pct, 100)}%` }}
                                />
                              </div>
                              <span className="text-xs text-text-secondary w-10 text-right">{pct.toFixed(1)}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
                {!filterMonth && (
                  <tfoot>
                    <tr className="border-t border-border">
                      <td className="py-2 pr-4 font-semibold text-text-primary">Total</td>
                      <td className="py-2 pr-4 text-right font-mono text-text-secondary">
                        {chartData.reduce((s, d) => s + d.count, 0)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono font-semibold text-text-primary">
                        {formatCurrency(Math.abs(ytdTotal))}
                      </td>
                      <td className="py-2 text-right text-xs text-text-muted">100%</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </Card>

          {/* Transaction detail table */}
          <Card padding="md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Receipt size={14} className="text-text-muted" />
                Transaction Detail
                {!txLoading && (
                  <span className="text-xs font-normal text-text-muted">
                    ({transactions.length} transaction{transactions.length !== 1 ? "s" : ""})
                  </span>
                )}
              </h3>
            </div>
            {txLoading ? (
              <div className="flex items-center gap-2 text-text-secondary text-sm py-8 justify-center">
                <Loader2 size={14} className="animate-spin" /> Loading transactions...
              </div>
            ) : transactions.length === 0 ? (
              <p className="text-sm text-text-muted text-center py-8">
                No transactions found{filterMonth ? ` for ${monthName(filterMonth)}` : ""}.
              </p>
            ) : (
              <div className="max-h-[600px] overflow-y-auto">
                <table className="w-full text-sm table-fixed">
                  <thead className="sticky top-0 bg-card z-10">
                    <tr className="border-b border-card-border">
                      <th className="text-left text-xs font-medium text-text-secondary pb-2 pr-2 w-[70px]">Date</th>
                      <th className="text-left text-xs font-medium text-text-secondary pb-2 pr-2">Description</th>
                      <th className="text-left text-xs font-medium text-text-secondary pb-2 pr-2 w-[140px]">Category</th>
                      <th className="text-right text-xs font-medium text-text-secondary pb-2 w-[100px]">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx, i) => (
                      <tr key={`${tx.date}-${tx.amount}-${i}`} className="border-b border-border-light hover:bg-surface">
                        <td className="py-1.5 pr-2 text-text-secondary whitespace-nowrap text-xs">
                          {new Date(tx.date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        </td>
                        <td className="py-1.5 pr-2 text-text-primary truncate" title={tx.description}>
                          {tx.description}
                          {tx.notes && (
                            <span className="ml-1 text-xs text-text-muted" title={tx.notes}>
                              · {tx.notes}
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 pr-2 text-text-secondary text-xs truncate" title={tx.category}>
                          {tx.category ? tx.category.replace(/^Business — /, "") : "—"}
                        </td>
                        <td className={`py-1.5 text-right font-mono text-xs whitespace-nowrap ${
                          tx.amount < 0 ? "text-text-primary" : "text-green-600"
                        }`}>
                          {formatCurrency(Math.abs(tx.amount))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="sticky bottom-0 bg-card">
                    <tr className="border-t border-border">
                      <td colSpan={3} className="py-2 font-semibold text-text-primary">Total</td>
                      <td className="py-2 text-right font-mono text-xs font-semibold text-text-primary">
                        {formatCurrency(Math.abs(transactions.reduce((s, tx) => s + tx.amount, 0)))}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </Card>

          {/* Entity description — print only */}
          {entity?.description && (
            <div className="hidden print:block text-xs text-text-secondary mt-4">
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
