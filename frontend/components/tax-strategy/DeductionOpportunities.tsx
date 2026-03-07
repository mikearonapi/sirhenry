"use client";
import { useState } from "react";
import {
  ChevronDown, ChevronUp, DollarSign, Lightbulb, MessageCircle, TrendingDown,
  Car, Monitor, PiggyBank, Home, Heart, GraduationCap, ShieldCheck,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { TaxDeductionInsights } from "@/types/api";

const OPPORTUNITY_ICONS: Record<string, typeof Car> = {
  vehicle: Car, equipment: Monitor, retirement: PiggyBank,
  home_office: Home, charitable: Heart, education: GraduationCap, other: ShieldCheck,
};
const URGENCY_COLORS: Record<string, string> = {
  high: "bg-red-50 text-red-700 border-red-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-blue-50 text-blue-700 border-blue-200",
};

const OPPORTUNITY_SIMULATOR: Record<string, string> = {
  sep_ira: "roth-conversion",
  backdoor_roth: "roth-conversion",
  maximize_401k: "roth-conversion",
  charitable_daf: "daf-bunching",
};

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function DeductionOpportunities({ deductions, onOpenSimulator }: {
  deductions: TaxDeductionInsights;
  onOpenSimulator?: (key: string) => void;
  onOpenPayments?: () => void;
}) {
  const [expandedOpp, setExpandedOpp] = useState<string | null>(null);

  if (deductions.opportunities.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Deduction Opportunities</h2>
          <Lightbulb size={14} className="text-amber-400" />
        </div>
        {deductions.estimated_balance_due > 0 && onOpenSimulator && (
          <button type="button" onClick={() => onOpenSimulator("estimated-payments")} className="text-sm text-red-600 font-medium hover:underline">
            Est. balance due: <span className="font-mono tabular-nums">{formatCurrency(deductions.estimated_balance_due)}</span> — Plan payments &rarr;
          </button>
        )}
      </div>
      <div className="bg-gradient-to-r from-accent-light to-blue-50 rounded-xl border border-accent/20 p-4 mb-4">
        <div className="flex items-start gap-3">
          <TrendingDown size={20} className="text-accent mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm text-indigo-900 leading-relaxed">{deductions.summary}</p>
            <div className="flex gap-4 mt-2 text-xs text-accent">
              <span>Marginal Rate: <strong className="font-mono tabular-nums">{deductions.marginal_rate}%</strong></span>
              <span>Effective Rate: <strong className="font-mono tabular-nums">{deductions.effective_rate}%</strong></span>
            </div>
          </div>
        </div>
      </div>
      <div className="space-y-3">
        {deductions.opportunities.map((opp) => {
          const Icon = OPPORTUNITY_ICONS[opp.category] ?? DollarSign;
          const isExp = expandedOpp === opp.id;
          const simulatorKey = OPPORTUNITY_SIMULATOR[opp.id];
          return (
            <div key={opp.id} className="bg-card rounded-xl border border-card-border shadow-sm">
              <div className="flex items-center gap-4 p-4 cursor-pointer hover:bg-surface/50 transition-colors rounded-xl" onClick={() => setExpandedOpp(isExp ? null : opp.id)}>
                <div className="w-9 h-9 rounded-lg bg-accent-light flex items-center justify-center flex-shrink-0"><Icon size={18} className="text-accent" /></div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-text-primary text-sm">{opp.title}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${URGENCY_COLORS[opp.urgency]}`}>{opp.urgency}</span>
                    {opp.deadline && <span className="text-xs text-text-muted">{opp.deadline}</span>}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  {opp.estimated_tax_savings_low === 0 && opp.estimated_tax_savings_high === 0 ? (
                    <p className="font-medium text-text-secondary text-sm">Tax-free growth</p>
                  ) : (
                    <>
                      <p className="font-semibold text-green-600 text-sm font-mono tabular-nums">{formatCurrency(opp.estimated_tax_savings_low, true)}–{formatCurrency(opp.estimated_tax_savings_high, true)}</p>
                      <p className="text-xs text-text-muted">tax savings</p>
                    </>
                  )}
                </div>
                {isExp ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
              </div>
              {isExp && (
                <div className="px-4 pb-4 border-t border-border-light">
                  <p className="text-sm text-text-secondary mt-3 leading-relaxed">{opp.description}</p>
                  {opp.estimated_cost != null && opp.estimated_cost > 0 && (
                    <div className="mt-3 flex gap-4">
                      <div className="bg-surface rounded-lg p-3 flex-1"><p className="text-xs text-text-secondary">Estimated Cost</p><p className="font-semibold text-text-primary mt-0.5 font-mono tabular-nums">{formatCurrency(opp.estimated_cost)}</p></div>
                      <div className="bg-green-50 rounded-lg p-3 flex-1"><p className="text-xs text-green-600">Tax Savings</p><p className="font-semibold text-green-700 mt-0.5 font-mono tabular-nums">{formatCurrency(opp.estimated_tax_savings_low)}–{formatCurrency(opp.estimated_tax_savings_high)}</p></div>
                    </div>
                  )}
                  <div className="mt-3 bg-blue-50 rounded-lg p-3">
                    <p className="text-xs font-semibold text-blue-700 mb-1">Bottom Line</p>
                    <p className="text-sm text-blue-800">{opp.net_benefit_explanation}</p>
                  </div>
                  <div className="flex items-center gap-4 mt-3">
                    {simulatorKey && onOpenSimulator && (
                      <button type="button" onClick={() => onOpenSimulator(simulatorKey)} className="text-xs text-accent hover:underline">
                        Model this in Simulator &rarr;
                      </button>
                    )}
                    <button type="button" onClick={() => askHenry(`Tell me more about "${opp.title}". Is this a good fit for my situation? What should I know?`)} className="flex items-center gap-1 text-xs text-accent hover:underline">
                      <MessageCircle size={11} /> Ask about this
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
