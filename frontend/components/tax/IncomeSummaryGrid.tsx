import { formatCurrency } from "@/lib/utils";
import type { TaxSummary } from "@/types/api";

function SummaryCell({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface rounded-lg p-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="font-semibold text-text-primary mt-0.5 tabular-nums">{value}</p>
      {sub && <p className="text-xs text-text-muted mt-0.5">{sub}</p>}
    </div>
  );
}

export default function IncomeSummaryGrid({ summary, year }: { summary: TaxSummary; year: number }) {
  const totalK1 = summary.k1_ordinary_income + summary.k1_guaranteed_payments + summary.k1_rental_income;
  const totalCapGains = summary.capital_gains_long + summary.capital_gains_short;
  const totalOther = summary.unemployment_income + summary.state_tax_refund + summary.payment_platform_income;

  return (
    <div>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-3">
        Income Summary — {year}
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Row 1: Primary income */}
        <SummaryCell label="W-2 Wages" value={formatCurrency(summary.w2_total_wages)} />
        <SummaryCell label="1099-NEC" value={formatCurrency(summary.nec_total)} />
        <SummaryCell
          label="Dividends"
          value={formatCurrency(summary.div_ordinary)}
          sub={`${formatCurrency(summary.div_qualified)} qualified`}
        />
        <SummaryCell
          label="Capital Gains"
          value={formatCurrency(totalCapGains)}
          sub={`LT: ${formatCurrency(summary.capital_gains_long)} · ST: ${formatCurrency(summary.capital_gains_short)}`}
        />

        {/* Row 2: Other income */}
        <SummaryCell label="Interest" value={formatCurrency(summary.interest_income)} />
        <SummaryCell
          label="K-1 Income"
          value={formatCurrency(totalK1)}
          sub={totalK1 !== 0 ? `Ordinary: ${formatCurrency(summary.k1_ordinary_income)} · GP: ${formatCurrency(summary.k1_guaranteed_payments)}` : undefined}
        />
        <SummaryCell
          label="Retirement (1099-R)"
          value={formatCurrency(summary.retirement_distributions)}
          sub={summary.retirement_distributions !== 0 ? `Taxable: ${formatCurrency(summary.retirement_taxable)}` : undefined}
        />
        <SummaryCell
          label="Other Income"
          value={formatCurrency(totalOther)}
          sub={totalOther !== 0 ? `Unemp: ${formatCurrency(summary.unemployment_income)} · Platform: ${formatCurrency(summary.payment_platform_income)}` : undefined}
        />

        {/* Row 3: Deductions */}
        <SummaryCell label="Mortgage Interest (1098)" value={formatCurrency(summary.mortgage_interest_deduction)} />
        <SummaryCell label="Property Tax" value={formatCurrency(summary.property_tax_deduction)} />
      </div>
    </div>
  );
}
