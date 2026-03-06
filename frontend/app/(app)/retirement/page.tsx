"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Loader2, AlertCircle, TrendingUp, Target,
  DollarSign, Clock, ChevronDown, ChevronUp,
  CheckCircle, XCircle, Save, Plus, Trash2, Zap, Calendar, BarChart3, MessageCircle,
  ArrowDown, Wallet, Users,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { calculateRetirement, getRetirementProfiles, createRetirementProfile, getRetirementBudgetSnapshot, getSmartDefaults } from "@/lib/api";
import { getRetirementBudget } from "@/lib/api-retirement";
import { request } from "@/lib/api-client";
import type { RetirementResults, RetirementProfile, DebtPayoff, BudgetSnapshot, SmartDefaults } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import RetirementBudgetTable from "@/components/retirement/RetirementBudgetTable";
import { AutoFilledIndicator, MissingDataHint } from "@/components/ui/AutoFilledIndicator";
import SirHenryName from "@/components/ui/SirHenryName";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

interface RetirementInputState {
  name: string;
  current_age: number;
  retirement_age: number;
  life_expectancy: number;
  current_annual_income: number;
  expected_income_growth_pct: number;
  expected_social_security_monthly: number;
  social_security_start_age: number;
  pension_monthly: number;
  other_retirement_income_monthly: number;
  current_retirement_savings: number;
  current_other_investments: number;
  monthly_retirement_contribution: number;
  employer_match_pct: number;
  employer_match_limit_pct: number;
  desired_annual_retirement_income: number;
  income_replacement_pct: number;
  healthcare_annual_estimate: number;
  additional_annual_expenses: number;
  inflation_rate_pct: number;
  pre_retirement_return_pct: number;
  post_retirement_return_pct: number;
  tax_rate_in_retirement_pct: number;
  current_annual_expenses: number;
  debt_payoffs: DebtPayoff[];
  is_primary: boolean;
  notes: string | null;
}

const DEFAULT_INPUTS: RetirementInputState = {
  name: "My Retirement Plan",
  current_age: 35,
  retirement_age: 65,
  life_expectancy: 90,
  current_annual_income: 200000,
  expected_income_growth_pct: 3,
  expected_social_security_monthly: 2800,
  social_security_start_age: 67,
  pension_monthly: 0,
  other_retirement_income_monthly: 0,
  current_retirement_savings: 250000,
  current_other_investments: 100000,
  monthly_retirement_contribution: 3000,
  employer_match_pct: 50,
  employer_match_limit_pct: 6,
  desired_annual_retirement_income: 0,
  income_replacement_pct: 80,
  healthcare_annual_estimate: 15000,
  additional_annual_expenses: 10000,
  inflation_rate_pct: 3,
  pre_retirement_return_pct: 7,
  post_retirement_return_pct: 5,
  tax_rate_in_retirement_pct: 22,
  current_annual_expenses: 0,
  debt_payoffs: [],
  is_primary: true,
  notes: null,
};

type InputKey = keyof RetirementInputState;

export default function RetirementPage() {
  const [inputs, setInputs] = useState<RetirementInputState>(DEFAULT_INPUTS);
  const [results, setResults] = useState<RetirementResults | null>(null);
  const [profiles, setProfiles] = useState<RetirementProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(true);
  const [budgetSnapshot, setBudgetSnapshot] = useState<BudgetSnapshot | null>(null);
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
  // Track whether defaults were seeded from real data so we don't overwrite a loaded profile
  const [contextSeeded, setContextSeeded] = useState(false);
  // Track which fields were auto-filled for UI indicators
  const [autoFilledFields, setAutoFilledFields] = useState<Record<string, string>>({});
  // Tab: "simulator" or "budget"
  const [activeTab, setActiveTab] = useState<"simulator" | "budget">("budget");
  // Retirement budget annual total (from the budget table, feeds into simulator)
  const [retirementBudgetAnnual, setRetirementBudgetAnnual] = useState<number>(0);
  // Lump sum "What If" scenario
  const [lumpSumAmount, setLumpSumAmount] = useState<number>(50000);
  const [lumpSumResults, setLumpSumResults] = useState<RetirementResults | null>(null);
  const [lumpSumLoading, setLumpSumLoading] = useState(false);
  // Second Income "What If" scenario
  const [secondIncome, setSecondIncome] = useState({
    salary: 0, startsInYears: 1, worksUntilRetirement: true, workYears: 10,
    monthlySavings: 0, matchPct: 50, matchLimit: 6,
  });
  const [secondIncomeResults, setSecondIncomeResults] = useState<RetirementResults | null>(null);
  const [secondIncomeLoading, setSecondIncomeLoading] = useState(false);

  /** Seed defaults from SmartDefaults engine — one call pulls all data */
  const seedFromContext = useCallback(async () => {
    try {
      const defaults = await getSmartDefaults().catch(() => null as SmartDefaults | null);
      if (!defaults) { setContextSeeded(true); return; }

      const filled: Record<string, string> = {};
      const patch: Partial<RetirementInputState> = {};

      // Age from family member DOB
      if (defaults.age?.current_age) {
        patch.current_age = defaults.age.current_age;
        filled.current_age = "Date of Birth";
      }

      // Income from W-2 or household
      if (defaults.income?.combined > 0) {
        patch.current_annual_income = defaults.income.combined;
        filled.current_annual_income = defaults.data_sources?.has_w2 ? "W-2" : "Household Profile";
      }

      // Retirement savings from tagged accounts
      if (defaults.retirement?.total_savings > 0) {
        patch.current_retirement_savings = defaults.retirement.total_savings;
        filled.current_retirement_savings = "Retirement Accounts";
      }

      // Monthly contribution from W-2 Box 12 or account data
      if (defaults.retirement?.monthly_contribution > 0) {
        patch.monthly_retirement_contribution = defaults.retirement.monthly_contribution;
        filled.monthly_retirement_contribution = defaults.data_sources?.has_w2 ? "W-2 Box 12" : "Account Data";
      }

      // Employer match from benefits
      if (defaults.benefits?.match_pct > 0) {
        patch.employer_match_pct = defaults.benefits.match_pct;
        filled.employer_match_pct = "Benefits Package";
      }
      if (defaults.benefits?.match_limit_pct > 0) {
        patch.employer_match_limit_pct = defaults.benefits.match_limit_pct;
        filled.employer_match_limit_pct = "Benefits Package";
      }

      // Other investments from assets
      if (defaults.assets?.investment_total > 0) {
        patch.current_other_investments = defaults.assets.investment_total;
        filled.current_other_investments = "Investment Accounts";
      }

      // Annual expenses: prefer curated budget data over raw transaction totals
      // (raw totals include credit card payments, transfers, savings — not real spending)
      const snapshot = await getRetirementBudgetSnapshot().catch(() => null);
      if (snapshot) setBudgetSnapshot(snapshot);
      if (snapshot && snapshot.annual_expenses > 0) {
        patch.current_annual_expenses = snapshot.annual_expenses;
        filled.current_annual_expenses = "Personal Budget";
      }

      // Debts from liabilities — only retirement-relevant ones (mortgage, car loans)
      // not revolving credit cards
      if (defaults.debts?.length > 0) {
        const retDebts = defaults.debts.filter(
          (d: { retirement_relevant?: boolean }) => d.retirement_relevant !== false,
        );
        if (retDebts.length > 0) {
          const currentAge = patch.current_age || inputs.current_age;
          patch.debt_payoffs = retDebts.map(
            (d: { name: string; monthly_payment?: number; balance?: number }) => {
              let payoffAge = 65;
              // Estimate payoff age from balance and monthly payment
              if (d.monthly_payment && d.monthly_payment > 0 && d.balance) {
                const monthsLeft = Math.ceil(d.balance / d.monthly_payment);
                const yearsLeft = Math.ceil(monthsLeft / 12);
                payoffAge = Math.min(currentAge + yearsLeft, 90);
              }
              return {
                name: d.name,
                monthly_payment: d.monthly_payment || 0,
                payoff_age: payoffAge,
              };
            },
          );
          filled.debt_payoffs = "Linked Accounts";
        }
      }

      setInputs((prev) => ({ ...prev, ...patch }));
      setAutoFilledFields(filled);
      setContextSeeded(true);
    } catch {
      setContextSeeded(true);
    }
  }, []);

  const loadProfiles = useCallback(async () => {
    try {
      const p = await getRetirementProfiles();
      setProfiles(Array.isArray(p) ? p : []);
      if (p.length > 0) {
        const primary = p.find((pr) => pr.is_primary) || p[0];
        const loaded: RetirementInputState = { ...DEFAULT_INPUTS };
        const primaryRec = primary as unknown as Record<string, unknown>;
        const loadedRec = loaded as unknown as Record<string, unknown>;
        for (const key of Object.keys(DEFAULT_INPUTS) as InputKey[]) {
          if (key in primaryRec && primaryRec[key] != null) {
            loadedRec[key] = primaryRec[key];
          }
        }
        if (primary.debt_payoffs?.length) loaded.debt_payoffs = primary.debt_payoffs;
        setInputs(loaded);
        setDirty(true);
        setContextSeeded(true); // saved profile takes precedence — skip context seeding
      } else {
        // No saved profile: seed defaults from household + accounts
        await seedFromContext();
        setDirty(true);
      }
    } catch {
      setContextSeeded(true);
    }
  }, [seedFromContext]);

  useEffect(() => { loadProfiles(); }, [loadProfiles]);

  useEffect(() => {
    getRetirementBudgetSnapshot().then(setBudgetSnapshot).catch(() => {});
    // Pre-load retirement budget total so the simulator uses the correct expense number
    getRetirementBudget(inputs.retirement_age)
      .then((rb) => {
        if (rb.retirement_annual_total > 0) {
          setRetirementBudgetAnnual(rb.retirement_annual_total);
          setDirty(true);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const body: Record<string, unknown> = { ...inputs };
        if (!body.desired_annual_retirement_income) delete body.desired_annual_retirement_income;
        if (!body.current_annual_expenses) delete body.current_annual_expenses;
        // If retirement budget has been computed, pass it as the expense source
        if (retirementBudgetAnnual > 0) {
          body.retirement_budget_annual = retirementBudgetAnnual;
        }
        const r = await calculateRetirement(body);
        setResults(r);
      } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
      setLoading(false);
      setDirty(false);
    }, 400);
    return () => clearTimeout(timer);
  }, [inputs, dirty, retirementBudgetAnnual]);

  function update(key: InputKey, value: number | string) {
    setInputs((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  }

  function addDebtPayoff() {
    setInputs((prev) => ({
      ...prev,
      debt_payoffs: [...prev.debt_payoffs, { name: "", monthly_payment: 0, payoff_age: prev.current_age }],
    }));
    setDirty(true);
  }

  function updateDebtPayoff(idx: number, field: keyof DebtPayoff, value: string | number) {
    setInputs((prev) => {
      const debts = [...prev.debt_payoffs];
      debts[idx] = { ...debts[idx], [field]: value };
      return { ...prev, debt_payoffs: debts };
    });
    setDirty(true);
  }

  function removeDebtPayoff(idx: number) {
    setInputs((prev) => ({
      ...prev,
      debt_payoffs: prev.debt_payoffs.filter((_, i) => i !== idx),
    }));
    setDirty(true);
  }

  function applyBudgetSnapshot() {
    if (!budgetSnapshot) return;
    setInputs((prev) => ({
      ...prev,
      current_annual_expenses: budgetSnapshot.annual_expenses,
    }));
    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await createRetirementProfile(inputs as unknown as Parameters<typeof createRetirementProfile>[0]);
      await loadProfiles();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setSaving(false);
  }

  const chartData = results?.yearly_projection.map((p) => ({
    age: p.age,
    balance: Math.round(p.balance),
    phase: p.phase,
  })) || [];

  // Convert future-dollar values to today's dollars for intuitive display.
  // The backend computes targets in inflation-adjusted future dollars (correct for math),
  // but users think in today's money. Dividing by the inflation multiplier fixes the mismatch.
  const inflationMult = results && results.years_to_retirement > 0
    ? (1 + inputs.inflation_rate_pct / 100) ** results.years_to_retirement
    : 1;
  const targetToday = results ? results.target_nest_egg / inflationMult : 0;
  const projectedToday = results ? results.projected_nest_egg / inflationMult : 0;
  const gapToday = results ? results.savings_gap / inflationMult : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Retirement Simulator"
        subtitle="Build your retirement budget, track your progress, and see what it takes to retire sooner"
        actions={
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "Am I on track for retirement? What should I change about my savings strategy?" } }))}
              className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:text-[#15803D] transition-colors"
            >
              <MessageCircle size={14} />
              Ask <SirHenryName />
            </button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm disabled:opacity-60">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save Profile
            </button>
          </div>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} /><p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="flex gap-1 bg-stone-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => setActiveTab("budget")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            activeTab === "budget" ? "bg-white text-stone-800 shadow-sm" : "text-stone-500 hover:text-stone-700"
          }`}
        >
          <span className="flex items-center gap-1.5"><Wallet size={14} /> Retirement Budget</span>
        </button>
        <button
          onClick={() => setActiveTab("simulator")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            activeTab === "simulator" ? "bg-white text-stone-800 shadow-sm" : "text-stone-500 hover:text-stone-700"
          }`}
        >
          <span className="flex items-center gap-1.5"><BarChart3 size={14} /> Simulator</span>
        </button>
      </div>

      {/* Retirement Budget Tab */}
      {activeTab === "budget" && (
        <RetirementBudgetTable
          retirementAge={inputs.retirement_age}
          onTotalChange={(total) => setRetirementBudgetAnnual(total)}
        />
      )}

      {/* Simulator Tab */}
      {activeTab === "simulator" && (
      <>
      {/* Results Summary */}
      {results && (() => {
        const currentSavings = inputs.current_retirement_savings + inputs.current_other_investments;
        const currentPct = targetToday > 0 ? Math.min(100, currentSavings / targetToday * 100) : 0;
        const projectedPct = results.retirement_readiness_pct;
        return (
        <div className="space-y-4">
          {/* Retirement Readiness — full-width card with progress visualization */}
          <div className={`rounded-xl border p-5 shadow-sm ${results.on_track ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {results.on_track ? <CheckCircle size={18} className="text-green-600" /> : <XCircle size={18} className="text-red-600" />}
                <p className="text-sm font-semibold text-stone-800">Retirement Readiness</p>
              </div>
              <span className={`text-sm font-semibold px-3 py-1 rounded-full ${results.on_track ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                {results.on_track ? "On Track" : "Needs Attention"}
              </span>
            </div>

            {/* Progress bar — current savings vs target */}
            <div className="mb-3">
              <div className="flex justify-between text-xs text-stone-500 mb-1">
                <span>Current savings: <span className="font-semibold font-mono text-stone-700">{formatCurrency(currentSavings, true)}</span></span>
                <span>Target: <span className="font-semibold font-mono text-stone-700">{formatCurrency(targetToday, true)}</span></span>
              </div>
              <div className="h-3 bg-stone-200 rounded-full overflow-hidden relative">
                <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${Math.min(currentPct, 100)}%` }} />
              </div>
              <p className="text-xs text-stone-500 mt-1">
                <span className="font-semibold font-mono text-stone-700">{currentPct.toFixed(1)}%</span> saved today
              </p>
            </div>

            {/* How you get there */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-stone-200/60">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-stone-400">Monthly Contributions</p>
                <p className="text-sm font-semibold font-mono tabular-nums text-stone-800">{formatCurrency(results.total_monthly_contribution)}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-stone-400">Growth Rate</p>
                <p className="text-sm font-semibold text-stone-800">{inputs.pre_retirement_return_pct}% / yr</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-stone-400">Years to Grow</p>
                <p className="text-sm font-semibold text-stone-800">{results.years_to_retirement} years</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-stone-400">Projected at Retirement</p>
                <p className="text-sm font-semibold font-mono tabular-nums text-stone-800">{formatCurrency(projectedToday, true)}</p>
                <p className="text-[10px] text-stone-400">{projectedPct.toFixed(0)}% of target</p>
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
            <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
              <div className="flex items-center gap-2"><Wallet size={18} className="text-emerald-500" /><p className="text-xs font-medium text-stone-500">Retirement Budget</p></div>
              <p className="text-2xl font-bold text-stone-900 mt-2 font-mono tabular-nums">{formatCurrency(results.annual_income_needed_today, true)}<span className="text-sm font-normal text-stone-400">/yr</span></p>
              <p className="text-xs text-stone-400 mt-1">
                {results.debt_payoff_savings_annual > 0 ? `Saves ${formatCurrency(results.debt_payoff_savings_annual, true)}/yr from paid-off loans` : `${formatCurrency(results.annual_income_needed_today / 12)}/mo in today's dollars`}
              </p>
            </div>

            <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
              <div className="flex items-center gap-2"><Calendar size={18} className="text-indigo-500" /><p className="text-xs font-medium text-stone-500">Earliest Retirement</p></div>
              <p className="text-2xl font-bold text-stone-900 mt-2">Age {results.earliest_retirement_age}</p>
              <p className="text-xs text-stone-400 mt-1">
                {results.earliest_retirement_age <= inputs.current_age ? "You could retire now" :
                 results.earliest_retirement_age < inputs.retirement_age ? `${inputs.retirement_age - results.earliest_retirement_age}yr earlier possible` :
                 results.earliest_retirement_age === inputs.retirement_age ? "Matches your target" :
                 `${results.earliest_retirement_age - inputs.retirement_age}yr later than target`}
              </p>
            </div>

            <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
              <div className="flex items-center gap-2"><Clock size={18} className="text-purple-500" /><p className="text-xs font-medium text-stone-500">Money Lasts</p></div>
              <p className="text-2xl font-bold text-stone-900 mt-2">{results.years_money_will_last.toFixed(0)} years</p>
              <p className="text-xs text-stone-400 mt-1">
                {results.years_money_will_last >= results.years_in_retirement ? `Covers all ${results.years_in_retirement} years` : `${(results.years_in_retirement - results.years_money_will_last).toFixed(0)}yr shortfall`}
              </p>
            </div>

            <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
              <div className="flex items-center gap-2"><TrendingUp size={18} className="text-amber-500" /><p className="text-xs font-medium text-stone-500">Savings Rate</p></div>
              <p className="text-2xl font-bold text-stone-900 mt-2 font-mono tabular-nums">{results.current_savings_rate_pct.toFixed(1)}%</p>
              <p className="text-xs text-stone-400 mt-1">
                {results.recommended_savings_rate_pct > results.current_savings_rate_pct
                  ? `Recommended: ${results.recommended_savings_rate_pct.toFixed(1)}%`
                  : "Exceeds recommended rate"}
              </p>
            </div>
          </div>
        </div>);
      })()}

      {/* Projection Chart */}
      {chartData.length > 0 && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-800 mb-4">Portfolio Projection Over Time</h3>
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

      {/* How the Simulator Works */}
      {results && (
        <Card padding="lg">
          <details>
            <summary className="cursor-pointer flex items-center gap-2 text-sm font-semibold text-stone-800">
              <AlertCircle size={16} className="text-blue-500" />
              How the Simulator Works
            </summary>
            <div className="mt-4 space-y-3 text-sm text-stone-600">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-stone-50 rounded-lg p-4">
                  <p className="font-semibold text-stone-700 mb-1">1. Retirement Budget</p>
                  <p>Your annual spending in retirement, based on your current budget adjusted for retirement (mortgage paid off, less commuting, more healthcare). Currently: <span className="font-mono font-semibold">{formatCurrency(results.annual_income_needed_today, true)}/yr</span></p>
                </div>
                <div className="bg-stone-50 rounded-lg p-4">
                  <p className="font-semibold text-stone-700 mb-1">2. Target Savings</p>
                  <p>How much you need saved to fund {results.years_in_retirement} years of retirement ({inputs.life_expectancy - inputs.retirement_age}yr from age {inputs.retirement_age} to {inputs.life_expectancy}), accounting for inflation ({inputs.inflation_rate_pct}%) and portfolio returns ({inputs.post_retirement_return_pct}% in retirement). Target: <span className="font-mono font-semibold">{formatCurrency(targetToday, true)}</span></p>
                </div>
                <div className="bg-stone-50 rounded-lg p-4">
                  <p className="font-semibold text-stone-700 mb-1">3. Portfolio Growth</p>
                  <p>Your current <span className="font-mono font-semibold">{formatCurrency(inputs.current_retirement_savings + inputs.current_other_investments, true)}</span> grows at <span className="font-semibold">{inputs.pre_retirement_return_pct}%/yr</span> (historical stock market average) with compound interest. Plus <span className="font-mono font-semibold">{formatCurrency(results.total_monthly_contribution)}/mo</span> in contributions (including employer match).</p>
                </div>
                <div className="bg-stone-50 rounded-lg p-4">
                  <p className="font-semibold text-stone-700 mb-1">4. On Track?</p>
                  <p>After {results.years_to_retirement} years of growth + contributions, your portfolio is projected to reach <span className="font-mono font-semibold">{formatCurrency(projectedToday, true)}</span> (today&apos;s dollars) — {projectedToday >= targetToday ? "exceeding" : "short of"} the <span className="font-mono font-semibold">{formatCurrency(targetToday, true)}</span> target. {results.on_track ? "You're on track." : `You need to save an extra ${formatCurrency(results.monthly_savings_needed)}/mo.`}</p>
                </div>
              </div>
            </div>
          </details>
        </Card>
      )}

      {/* What If You Retire Earlier? */}
      {results && results.retire_earlier_scenarios?.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp size={18} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-stone-800">What If You Retire Earlier?</h3>
          </div>
          <p className="text-xs text-stone-400 mb-4">
            See what it takes to retire sooner. You can adjust the retirement age slider above to explore any target.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {results.retire_earlier_scenarios.map((scenario) => {
              const scenarioInflation = (1 + inputs.inflation_rate_pct / 100) ** (scenario.retirement_age - inputs.current_age);
              const scenarioTargetToday = scenario.target_nest_egg / scenarioInflation;
              const scenarioProjectedToday = scenario.projected_nest_egg / scenarioInflation;
              return (<div key={scenario.years_earlier} className={`rounded-xl border p-5 ${scenario.on_track ? "bg-green-50 border-green-200" : "bg-stone-50 border-stone-200"}`}>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-semibold text-stone-800">
                    Retire at {scenario.retirement_age} <span className="text-xs font-normal text-stone-400">({scenario.years_earlier}yr earlier)</span>
                  </p>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${scenario.on_track ? "bg-green-100 text-green-700" : "bg-stone-200 text-stone-600"}`}>
                    {scenario.readiness_pct.toFixed(0)}% ready
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-stone-400">Target Savings</p>
                    <p className="font-semibold font-mono tabular-nums">{formatCurrency(scenarioTargetToday, true)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-400">Projected</p>
                    <p className="font-semibold font-mono tabular-nums">{formatCurrency(scenarioProjectedToday, true)}</p>
                  </div>
                </div>
                {!scenario.on_track && scenario.monthly_savings_needed > 0 && (
                  <div className="mt-3 pt-3 border-t border-stone-200">
                    <p className="text-xs text-stone-500">
                      To hit this target, save an extra <span className="font-semibold text-stone-700">{formatCurrency(scenario.monthly_savings_needed)}/mo</span> beyond your current contributions
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

      {/* Lump Sum "What If" Scenario */}
      {results && (
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-1">
            <Zap size={18} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-stone-800">What If You Invest a Lump Sum Today?</h3>
          </div>
          <p className="text-xs text-stone-400 mb-4">
            See how a one-time investment today compounds over time and impacts your retirement timeline.
          </p>

          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1 max-w-xs">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
              <input
                type="number"
                value={lumpSumAmount}
                onChange={(e) => setLumpSumAmount(Number(e.target.value) || 0)}
                className="w-full pl-7 pr-3 py-2 border border-stone-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A]"
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
                  const body: Record<string, unknown> = { ...inputs };
                  // Add lump sum to other investments
                  body.current_other_investments = (inputs.current_other_investments || 0) + lumpSumAmount;
                  if (!body.desired_annual_retirement_income) delete body.desired_annual_retirement_income;
                  if (!body.current_annual_expenses) delete body.current_annual_expenses;
                  if (retirementBudgetAnnual > 0) body.retirement_budget_annual = retirementBudgetAnnual;
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

          {lumpSumResults && results && (() => {
            const currentEarliest = results.earliest_retirement_age;
            const newEarliest = lumpSumResults.earliest_retirement_age;
            const yearsSooner = currentEarliest - newEarliest;
            const newProjectedToday = lumpSumResults.projected_nest_egg / inflationMult;
            const extraAtRetirement = newProjectedToday - projectedToday;
            // Compound growth of the lump sum alone over years_to_retirement at pre_retirement_return
            const lumpGrowth = lumpSumAmount * ((1 + inputs.pre_retirement_return_pct / 100) ** results.years_to_retirement) - lumpSumAmount;
            const newMoneyLasts = lumpSumResults.years_money_will_last;
            const extraYears = newMoneyLasts - results.years_money_will_last;

            return (
              <div className="bg-amber-50 rounded-xl border border-amber-200 p-5">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-stone-500">Retire Earlier By</p>
                    <p className="text-xl font-bold text-amber-700 font-mono tabular-nums">
                      {yearsSooner > 0 ? `${yearsSooner} yr` : yearsSooner === 0 ? "Same" : "—"}
                    </p>
                    <p className="text-[10px] text-stone-400">
                      {yearsSooner > 0 ? `Age ${newEarliest} vs ${currentEarliest}` : "Already optimal"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-500">Lump Sum Grows To</p>
                    <p className="text-xl font-bold text-stone-800 font-mono tabular-nums">{formatCurrency(lumpSumAmount + lumpGrowth, true)}</p>
                    <p className="text-[10px] text-stone-400">{formatCurrency(lumpGrowth, true)} in compound growth</p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-500">Extra at Retirement</p>
                    <p className="text-xl font-bold text-stone-800 font-mono tabular-nums">+{formatCurrency(extraAtRetirement, true)}</p>
                    <p className="text-[10px] text-stone-400">Added to nest egg (today&apos;s $)</p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-500">Money Lasts</p>
                    <p className="text-xl font-bold text-stone-800 font-mono tabular-nums">{newMoneyLasts.toFixed(0)} yr</p>
                    <p className="text-[10px] text-stone-400">
                      {extraYears > 0.5 ? `+${extraYears.toFixed(0)}yr longer` : "Same duration"}
                    </p>
                  </div>
                </div>

                <p className="text-xs text-stone-500 mt-4 pt-3 border-t border-amber-200/60">
                  A one-time <span className="font-semibold">{formatCurrency(lumpSumAmount, true)}</span> investment today,
                  growing at {inputs.pre_retirement_return_pct}%/yr for {results.years_to_retirement} years,
                  becomes <span className="font-semibold">{formatCurrency(lumpSumAmount + lumpGrowth, true)}</span> at retirement
                  {yearsSooner > 0 && <> — letting you retire <span className="font-semibold text-amber-700">{yearsSooner} year{yearsSooner > 1 ? "s" : ""} sooner</span></>}.
                </p>
              </div>
            );
          })()}
        </Card>
      )}

      {/* Second Income "What If" Scenario */}
      {results && (
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-1">
            <Users size={18} className="text-emerald-600" />
            <h3 className="text-sm font-semibold text-stone-800">What If You Add a Second Income?</h3>
          </div>
          <p className="text-xs text-stone-400 mb-4">
            Model a spouse or partner returning to work — see how their savings accelerate your retirement timeline.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-stone-400 mb-1 block">Annual Salary</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
                <input type="number" value={secondIncome.salary || ""} onChange={(e) => setSecondIncome(s => ({...s, salary: Number(e.target.value) || 0}))}
                  className="w-full pl-7 pr-3 py-2 border border-stone-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                  placeholder="150000" step={10000} min={0} />
              </div>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-stone-400 mb-1 block">Monthly Savings</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
                <input type="number" value={secondIncome.monthlySavings || ""} onChange={(e) => setSecondIncome(s => ({...s, monthlySavings: Number(e.target.value) || 0}))}
                  className="w-full pl-7 pr-3 py-2 border border-stone-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                  placeholder="5000" step={500} min={0} />
              </div>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-stone-400 mb-1 block">Starts In</label>
              <div className="relative">
                <input type="number" value={secondIncome.startsInYears} onChange={(e) => setSecondIncome(s => ({...s, startsInYears: Math.max(0, Number(e.target.value) || 0)}))}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                  min={0} max={30} />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 text-xs">years</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 mb-4">
            <label className="flex items-center gap-2 text-sm text-stone-600 cursor-pointer">
              <input type="checkbox" checked={secondIncome.worksUntilRetirement}
                onChange={(e) => setSecondIncome(s => ({...s, worksUntilRetirement: e.target.checked}))}
                className="rounded border-stone-300 text-emerald-600 focus:ring-emerald-500" />
              Works until retirement
            </label>
            {!secondIncome.worksUntilRetirement && (
              <div className="flex items-center gap-2">
                <label className="text-xs text-stone-400">Years working:</label>
                <input type="number" value={secondIncome.workYears} onChange={(e) => setSecondIncome(s => ({...s, workYears: Math.max(1, Number(e.target.value) || 1)}))}
                  className="w-16 px-2 py-1 border border-stone-200 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                  min={1} max={30} />
              </div>
            )}
            <div className="flex items-center gap-2">
              <label className="text-xs text-stone-400">Employer match:</label>
              <input type="number" value={secondIncome.matchPct} onChange={(e) => setSecondIncome(s => ({...s, matchPct: Number(e.target.value) || 0}))}
                className="w-14 px-2 py-1 border border-stone-200 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                min={0} max={100} />
              <span className="text-xs text-stone-400">% up to</span>
              <input type="number" value={secondIncome.matchLimit} onChange={(e) => setSecondIncome(s => ({...s, matchLimit: Number(e.target.value) || 0}))}
                className="w-14 px-2 py-1 border border-stone-200 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                min={0} max={100} />
              <span className="text-xs text-stone-400">%</span>
            </div>
          </div>

          <button
            onClick={async () => {
              if (secondIncome.salary <= 0 || secondIncome.monthlySavings <= 0 || !results) return;
              setSecondIncomeLoading(true);
              try {
                const body: Record<string, unknown> = { ...inputs };
                if (!body.desired_annual_retirement_income) delete body.desired_annual_retirement_income;
                if (!body.current_annual_expenses) delete body.current_annual_expenses;
                if (retirementBudgetAnnual > 0) body.retirement_budget_annual = retirementBudgetAnnual;
                // Second income fields
                body.second_income_annual = secondIncome.salary;
                body.second_income_start_age = inputs.current_age + secondIncome.startsInYears;
                body.second_income_end_age = secondIncome.worksUntilRetirement
                  ? inputs.retirement_age
                  : inputs.current_age + secondIncome.startsInYears + secondIncome.workYears;
                body.second_income_monthly_contribution = secondIncome.monthlySavings;
                body.second_income_employer_match_pct = secondIncome.matchPct;
                body.second_income_employer_match_limit_pct = secondIncome.matchLimit;
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

          {secondIncomeResults && results && (() => {
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
                    <p className="text-xs text-stone-500">Retire Earlier By</p>
                    <p className="text-xl font-bold text-emerald-700 font-mono tabular-nums">
                      {yearsSooner > 0 ? `${yearsSooner} yr` : yearsSooner === 0 ? "Same" : "—"}
                    </p>
                    <p className="text-[10px] text-stone-400">
                      {yearsSooner > 0 ? `Age ${newEarliest} vs ${currentEarliest}` : `Earliest: age ${newEarliest}`}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-500">Extra Savings</p>
                    <p className="text-xl font-bold text-stone-800 font-mono tabular-nums">+{formatCurrency(extraProjected, true)}</p>
                    <p className="text-[10px] text-stone-400">Added to nest egg (today&apos;s $)</p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-500">New Earliest Age</p>
                    <p className="text-xl font-bold text-stone-800 font-mono tabular-nums">{newEarliest}</p>
                    <p className="text-[10px] text-stone-400">
                      {yearsSooner > 0 ? `${yearsSooner} yr sooner` : "Same as current"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-500">Readiness</p>
                    <p className="text-xl font-bold text-stone-800 font-mono tabular-nums">
                      {results.retirement_readiness_pct.toFixed(0)}% → {newReadiness.toFixed(0)}%
                    </p>
                    <p className="text-[10px] text-stone-400">
                      +{(newReadiness - results.retirement_readiness_pct).toFixed(0)} percentage points
                    </p>
                  </div>
                </div>

                <p className="text-xs text-stone-500 mt-4 pt-3 border-t border-emerald-200/60">
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
      )}

      {/* Monte Carlo Simulation */}
      {results && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 size={18} className="text-indigo-500" />
              <h3 className="text-sm font-semibold text-stone-800">Monte Carlo Simulation</h3>
            </div>
            <button
              onClick={async () => {
                setMcLoading(true);
                try {
                  const mc = await request<typeof monteCarloResult>("/retirement/monte-carlo", {
                    method: "POST",
                    body: JSON.stringify(inputs),
                  });
                  setMonteCarloResult(mc);
                } catch (e: unknown) {
                  setError(getErrorMessage(e));
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
          <p className="text-xs text-stone-400 mb-4">
            Runs 1,000 simulations varying annual returns and inflation to assess the probability your savings last through retirement.
          </p>
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
                  <p className="text-xs text-stone-500 mt-1">Success Rate</p>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-stone-600">
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
                  <div key={label} className="bg-stone-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-stone-400">{label}</p>
                    <p className="text-sm font-bold font-mono tabular-nums mt-1">{formatCurrency(value, true)}</p>
                  </div>
                ))}
              </div>
              <p className="text-xs text-stone-400">
                Based on {monteCarloResult.num_simulations.toLocaleString()} simulations. Final balance at age {inputs.life_expectancy}.
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Input Form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Personal & Income */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-800 mb-4">Personal & Income</h3>
          <div className="space-y-4">
            {[
              { key: "current_age" as InputKey, label: "Current Age", min: 18, max: 80, step: 1, suffix: "years old" },
              { key: "retirement_age" as InputKey, label: "Target Retirement Age", min: 40, max: 80, step: 1, suffix: "years old" },
              { key: "life_expectancy" as InputKey, label: "Life Expectancy", min: 70, max: 110, step: 1, suffix: "years" },
              { key: "current_annual_income" as InputKey, label: "Current Annual Income", min: 0, max: 2000000, step: 5000, prefix: "$" },
            ].map(({ key, label, min, max, step, prefix, suffix }) => (
              <div key={key}>
                <div className="flex justify-between items-center mb-1">
                  <span className="flex items-center gap-1.5">
                    <label className="text-xs text-stone-500">{label}</label>
                    {autoFilledFields[key] && <AutoFilledIndicator source={autoFilledFields[key]} />}
                  </span>
                  <span className="text-xs font-semibold text-stone-700 tabular-nums">
                    {prefix}{typeof inputs[key] === "number" ? (prefix === "$" ? (inputs[key] as number).toLocaleString() : String(inputs[key])) : String(inputs[key] ?? "")}{suffix ? ` ${suffix}` : ""}
                  </span>
                </div>
                <input type="range" min={min} max={max} step={step} value={inputs[key] as number} onChange={(e) => update(key, Number(e.target.value))} className="w-full h-1.5 bg-stone-200 rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
              </div>
            ))}
          </div>
        </Card>

        {/* Current Savings */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-800 mb-4">Current Savings & Contributions</h3>
          <div className="space-y-4">
            {[
              { key: "current_retirement_savings" as InputKey, label: "Retirement Savings (401k, IRA, etc.)", max: 5000000, step: 10000 },
              { key: "current_other_investments" as InputKey, label: "Other Investments", max: 5000000, step: 10000 },
              { key: "monthly_retirement_contribution" as InputKey, label: "Monthly Contribution", max: 10000, step: 100 },
            ].map(({ key, label, max, step }) => (
              <div key={key}>
                <div className="flex justify-between items-center mb-1">
                  <span className="flex items-center gap-1.5">
                    <label className="text-xs text-stone-500">{label}</label>
                    {autoFilledFields[key] && <AutoFilledIndicator source={autoFilledFields[key]} />}
                  </span>
                  <span className="text-xs font-semibold text-stone-700 tabular-nums">${(inputs[key] as number).toLocaleString()}</span>
                </div>
                <input type="range" min={0} max={max} step={step} value={inputs[key] as number} onChange={(e) => update(key, Number(e.target.value))} className="w-full h-1.5 bg-stone-200 rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
              </div>
            ))}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-stone-500">Employer Match %</label>
                <input type="number" value={inputs.employer_match_pct} onChange={(e) => update("employer_match_pct", Number(e.target.value))} min={0} max={100} className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
              </div>
              <div>
                <label className="text-xs text-stone-500">Match Limit %</label>
                <input type="number" value={inputs.employer_match_limit_pct} onChange={(e) => update("employer_match_limit_pct", Number(e.target.value))} min={0} max={100} className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
              </div>
            </div>
          </div>
        </Card>

        {/* Retirement Income */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-800 mb-4">Retirement Income Sources</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-stone-500">Expected Social Security (monthly)</label>
                <span className="text-xs font-semibold text-stone-700">${(inputs.expected_social_security_monthly).toLocaleString()}</span>
              </div>
              <input type="range" min={0} max={5000} step={100} value={inputs.expected_social_security_monthly} onChange={(e) => update("expected_social_security_monthly", Number(e.target.value))} className="w-full h-1.5 bg-stone-200 rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-stone-500">SS Start Age</label>
                <input type="number" value={inputs.social_security_start_age} onChange={(e) => update("social_security_start_age", Number(e.target.value))} min={62} max={70} className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
              </div>
              <div>
                <label className="text-xs text-stone-500">Pension (monthly)</label>
                <input type="number" value={inputs.pension_monthly} onChange={(e) => update("pension_monthly", Number(e.target.value))} min={0} className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-stone-500">Income Replacement %</label>
                <span className="text-xs font-semibold text-stone-700">{inputs.income_replacement_pct}%</span>
              </div>
              <input type="range" min={40} max={120} step={5} value={inputs.income_replacement_pct} onChange={(e) => update("income_replacement_pct", Number(e.target.value))} className="w-full h-1.5 bg-stone-200 rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>
          </div>
        </Card>

        {/* Retirement Expenses */}
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-800 mb-4">Retirement Expenses & Assumptions</h3>
          <div className="space-y-4">
            {/* Budget-based expenses */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-stone-500">Current Annual Expenses (from budget)</label>
                <span className="text-xs font-semibold text-stone-700">
                  {inputs.current_annual_expenses > 0 ? `$${inputs.current_annual_expenses.toLocaleString()}` : "Not set — using income replacement %"}
                </span>
              </div>
              {budgetSnapshot && budgetSnapshot.annual_expenses > 0 && inputs.current_annual_expenses === 0 && (
                <button
                  onClick={applyBudgetSnapshot}
                  className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:text-[#15803D] font-medium mt-1"
                >
                  <Zap size={12} />
                  Use actual budget: ${budgetSnapshot.annual_expenses.toLocaleString()}/yr
                </button>
              )}
              {inputs.current_annual_expenses > 0 && (
                <div className="flex items-center gap-2 mt-1">
                  <input type="range" min={0} max={500000} step={5000} value={inputs.current_annual_expenses}
                    onChange={(e) => update("current_annual_expenses", Number(e.target.value))}
                    className="flex-1 h-1.5 bg-stone-200 rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
                  <button onClick={() => { update("current_annual_expenses", 0); }} className="text-xs text-stone-400 hover:text-stone-600">Clear</button>
                </div>
              )}
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-stone-500">Healthcare (annual)</label>
                <span className="text-xs font-semibold text-stone-700">${(inputs.healthcare_annual_estimate).toLocaleString()}</span>
              </div>
              <input type="range" min={0} max={50000} step={1000} value={inputs.healthcare_annual_estimate} onChange={(e) => update("healthcare_annual_estimate", Number(e.target.value))} className="w-full h-1.5 bg-stone-200 rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs text-stone-500">Additional Expenses (annual)</label>
                <span className="text-xs font-semibold text-stone-700">${(inputs.additional_annual_expenses).toLocaleString()}</span>
              </div>
              <input type="range" min={0} max={100000} step={1000} value={inputs.additional_annual_expenses} onChange={(e) => update("additional_annual_expenses", Number(e.target.value))} className="w-full h-1.5 bg-stone-200 rounded-full appearance-none cursor-pointer accent-[#16A34A]" />
            </div>

            <button onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1 text-xs text-stone-500 hover:text-stone-700 mt-2">
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Advanced Assumptions
            </button>

            {showAdvanced && (
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-stone-100">
                {[
                  { key: "inflation_rate_pct" as InputKey, label: "Inflation Rate %" },
                  { key: "pre_retirement_return_pct" as InputKey, label: "Pre-Retirement Return %" },
                  { key: "post_retirement_return_pct" as InputKey, label: "Post-Retirement Return %" },
                  { key: "tax_rate_in_retirement_pct" as InputKey, label: "Tax Rate in Retirement %" },
                ].map(({ key, label }) => (
                  <div key={key}>
                    <label className="text-xs text-stone-500">{label}</label>
                    <input type="number" value={inputs[key] as number} onChange={(e) => update(key, Number(e.target.value))} min={0} max={50} step={0.5} className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Debt Payoffs — expenses that go away */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-stone-800">Debts That Pay Off Before Retirement</h3>
            <p className="text-xs text-stone-400 mt-0.5">Mortgage, car loans, student loans — these reduce your retirement expenses once paid off</p>
          </div>
          <button onClick={addDebtPayoff} className="flex items-center gap-1 text-xs font-medium text-[#16A34A] hover:text-[#15803D]">
            <Plus size={14} /> Add Debt
          </button>
        </div>
        {inputs.debt_payoffs.length === 0 ? (
          <p className="text-xs text-stone-400 text-center py-4">No debts added. Add mortgage, car loans, etc. to get more accurate retirement projections.</p>
        ) : (
          <div className="space-y-3">
            {inputs.debt_payoffs.map((debt, idx) => (
              <div key={idx} className="grid grid-cols-[1fr_120px_100px_32px] gap-2 items-end">
                <div>
                  <label className="text-xs text-stone-500">Debt Name</label>
                  <input type="text" value={debt.name} onChange={(e) => updateDebtPayoff(idx, "name", e.target.value)} placeholder="e.g. Mortgage"
                    className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                </div>
                <div>
                  <label className="text-xs text-stone-500">Monthly Payment</label>
                  <input type="number" value={debt.monthly_payment} onChange={(e) => updateDebtPayoff(idx, "monthly_payment", Number(e.target.value))} min={0}
                    className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                </div>
                <div>
                  <label className="text-xs text-stone-500">Payoff Age</label>
                  <input type="number" value={debt.payoff_age} onChange={(e) => updateDebtPayoff(idx, "payoff_age", Number(e.target.value))} min={inputs.current_age} max={100}
                    className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                </div>
                <button onClick={() => removeDebtPayoff(idx)} className="p-2 text-stone-400 hover:text-red-500 mb-0.5">
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

      {/* Detailed Results */}
      {results && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-800 mb-4">Detailed Analysis</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><p className="text-xs text-stone-400">Years to Retirement</p><p className="font-semibold">{results.years_to_retirement}</p></div>
            <div><p className="text-xs text-stone-400">Years in Retirement</p><p className="font-semibold">{results.years_in_retirement}</p></div>
            <div><p className="text-xs text-stone-400">Earliest Retirement Age</p><p className="font-semibold text-indigo-600">Age {results.earliest_retirement_age}</p></div>
            <div><p className="text-xs text-stone-400">Retirement Budget (today&apos;s $)</p><p className="font-semibold">{formatCurrency(results.annual_income_needed_today, true)}/yr</p></div>
            <div><p className="text-xs text-stone-400">Budget at Retirement (inflated)</p><p className="font-semibold">{formatCurrency(results.annual_income_needed_at_retirement, true)}/yr</p><p className="text-[10px] text-stone-300">After {results.years_to_retirement}yr of {inputs.inflation_rate_pct}% inflation + {inputs.tax_rate_in_retirement_pct}% tax</p></div>
            <div><p className="text-xs text-stone-400">Target Savings (today&apos;s $)</p><p className="font-semibold">{formatCurrency(targetToday, true)}</p></div>
            <div><p className="text-xs text-stone-400">Target at Retirement (inflated)</p><p className="font-semibold">{formatCurrency(results.target_nest_egg, true)}</p><p className="text-[10px] text-stone-300">Actual dollars needed on retirement day</p></div>
            <div><p className="text-xs text-stone-400">Projected Monthly Income</p><p className="font-semibold">{formatCurrency(results.projected_monthly_income)}</p></div>
            <div><p className="text-xs text-stone-400">Social Security (annual)</p><p className="font-semibold">{formatCurrency(results.social_security_annual, true)}</p></div>
            <div><p className="text-xs text-stone-400">Needed from Portfolio</p><p className="font-semibold">{formatCurrency(results.portfolio_income_needed_annual, true)}/yr</p></div>
            <div><p className="text-xs text-stone-400">Current Savings Rate</p><p className="font-semibold">{formatPercent(results.current_savings_rate_pct)}</p></div>
            <div><p className="text-xs text-stone-400">Recommended Savings Rate</p><p className="font-semibold">{formatPercent(results.recommended_savings_rate_pct)}</p></div>
            <div><p className="text-xs text-stone-400">Monthly Contribution (with match)</p><p className="font-semibold">{formatCurrency(results.total_monthly_contribution)}</p></div>
            <div><p className="text-xs text-stone-400">Employer Match (monthly)</p><p className="font-semibold">{formatCurrency(results.employer_match_monthly)}</p></div>
            <div>
              <p className="text-xs text-stone-400">Retirement Target (25x rule)</p>
              <p className="font-semibold">{formatCurrency(results.fire_number, true)}</p>
              <p className="text-[10px] text-stone-300">25x your annual expenses — assumes 4% annual withdrawal</p>
            </div>
            <div>
              <p className="text-xs text-stone-400">Coast Number</p>
              <p className="font-semibold">{formatCurrency(results.coast_fire_number, true)}</p>
              <p className="text-[10px] text-stone-300">What you&apos;d need today to stop saving and still reach your target</p>
            </div>
            {results.debt_payoff_savings_annual > 0 && (
              <div><p className="text-xs text-stone-400">Debt Payoff Savings</p><p className="font-semibold text-green-600">{formatCurrency(results.debt_payoff_savings_annual)}/yr</p></div>
            )}
            {!results.on_track && (
              <div><p className="text-xs text-stone-400">Extra Monthly Savings Needed</p><p className="font-semibold text-red-600">{formatCurrency(results.monthly_savings_needed)}</p></div>
            )}
          </div>
        </Card>
      )}

      </>
      )}

      {loading && (
        <div className="fixed bottom-6 right-6 bg-stone-900 text-white px-4 py-2 rounded-full text-xs flex items-center gap-2 shadow-lg">
          <Loader2 size={14} className="animate-spin" /> Calculating...
        </div>
      )}
    </div>
  );
}
