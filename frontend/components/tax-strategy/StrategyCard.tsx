"use client";
import { useState } from "react";
import { ChevronDown, ChevronUp, MessageCircle, X, Shield, Info } from "lucide-react";
import { formatCurrency, priorityColor, priorityLabel } from "@/lib/utils";
import type { TaxStrategy } from "@/types/api";
import Badge from "@/components/ui/Badge";
import SirHenryName from "@/components/ui/SirHenryName";

const STRATEGY_TYPE_SIMULATOR: Record<string, string> = {
  retirement: "roth-conversion",
  structure: "scorp-analysis",
  timing: "estimated-payments",
  deduction: "daf-bunching",
};

const COMPLEXITY_CONFIG = {
  low: { label: "Simple", color: "text-green-600 bg-green-50" },
  medium: { label: "Moderate", color: "text-amber-600 bg-amber-50" },
  high: { label: "Complex", color: "text-red-600 bg-red-50" },
} as const;

function confidenceColor(c: number): string {
  if (c >= 0.8) return "text-green-600 bg-green-50 border-green-200";
  if (c >= 0.5) return "text-amber-600 bg-amber-50 border-amber-200";
  return "text-red-600 bg-red-50 border-red-200";
}

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function StrategyCard({ strategy, onDismiss, onOpenSimulator }: {
  strategy: TaxStrategy;
  onDismiss: (id: number) => void;
  onOpenSimulator?: (key: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const simulatorKey = strategy.related_simulator ?? STRATEGY_TYPE_SIMULATOR[strategy.strategy_type];
  const prerequisites: string[] = strategy.prerequisites_json ? (() => { try { return JSON.parse(strategy.prerequisites_json); } catch { return []; } })() : [];

  return (
    <div className="bg-card rounded-xl border border-card-border shadow-sm">
      <div className="flex items-center gap-4 p-5 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <Badge className={priorityColor(strategy.priority)}>{priorityLabel(strategy.priority)}</Badge>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-semibold text-text-primary">{strategy.title}</p>
            {strategy.confidence != null && (
              <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${confidenceColor(strategy.confidence)}`}>
                {(strategy.confidence * 100).toFixed(0)}%
              </span>
            )}
            {strategy.complexity && (
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${COMPLEXITY_CONFIG[strategy.complexity]?.color ?? ""}`}>
                {COMPLEXITY_CONFIG[strategy.complexity]?.label ?? strategy.complexity}
              </span>
            )}
          </div>
          <p className="text-xs text-text-secondary mt-0.5 capitalize">{strategy.strategy_type.replace("_", " ")}</p>
        </div>
        {(strategy.estimated_savings_low || strategy.estimated_savings_high) && (
          <div className="text-right text-sm">
            <p className="font-semibold text-green-600 font-mono tabular-nums">
              {strategy.estimated_savings_low != null && strategy.estimated_savings_high != null
                ? `${formatCurrency(strategy.estimated_savings_low, true)}–${formatCurrency(strategy.estimated_savings_high, true)}`
                : formatCurrency(strategy.estimated_savings_high ?? strategy.estimated_savings_low ?? 0, true)}
            </p>
            <p className="text-xs text-text-muted">est. savings</p>
          </div>
        )}
        <div className="flex items-center gap-2">
          {strategy.deadline && <span className="text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded">{strategy.deadline}</span>}
          {expanded ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
          <button onClick={(e) => { e.stopPropagation(); onDismiss(strategy.id); }} className="p-1 rounded hover:bg-surface text-text-muted hover:text-text-secondary" aria-label="Dismiss strategy"><X size={14} /></button>
        </div>
      </div>
      {expanded && (
        <div className="px-5 pb-5 border-t border-border-light">
          <p className="text-sm text-text-secondary mt-3 leading-relaxed">{strategy.description}</p>

          {strategy.who_its_for && (
            <div className="mt-2 flex items-start gap-1.5">
              <Info size={12} className="text-text-muted mt-0.5 flex-shrink-0" />
              <p className="text-xs text-text-secondary">Best for: {strategy.who_its_for}</p>
            </div>
          )}

          {strategy.confidence_reasoning && (
            <div className="mt-2 flex items-start gap-1.5">
              <Shield size={12} className="text-text-muted mt-0.5 flex-shrink-0" />
              <p className="text-xs text-text-secondary">{strategy.confidence_reasoning}</p>
            </div>
          )}

          {prerequisites.length > 0 && (
            <div className="mt-3 bg-surface rounded-lg p-3">
              <p className="text-xs font-semibold text-text-secondary mb-1">Prerequisites</p>
              <ul className="text-xs text-text-secondary space-y-0.5">
                {prerequisites.map((p, i) => <li key={i} className="flex gap-1.5"><span className="text-text-muted">•</span>{p}</li>)}
              </ul>
            </div>
          )}

          {strategy.action_required && (
            <div className="mt-3 bg-accent-light rounded-lg p-3">
              <p className="text-xs font-semibold text-accent mb-1">Action Required</p>
              <p className="text-sm text-accent">{strategy.action_required}</p>
            </div>
          )}
          <div className="flex items-center gap-4 mt-3">
            {simulatorKey && onOpenSimulator && (
              <button type="button" onClick={(e) => { e.stopPropagation(); onOpenSimulator(simulatorKey); }} className="text-xs text-accent hover:underline">
                Explore in Simulator &rarr;
              </button>
            )}
            <button type="button" onClick={(e) => { e.stopPropagation(); askHenry(`Tell me more about this tax strategy: "${strategy.title}". Is it a good fit for my situation?`); }} className="flex items-center gap-1 text-xs text-accent hover:underline">
              <MessageCircle size={11} /> Ask <SirHenryName />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
