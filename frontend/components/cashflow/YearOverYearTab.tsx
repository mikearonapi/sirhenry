"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import { ArrowUpRight, ArrowDownRight, BarChart3 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { useThemeColors } from "@/hooks/useThemeColors";
import type { Insights } from "@/types/api";
import Card from "@/components/ui/Card";
import { SkeletonCard, SkeletonChart } from "./constants";

interface Props {
  insights: {
    data: Insights | null;
    loading: boolean;
  };
  year: number;
}

export default function YearOverYearTab({ insights, year }: Props) {
  const colors = useThemeColors();
  const iData = insights.data;

  if (insights.loading) {
    return (
      <div className="space-y-5">
        <SkeletonCard rows={5} />
        <SkeletonChart />
      </div>
    );
  }

  if (!iData) return null;

  const yoy = iData.year_over_year;

  return (
    <div className="space-y-6">
      {/* Year Over Year Comparison */}
      {yoy ? (
        <Card padding="lg">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">
            Year Over Year: {year} vs {year - 1}
          </h2>
          <div className="space-y-4 mb-5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary">Income</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-text-primary tabular-nums">
                  {formatCurrency(yoy.current_year_income, true)}
                </span>
                <span className={`text-xs font-medium flex items-center gap-0.5 ${
                  yoy.income_change_pct >= 0 ? "text-green-600" : "text-red-600"
                }`}>
                  {yoy.income_change_pct >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                  {Math.abs(yoy.income_change_pct).toFixed(1)}%
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary">Expenses</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-text-primary tabular-nums">
                  {formatCurrency(yoy.current_year_expenses, true)}
                </span>
                <span className={`text-xs font-medium flex items-center gap-0.5 ${
                  yoy.expense_change_pct <= 0 ? "text-green-600" : "text-red-600"
                }`}>
                  {yoy.expense_change_pct >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                  {Math.abs(yoy.expense_change_pct).toFixed(1)}%
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between border-t border-card-border pt-3">
              <span className="text-sm font-medium text-text-secondary">Net Savings</span>
              <span className={`text-sm font-bold tabular-nums ${
                yoy.current_year_net >= 0 ? "text-green-600" : "text-red-600"
              }`}>
                {formatCurrency(yoy.current_year_net, true)}
              </span>
            </div>
          </div>
          <h3 className="text-xs font-medium text-text-muted uppercase mb-3">Biggest Category Changes</h3>
          <div className="space-y-2">
            {yoy.category_changes.slice(0, 6).map((cat) => (
              <div key={cat.category} className="flex items-center gap-3">
                <span className="text-xs text-text-secondary flex-1 truncate">{cat.category}</span>
                <span className={`text-xs font-medium flex items-center gap-0.5 ${
                  cat.change_pct > 10 ? "text-red-500" : cat.change_pct < -10 ? "text-green-500" : "text-text-muted"
                }`}>
                  {cat.change_pct > 0 ? "+" : ""}{cat.change_pct.toFixed(0)}%
                </span>
                <span className="text-xs tabular-nums text-text-secondary w-16 text-right">
                  {formatCurrency(cat.current_year, true)}
                </span>
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
            <p className="text-text-muted text-xs mt-1">Import {year - 1} statements to enable YoY analysis.</p>
          </div>
        </Card>
      )}

      {/* Monthly Expense Comparison (YoY chart) */}
      {yoy && yoy.monthly_comparison.length > 0 && (() => {
        const hasPrior2 = yoy.prior_year_2 != null
          && yoy.monthly_comparison.some((m) => (m.prior_2_expenses ?? 0) > 0);
        const prior2Year = yoy.prior_year_2;
        const chartYears = hasPrior2
          ? `${year} vs ${year - 1} vs ${prior2Year}`
          : `${year} vs ${year - 1}`;
        return (
          <Card padding="lg">
            <div className="mb-5">
              <h2 className="text-sm font-semibold text-text-secondary">Monthly Expense Comparison: {chartYears}</h2>
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
                <CartesianGrid strokeDasharray="3 3" stroke={colors.gridLine} />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: colors.axisText }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12, fill: colors.axisText }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: `1px solid ${colors.tooltipBorder}`, backgroundColor: colors.tooltipBg, color: colors.tooltipText, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                  formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: colors.axisText }} />
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
    </div>
  );
}
