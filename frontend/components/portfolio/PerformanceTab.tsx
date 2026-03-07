"use client";
import { Loader2 } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { PortfolioSummary, PortfolioPerformance } from "@/types/api";
import Card from "@/components/ui/Card";

interface PerformanceTabProps {
  performance: PortfolioPerformance | null;
  summary: PortfolioSummary | null;
  loading: boolean;
}

export default function PerformanceTab({ performance, summary, loading }: PerformanceTabProps) {
  if (loading) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-text-muted" size={28} /></div>;
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <Card padding="lg">
        <p className="text-xs text-text-secondary font-medium">Time-Weighted Return</p>
        <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${(performance?.time_weighted_return ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
          {performance ? `${performance.time_weighted_return >= 0 ? "+" : ""}${formatPercent(performance.time_weighted_return)}` : "-"}
        </p>
      </Card>
      <Card padding="lg">
        {summary?.has_cost_basis ? (
          <>
            <p className="text-xs text-text-secondary font-medium">Total Return</p>
            <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${(summary?.total_gain_loss_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
              {summary ? `${summary.total_gain_loss_pct >= 0 ? "+" : ""}${formatPercent(summary.total_gain_loss_pct)}` : "-"}
            </p>
          </>
        ) : summary?.weighted_avg_return != null ? (
          <>
            <p className="text-xs text-text-secondary font-medium">Avg Annual Return</p>
            <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${summary.weighted_avg_return >= 0 ? "text-green-600" : "text-red-600"}`}>
              {summary.weighted_avg_return >= 0 ? "+" : ""}{formatPercent(summary.weighted_avg_return)}
            </p>
          </>
        ) : (
          <>
            <p className="text-xs text-text-secondary font-medium">Total Return</p>
            <p className="text-xl font-semibold text-text-muted mt-1">-</p>
          </>
        )}
      </Card>
      <Card padding="lg">
        <p className="text-xs text-text-secondary font-medium">Total Value</p>
        <p className="text-2xl font-bold text-text-primary mt-1 font-mono tabular-nums">{summary ? formatCurrency(summary.total_value, true) : "-"}</p>
      </Card>
      <Card padding="lg">
        <p className="text-xs text-text-secondary font-medium">Cost Basis</p>
        {summary?.has_cost_basis ? (
          <p className="text-2xl font-bold text-text-primary mt-1 font-mono tabular-nums">{formatCurrency(summary.total_cost_basis, true)}</p>
        ) : (
          <p className="text-xl font-semibold text-text-muted mt-1">Not tracked</p>
        )}
      </Card>
    </div>
  );
}
