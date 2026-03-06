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
    <div className="bg-white rounded-xl border border-stone-100 shadow-sm">
      <div className="flex items-center gap-4 p-5 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <Badge className={priorityColor(strategy.priority)}>{priorityLabel(strategy.priority)}</Badge>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-semibold text-stone-800">{strategy.title}</p>
            {strategy.confidence != null && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${confidenceColor(strategy.confidence)}`}>
                {(strategy.confidence * 100).toFixed(0)}%
              </span>
            )}
            {strategy.complexity && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${COMPLEXITY_CONFIG[strategy.complexity]?.color ?? ""}`}>
                {COMPLEXITY_CONFIG[strategy.complexity]?.label ?? strategy.complexity}
              </span>
            )}
          </div>
          <p className="text-xs text-stone-500 mt-0.5 capitalize">{strategy.strategy_type.replace("_", " ")}</p>
        </div>
        {(strategy.estimated_savings_low || strategy.estimated_savings_high) && (
          <div className="text-right text-sm">
            <p className="font-semibold text-green-600 font-mono tabular-nums">
              {strategy.estimated_savings_low != null && strategy.estimated_savings_high != null
                ? `${formatCurrency(strategy.estimated_savings_low, true)}–${formatCurrency(strategy.estimated_savings_high, true)}`
                : formatCurrency(strategy.estimated_savings_high ?? strategy.estimated_savings_low ?? 0, true)}
            </p>
            <p className="text-xs text-stone-400">est. savings</p>
          </div>
        )}
        <div className="flex items-center gap-2">
          {strategy.deadline && <span className="text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded">{strategy.deadline}</span>}
          {expanded ? <ChevronUp size={16} className="text-stone-400" /> : <ChevronDown size={16} className="text-stone-400" />}
          <button onClick={(e) => { e.stopPropagation(); onDismiss(strategy.id); }} className="p-1 rounded hover:bg-stone-100 text-stone-300 hover:text-stone-500" aria-label="Dismiss strategy"><X size={14} /></button>
        </div>
      </div>
      {expanded && (
        <div className="px-5 pb-5 border-t border-stone-50">
          <p className="text-sm text-stone-700 mt-3 leading-relaxed">{strategy.description}</p>

          {strategy.who_its_for && (
            <div className="mt-2 flex items-start gap-1.5">
              <Info size={12} className="text-stone-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-stone-500">Best for: {strategy.who_its_for}</p>
            </div>
          )}

          {strategy.confidence_reasoning && (
            <div className="mt-2 flex items-start gap-1.5">
              <Shield size={12} className="text-stone-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-stone-500">{strategy.confidence_reasoning}</p>
            </div>
          )}

          {prerequisites.length > 0 && (
            <div className="mt-3 bg-stone-50 rounded-lg p-3">
              <p className="text-xs font-semibold text-stone-600 mb-1">Prerequisites</p>
              <ul className="text-xs text-stone-600 space-y-0.5">
                {prerequisites.map((p, i) => <li key={i} className="flex gap-1.5"><span className="text-stone-400">•</span>{p}</li>)}
              </ul>
            </div>
          )}

          {strategy.action_required && (
            <div className="mt-3 bg-[#DCFCE7] rounded-lg p-3">
              <p className="text-xs font-semibold text-[#16A34A] mb-1">Action Required</p>
              <p className="text-sm text-[#16A34A]">{strategy.action_required}</p>
            </div>
          )}
          <div className="flex items-center gap-4 mt-3">
            {simulatorKey && onOpenSimulator && (
              <button type="button" onClick={(e) => { e.stopPropagation(); onOpenSimulator(simulatorKey); }} className="text-xs text-[#16A34A] hover:underline">
                Explore in Simulator &rarr;
              </button>
            )}
            <button type="button" onClick={(e) => { e.stopPropagation(); askHenry(`Tell me more about this tax strategy: "${strategy.title}". Is it a good fit for my situation?`); }} className="flex items-center gap-1 text-xs text-[#16A34A] hover:underline">
              <MessageCircle size={11} /> Ask <SirHenryName />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
