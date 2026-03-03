"use client";
import { Loader2, Target } from "lucide-react";
import { formatCurrency, monthName } from "@/lib/utils";
import type { BudgetForecastResponse, SpendVelocity } from "@/types/api";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";

interface Props {
  forecastData: BudgetForecastResponse | null;
  velocity: SpendVelocity[];
  loading: boolean;
  year: number;
  month: number;
}

const now = new Date();

export default function BudgetForecastPanel({ forecastData, velocity, loading, year, month }: Props) {
  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-stone-300" size={24} />
      </div>
    );
  }

  if (!forecastData) {
    return (
      <Card className="text-center py-10">
        <Target className="mx-auto text-stone-200 mb-3" size={36} />
        <p className="text-stone-400 text-sm">No forecast data available.</p>
      </Card>
    );
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  const isCurrentMonth = year === now.getFullYear() && month === now.getMonth();

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">
          Next Month Forecast — {monthName(forecastData.forecast.month)} {forecastData.forecast.year}
        </h3>
        <div className="space-y-2">
          {forecastData.forecast.categories.map((c) => {
            const confLabel = c.confidence >= 0.7 ? "high" : c.confidence >= 0.4 ? "medium" : "low";
            const confColor = confLabel === "high" ? "text-green-600" : confLabel === "medium" ? "text-amber-600" : "text-stone-500";
            return (
              <div key={c.category} className="flex items-center justify-between py-2 border-b border-stone-100 last:border-0">
                <span className="text-sm text-stone-700">{c.category}</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium tabular-nums text-stone-900">{formatCurrency(c.predicted_amount)}</span>
                  <span className={`text-xs font-medium ${confColor}`}>{confLabel}</span>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card padding="lg">
        <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Spend Velocity</h3>
        <div className="space-y-4">
          {velocity.length === 0 ? (
            <p className="text-sm text-stone-500">No budget categories set for this month.</p>
          ) : (
            velocity.map((v) => {
              const statusColor = v.status === "on_track" ? "text-green-600" : v.status === "watch" ? "text-amber-600" : "text-red-600";
              const barColor = v.status === "on_track" ? "#16a34a" : v.status === "watch" ? "#f59e0b" : "#dc2626";
              const daysElapsed = isCurrentMonth ? Math.min(now.getDate(), daysInMonth) : daysInMonth;
              const daysRemaining = Math.max(0, daysInMonth - daysElapsed);
              return (
                <div key={v.category} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-stone-700 font-medium">{v.category}</span>
                    <span className="tabular-nums text-stone-500">
                      {formatCurrency(v.spent_so_far)} / {formatCurrency(v.budget)}
                    </span>
                  </div>
                  <ProgressBar value={v.spent_so_far} max={v.budget} color={barColor} size="sm" />
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-medium ${statusColor}`}>{v.status.replace("_", " ")}</span>
                    <span className="text-stone-500">
                      Projected: {formatCurrency(v.projected_total)}
                      {isCurrentMonth && daysRemaining > 0 && ` · ${daysRemaining} days left`}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>

      {forecastData.seasonal && Object.keys(forecastData.seasonal).length > 0 && (
        <Card padding="lg">
          <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Seasonal Patterns</h3>
          <div className="space-y-2">
            {Object.entries(forecastData.seasonal).map(([cat, data]) => {
              const peaks = data?.peaks ?? {};
              const targetPeak = peaks[forecastData.target_month];
              if (!targetPeak) return null;
              return (
                <p key={cat} className="text-sm text-stone-600">
                  <span className="font-medium text-stone-700">{cat}</span>
                  {" — "}
                  {monthName(forecastData.target_month)} historically {targetPeak.toFixed(1)}x average
                </p>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
