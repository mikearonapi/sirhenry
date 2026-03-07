"use client";
import { useState } from "react";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Insights, MonthlyAnalysis, CategoryTrend, OutlierTransaction } from "@/types/api";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { CLASSIFICATION_STYLES, TREND_ICONS } from "@/components/insights/constants";
import ExpenseOutlierReview from "@/components/insights/ExpenseOutlierReview";
import { SkeletonCard, SkeletonChart } from "./constants";

interface InsightsHook {
  data: Insights | null;
  loading: boolean;
  classify: (tx: OutlierTransaction, classification: import("@/types/api").OutlierClassification, note?: string) => Promise<void>;
  undoClassification: (tx: OutlierTransaction) => Promise<void>;
  setError: (msg: string | null) => void;
}

interface Props {
  insights: InsightsHook;
}

export default function TrendsTab({ insights }: Props) {
  const [expandedCategories, setExpandedCategories] = useState(false);
  const iData = insights.data;

  const monthlyChartData = iData?.monthly_analysis.map((m: MonthlyAnalysis) => ({
    name: m.month_name.slice(0, 3),
    "Total Expenses": Math.round(m.total_expenses),
    "Normalized Expenses": Math.round(m.expenses_excl_outliers),
    "Outlier Amount": Math.round(m.outlier_expense_total),
    Income: Math.round(m.total_income),
    classification: m.classification,
  })) ?? [];

  const visibleCategories = iData
    ? (expandedCategories ? iData.category_trends : iData.category_trends.slice(0, 10))
    : [];

  /* Loading skeleton */
  if (insights.loading) {
    return (
      <div className="space-y-5">
        <SkeletonChart />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <SkeletonCard rows={4} />
          <SkeletonCard rows={4} />
        </div>
      </div>
    );
  }

  if (!iData) return null;

  return (
    <div className="space-y-6">
      {/* Monthly Expenses: Actual vs Normalized */}
      {monthlyChartData.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-sm font-semibold text-text-secondary">Monthly Spending: Actual vs Normalized</h2>
              <p className="text-xs text-text-muted mt-0.5">
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
                    <span className="text-xs text-text-muted ml-1">
                      ({m.outlier_count} outlier{m.outlier_count > 1 ? "s" : ""})
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Expense Outlier Review */}
      <ExpenseOutlierReview
        expenseOutliers={iData.expense_outliers}
        outlierReview={iData.outlier_review}
        onClassify={insights.classify}
        onUndo={insights.undoClassification}
        onError={(msg) => insights.setError(msg)}
      />

      {/* Income Windfalls & Bonuses */}
      <Card padding="none">
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <div>
            <h2 className="text-sm font-semibold text-text-secondary">Income Windfalls & Bonuses</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Income above your regular monthly pattern
            </p>
          </div>
          <Badge variant="success">{iData.income_outliers.length}</Badge>
        </div>
        {iData.income_outliers.length === 0 ? (
          <p className="text-text-muted text-sm text-center py-8 px-5">No income outliers detected.</p>
        ) : (
          <div className="divide-y divide-border-light">
            {iData.income_outliers.slice(0, 8).map((tx: OutlierTransaction) => (
              <div key={tx.id} className="px-5 py-3 hover:bg-surface/50">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">{tx.description}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-text-muted">
                        {tx.date ? formatDate(tx.date) : "\u2014"}
                      </span>
                      <Badge variant="default">{tx.category}</Badge>
                    </div>
                  </div>
                  <div className="text-right ml-3">
                    <p className="text-sm font-semibold text-green-600 tabular-nums">+{formatCurrency(tx.amount)}</p>
                    <p className="text-xs text-text-muted">typical: {formatCurrency(tx.typical_amount)}</p>
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

      {/* Category Spending Trends */}
      {iData.category_trends.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-sm font-semibold text-text-secondary">Category Spending Trends</h2>
              <p className="text-xs text-text-muted mt-0.5">
                Direction and volatility of spending by category (first half vs second half of year)
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-card-border">
                  <th className="text-left py-2 text-xs font-medium text-text-muted uppercase">Category</th>
                  <th className="text-center py-2 text-xs font-medium text-text-muted uppercase">Trend</th>
                  <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Annual Total</th>
                  <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Avg / Mo</th>
                  <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Volatility</th>
                  <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Share</th>
                </tr>
              </thead>
              <tbody>
                {visibleCategories.map((cat: CategoryTrend) => (
                  <tr key={cat.category} className="border-b border-border-light hover:bg-surface/50">
                    <td className="py-2.5 font-medium text-text-secondary">{cat.category}</td>
                    <td className="py-2.5 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        {TREND_ICONS[cat.trend]}
                        <span className={`text-xs font-medium capitalize ${
                          cat.trend === "increasing" ? "text-red-500"
                          : cat.trend === "decreasing" ? "text-green-500"
                          : "text-text-muted"
                        }`}>
                          {cat.trend === "insufficient_data" ? "N/A" : cat.trend}
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 text-right tabular-nums font-semibold text-text-primary">
                      {formatCurrency(cat.total_annual)}
                    </td>
                    <td className="py-2.5 text-right tabular-nums text-text-secondary">
                      {formatCurrency(cat.monthly_average)}
                    </td>
                    <td className="py-2.5 text-right tabular-nums text-text-muted">
                      \u00b1{formatCurrency(cat.volatility)}
                    </td>
                    <td className="py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 h-1.5 bg-surface rounded-full overflow-hidden">
                          <div
                            className="h-full bg-accent rounded-full"
                            style={{ width: `${Math.min(cat.budget_share_pct, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs tabular-nums text-text-secondary w-10 text-right">
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
              className="w-full py-2.5 mt-2 text-xs text-accent font-medium hover:bg-surface rounded-lg flex items-center justify-center gap-1"
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
    </div>
  );
}
