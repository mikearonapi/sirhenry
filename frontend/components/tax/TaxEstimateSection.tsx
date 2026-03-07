"use client";
import { MessageCircle } from "lucide-react";
import SirHenryName from "@/components/ui/SirHenryName";
import { formatCurrency } from "@/lib/utils";
import type { TaxEstimate } from "@/types/api";
import StatCard from "@/components/ui/StatCard";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function TaxEstimateSection({ estimate, year }: { estimate: TaxEstimate; year: number }) {
  return (
    <div>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-3">
        {year} Tax Estimate
        <span className="ml-2 text-text-muted font-normal normal-case">(rough estimate — not professional advice)</span>
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Estimated Adjusted Gross Income" value={formatCurrency(estimate.estimated_agi, true)} />
        <StatCard label="Total Tax Estimate" value={formatCurrency(estimate.total_estimated_tax, true)} />
        <StatCard label="Effective Rate" value={`${estimate.effective_rate}%`} />
        <StatCard
          label="Est. Balance Due"
          value={formatCurrency(estimate.estimated_balance_due, true)}
          trend={estimate.estimated_balance_due > 0 ? "down" : "up"}
          sub={estimate.estimated_balance_due > 0 ? "See Tax Strategy for payment plan" : "Possible refund"}
        />
      </div>
      <div className="mt-4 bg-card rounded-xl border border-card-border shadow-sm p-5 print:shadow-none print:border-border">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">Tax Breakdown</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          {[
            { label: "Federal Income Tax", value: estimate.federal_income_tax },
            { label: "Self-Employment Tax", value: estimate.self_employment_tax },
            { label: "Net Investment Income Tax (3.8%)", value: estimate.niit },
            { label: "Additional Medicare (0.9%)", value: estimate.additional_medicare_tax },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface rounded-lg p-3">
              <p className="text-xs text-text-secondary">{label}</p>
              <p className="font-semibold text-text-primary mt-1 tabular-nums">{formatCurrency(value)}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-4 text-sm border-t border-card-border pt-3">
          <div>
            <p className="text-xs text-text-secondary">W-2 Already Withheld</p>
            <p className="font-semibold text-green-600 tabular-nums">{formatCurrency(estimate.w2_federal_already_withheld)}</p>
          </div>
          <div>
            <p className="text-xs text-text-secondary">Ordinary Income</p>
            <p className="font-semibold text-text-primary tabular-nums">{formatCurrency(estimate.ordinary_income)}</p>
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => askHenry(`Based on my ${year} tax estimate showing $${Math.round(estimate.total_estimated_tax).toLocaleString()} in total tax and $${Math.round(estimate.estimated_agi).toLocaleString()} adjusted gross income, am I on track? What should I prioritize to reduce my tax bill?`)}
        className="flex items-center gap-1.5 text-xs text-accent hover:underline mt-3 print:hidden"
      >
        <MessageCircle size={12} /> Ask <SirHenryName /> about my tax situation
      </button>
    </div>
  );
}
