"use client";
import { TrendingDown, Target, BarChart3 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { TaxStrategy } from "@/types/api";

export default function StrategySummaryBar({ strategies }: { strategies: TaxStrategy[] }) {
  if (strategies.length === 0) return null;

  const totalSavingsLow = strategies.reduce((sum, s) => sum + (s.estimated_savings_low ?? 0), 0);
  const totalSavingsHigh = strategies.reduce((sum, s) => sum + (s.estimated_savings_high ?? 0), 0);
  const withConfidence = strategies.filter((s) => s.confidence != null);
  const avgConfidence = withConfidence.length > 0
    ? withConfidence.reduce((sum, s) => sum + (s.confidence ?? 0), 0) / withConfidence.length
    : null;

  const categoryCounts = strategies.reduce<Record<string, number>>((acc, s) => {
    const cat = s.category ?? "this_year";
    acc[cat] = (acc[cat] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="bg-gradient-to-r from-[#DCFCE7] to-emerald-50 rounded-xl border border-[#16A34A]/20 p-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#16A34A]/10 flex items-center justify-center flex-shrink-0">
            <TrendingDown size={18} className="text-[#16A34A]" />
          </div>
          <div>
            <p className="text-xs text-stone-500">Potential Savings</p>
            <p className="font-semibold text-[#16A34A] font-mono tabular-nums">
              {formatCurrency(totalSavingsLow, true)}–{formatCurrency(totalSavingsHigh, true)}
            </p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#16A34A]/10 flex items-center justify-center flex-shrink-0">
            <Target size={18} className="text-[#16A34A]" />
          </div>
          <div>
            <p className="text-xs text-stone-500">Strategies Found</p>
            <p className="font-semibold text-stone-800">{strategies.length}</p>
          </div>
        </div>
        {avgConfidence != null && (
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#16A34A]/10 flex items-center justify-center flex-shrink-0">
              <BarChart3 size={18} className="text-[#16A34A]" />
            </div>
            <div>
              <p className="text-xs text-stone-500">Avg Confidence</p>
              <p className="font-semibold text-stone-800 font-mono tabular-nums">{(avgConfidence * 100).toFixed(0)}%</p>
            </div>
          </div>
        )}
        <div className="flex items-start gap-3">
          <div className="flex flex-wrap gap-1.5">
            {categoryCounts.quick_win && (
              <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">{categoryCounts.quick_win} Quick Win{categoryCounts.quick_win > 1 ? "s" : ""}</span>
            )}
            {categoryCounts.this_year && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">{categoryCounts.this_year} This Year</span>
            )}
            {categoryCounts.big_move && (
              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">{categoryCounts.big_move} Big Move{categoryCounts.big_move > 1 ? "s" : ""}</span>
            )}
            {categoryCounts.long_term && (
              <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">{categoryCounts.long_term} Long-Term</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
