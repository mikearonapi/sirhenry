"use client";
import { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, Cell,
} from "recharts";
import {
  Loader2, AlertCircle, AlertTriangle, DollarSign, BarChart3, Zap,
  ArrowUpRight, ArrowDownRight, Activity,
} from "lucide-react";
import { getInsights, submitOutlierFeedback, deleteOutlierFeedback } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Insights, OutlierTransaction, OutlierClassification } from "@/types/api";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { SEASONAL_COLORS } from "@/components/insights/constants";
import { useThemeColors } from "@/hooks/useThemeColors";
import ExpenseOutlierReview from "@/components/insights/ExpenseOutlierReview";
import MonthlyAnalysisSection from "@/components/insights/MonthlyAnalysisSection";
import CategoryTrendsSection from "@/components/insights/CategoryTrendsSection";

interface InsightsSectionProps {
  selectedYear: number;
}

export default function InsightsSection({ selectedYear }: InsightsSectionProps) {
  const [data, setData] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadInsights = useCallback((signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    getInsights(selectedYear)
      .then((insights) => {
        if (signal?.aborted) return;
        setData(insights);
      })
      .catch((e: Error) => {
        if (!signal?.aborted) setError(e.message);
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false);
      });
  }, [selectedYear]);

  useEffect(() => {
    const controller = new AbortController();
    loadInsights(controller.signal);
    return () => controller.abort();
  }, [loadInsights]);

  const handleClassify = async (tx: OutlierTransaction, classification: OutlierClassification, note?: string) => {
    await submitOutlierFeedback({
      transaction_id: tx.id,
      classification,
      user_note: note,
      apply_to_future: true,
      year: selectedYear,
    });
    loadInsights();
  };

  const handleUndo = async (tx: OutlierTransaction) => {
    if (!tx.feedback) return;
    await deleteOutlierFeedback(tx.feedback.id);
    loadInsights();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-text-muted">
        <Loader2 className="animate-spin" size={22} />
        <span>Analyzing {selectedYear} financial data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40">
        <div className="flex items-center gap-3 text-red-700 dark:text-red-400">
          <AlertCircle size={20} />
          <div>
            <p className="font-semibold">Failed to load insights</p>
            <p className="text-sm mt-0.5">{error}</p>
          </div>
        </div>
      </Card>
    );
  }

  if (!data) return null;

  const { summary, monthly_analysis, normalized_budget, seasonal_patterns,
    category_trends, income_analysis, year_over_year } = data;

  const colors = useThemeColors();

  const seasonalChartData = seasonal_patterns.map((s) => ({
    name: s.month_name.slice(0, 3),
    index: s.seasonal_index,
    label: s.label,
    amount: Math.round(s.average_expenses),
  }));

  const savingsFromNormalization = summary.normalization_savings;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-green-50 dark:bg-green-950/40 flex items-center justify-center">
              <DollarSign size={16} className="text-green-600 dark:text-green-400" />
            </div>
            <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Normalized Budget</span>
          </div>
          <p className="text-2xl font-bold text-text-primary tabular-nums">
            {formatCurrency(summary.normalized_monthly_budget, true)}
          </p>
          <p className="text-xs text-text-muted mt-1">per month (excluding outliers)</p>
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-xs text-text-secondary">
              vs {formatCurrency(summary.actual_monthly_average, true)} actual avg
            </span>
          </div>
        </Card>

        <Card padding="lg">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950/40 flex items-center justify-center">
              <AlertTriangle size={16} className="text-amber-600 dark:text-amber-400" />
            </div>
            <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Expense Outliers</span>
          </div>
          <p className="text-2xl font-bold text-text-primary tabular-nums">{summary.expense_outlier_count}</p>
          <p className="text-xs text-text-muted mt-1">flagged transactions</p>
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-xs text-red-500 font-medium">{formatCurrency(summary.total_outlier_expenses, true)} total</span>
          </div>
        </Card>

        <Card padding="lg">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950/40 flex items-center justify-center">
              <Zap size={16} className="text-blue-600 dark:text-blue-400" />
            </div>
            <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Income Outliers</span>
          </div>
          <p className="text-2xl font-bold text-text-primary tabular-nums">{summary.income_outlier_count}</p>
          <p className="text-xs text-text-muted mt-1">bonus / windfall items</p>
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-xs text-green-500 font-medium">{formatCurrency(summary.total_outlier_income, true)} total</span>
          </div>
        </Card>

        <Card padding="lg">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-purple-50 dark:bg-purple-950/40 flex items-center justify-center">
              <Activity size={16} className="text-purple-600 dark:text-purple-400" />
            </div>
            <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Budget Impact</span>
          </div>
          <p className="text-2xl font-bold text-text-primary tabular-nums">{formatCurrency(savingsFromNormalization, true)}</p>
          <p className="text-xs text-text-muted mt-1">avg/month from outliers</p>
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-xs text-text-secondary">{data.transaction_count.toLocaleString()} total transactions</span>
          </div>
        </Card>
      </div>

      {/* Monthly Expenses: Actual vs Normalized */}
      <MonthlyAnalysisSection monthlyAnalysis={monthly_analysis} />

      {/* Outlier Review Section */}
      <ExpenseOutlierReview
        expenseOutliers={data.expense_outliers}
        outlierReview={data.outlier_review ?? null}
        onClassify={handleClassify}
        onUndo={handleUndo}
        onError={(msg) => setError(msg)}
      />

      {/* Income Outliers */}
      <Card padding="none">
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <div>
            <h2 className="text-sm font-semibold text-text-secondary">Income Windfalls & Bonuses</h2>
            <p className="text-xs text-text-muted mt-0.5">Income above your regular monthly pattern</p>
          </div>
          <Badge variant="success">{data.income_outliers.length}</Badge>
        </div>
        {data.income_outliers.length === 0 ? (
          <p className="text-text-muted text-sm text-center py-8 px-5">No income outliers detected.</p>
        ) : (
          <div className="divide-y divide-border-light">
            {data.income_outliers.slice(0, 8).map((tx) => (
              <div key={tx.id} className="px-5 py-3 hover:bg-surface/50">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">{tx.description}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-text-muted">{tx.date ? formatDate(tx.date) : "\u2014"}</span>
                      <Badge variant="default">{tx.category}</Badge>
                    </div>
                  </div>
                  <div className="text-right ml-3">
                    <p className="text-sm font-semibold text-green-600 tabular-nums">+{formatCurrency(tx.amount)}</p>
                    <p className="text-xs text-text-muted">typical: {formatCurrency(tx.typical_amount)}</p>
                  </div>
                </div>
                <p className="text-xs text-blue-600 dark:text-blue-400 mt-1.5 bg-blue-50/50 dark:bg-blue-950/30 rounded px-2 py-1">{tx.reason}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Normalized Budget */}
      <Card padding="lg">
        <div className="mb-5">
          <h2 className="text-sm font-semibold text-text-secondary">Your Normalized Monthly Budget</h2>
          <p className="text-xs text-text-muted mt-0.5">
            What your &quot;real&quot; monthly spending looks like with outliers removed &mdash; the median of typical months
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-green-50 dark:bg-green-950/40 rounded-lg p-4 text-center">
            <p className="text-xl font-bold text-green-700 dark:text-green-400">{formatCurrency(normalized_budget.normalized_monthly_total, true)}</p>
            <p className="text-xs text-green-600 dark:text-green-500 uppercase mt-1">Normalized / Mo</p>
          </div>
          <div className="bg-surface rounded-lg p-4 text-center">
            <p className="text-xl font-bold text-text-secondary">{formatCurrency(normalized_budget.mean_monthly_total, true)}</p>
            <p className="text-xs text-text-secondary uppercase mt-1">Actual Avg / Mo</p>
          </div>
          <div className="bg-blue-50 dark:bg-blue-950/40 rounded-lg p-4 text-center">
            <p className="text-xl font-bold text-blue-700 dark:text-blue-400">{formatCurrency(normalized_budget.min_month, true)}</p>
            <p className="text-xs text-blue-600 dark:text-blue-500 uppercase mt-1">Lowest Month</p>
          </div>
          <div className="bg-red-50 dark:bg-red-950/40 rounded-lg p-4 text-center">
            <p className="text-xl font-bold text-red-700 dark:text-red-400">{formatCurrency(normalized_budget.max_month, true)}</p>
            <p className="text-xs text-red-600 dark:text-red-500 uppercase mt-1">Highest Month</p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-card-border">
                <th className="text-left py-2 text-xs font-medium text-text-muted uppercase">Category</th>
                <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Normalized / Mo</th>
                <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Avg / Mo</th>
                <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Range</th>
                <th className="text-right py-2 text-xs font-medium text-text-muted uppercase">Months</th>
              </tr>
            </thead>
            <tbody>
              {normalized_budget.by_category.slice(0, 15).map((cat) => (
                <tr key={cat.category} className="border-b border-border-light hover:bg-surface/50">
                  <td className="py-2.5 font-medium text-text-secondary">{cat.category}</td>
                  <td className="py-2.5 text-right tabular-nums font-semibold text-text-primary">{formatCurrency(cat.normalized_monthly)}</td>
                  <td className="py-2.5 text-right tabular-nums text-text-secondary">{formatCurrency(cat.mean_monthly)}</td>
                  <td className="py-2.5 text-right tabular-nums text-text-muted text-xs">{formatCurrency(cat.min_monthly)} – {formatCurrency(cat.max_monthly)}</td>
                  <td className="py-2.5 text-right tabular-nums text-text-muted">{cat.months_active}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Seasonal Patterns */}
      <Card padding="lg">
        <div className="mb-5">
          <h2 className="text-sm font-semibold text-text-secondary">Seasonal Spending Patterns</h2>
          <p className="text-xs text-text-muted mt-0.5">
            Spending index relative to your annual average (100 = average). Higher values indicate months where you consistently spend more.
          </p>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={seasonalChartData} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.gridLine} />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: colors.axisText }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={(v: number) => `${v}`} tick={{ fontSize: 12, fill: colors.axisText }} axisLine={false} tickLine={false} domain={[0, "auto"]} />
            <Tooltip
              contentStyle={{ borderRadius: 8, border: `1px solid ${colors.tooltipBorder}`, backgroundColor: colors.tooltipBg, color: colors.tooltipText, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
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
              <span className="text-xs text-text-secondary capitalize">{label.replace("_", " ")}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Category Trends */}
      <CategoryTrendsSection categoryTrends={category_trends} />

      {/* Income Analysis & Year Over Year */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card padding="lg">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Income Breakdown</h2>
          <div className="grid grid-cols-2 gap-4 mb-5">
            <div className="bg-green-50 dark:bg-green-950/40 rounded-lg p-4 text-center">
              <p className="text-xl font-bold text-green-700 dark:text-green-400">{formatCurrency(income_analysis.regular_monthly_median, true)}</p>
              <p className="text-xs text-green-600 dark:text-green-500 uppercase mt-1">Regular / Mo</p>
            </div>
            <div className="bg-amber-50 dark:bg-amber-950/40 rounded-lg p-4 text-center">
              <p className="text-xl font-bold text-amber-700 dark:text-amber-400">{formatCurrency(income_analysis.total_irregular, true)}</p>
              <p className="text-xs text-amber-600 dark:text-amber-500 uppercase mt-1">Irregular / Year</p>
            </div>
          </div>
          <h3 className="text-xs font-medium text-text-muted uppercase mb-3">Income Sources</h3>
          <div className="space-y-2">
            {income_analysis.by_source.map((src) => {
              const total = income_analysis.total_regular + income_analysis.total_irregular;
              const pct = total > 0 ? (src.total / total * 100) : 0;
              return (
                <div key={src.source} className="flex items-center gap-3">
                  <span className="text-sm text-text-secondary flex-1 truncate">{src.source}</span>
                  <div className="w-20 h-1.5 bg-surface rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                  <span className="text-sm font-semibold text-text-primary tabular-nums w-20 text-right">{formatCurrency(src.total, true)}</span>
                </div>
              );
            })}
          </div>
        </Card>

        {year_over_year ? (
          <Card padding="lg">
            <h2 className="text-sm font-semibold text-text-secondary mb-4">
              Year Over Year: {selectedYear} vs {selectedYear - 1}
            </h2>
            <div className="space-y-4 mb-5">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">Income</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-text-primary tabular-nums">{formatCurrency(year_over_year.current_year_income, true)}</span>
                  <span className={`text-xs font-medium flex items-center gap-0.5 ${year_over_year.income_change_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {year_over_year.income_change_pct >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                    {Math.abs(year_over_year.income_change_pct).toFixed(1)}%
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">Expenses</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-text-primary tabular-nums">{formatCurrency(year_over_year.current_year_expenses, true)}</span>
                  <span className={`text-xs font-medium flex items-center gap-0.5 ${year_over_year.expense_change_pct <= 0 ? "text-green-600" : "text-red-600"}`}>
                    {year_over_year.expense_change_pct >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                    {Math.abs(year_over_year.expense_change_pct).toFixed(1)}%
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between border-t border-card-border pt-3">
                <span className="text-sm font-medium text-text-secondary">Net Savings</span>
                <span className={`text-sm font-bold tabular-nums ${year_over_year.current_year_net >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {formatCurrency(year_over_year.current_year_net, true)}
                </span>
              </div>
            </div>
            <h3 className="text-xs font-medium text-text-muted uppercase mb-3">Biggest Category Changes</h3>
            <div className="space-y-2">
              {year_over_year.category_changes.slice(0, 6).map((cat) => (
                <div key={cat.category} className="flex items-center gap-3">
                  <span className="text-xs text-text-secondary flex-1 truncate">{cat.category}</span>
                  <span className={`text-xs font-medium flex items-center gap-0.5 ${cat.change_pct > 10 ? "text-red-500" : cat.change_pct < -10 ? "text-green-500" : "text-text-muted"}`}>
                    {cat.change_pct > 0 ? "+" : ""}{cat.change_pct.toFixed(0)}%
                  </span>
                  <span className="text-xs tabular-nums text-text-secondary w-16 text-right">{formatCurrency(cat.current_year, true)}</span>
                </div>
              ))}
            </div>
          </Card>
        ) : (
          <Card padding="lg">
            <h2 className="text-sm font-semibold text-text-secondary mb-4">Year Over Year</h2>
            <div className="text-center py-8">
              <BarChart3 className="mx-auto text-text-muted mb-2" size={32} />
              <p className="text-text-muted text-sm">No prior year data available for comparison.</p>
              <p className="text-text-muted text-xs mt-1">Import {selectedYear - 1} statements to enable YoY analysis.</p>
            </div>
          </Card>
        )}
      </div>

      {/* Monthly YoY Comparison Chart */}
      {year_over_year && year_over_year.monthly_comparison.length > 0 && (() => {
        const hasPrior2 = year_over_year.prior_year_2 != null
          && year_over_year.monthly_comparison.some((m) => (m.prior_2_expenses ?? 0) > 0);
        const prior2Year = year_over_year.prior_year_2;
        const chartYears = hasPrior2
          ? `${selectedYear} vs ${selectedYear - 1} vs ${prior2Year}`
          : `${selectedYear} vs ${selectedYear - 1}`;
        return (
          <Card padding="lg">
            <div className="mb-5">
              <h2 className="text-sm font-semibold text-text-secondary">Monthly Expense Comparison: {chartYears}</h2>
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={year_over_year.monthly_comparison.map((m) => {
                  const row: Record<string, string | number> = {
                    name: m.month_name.slice(0, 3),
                    [String(selectedYear)]: Math.round(m.current_expenses),
                    [String(selectedYear - 1)]: Math.round(m.prior_expenses),
                  };
                  if (hasPrior2 && prior2Year != null) {
                    row[String(prior2Year)] = Math.round(m.prior_2_expenses ?? 0);
                  }
                  return row;
                })}
                margin={{ top: 5, right: 5, left: 5, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={colors.gridLine} />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: colors.axisText }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12, fill: colors.axisText }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: `1px solid ${colors.tooltipBorder}`, backgroundColor: colors.tooltipBg, color: colors.tooltipText, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                  formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: colors.axisText }} />
                <Bar dataKey={String(selectedYear)} fill={colors.accent} radius={[4, 4, 0, 0]} />
                <Bar dataKey={String(selectedYear - 1)} fill={colors.neutral} radius={[4, 4, 0, 0]} />
                {hasPrior2 && prior2Year != null && (
                  <Bar dataKey={String(prior2Year)} fill={colors.axisText} radius={[4, 4, 0, 0]} />
                )}
              </BarChart>
            </ResponsiveContainer>
          </Card>
        );
      })()}
    </div>
  );
}
