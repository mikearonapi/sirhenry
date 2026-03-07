"use client";
import { useState } from "react";
import {
  Loader2, Zap, BarChart3, Users,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { calculateRetirement } from "@/lib/api";
import { request } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import type { RetirementResults, RetirementProfileInput } from "@/types/api";
import type { RetirementInputState } from "./constants";

interface ScenariosTabProps {
  inputs: RetirementInputState;
  results: RetirementResults | null;
  retirementBudgetAnnual: number;
}

export default function ScenariosTab({ inputs, results, retirementBudgetAnnual }: ScenariosTabProps) {
  // Lump Sum scenario state
  const [lumpSumAmount, setLumpSumAmount] = useState<number>(50000);
  const [lumpSumResults, setLumpSumResults] = useState<RetirementResults | null>(null);
  const [lumpSumLoading, setLumpSumLoading] = useState(false);

  // Second Income scenario state
  const [secondIncome, setSecondIncome] = useState({
    salary: 0, startsInYears: 1, worksUntilRetirement: true, workYears: 10,
    monthlySavings: 0, matchPct: 50, matchLimit: 6,
  });
  const [secondIncomeResults, setSecondIncomeResults] = useState<RetirementResults | null>(null);
  const [secondIncomeLoading, setSecondIncomeLoading] = useState(false);

  // Monte Carlo state
  const [monteCarloResult, setMonteCarloResult] = useState<{
    success_rate: number;
    num_simulations: number;
    final_balance_p10: number;
    final_balance_p25: number;
    final_balance_p50: number;
    final_balance_p75: number;
    final_balance_p90: number;
  } | null>(null);
  const [mcLoading, setMcLoading] = useState(false);
  const [mcError, setMcError] = useState<string | null>(null);

  // Inflation multiplier for today's-dollar conversions
  const inflationMult = results && results.years_to_retirement > 0
    ? (1 + inputs.inflation_rate_pct / 100) ** results.years_to_retirement
    : 1;
  const projectedToday = results ? results.projected_nest_egg / inflationMult : 0;

  if (!results) {
    return (
      <div className="flex items-center justify-center py-20 text-text-muted text-sm">
        Run the simulator first to unlock what-if scenarios.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Lump Sum "What If" Scenario */}
      <Card padding="lg">
        <div className="flex items-center gap-2 mb-1">
          <Zap size={18} className="text-amber-500" />
          <h3 className="text-sm font-semibold text-text-primary">What If You Invest a Lump Sum Today?</h3>
        </div>
        <p className="text-xs text-text-muted mb-4">
          See how a one-time investment today compounds over time and impacts your retirement timeline.
        </p>

        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1 max-w-xs">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
            <input
              type="number"
              value={lumpSumAmount}
              onChange={(e) => setLumpSumAmount(Number(e.target.value) || 0)}
              className="w-full pl-7 pr-3 py-2 border border-border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              placeholder="50000"
              step={10000}
              min={0}
            />
          </div>
          <button
            onClick={async () => {
              if (lumpSumAmount <= 0 || !results) return;
              setLumpSumLoading(true);
              try {
                const body: RetirementProfileInput = {
                  ...inputs,
                  current_other_investments: (inputs.current_other_investments || 0) + lumpSumAmount,
                  desired_annual_retirement_income: inputs.desired_annual_retirement_income || null,
                  current_annual_expenses: inputs.current_annual_expenses || null,
                  retirement_budget_annual: retirementBudgetAnnual > 0 ? retirementBudgetAnnual : null,
                };
                const r = await calculateRetirement(body);
                setLumpSumResults(r);
              } catch {
                setLumpSumResults(null);
              }
              setLumpSumLoading(false);
            }}
            disabled={lumpSumLoading || lumpSumAmount <= 0}
            className="px-4 py-2 bg-amber-500 text-white text-sm font-medium rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors flex items-center gap-1.5"
          >
            {lumpSumLoading ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            Calculate
          </button>
        </div>

        {lumpSumResults && (() => {
          const currentEarliest = results.earliest_retirement_age;
          const newEarliest = lumpSumResults.earliest_retirement_age;
          const yearsSooner = currentEarliest - newEarliest;
          const newProjectedToday = lumpSumResults.projected_nest_egg / inflationMult;
          const extraAtRetirement = newProjectedToday - projectedToday;
          const lumpGrowth = lumpSumAmount * ((1 + inputs.pre_retirement_return_pct / 100) ** results.years_to_retirement) - lumpSumAmount;
          const newMoneyLasts = lumpSumResults.years_money_will_last;
          const extraYears = newMoneyLasts - results.years_money_will_last;

          return (
            <div className="bg-amber-50 rounded-xl border border-amber-200 p-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-xs text-text-secondary">Retire Earlier By</p>
                  <p className="text-xl font-bold text-amber-700 font-mono tabular-nums">
                    {yearsSooner > 0 ? `${yearsSooner} yr` : yearsSooner === 0 ? "Same" : "\u2014"}
                  </p>
                  <p className="text-xs text-text-muted">
                    {yearsSooner > 0 ? `Age ${newEarliest} vs ${currentEarliest}` : "Already optimal"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">Lump Sum Grows To</p>
                  <p className="text-xl font-bold text-text-primary font-mono tabular-nums">{formatCurrency(lumpSumAmount + lumpGrowth, true)}</p>
                  <p className="text-xs text-text-muted">{formatCurrency(lumpGrowth, true)} in compound growth</p>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">Extra at Retirement</p>
                  <p className="text-xl font-bold text-text-primary font-mono tabular-nums">+{formatCurrency(extraAtRetirement, true)}</p>
                  <p className="text-xs text-text-muted">Added to nest egg (today&apos;s $)</p>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">Money Lasts</p>
                  <p className="text-xl font-bold text-text-primary font-mono tabular-nums">{newMoneyLasts.toFixed(0)} yr</p>
                  <p className="text-xs text-text-muted">
                    {extraYears > 0.5 ? `+${extraYears.toFixed(0)}yr longer` : "Same duration"}
                  </p>
                </div>
              </div>

              <p className="text-xs text-text-secondary mt-4 pt-3 border-t border-amber-200/60">
                A one-time <span className="font-semibold">{formatCurrency(lumpSumAmount, true)}</span> investment today,
                growing at {inputs.pre_retirement_return_pct}%/yr for {results.years_to_retirement} years,
                becomes <span className="font-semibold">{formatCurrency(lumpSumAmount + lumpGrowth, true)}</span> at retirement
                {yearsSooner > 0 && <> — letting you retire <span className="font-semibold text-amber-700">{yearsSooner} year{yearsSooner > 1 ? "s" : ""} sooner</span></>}.
              </p>
            </div>
          );
        })()}
      </Card>

      {/* Second Income "What If" Scenario */}
      <Card padding="lg">
        <div className="flex items-center gap-2 mb-1">
          <Users size={18} className="text-emerald-600" />
          <h3 className="text-sm font-semibold text-text-primary">What If You Add a Second Income?</h3>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Model a spouse or partner returning to work — see how their savings accelerate your retirement timeline.
        </p>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
          <div>
            <label className="text-xs uppercase tracking-wider text-text-muted mb-1 block">Annual Salary</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
              <input type="number" value={secondIncome.salary || ""} onChange={(e) => setSecondIncome(s => ({...s, salary: Number(e.target.value) || 0}))}
                className="w-full pl-7 pr-3 py-2 border border-border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                placeholder="150000" step={10000} min={0} />
            </div>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider text-text-muted mb-1 block">Monthly Savings</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
              <input type="number" value={secondIncome.monthlySavings || ""} onChange={(e) => setSecondIncome(s => ({...s, monthlySavings: Number(e.target.value) || 0}))}
                className="w-full pl-7 pr-3 py-2 border border-border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                placeholder="5000" step={500} min={0} />
            </div>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider text-text-muted mb-1 block">Starts In</label>
            <div className="relative">
              <input type="number" value={secondIncome.startsInYears} onChange={(e) => setSecondIncome(s => ({...s, startsInYears: Math.max(0, Number(e.target.value) || 0)}))}
                className="w-full px-3 py-2 border border-border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                min={0} max={30} />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted text-xs">years</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 mb-4">
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
            <input type="checkbox" checked={secondIncome.worksUntilRetirement}
              onChange={(e) => setSecondIncome(s => ({...s, worksUntilRetirement: e.target.checked}))}
              className="rounded border-border text-emerald-600 focus:ring-emerald-500" />
            Works until retirement
          </label>
          {!secondIncome.worksUntilRetirement && (
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted">Years working:</label>
              <input type="number" value={secondIncome.workYears} onChange={(e) => setSecondIncome(s => ({...s, workYears: Math.max(1, Number(e.target.value) || 1)}))}
                className="w-16 px-2 py-1 border border-border rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                min={1} max={30} />
            </div>
          )}
          <div className="flex items-center gap-2">
            <label className="text-xs text-text-muted">Employer match:</label>
            <input type="number" value={secondIncome.matchPct} onChange={(e) => setSecondIncome(s => ({...s, matchPct: Number(e.target.value) || 0}))}
              className="w-14 px-2 py-1 border border-border rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
              min={0} max={100} />
            <span className="text-xs text-text-muted">% up to</span>
            <input type="number" value={secondIncome.matchLimit} onChange={(e) => setSecondIncome(s => ({...s, matchLimit: Number(e.target.value) || 0}))}
              className="w-14 px-2 py-1 border border-border rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
              min={0} max={100} />
            <span className="text-xs text-text-muted">%</span>
          </div>
        </div>

        <button
          onClick={async () => {
            if (secondIncome.salary <= 0 || secondIncome.monthlySavings <= 0 || !results) return;
            setSecondIncomeLoading(true);
            try {
              const body: RetirementProfileInput = {
                ...inputs,
                desired_annual_retirement_income: inputs.desired_annual_retirement_income || null,
                current_annual_expenses: inputs.current_annual_expenses || null,
                retirement_budget_annual: retirementBudgetAnnual > 0 ? retirementBudgetAnnual : null,
                second_income_annual: secondIncome.salary,
                second_income_start_age: inputs.current_age + secondIncome.startsInYears,
                second_income_end_age: secondIncome.worksUntilRetirement
                  ? inputs.retirement_age
                  : inputs.current_age + secondIncome.startsInYears + secondIncome.workYears,
                second_income_monthly_contribution: secondIncome.monthlySavings,
                second_income_employer_match_pct: secondIncome.matchPct,
                second_income_employer_match_limit_pct: secondIncome.matchLimit,
              };
              const r = await calculateRetirement(body);
              setSecondIncomeResults(r);
            } catch {
              setSecondIncomeResults(null);
            }
            setSecondIncomeLoading(false);
          }}
          disabled={secondIncomeLoading || secondIncome.salary <= 0 || secondIncome.monthlySavings <= 0}
          className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors flex items-center gap-1.5 mb-4"
        >
          {secondIncomeLoading ? <Loader2 size={14} className="animate-spin" /> : <Users size={14} />}
          Calculate Impact
        </button>

        {secondIncomeResults && (() => {
          const currentEarliest = results.earliest_retirement_age;
          const newEarliest = secondIncomeResults.earliest_retirement_age;
          const yearsSooner = currentEarliest - newEarliest;
          const extraProjected = (secondIncomeResults.projected_nest_egg - results.projected_nest_egg) / inflationMult;
          const workingYears = secondIncome.worksUntilRetirement
            ? Math.max(0, inputs.retirement_age - inputs.current_age - secondIncome.startsInYears)
            : secondIncome.workYears;
          const newReadiness = secondIncomeResults.retirement_readiness_pct;

          return (
            <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-xs text-text-secondary">Retire Earlier By</p>
                  <p className="text-xl font-bold text-emerald-700 font-mono tabular-nums">
                    {yearsSooner > 0 ? `${yearsSooner} yr` : yearsSooner === 0 ? "Same" : "\u2014"}
                  </p>
                  <p className="text-xs text-text-muted">
                    {yearsSooner > 0 ? `Age ${newEarliest} vs ${currentEarliest}` : `Earliest: age ${newEarliest}`}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">Extra Savings</p>
                  <p className="text-xl font-bold text-text-primary font-mono tabular-nums">+{formatCurrency(extraProjected, true)}</p>
                  <p className="text-xs text-text-muted">Added to nest egg (today&apos;s $)</p>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">New Earliest Age</p>
                  <p className="text-xl font-bold text-text-primary font-mono tabular-nums">{newEarliest}</p>
                  <p className="text-xs text-text-muted">
                    {yearsSooner > 0 ? `${yearsSooner} yr sooner` : "Same as current"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">Readiness</p>
                  <p className="text-xl font-bold text-text-primary font-mono tabular-nums">
                    {results.retirement_readiness_pct.toFixed(0)}% → {newReadiness.toFixed(0)}%
                  </p>
                  <p className="text-xs text-text-muted">
                    +{(newReadiness - results.retirement_readiness_pct).toFixed(0)} percentage points
                  </p>
                </div>
              </div>

              <p className="text-xs text-text-secondary mt-4 pt-3 border-t border-emerald-200/60">
                A second income of <span className="font-semibold">{formatCurrency(secondIncome.salary, true)}</span>/yr
                saving <span className="font-semibold">{formatCurrency(secondIncome.monthlySavings, true)}</span>/mo
                for {workingYears} years adds <span className="font-semibold text-emerald-700">+{formatCurrency(extraProjected, true)}</span> to
                your nest egg
                {yearsSooner > 0 && <>, moving earliest retirement from <span className="font-semibold">{currentEarliest}</span> to <span className="font-semibold text-emerald-700">{newEarliest}</span></>}.
              </p>
            </div>
          );
        })()}
      </Card>

      {/* Monte Carlo Simulation */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 size={18} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-text-primary">Monte Carlo Simulation</h3>
          </div>
          <button
            onClick={async () => {
              setMcLoading(true);
              setMcError(null);
              try {
                const mc = await request<typeof monteCarloResult>("/retirement/monte-carlo", {
                  method: "POST",
                  body: JSON.stringify(inputs),
                });
                setMonteCarloResult(mc);
              } catch (e: unknown) {
                setMcError(getErrorMessage(e));
              }
              setMcLoading(false);
            }}
            disabled={mcLoading}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 shadow-sm"
          >
            {mcLoading ? <Loader2 size={13} className="animate-spin" /> : <BarChart3 size={13} />}
            {mcLoading ? "Running 1,000 simulations..." : "Run Monte Carlo"}
          </button>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Runs 1,000 simulations varying annual returns and inflation to assess the probability your savings last through retirement.
        </p>
        {mcError && (
          <p className="text-xs text-red-600 mb-3">{mcError}</p>
        )}
        {monteCarloResult && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className={`text-center px-6 py-4 rounded-xl ${
                monteCarloResult.success_rate >= 85 ? "bg-green-50 border border-green-200" :
                monteCarloResult.success_rate >= 60 ? "bg-yellow-50 border border-yellow-200" :
                "bg-red-50 border border-red-200"
              }`}>
                <p className={`text-4xl font-bold font-mono tabular-nums ${
                  monteCarloResult.success_rate >= 85 ? "text-green-700" :
                  monteCarloResult.success_rate >= 60 ? "text-yellow-700" :
                  "text-red-700"
                }`}>
                  {monteCarloResult.success_rate}%
                </p>
                <p className="text-xs text-text-secondary mt-1">Success Rate</p>
              </div>
              <div className="flex-1">
                <p className="text-sm text-text-secondary">
                  {monteCarloResult.success_rate >= 85
                    ? "Your retirement plan has a strong probability of success. You're well-positioned."
                    : monteCarloResult.success_rate >= 60
                    ? "Your plan has a moderate chance of success. Consider increasing contributions or adjusting your target."
                    : "Your plan has a significant risk of running short. Consider increasing savings or adjusting retirement age."}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-5 gap-3">
              {[
                { label: "P10 (pessimistic)", value: monteCarloResult.final_balance_p10 },
                { label: "P25", value: monteCarloResult.final_balance_p25 },
                { label: "P50 (median)", value: monteCarloResult.final_balance_p50 },
                { label: "P75", value: monteCarloResult.final_balance_p75 },
                { label: "P90 (optimistic)", value: monteCarloResult.final_balance_p90 },
              ].map(({ label, value }) => (
                <div key={label} className="bg-surface rounded-lg p-3 text-center">
                  <p className="text-xs text-text-muted">{label}</p>
                  <p className="text-sm font-bold font-mono tabular-nums mt-1">{formatCurrency(value, true)}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-text-muted">
              Based on {monteCarloResult.num_simulations.toLocaleString()} simulations. Final balance at age {inputs.life_expectancy}.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
