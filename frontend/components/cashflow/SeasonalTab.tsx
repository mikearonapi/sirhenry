"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell,
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import { useThemeColors } from "@/hooks/useThemeColors";
import type { Insights } from "@/types/api";
import Card from "@/components/ui/Card";
import { SEASONAL_COLORS } from "@/components/insights/constants";
import { SkeletonCard, SkeletonChart } from "./constants";

interface Props {
  insights: {
    data: Insights | null;
    loading: boolean;
  };
}

export default function SeasonalTab({ insights }: Props) {
  const colors = useThemeColors();
  const iData = insights.data;

  const seasonalChartData = iData?.seasonal_patterns.map((s) => ({
    name: s.month_name.slice(0, 3),
    index: s.seasonal_index,
    label: s.label,
    amount: Math.round(s.average_expenses),
  })) ?? [];

  if (insights.loading) {
    return (
      <div className="space-y-5">
        <SkeletonChart />
        <SkeletonCard rows={4} />
      </div>
    );
  }

  if (!iData) return null;

  return (
    <div className="space-y-6">
      {/* Seasonal Spending Patterns */}
      {seasonalChartData.length > 0 && (
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
      )}

      {/* Income Breakdown */}
      <Card padding="lg">
        <h2 className="text-sm font-semibold text-text-secondary mb-4">Income Breakdown</h2>
        <div className="grid grid-cols-2 gap-4 mb-5">
          <div className="bg-green-50 rounded-lg p-4 text-center">
            <p className="text-xl font-bold text-green-700">
              {formatCurrency(iData.income_analysis.regular_monthly_median, true)}
            </p>
            <p className="text-xs text-green-600 uppercase mt-1">Regular / Mo</p>
          </div>
          <div className="bg-amber-50 rounded-lg p-4 text-center">
            <p className="text-xl font-bold text-amber-700">
              {formatCurrency(iData.income_analysis.total_irregular, true)}
            </p>
            <p className="text-xs text-amber-600 uppercase mt-1">Irregular / Year</p>
          </div>
        </div>
        <h3 className="text-xs font-medium text-text-muted uppercase mb-3">Income Sources</h3>
        <div className="space-y-2">
          {iData.income_analysis.by_source.map((src) => {
            const total = iData.income_analysis.total_regular + iData.income_analysis.total_irregular;
            const pct = total > 0 ? (src.total / total * 100) : 0;
            return (
              <div key={src.source} className="flex items-center gap-3">
                <span className="text-sm text-text-secondary flex-1 truncate">{src.source}</span>
                <div className="w-20 h-1.5 bg-surface rounded-full overflow-hidden">
                  <div className="h-full bg-green-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <span className="text-sm font-semibold text-text-primary tabular-nums w-20 text-right">
                  {formatCurrency(src.total, true)}
                </span>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
