"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Calculator, Loader2, AlertCircle, TrendingUp, Target,
  DollarSign, Clock, Flame, Shield, ChevronDown, ChevronUp,
  CheckCircle, XCircle, Save, Plus, Trash2, Zap, Calendar,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { calculateRetirement, getRetirementProfiles, createRetirementProfile, getRetirementBudgetSnapshot } from "@/lib/api";
import { getManualAssets } from "@/lib/api-assets";
import { getHouseholdProfiles, getHouseholdBenefits, getFamilyMembers } from "@/lib/api-household";
import type { RetirementResults, RetirementProfile, DebtPayoff, BudgetSnapshot } from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";
import type { HouseholdProfile, BenefitPackageType, FamilyMember } from "@/types/household";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
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
  // Track whether defaults were seeded from real data so we don't overwrite a loaded profile
  const [contextSeeded, setContextSeeded] = useState(false);

  /** Seed defaults from household + assets when no saved profile exists */
  const seedFromContext = useCallback(async () => {
    try {
      const [assets, profiles, members] = await Promise.all([
        getManualAssets().catch(() => [] as ManualAsset[]),
        getHouseholdProfiles().catch(() => [] as HouseholdProfile[]),
        getFamilyMembers().catch(() => [] as FamilyMember[]),
      ]);

      const primary = profiles.find((p) => p.is_primary) ?? profiles[0] ?? null;
      const primaryMember = members.find((m) => m.relationship === "self") ?? null;

      const retirementAssets = assets.filter((a) => a.is_retirement_account && !a.is_liability && a.is_active !== false);
      const totalRetirementSavings = retirementAssets.reduce((sum, a) => sum + (a.current_value ?? 0), 0);
      const otherInvestmentAssets = assets.filter((a) => a.asset_type === "investment" && !a.is_retirement_account && !a.is_liability && a.is_active !== false);
      const totalOtherInvestments = otherInvestmentAssets.reduce((sum, a) => sum + (a.current_value ?? 0), 0);

      // Best employer match from any retirement asset or benefit package
      let bestMatchPct = 0;
      let bestMatchLimitPct = 0;
      for (const a of retirementAssets) {
        if ((a.employer_match_pct ?? 0) > bestMatchPct) {
          bestMatchPct = a.employer_match_pct ?? 0;
          bestMatchLimitPct = a.employer_match_limit_pct ?? 0;
        }
      }

      // Try benefits if assets don't have match info
      if (bestMatchPct === 0 && primary) {
        const benefits = await getHouseholdBenefits(primary.id).catch(() => [] as BenefitPackageType[]);
        for (const b of benefits) {
          if ((b.employer_match_pct ?? 0) > bestMatchPct) {
            bestMatchPct = b.employer_match_pct ?? 0;
            bestMatchLimitPct = b.employer_match_limit_pct ?? 0;
          }
        }
      }

      // Calculate age from DOB
      let currentAge = DEFAULT_INPUTS.current_age;
      if (primaryMember?.date_of_birth) {
        const dob = new Date(primaryMember.date_of_birth);
        const today = new Date();
        currentAge = today.getFullYear() - dob.getFullYear();
        const hadBirthday = today.getMonth() > dob.getMonth() || (today.getMonth() === dob.getMonth() && today.getDate() >= dob.getDate());
        if (!hadBirthday) currentAge--;
      }

      setInputs((prev) => ({
        ...prev,
        current_annual_income: primary?.combined_income > 0 ? primary.combined_income : prev.current_annual_income,
        current_retirement_savings: totalRetirementSavings > 0 ? totalRetirementSavings : prev.current_retirement_savings,
        current_other_investments: totalOtherInvestments > 0 ? totalOtherInvestments : prev.current_other_investments,
        employer_match_pct: bestMatchPct > 0 ? bestMatchPct : prev.employer_match_pct,
        employer_match_limit_pct: bestMatchLimitPct > 0 ? bestMatchLimitPct : prev.employer_match_limit_pct,
        current_age: currentAge,
      }));
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
  }, []);

  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const body: Record<string, unknown> = { ...inputs };
        if (!body.desired_annual_retirement_income) delete body.desired_annual_retirement_income;
        if (!body.current_annual_expenses) delete body.current_annual_expenses;
        const r = await calculateRetirement(body);
        setResults(r);
      } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
      setLoading(false);
      setDirty(false);
    }, 400);
    return () => clearTimeout(timer);
  }, [inputs, dirty]);

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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Retirement Calculator"
        subtitle="How much do you need? When can you retire? Are you on track?"
        actions={
          <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm disabled:opacity-60">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save Profile
          </button>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} /><p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {/* Results Summary */}
      {results && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <div className={`rounded-xl border p-5 shadow-sm ${results.on_track ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
            <div className="flex items-center gap-2">
              {results.on_track ? <CheckCircle size={18} className="text-green-600" /> : <XCircle size={18} className="text-red-600" />}
              <p className="text-xs font-medium text-stone-600">Retirement Readiness</p>
            </div>
            <p className={`text-3xl font-bold mt-2 ${results.on_track ? "text-green-700" : "text-red-700"}`}>
              {formatPercent(results.retirement_readiness_pct)}
            </p>
            <p className={`text-xs mt-1 ${results.on_track ? "text-green-600" : "text-red-600"}`}>
              {results.on_track ? "You're on track!" : `Need ${formatCurrency(Math.abs(results.savings_gap), true)} more`}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
            <div className="flex items-center gap-2"><Target size={18} className="text-blue-500" /><p className="text-xs font-medium text-stone-500">Target Nest Egg</p></div>
            <p className="text-2xl font-bold text-stone-900 mt-2 tabular-nums">{formatCurrency(results.target_nest_egg, true)}</p>
            <p className="text-xs text-stone-400 mt-1">Projected: {formatCurrency(results.projected_nest_egg, true)}</p>
          </div>

          <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
            <div className="flex items-center gap-2"><Flame size={18} className="text-orange-500" /><p className="text-xs font-medium text-stone-500">FIRE Number</p></div>
            <p className="text-2xl font-bold text-stone-900 mt-2 tabular-nums">{formatCurrency(results.fire_number, true)}</p>
            <p className="text-xs text-stone-400 mt-1">Coast FIRE: {formatCurrency(results.coast_fire_number, true)}</p>
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
              {results.years_money_will_last >= results.years_in_retirement ? "Covers full retirement" : `${(results.years_in_retirement - results.years_money_will_last).toFixed(0)}yr shortfall`}
            </p>
          </div>
        </div>
      )}

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
                  <label className="text-xs text-stone-500">{label}</label>
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
                  <label className="text-xs text-stone-500">{label}</label>
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
            <div><p className="text-xs text-stone-400">Annual Income Needed (today)</p><p className="font-semibold">{formatCurrency(results.annual_income_needed_today, true)}</p></div>
            <div><p className="text-xs text-stone-400">Annual Income Needed (at retirement)</p><p className="font-semibold">{formatCurrency(results.annual_income_needed_at_retirement, true)}</p></div>
            <div><p className="text-xs text-stone-400">Projected Monthly Income</p><p className="font-semibold">{formatCurrency(results.projected_monthly_income)}</p></div>
            <div><p className="text-xs text-stone-400">Social Security (annual)</p><p className="font-semibold">{formatCurrency(results.social_security_annual, true)}</p></div>
            <div><p className="text-xs text-stone-400">Portfolio Income Needed</p><p className="font-semibold">{formatCurrency(results.portfolio_income_needed_annual, true)}/yr</p></div>
            <div><p className="text-xs text-stone-400">Current Savings Rate</p><p className="font-semibold">{formatPercent(results.current_savings_rate_pct)}</p></div>
            <div><p className="text-xs text-stone-400">Recommended Savings Rate</p><p className="font-semibold">{formatPercent(results.recommended_savings_rate_pct)}</p></div>
            <div><p className="text-xs text-stone-400">Monthly Contribution (with match)</p><p className="font-semibold">{formatCurrency(results.total_monthly_contribution)}</p></div>
            <div><p className="text-xs text-stone-400">Employer Match (monthly)</p><p className="font-semibold">{formatCurrency(results.employer_match_monthly)}</p></div>
            <div><p className="text-xs text-stone-400">Lean FIRE Number</p><p className="font-semibold">{formatCurrency(results.lean_fire_number, true)}</p></div>
            {results.debt_payoff_savings_annual > 0 && (
              <div><p className="text-xs text-stone-400">Debt Payoff Savings</p><p className="font-semibold text-green-600">{formatCurrency(results.debt_payoff_savings_annual)}/yr</p></div>
            )}
            {!results.on_track && (
              <div><p className="text-xs text-stone-400">Extra Monthly Savings Needed</p><p className="font-semibold text-red-600">{formatCurrency(results.monthly_savings_needed)}</p></div>
            )}
          </div>
        </Card>
      )}

      {loading && (
        <div className="fixed bottom-6 right-6 bg-stone-900 text-white px-4 py-2 rounded-full text-xs flex items-center gap-2 shadow-lg">
          <Loader2 size={14} className="animate-spin" /> Calculating...
        </div>
      )}
    </div>
  );
}
