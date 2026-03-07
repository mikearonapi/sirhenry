"use client";
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { CategoryTrend } from "@/types/api";
import Card from "@/components/ui/Card";
import { TREND_ICONS } from "@/components/insights/constants";

interface Props {
  categoryTrends: CategoryTrend[];
}

export default function CategoryTrendsSection({ categoryTrends }: Props) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? categoryTrends : categoryTrends.slice(0, 10);

  return (
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
            {visible.map((cat) => (
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
                  ±{formatCurrency(cat.volatility)}
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
      {categoryTrends.length > 10 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full py-2.5 mt-2 text-xs text-accent font-medium hover:bg-surface rounded-lg flex items-center justify-center gap-1"
        >
          {expanded ? (
            <><ChevronUp size={14} /> Show top 10</>
          ) : (
            <><ChevronDown size={14} /> Show all {categoryTrends.length} categories</>
          )}
        </button>
      )}
    </Card>
  );
}
