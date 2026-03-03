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
    <div className="bg-white border border-stone-100 rounded-xl p-6 shadow-sm">
      <h3 className="text-sm font-semibold text-stone-900 mb-1">Getting Started</h3>
      <p className="text-xs text-stone-500 mb-4">Complete these steps to get a full picture of your financial life.</p>
      <div className="space-y-3">
        {STEPS.map((step, i) => (
          <button key={i} onClick={onAddAccount} className="w-full flex items-center gap-3 p-3 rounded-lg border border-dashed border-stone-200 hover:border-[#16A34A] hover:bg-green-50 transition-colors text-left">
            <div className="w-6 h-6 rounded-full bg-stone-100 flex items-center justify-center text-xs font-bold text-stone-500 shrink-0">{i + 1}</div>
            <div>
              <p className="text-sm font-medium text-stone-800">{step.label}</p>
              <p className="text-xs text-stone-500">{step.sub}</p>
            </div>
            <Plus size={14} className="ml-auto text-stone-400 shrink-0" />
          </button>
        ))}
      </div>
    </div>
  );
}
