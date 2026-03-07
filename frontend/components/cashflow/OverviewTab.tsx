"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import { formatCurrency, CATEGORY_COLORS } from "@/lib/utils";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import { EXPENSE_COLORS, INCOME_COLORS } from "./constants";

interface ChartDatum {
  name: string;
  Income: number;
  Expenses: number;
  Net: number;
}

interface Props {
  totalIncome: number;
  totalExpenses: number;
  totalSavings: number;
  savingsRate: number;
  chartData: ChartDatum[];
  topExpenseCategories: [string, number][];
  incomeEntries: [string, number][];
  year: number;
}

export default function OverviewTab({
  totalIncome,
  totalExpenses,
  totalSavings,
  savingsRate,
  chartData,
  topExpenseCategories,
  incomeEntries,
  year,
}: Props) {
  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card padding="lg">
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-1">Income</p>
          <p className="text-2xl font-bold text-text-primary tracking-tight">{formatCurrency(totalIncome, true)}</p>
        </Card>
        <Card padding="lg">
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-1">Expenses</p>
          <p className="text-2xl font-bold text-text-primary tracking-tight">{formatCurrency(totalExpenses, true)}</p>
        </Card>
        <Card padding="lg">
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-1">Total Savings</p>
          <p className={`text-2xl font-bold tracking-tight ${totalSavings >= 0 ? "text-green-600" : "text-red-600"}`}>
            {formatCurrency(totalSavings, true)}
          </p>
        </Card>
        <Card padding="lg" className={savingsRate >= 20 ? "ring-1 ring-green-200" : ""}>
          <p className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-1">Savings Rate</p>
          <p className={`text-2xl font-bold tracking-tight ${savingsRate >= 20 ? "text-green-600" : savingsRate >= 0 ? "text-amber-600" : "text-red-600"}`}>
            {savingsRate.toFixed(1)}%
          </p>
        </Card>
      </div>

      {/* Cash Flow Chart */}
      {chartData.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-text-secondary">Cash Flow — {year}</h2>
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

      {/* Income & Expense Breakdowns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Income */}
        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-secondary">Income</h2>
            <span className="text-xs text-text-muted">By source</span>
          </div>
          {incomeEntries.length === 0 ? (
            <p className="text-text-muted text-sm text-center py-6">No income data yet.</p>
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
                        <span className="text-sm text-text-secondary truncate">{cat}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-semibold tabular-nums text-text-primary">{formatCurrency(amt, true)}</span>
                        <span className="text-xs text-text-muted w-12 text-right tabular-nums">{pct.toFixed(1)}%</span>
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
            <h2 className="text-sm font-semibold text-text-secondary">Expenses</h2>
            <span className="text-xs text-text-muted">By category</span>
          </div>
          {topExpenseCategories.length === 0 ? (
            <p className="text-text-muted text-sm text-center py-6">No expense data yet.</p>
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
                        <span className="text-sm text-text-secondary truncate">{cat}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-semibold tabular-nums text-text-primary">{formatCurrency(amt, true)}</span>
                        <span className="text-xs text-text-muted w-12 text-right tabular-nums">{pct.toFixed(1)}%</span>
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
    </div>
  );
}
