"use client";
import {
  ChevronDown, ChevronUp, Plus, Trash2, Zap,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import { AutoFilledIndicator } from "@/components/ui/AutoFilledIndicator";
import type { RetirementInputState, InputKey } from "./constants";
import type { DebtPayoff, BudgetSnapshot, RetirementResults } from "@/types/api";

interface InputsTabProps {
  inputs: RetirementInputState;
  update: (key: InputKey, value: number | string) => void;
  autoFilledFields: Record<string, string>;
  budgetSnapshot: BudgetSnapshot | null;
  retirementBudgetAnnual: number;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  addDebtPayoff: () => void;
  updateDebtPayoff: (idx: number, field: keyof DebtPayoff, value: string | number) => void;
  removeDebtPayoff: (idx: number) => void;
  onApplyBudgetSnapshot: () => void;
  results: RetirementResults | null;
}

export default function InputsTab({
  inputs,
  update,
  autoFilledFields,
  budgetSnapshot,
  showAdvanced,
  setShowAdvanced,
  addDebtPayoff,
  updateDebtPayoff,
  removeDebtPayoff,
  onApplyBudgetSnapshot,
  results,
}: InputsTabProps) {
  return (
    <>
      {/* Input Form Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Personal & Income */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Personal & Income</h3>
          <div className="space-y-4">
            {([
              { key: "current_age" as InputKey, label: "Current Age", min: 18, max: 80, step: 1, suffix: "years old", prefix: undefined },
              { key: "retirement_age" as InputKey, label: "Target Retirement Age", min: 40, max: 80, step: 1, suffix: "years old", prefix: undefined },
              { key: "life_expectancy" as InputKey, label: "Life Expectancy", min: 70, max: 110, step: 1, suffix: "years", prefix: undefined },
              { key: "current_annual_income" as InputKey, label: "Current Annual Income", min: 0, max: 2000000, step: 5000, prefix: "$", suffix: undefined },
            ]).map(({ key, label, min, max, step, prefix, suffix }) => (
              <div key={key}>
                <div className="flex justify-between items-center mb-1">
                  <span className="flex items-center gap-1.5">
                    <label className="text-xs text-text-secondary">{label}</label>
                    {autoFilledFields[key] && <AutoFilledIndicator source={autoFilledFields[key]} />}
                  </span>
                  <span className="text-xs font-semibold text-text-secondary tabular-nums">
                    {prefix}{typeof inputs[key] === "number" ? (prefix === "$" ? (inputs[key] as number).toLocaleString() : String(inputs[key])) : String(inputs[key] ?? "")}{suffix ? ` ${suffix}` : ""}
                  </span>
                </div>
                <input type="range" min={min} max={max} step={step} value={inputs[key] as number} onChange={(e) => update(key, Number(e.target.value))} className="w-full h-1.5 bg-surface rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
              </div>
            ))}
          </div>
        </Card>

        {/* Current Savings */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Current Savings & Contributions</h3>
          <div className="space-y-4">
            {[
              { key: "current_retirement_savings" as InputKey, label: "Retirement Savings (401k, IRA, etc.)", max: 5000000, step: 10000 },
              { key: "current_other_investments" as InputKey, label: "Other Investments", max: 5000000, step: 10000 },
              { key: "monthly_retirement_contribution" as InputKey, label: "Monthly Contribution", max: 10000, step: 100 },
            ].map(({ key, label, max, step }) => (
              <div key={key}>
                <div className="flex justify-between items-center mb-1">
                  <span className="flex items-center gap-1.5">
                    <label className="text-xs text-text-secondary">{label}</label>
                    {autoFilledFields[key] && <AutoFilledIndicator source={autoFilledFields[key]} />}
                  </span>
                  <span className="text-xs font-semibold text-text-secondary tabular-nums">${(inputs[key] as number).toLocaleString()}</span>
                </div>
                <input type="range" min={0} max={max} step={step} value={inputs[key] as number} onChange={(e) => update(key, Number(e.target.value))} className="w-full h-1.5 bg-surface rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
              </div>
            ))}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-text-secondary">Employer Match %</label>
                <input type="number" value={inputs.employer_match_pct} onChange={(e) => update("employer_match_pct", Number(e.target.value))} min={0} max={100} className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
              </div>
              <div>
                <label className="text-xs text-text-secondary">Match Limit %</label>
                <input type="number" value={inputs.employer_match_limit_pct} onChange={(e) => update("employer_match_limit_pct", Number(e.target.value))} min={0} max={100} className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
              </div>
            </div>
          </div>
        </Card>

        {/* Retirement Income */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Retirement Income Sources</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-text-secondary">Expected Social Security (monthly)</label>
                <span className="text-xs font-semibold text-text-secondary">${(inputs.expected_social_security_monthly).toLocaleString()}</span>
              </div>
              <input type="range" min={0} max={5000} step={100} value={inputs.expected_social_security_monthly} onChange={(e) => update("expected_social_security_monthly", Number(e.target.value))} className="w-full h-1.5 bg-surface rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-text-secondary">SS Start Age</label>
                <input type="number" value={inputs.social_security_start_age} onChange={(e) => update("social_security_start_age", Number(e.target.value))} min={62} max={70} className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
              </div>
              <div>
                <label className="text-xs text-text-secondary">Pension (monthly)</label>
                <input type="number" value={inputs.pension_monthly} onChange={(e) => update("pension_monthly", Number(e.target.value))} min={0} className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-text-secondary">Income Replacement %</label>
                <span className="text-xs font-semibold text-text-secondary">{inputs.income_replacement_pct}%</span>
              </div>
              <input type="range" min={40} max={120} step={5} value={inputs.income_replacement_pct} onChange={(e) => update("income_replacement_pct", Number(e.target.value))} className="w-full h-1.5 bg-surface rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>
          </div>
        </Card>

        {/* Retirement Expenses */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Retirement Expenses & Assumptions</h3>
          <div className="space-y-4">
            {/* Budget-based expenses */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-text-secondary">Current Annual Expenses (from budget)</label>
                <span className="text-xs font-semibold text-text-secondary">
                  {inputs.current_annual_expenses > 0 ? `$${inputs.current_annual_expenses.toLocaleString()}` : "Not set — using income replacement %"}
                </span>
              </div>
              {budgetSnapshot && budgetSnapshot.annual_expenses > 0 && inputs.current_annual_expenses === 0 && (
                <button
                  onClick={onApplyBudgetSnapshot}
                  className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover font-medium mt-1"
                >
                  <Zap size={12} />
                  Use actual budget: ${budgetSnapshot.annual_expenses.toLocaleString()}/yr
                </button>
              )}
              {inputs.current_annual_expenses > 0 && (
                <div className="flex items-center gap-2 mt-1">
                  <input type="range" min={0} max={500000} step={5000} value={inputs.current_annual_expenses}
                    onChange={(e) => update("current_annual_expenses", Number(e.target.value))}
                    className="flex-1 h-1.5 bg-surface rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
                  <button onClick={() => { update("current_annual_expenses", 0); }} className="text-xs text-text-muted hover:text-text-secondary">Clear</button>
                </div>
              )}
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-text-secondary">Healthcare (annual)</label>
                <span className="text-xs font-semibold text-text-secondary">${(inputs.healthcare_annual_estimate).toLocaleString()}</span>
              </div>
              <input type="range" min={0} max={50000} step={1000} value={inputs.healthcare_annual_estimate} onChange={(e) => update("healthcare_annual_estimate", Number(e.target.value))} className="w-full h-1.5 bg-surface rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-text-secondary">Additional Expenses (annual)</label>
                <span className="text-xs font-semibold text-text-secondary">${(inputs.additional_annual_expenses).toLocaleString()}</span>
              </div>
              <input type="range" min={0} max={100000} step={1000} value={inputs.additional_annual_expenses} onChange={(e) => update("additional_annual_expenses", Number(e.target.value))} className="w-full h-1.5 bg-surface rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>

            <button onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-secondary mt-2">
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Advanced Assumptions
            </button>

            {showAdvanced && (
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-card-border">
                {[
                  { key: "inflation_rate_pct" as InputKey, label: "Inflation Rate %" },
                  { key: "pre_retirement_return_pct" as InputKey, label: "Pre-Retirement Return %" },
                  { key: "post_retirement_return_pct" as InputKey, label: "Post-Retirement Return %" },
                  { key: "tax_rate_in_retirement_pct" as InputKey, label: "Tax Rate in Retirement %" },
                ].map(({ key, label }) => (
                  <div key={key}>
                    <label className="text-xs text-text-secondary">{label}</label>
                    <input type="number" value={inputs[key] as number} onChange={(e) => update(key, Number(e.target.value))} min={0} max={50} step={0.5} className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Debt Payoffs */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Debts That Pay Off Before Retirement</h3>
            <p className="text-xs text-text-muted mt-0.5">Mortgage, car loans, student loans — these reduce your retirement expenses once paid off</p>
          </div>
          <button onClick={addDebtPayoff} className="flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover">
            <Plus size={14} /> Add Debt
          </button>
        </div>
        {inputs.debt_payoffs.length === 0 ? (
          <p className="text-xs text-text-muted text-center py-4">No debts added. Add mortgage, car loans, etc. to get more accurate retirement projections.</p>
        ) : (
          <div className="space-y-3">
            {inputs.debt_payoffs.map((debt, idx) => (
              <div key={idx} className="grid grid-cols-[1fr_120px_100px_32px] gap-2 items-end">
                <div>
                  <label className="text-xs text-text-secondary">Debt Name</label>
                  <input type="text" value={debt.name} onChange={(e) => updateDebtPayoff(idx, "name", e.target.value)} placeholder="e.g. Mortgage"
                    className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                </div>
                <div>
                  <label className="text-xs text-text-secondary">Monthly Payment</label>
                  <input type="number" value={debt.monthly_payment} onChange={(e) => updateDebtPayoff(idx, "monthly_payment", Number(e.target.value))} min={0}
                    className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                </div>
                <div>
                  <label className="text-xs text-text-secondary">Payoff Age</label>
                  <input type="number" value={debt.payoff_age} onChange={(e) => updateDebtPayoff(idx, "payoff_age", Number(e.target.value))} min={inputs.current_age} max={100}
                    className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                </div>
                <button onClick={() => removeDebtPayoff(idx)} className="p-2 text-text-muted hover:text-red-500 mb-0.5">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            {results && results.debt_payoff_savings_annual > 0 && (
              <div className="bg-green-50 rounded-lg p-3 border border-green-100 mt-2">
                <p className="text-xs text-green-700 font-medium">
                  Debt payoffs reduce your retirement expenses by {formatCurrency(results.debt_payoff_savings_annual)}/year
                </p>
              </div>
            )}
          </div>
        )}
      </Card>
    </>
  );
}
