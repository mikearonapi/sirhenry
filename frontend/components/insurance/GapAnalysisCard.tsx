"use client";

import { ShieldCheck, Loader2 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import type { InsuranceGapAnalysis } from "@/types/api";
import { SEVERITY_CONFIG } from "./constants";

interface GapAnalysisCardProps {
  gapAnalysis: InsuranceGapAnalysis | null;
  loading: boolean;
  onRun: () => void;
}

export default function GapAnalysisCard({ gapAnalysis, loading, onRun }: GapAnalysisCardProps) {
  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Coverage Gap Analysis</h3>
          <p className="text-xs text-text-secondary mt-0.5">Compare your coverage against recommended levels</p>
        </div>
        <button
          onClick={onRun}
          disabled={loading}
          className="flex items-center gap-2 bg-text-primary text-white px-3 py-2 rounded-lg text-xs font-medium hover:bg-text-secondary disabled:opacity-60"
        >
          {loading ? <Loader2 size={13} className="animate-spin" /> : <ShieldCheck size={13} />}
          Run Analysis
        </button>
      </div>

      {gapAnalysis ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="text-center p-3 bg-surface rounded-xl">
              <p className="text-xl font-bold text-text-primary">{gapAnalysis.total_policies}</p>
              <p className="text-xs text-text-secondary">Active Policies</p>
            </div>
            <div className="text-center p-3 bg-surface rounded-xl">
              <p className="text-xl font-bold text-text-primary">{formatCurrency(gapAnalysis.total_monthly_premium)}</p>
              <p className="text-xs text-text-secondary">Monthly Cost</p>
            </div>
            <div className="text-center p-3 bg-red-50 rounded-xl">
              <p className="text-xl font-bold text-red-600">{gapAnalysis.high_severity_gaps}</p>
              <p className="text-xs text-red-500">Critical Gaps</p>
            </div>
            <div className="text-center p-3 bg-amber-50 rounded-xl">
              <p className="text-xl font-bold text-amber-600">{gapAnalysis.medium_severity_gaps}</p>
              <p className="text-xs text-amber-500">Review Needed</p>
            </div>
          </div>

          {gapAnalysis.gaps.map((gap) => {
            const cfg = SEVERITY_CONFIG[gap.severity];
            const Icon = cfg.icon;
            return (
              <div key={gap.type} className={`p-4 rounded-xl border ${cfg.bg}`}>
                <div className="flex items-start gap-3">
                  <Icon size={16} className={`mt-0.5 shrink-0 ${cfg.color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-text-primary">{gap.label}</p>
                      <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                    </div>
                    <p className="text-xs text-text-secondary mt-1">{gap.note}</p>
                    {gap.gap > 0 && (
                      <div className="mt-2 flex items-center gap-4 text-xs">
                        <span className="text-text-secondary">Current: <span className="font-medium text-text-secondary">{formatCurrency(gap.current_coverage)}</span></span>
                        <span className="text-text-secondary">Recommended: <span className="font-medium text-text-secondary">{formatCurrency(gap.recommended_coverage)}</span></span>
                        <span className="text-text-secondary">Gap: <span className="font-medium text-red-600">{formatCurrency(gap.gap)}</span></span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-text-muted text-center py-4">Run the analysis to see coverage gaps and recommendations.</p>
      )}
    </Card>
  );
}
