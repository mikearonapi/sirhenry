"use client";
import { PiggyBank, Baby } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { HouseholdOptimizationResult } from "@/types/api";
import Card from "@/components/ui/Card";

// ---------------------------------------------------------------------------
// OptimizationResults
// ---------------------------------------------------------------------------

export interface OptimizationResultsProps {
  result: HouseholdOptimizationResult;
}

export default function OptimizationResults({ result }: OptimizationResultsProps) {
  return (
    <div className="space-y-4 mt-6">
      <h3 className="text-sm font-semibold text-stone-900">Optimization Recommendations</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-3">
            <PiggyBank size={18} className="text-[#16A34A]" />
            <h4 className="text-sm font-semibold text-stone-900">Retirement Strategy</h4>
          </div>
          {result.retirement_strategy && Object.keys(result.retirement_strategy).length > 0 ? (
            <pre className="text-xs bg-stone-50 p-3 rounded-lg overflow-auto max-h-32">
              {JSON.stringify(result.retirement_strategy, null, 2)}
            </pre>
          ) : (
            <p className="text-sm text-stone-500">No retirement strategy data</p>
          )}
        </Card>
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-3">
            <Baby size={18} className="text-[#16A34A]" />
            <h4 className="text-sm font-semibold text-stone-900">Childcare Strategy</h4>
          </div>
          {result.childcare_strategy && Object.keys(result.childcare_strategy).length > 0 ? (
            <pre className="text-xs bg-stone-50 p-3 rounded-lg overflow-auto max-h-32">
              {JSON.stringify(result.childcare_strategy, null, 2)}
            </pre>
          ) : (
            <p className="text-sm text-stone-500">No childcare strategy data</p>
          )}
        </Card>
      </div>
      {result.recommendations.length > 0 && (
        <Card padding="lg">
          <h4 className="text-sm font-semibold text-stone-900 mb-3">All Recommendations</h4>
          <ul className="space-y-2">
            {result.recommendations.map((r, i) => (
              <li key={i} className="flex items-start justify-between gap-4 text-sm">
                <span className="text-stone-700">
                  <span className="font-medium text-stone-900">{r.area}:</span> {r.action}
                </span>
                <span className={`font-medium shrink-0 ${r.savings >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {formatCurrency(r.savings)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
