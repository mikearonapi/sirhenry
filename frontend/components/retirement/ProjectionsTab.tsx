"use client";
import {
  TrendingUp, Target, Clock, CheckCircle, XCircle, AlertCircle, Calendar, Wallet,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import Card from "@/components/ui/Card";
import type { RetirementResults } from "@/types/api";
import type { RetirementInputState } from "./constants";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

interface ProjectionsTabProps {
  results: RetirementResults | null;
  inputs: RetirementInputState;
  loading: boolean;
}

export default function ProjectionsTab({ results, inputs, loading }: ProjectionsTabProps) {
  if (!results) {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-20 text-text-muted text-sm">
          Calculating projections...
        </div>
      );
    }
    return (
      <div className="flex items-center justify-center py-20 text-text-muted text-sm">
        Adjust your inputs to see projections.
      </div>
    );
  }

  // Convert future-dollar values to today's dollars for intuitive display.
  const inflationMult = results.years_to_retirement > 0
    ? (1 + inputs.inflation_rate_pct / 100) ** results.years_to_retirement
    : 1;
  const targetToday = results.target_nest_egg / inflationMult;
  const projectedToday = results.projected_nest_egg / inflationMult;

  const currentSavings = inputs.current_retirement_savings + inputs.current_other_investments;
  const currentPct = targetToday > 0 ? Math.min(100, currentSavings / targetToday * 100) : 0;
  const projectedPct = results.retirement_readiness_pct;

  const chartData = results.yearly_projection.map((p) => ({
    age: p.age,
    balance: Math.round(p.balance),
    phase: p.phase,
  }));

  return (
    <div className="space-y-4">
      {/* Retirement Readiness */}
      <div className={`rounded-xl border p-5 shadow-sm ${results.on_track ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {results.on_track ? <CheckCircle size={18} className="text-green-600" /> : <XCircle size={18} className="text-red-600" />}
            <p className="text-sm font-semibold text-text-primary">Retirement Readiness</p>
          </div>
          <span className={`text-sm font-semibold px-3 py-1 rounded-full ${results.on_track ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
            {results.on_track ? "On Track" : "Needs Attention"}
          </span>
        </div>

        {/* Progress bar */}
        <div className="mb-3">
          <div className="flex justify-between text-xs text-text-secondary mb-1">
            <span>Current savings: <span className="font-semibold font-mono text-text-secondary">{formatCurrency(currentSavings, true)}</span></span>
            <span>Target: <span className="font-semibold font-mono text-text-secondary">{formatCurrency(targetToday, true)}</span></span>
          </div>
          <div className="h-3 bg-surface rounded-full overflow-hidden relative">
            <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${Math.min(currentPct, 100)}%` }} />
          </div>
          <p className="text-xs text-text-secondary mt-1">
            <span className="font-semibold font-mono text-text-secondary">{currentPct.toFixed(1)}%</span> saved today
          </p>
        </div>

        {/* How you get there */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-border/60">
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Monthly Contributions</p>
            <p className="text-sm font-semibold font-mono tabular-nums text-text-primary">{formatCurrency(results.total_monthly_contribution)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Growth Rate</p>
            <p className="text-sm font-semibold text-text-primary">{inputs.pre_retirement_return_pct}% / yr</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Years to Grow</p>
            <p className="text-sm font-semibold text-text-primary">{results.years_to_retirement} years</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Projected at Retirement</p>
            <p className="text-sm font-semibold font-mono tabular-nums text-text-primary">{formatCurrency(projectedToday, true)}</p>
            <p className="text-xs text-text-muted">{projectedPct.toFixed(0)}% of target</p>
          </div>
        </div>

        {!results.on_track && results.monthly_savings_needed > 0 && (
          <p className="text-xs text-red-600 mt-3 pt-2 border-t border-red-200/60">
            Save an extra <span className="font-semibold">{formatCurrency(results.monthly_savings_needed)}/mo</span> to close the gap by age {inputs.retirement_age}
          </p>
        )}
      </div>

      {/* Summary metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
          <div className="flex items-center gap-2"><Wallet size={18} className="text-emerald-500" /><p className="text-xs font-medium text-text-secondary">Retirement Budget</p></div>
          <p className="text-2xl font-bold text-text-primary mt-2 font-mono tabular-nums">{formatCurrency(results.annual_income_needed_today, true)}<span className="text-sm font-normal text-text-muted">/yr</span></p>
          <p className="text-xs text-text-muted mt-1">
            {results.debt_payoff_savings_annual > 0 ? `Saves ${formatCurrency(results.debt_payoff_savings_annual, true)}/yr from paid-off loans` : `${formatCurrency(results.annual_income_needed_today / 12)}/mo in today's dollars`}
          </p>
        </div>

        <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
          <div className="flex items-center gap-2"><Calendar size={18} className="text-indigo-500" /><p className="text-xs font-medium text-text-secondary">Earliest Retirement</p></div>
          <p className="text-2xl font-bold text-text-primary mt-2">Age {results.earliest_retirement_age}</p>
          <p className="text-xs text-text-muted mt-1">
            {results.earliest_retirement_age <= inputs.current_age ? "You could retire now" :
             results.earliest_retirement_age < inputs.retirement_age ? `${inputs.retirement_age - results.earliest_retirement_age}yr earlier possible` :
             results.earliest_retirement_age === inputs.retirement_age ? "Matches your target" :
             `${results.earliest_retirement_age - inputs.retirement_age}yr later than target`}
          </p>
        </div>

        <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
          <div className="flex items-center gap-2"><Clock size={18} className="text-purple-500" /><p className="text-xs font-medium text-text-secondary">Money Lasts</p></div>
          <p className="text-2xl font-bold text-text-primary mt-2">{results.years_money_will_last.toFixed(0)} years</p>
          <p className="text-xs text-text-muted mt-1">
            {results.years_money_will_last >= results.years_in_retirement ? `Covers all ${results.years_in_retirement} years` : `${(results.years_in_retirement - results.years_money_will_last).toFixed(0)}yr shortfall`}
          </p>
        </div>

        <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
          <div className="flex items-center gap-2"><TrendingUp size={18} className="text-amber-500" /><p className="text-xs font-medium text-text-secondary">Savings Rate</p></div>
          <p className="text-2xl font-bold text-text-primary mt-2 font-mono tabular-nums">{results.current_savings_rate_pct.toFixed(1)}%</p>
          <p className="text-xs text-text-muted mt-1">
            {results.recommended_savings_rate_pct > results.current_savings_rate_pct
              ? `Recommended: ${results.recommended_savings_rate_pct.toFixed(1)}%`
              : "Exceeds recommended rate"}
          </p>
        </div>
      </div>

      {/* Projection Chart */}
      {chartData.length > 0 && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Portfolio Projection Over Time</h3>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#16A34A" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#16A34A" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f1f0" />
              <XAxis dataKey="age" fontSize={11} label={{ value: "Age", position: "insideBottom", offset: -5, fontSize: 11 }} />
              <YAxis fontSize={11} tickFormatter={(v) => `$${(v / 1000000).toFixed(1)}M`} />
              <Tooltip
                formatter={(v) => formatCurrency(Number(v), true)}
                labelFormatter={(age) => `Age ${age}`}
              />
              <ReferenceLine x={inputs.retirement_age} stroke="#6366f1" strokeDasharray="5 5" label={{ value: "Retire", fill: "#6366f1", fontSize: 11 }} />
              <Area type="monotone" dataKey="balance" stroke="#16A34A" fill="url(#balGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Retire Earlier Scenarios */}
      {results.retire_earlier_scenarios?.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp size={18} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-text-primary">What If You Retire Earlier?</h3>
          </div>
          <p className="text-xs text-text-muted mb-4">
            See what it takes to retire sooner. You can adjust the retirement age slider in the Inputs tab to explore any target.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {results.retire_earlier_scenarios.map((scenario) => {
              const scenarioInflation = (1 + inputs.inflation_rate_pct / 100) ** (scenario.retirement_age - inputs.current_age);
              const scenarioTargetToday = scenario.target_nest_egg / scenarioInflation;
              const scenarioProjectedToday = scenario.projected_nest_egg / scenarioInflation;
              return (<div key={scenario.years_earlier} className={`rounded-xl border p-5 ${scenario.on_track ? "bg-green-50 border-green-200" : "bg-surface border-border"}`}>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-semibold text-text-primary">
                    Retire at {scenario.retirement_age} <span className="text-xs font-normal text-text-muted">({scenario.years_earlier}yr earlier)</span>
                  </p>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${scenario.on_track ? "bg-green-100 text-green-700" : "bg-surface text-text-secondary"}`}>
                    {scenario.readiness_pct.toFixed(0)}% ready
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-text-muted">Target Savings</p>
                    <p className="font-semibold font-mono tabular-nums">{formatCurrency(scenarioTargetToday, true)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-text-muted">Projected</p>
                    <p className="font-semibold font-mono tabular-nums">{formatCurrency(scenarioProjectedToday, true)}</p>
                  </div>
                </div>
                {!scenario.on_track && scenario.monthly_savings_needed > 0 && (
                  <div className="mt-3 pt-3 border-t border-border">
                    <p className="text-xs text-text-secondary">
                      To hit this target, save an extra <span className="font-semibold text-text-secondary">{formatCurrency(scenario.monthly_savings_needed)}/mo</span> beyond your current contributions
                    </p>
                  </div>
                )}
                {scenario.on_track && (
                  <div className="mt-3 pt-3 border-t border-green-200">
                    <p className="text-xs text-green-600 font-medium">You&apos;re already on track for this timeline</p>
                  </div>
                )}
              </div>);
            })}
          </div>
        </Card>
      )}

      {/* Detailed Analysis */}
      <Card padding="lg">
        <details>
          <summary className="cursor-pointer flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Target size={16} className="text-indigo-500" />
            Detailed Analysis
          </summary>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><p className="text-xs text-text-muted">Years to Retirement</p><p className="font-semibold">{results.years_to_retirement}</p></div>
            <div><p className="text-xs text-text-muted">Years in Retirement</p><p className="font-semibold">{results.years_in_retirement}</p></div>
            <div><p className="text-xs text-text-muted">Earliest Retirement Age</p><p className="font-semibold text-indigo-600">Age {results.earliest_retirement_age}</p></div>
            <div><p className="text-xs text-text-muted">Retirement Budget (today&apos;s $)</p><p className="font-semibold">{formatCurrency(results.annual_income_needed_today, true)}/yr</p></div>
            <div><p className="text-xs text-text-muted">Budget at Retirement (inflated)</p><p className="font-semibold">{formatCurrency(results.annual_income_needed_at_retirement, true)}/yr</p><p className="text-xs text-text-muted">After {results.years_to_retirement}yr of {inputs.inflation_rate_pct}% inflation + {inputs.tax_rate_in_retirement_pct}% tax</p></div>
            <div><p className="text-xs text-text-muted">Target Savings (today&apos;s $)</p><p className="font-semibold">{formatCurrency(targetToday, true)}</p></div>
            <div><p className="text-xs text-text-muted">Target at Retirement (inflated)</p><p className="font-semibold">{formatCurrency(results.target_nest_egg, true)}</p><p className="text-xs text-text-muted">Actual dollars needed on retirement day</p></div>
            <div><p className="text-xs text-text-muted">Projected Monthly Income</p><p className="font-semibold">{formatCurrency(results.projected_monthly_income)}</p></div>
            <div><p className="text-xs text-text-muted">Social Security (annual)</p><p className="font-semibold">{formatCurrency(results.social_security_annual, true)}</p></div>
            <div><p className="text-xs text-text-muted">Needed from Portfolio</p><p className="font-semibold">{formatCurrency(results.portfolio_income_needed_annual, true)}/yr</p></div>
            <div><p className="text-xs text-text-muted">Current Savings Rate</p><p className="font-semibold">{formatPercent(results.current_savings_rate_pct)}</p></div>
            <div><p className="text-xs text-text-muted">Recommended Savings Rate</p><p className="font-semibold">{formatPercent(results.recommended_savings_rate_pct)}</p></div>
            <div><p className="text-xs text-text-muted">Monthly Contribution (with match)</p><p className="font-semibold">{formatCurrency(results.total_monthly_contribution)}</p></div>
            <div><p className="text-xs text-text-muted">Employer Match (monthly)</p><p className="font-semibold">{formatCurrency(results.employer_match_monthly)}</p></div>
            <div>
              <p className="text-xs text-text-muted">Retirement Target (25x rule)</p>
              <p className="font-semibold">{formatCurrency(results.fire_number, true)}</p>
              <p className="text-xs text-text-muted">25x your annual expenses — assumes 4% annual withdrawal</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Coast Number</p>
              <p className="font-semibold">{formatCurrency(results.coast_fire_number, true)}</p>
              <p className="text-xs text-text-muted">What you&apos;d need today to stop saving and still reach your target</p>
            </div>
            {results.debt_payoff_savings_annual > 0 && (
              <div><p className="text-xs text-text-muted">Debt Payoff Savings</p><p className="font-semibold text-green-600">{formatCurrency(results.debt_payoff_savings_annual)}/yr</p></div>
            )}
            {!results.on_track && (
              <div><p className="text-xs text-text-muted">Extra Monthly Savings Needed</p><p className="font-semibold text-red-600">{formatCurrency(results.monthly_savings_needed)}</p></div>
            )}
          </div>
        </details>
      </Card>

      {/* How the Simulator Works */}
      <Card padding="lg">
        <details>
          <summary className="cursor-pointer flex items-center gap-2 text-sm font-semibold text-text-primary">
            <AlertCircle size={16} className="text-blue-500" />
            How the Simulator Works
          </summary>
          <div className="mt-4 space-y-3 text-sm text-text-secondary">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-surface rounded-lg p-4">
                <p className="font-semibold text-text-secondary mb-1">1. Retirement Budget</p>
                <p>Your annual spending in retirement, based on your current budget adjusted for retirement (mortgage paid off, less commuting, more healthcare). Currently: <span className="font-mono font-semibold">{formatCurrency(results.annual_income_needed_today, true)}/yr</span></p>
              </div>
              <div className="bg-surface rounded-lg p-4">
                <p className="font-semibold text-text-secondary mb-1">2. Target Savings</p>
                <p>How much you need saved to fund {results.years_in_retirement} years of retirement ({inputs.life_expectancy - inputs.retirement_age}yr from age {inputs.retirement_age} to {inputs.life_expectancy}), accounting for inflation ({inputs.inflation_rate_pct}%) and portfolio returns ({inputs.post_retirement_return_pct}% in retirement). Target: <span className="font-mono font-semibold">{formatCurrency(targetToday, true)}</span></p>
              </div>
              <div className="bg-surface rounded-lg p-4">
                <p className="font-semibold text-text-secondary mb-1">3. Portfolio Growth</p>
                <p>Your current <span className="font-mono font-semibold">{formatCurrency(inputs.current_retirement_savings + inputs.current_other_investments, true)}</span> grows at <span className="font-semibold">{inputs.pre_retirement_return_pct}%/yr</span> (historical stock market average) with compound interest. Plus <span className="font-mono font-semibold">{formatCurrency(results.total_monthly_contribution)}/mo</span> in contributions (including employer match).</p>
              </div>
              <div className="bg-surface rounded-lg p-4">
                <p className="font-semibold text-text-secondary mb-1">4. On Track?</p>
                <p>After {results.years_to_retirement} years of growth + contributions, your portfolio is projected to reach <span className="font-mono font-semibold">{formatCurrency(projectedToday, true)}</span> (today&apos;s dollars) — {projectedToday >= targetToday ? "exceeding" : "short of"} the <span className="font-mono font-semibold">{formatCurrency(targetToday, true)}</span> target. {results.on_track ? "You're on track." : `You need to save an extra ${formatCurrency(results.monthly_savings_needed)}/mo.`}</p>
              </div>
            </div>
          </div>
        </details>
      </Card>
    </div>
  );
}
