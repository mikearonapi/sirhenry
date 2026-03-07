"use client";

import { Plus } from "lucide-react";

interface GettingStartedChecklistProps {
  onAddAccount: () => void;
}

const STEPS = [
  { label: "Connect checking/savings account", sub: "Use Plaid to link your bank automatically" },
  { label: "Connect investment accounts", sub: "Link brokerage, 401k, or IRA via Plaid or add manually" },
  { label: "Add your home value", sub: "Enter current market value as a manual real estate asset" },
  { label: "Add outstanding loans", sub: "Mortgage, auto loans, student loans — to see your true net worth" },
];

export default function GettingStartedChecklist({ onAddAccount }: GettingStartedChecklistProps) {
  return (
    <div className="bg-card border border-card-border rounded-xl p-6 shadow-sm">
      <h3 className="text-sm font-semibold text-text-primary mb-1">Getting Started</h3>
      <p className="text-xs text-text-secondary mb-4">Complete these steps to get a full picture of your financial life.</p>
      <div className="space-y-3">
        {STEPS.map((step, i) => (
          <button key={i} onClick={onAddAccount} className="w-full flex items-center gap-3 p-3 rounded-lg border border-dashed border-border hover:border-accent hover:bg-green-50 transition-colors text-left">
            <div className="w-6 h-6 rounded-full bg-surface flex items-center justify-center text-xs font-bold text-text-secondary shrink-0">{i + 1}</div>
            <div>
              <p className="text-sm font-medium text-text-primary">{step.label}</p>
              <p className="text-xs text-text-secondary">{step.sub}</p>
            </div>
            <Plus size={14} className="ml-auto text-text-muted shrink-0" />
          </button>
        ))}
      </div>
    </div>
  );
}
