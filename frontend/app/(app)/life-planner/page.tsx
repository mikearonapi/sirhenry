"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Home, Car, Hammer, GraduationCap, Briefcase, Palmtree,
  Sparkles, Sunset, Loader2, AlertCircle, Star, Trash2, Plus,
  CheckCircle, XCircle, AlertTriangle, ChevronRight,
  TrendingUp, BarChart3, Target, GitCompare, MessageCircle,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  getScenarioTemplates, calculateScenario, getScenarios,
  createScenario, deleteScenario, updateScenario,
  composeScenarios, multiYearProjection, retirementImpact,
  monteCarloSimulation, compareScenarios,
} from "@/lib/api";
import { getHouseholdProfiles } from "@/lib/api-household";
import { getManualAssets } from "@/lib/api-assets";
import type {
  ScenarioTemplate, ScenarioCalcResult, LifeScenarioType,
  CompositeScenarioResult, MultiYearProjection, RetirementImpact,
  MonteCarloResult, ScenarioComparison,
} from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";
import type { HouseholdProfile } from "@/types/household";
import { getErrorMessage } from "@/lib/errors";
import { request } from "@/lib/api-client";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";

const ICONS: Record<string, React.ElementType> = {
  home: Home, car: Car, hammer: Hammer, "graduation-cap": GraduationCap,
  briefcase: Briefcase, "palm-tree": Palmtree, sparkles: Sparkles, sunset: Sunset,
};

const VERDICT_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  comfortable: { label: "Comfortable", color: "text-green-700", bg: "bg-green-50 border-green-200", icon: CheckCircle },
  feasible: { label: "Feasible", color: "text-blue-700", bg: "bg-blue-50 border-blue-200", icon: CheckCircle },
  stretch: { label: "Stretch", color: "text-amber-700", bg: "bg-amber-50 border-amber-200", icon: AlertTriangle },
  risky: { label: "Risky", color: "text-orange-700", bg: "bg-orange-50 border-orange-200", icon: AlertTriangle },
  not_recommended: { label: "Not Recommended", color: "text-red-700", bg: "bg-red-50 border-red-200", icon: XCircle },
};

export default function LifePlannerPage() {
  const [templates, setTemplates] = useState<Record<string, ScenarioTemplate>>({});
  const [savedScenarios, setSavedScenarios] = useState<LifeScenarioType[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [params, setParams] = useState<Record<string, number | string>>({});
  const [result, setResult] = useState<ScenarioCalcResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarioName, setScenarioName] = useState("");

  const [selectedScenarioIds, setSelectedScenarioIds] = useState<Set<number>>(new Set());
  const [composeResult, setComposeResult] = useState<CompositeScenarioResult | null>(null);
  const [compareResult, setCompareResult] = useState<ScenarioComparison | null>(null);
  const [yearProjections, setYearProjections] = useState<Record<number, MultiYearProjection>>({});
  const [monteCarloResults, setMonteCarloResults] = useState<Record<number, MonteCarloResult>>({});
  const [retirementResults, setRetirementResults] = useState<Record<number, RetirementImpact>>({});
  const [loadingCompose, setLoadingCompose] = useState(false);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [loadingProjection, setLoadingProjection] = useState<number | null>(null);
  const [loadingMonteCarlo, setLoadingMonteCarlo] = useState<number | null>(null);
  const [loadingRetirement, setLoadingRetirement] = useState<number | null>(null);
  const [aiAnalysisResults, setAiAnalysisResults] = useState<Record<number, string>>({});
  const [loadingAiAnalysis, setLoadingAiAnalysis] = useState<number | null>(null);

  // Financial context inputs — seeded from real household + account data
  const [annualIncome, setAnnualIncome] = useState(200000);
  const [monthlyTakeHome, setMonthlyTakeHome] = useState(12000);
  const [monthlyExpenses, setMonthlyExpenses] = useState(7000);
  const [monthlyDebt, setMonthlyDebt] = useState(2500);
  const [savings, setSavings] = useState(150000);
  const [investments, setInvestments] = useState(500000);
  const [contextLoaded, setContextLoaded] = useState(false);
  const [scenarioSuggestions, setScenarioSuggestions] = useState<Array<{ scenario_type: string; label: string; reason: string; source: string; source_detail?: string }>>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, s, sugg] = await Promise.all([
        getScenarioTemplates(),
        getScenarios(),
        request<{ suggestions: Array<{ scenario_type: string; label: string; reason: string; source: string; source_detail?: string }> }>("/scenarios/suggestions").catch(() => ({ suggestions: [] })),
      ]);
      setTemplates(t.templates || {});
      setSavedScenarios(Array.isArray(s) ? s : []);
      setScenarioSuggestions(sugg.suggestions || []);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setLoading(false);
  }, []);

  /** Seed financial snapshot from household + account data */
  const seedFinancialContext = useCallback(async () => {
    if (contextLoaded) return;
    try {
      const [profiles, assets] = await Promise.all([
        getHouseholdProfiles().catch(() => [] as HouseholdProfile[]),
        getManualAssets().catch(() => [] as ManualAsset[]),
      ]);
      const primary = profiles.find((p) => p.is_primary) ?? profiles[0] ?? null;

      // Liquid savings: checking + savings accounts
      const liquidAssets = assets.filter(
        (a) => !a.is_liability && a.is_active !== false &&
          (a.asset_type === "other_asset" || a.account_subtype === null) &&
          !a.is_retirement_account
      );
      // Investment accounts (non-retirement)
      const investmentAssets = assets.filter(
        (a) => a.asset_type === "investment" && !a.is_liability && !a.is_retirement_account && a.is_active !== false
      );
      // Liabilities for monthly debt
      const liabilityAssets = assets.filter((a) => a.is_liability && a.is_active !== false);

      const totalLiquid = liquidAssets.reduce((s, a) => s + (a.current_value ?? 0), 0);
      const totalInvestments = investmentAssets.reduce((s, a) => s + (a.current_value ?? 0), 0);

      // Rough monthly debt: liabilities value / 360 (30-year amortization proxy) — only as fallback
      const monthlyDebtEstimate = liabilityAssets.length > 0
        ? Math.round(liabilityAssets.reduce((s, a) => s + (a.current_value ?? 0), 0) / 360)
        : 2500;

      const combinedIncome = primary?.combined_income ?? 0;
      const estimatedMonthlyTakeHome = combinedIncome > 0 ? Math.round((combinedIncome * 0.72) / 12) : 12000;

      setAnnualIncome(combinedIncome > 0 ? combinedIncome : 200000);
      setMonthlyTakeHome(estimatedMonthlyTakeHome);
      if (totalLiquid > 0) setSavings(Math.round(totalLiquid));
      if (totalInvestments > 0) setInvestments(Math.round(totalInvestments));
      setMonthlyDebt(monthlyDebtEstimate);
      setContextLoaded(true);
    } catch {
      setContextLoaded(true);
    }
  }, [contextLoaded]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { seedFinancialContext(); }, [seedFinancialContext]);

  function selectTemplate(type: string) {
    const tmpl = templates[type];
    if (!tmpl) return;
    setSelectedType(type);
    const defaults: Record<string, number | string> = {};
    for (const [k, v] of Object.entries(tmpl.parameters)) {
      defaults[k] = v.default;
    }
    setParams(defaults);
    setResult(null);
    setScenarioName(tmpl.label);
  }

  async function handleCalculate() {
    if (!selectedType) return;
    setCalculating(true);
    try {
      const r = await calculateScenario({
        scenario_type: selectedType,
        parameters: params,
        annual_income: annualIncome,
        monthly_take_home: monthlyTakeHome,
        current_monthly_expenses: monthlyExpenses,
        current_monthly_debt_payments: monthlyDebt,
        current_savings: savings,
        current_investments: investments,
      });
      setResult(r);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setCalculating(false);
  }

  async function handleSave() {
    if (!selectedType || !result) return;
    try {
      await createScenario({
        name: scenarioName,
        scenario_type: selectedType,
        parameters: params,
        annual_income: annualIncome,
        monthly_take_home: monthlyTakeHome,
        current_monthly_expenses: monthlyExpenses,
        current_monthly_debt_payments: monthlyDebt,
        current_savings: savings,
        current_investments: investments,
      });
      await load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  async function handleDeleteScenario(id: number) {
    await deleteScenario(id);
    load();
  }

  async function toggleFavorite(s: LifeScenarioType) {
    await updateScenario(s.id, { is_favorite: !s.is_favorite });
    load();
  }

  function toggleScenarioSelection(id: number) {
    setSelectedScenarioIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleComposeScenarios() {
    const ids = Array.from(selectedScenarioIds);
    if (ids.length === 0) return;
    setLoadingCompose(true);
    setComposeResult(null);
    try {
      const r = await composeScenarios({ scenario_ids: ids });
      setComposeResult(r);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoadingCompose(false);
  }

  async function handleCompareScenarios() {
    const ids = Array.from(selectedScenarioIds);
    if (ids.length !== 2) return;
    setLoadingCompare(true);
    setCompareResult(null);
    try {
      const r = await compareScenarios({ scenario_a_id: ids[0], scenario_b_id: ids[1] });
      setCompareResult(r);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoadingCompare(false);
  }

  async function handleMultiYear(id: number) {
    setLoadingProjection(id);
    setYearProjections((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const r = await multiYearProjection(id, { years: 10 });
      setYearProjections((prev) => ({ ...prev, [id]: r }));
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoadingProjection(null);
  }

  async function handleMonteCarlo(id: number) {
    setLoadingMonteCarlo(id);
    setMonteCarloResults((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const r = await monteCarloSimulation(id, { runs: 1000 });
      setMonteCarloResults((prev) => ({ ...prev, [id]: r }));
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoadingMonteCarlo(null);
  }

  async function handleRetirementImpact(id: number) {
    setLoadingRetirement(id);
    setRetirementResults((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const r = await retirementImpact(id);
      setRetirementResults((prev) => ({ ...prev, [id]: r }));
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoadingRetirement(null);
  }

  async function handleAiAnalysis(id: number) {
    setLoadingAiAnalysis(id);
    try {
      const r = await request<{ analysis: string }>(`/scenarios/${id}/ai-analysis`, { method: "POST" });
      setAiAnalysisResults((prev) => ({ ...prev, [id]: r.analysis }));
      // Also update the savedScenarios to show the badge
      setSavedScenarios((prev) => prev.map((s) => s.id === id ? { ...s, ai_analysis: r.analysis } : s));
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoadingAiAnalysis(null);
  }

  const tmpl = selectedType ? templates[selectedType] : null;
  const verdict = result?.verdict ? VERDICT_CONFIG[result.verdict] : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Life Planner"
        subtitle="Can you afford it? Model major life decisions before you commit. Every scenario uses your actual financial data."
        actions={
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "What major financial decisions should I be planning for? Review my scenarios and life events and give me advice." } }))}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-[#16A34A]/10 text-[#16A34A] hover:bg-[#16A34A]/20 transition-colors"
          >
            <MessageCircle size={14} /> Ask Sir Henry
          </button>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} /><p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="animate-spin text-stone-300" size={28} /></div>
      ) : (
        <>
          {/* Suggested Scenarios from Life Events */}
          {!selectedType && scenarioSuggestions.length > 0 && (
            <Card padding="lg" className="border-[#16A34A]/20 bg-green-50/30">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={16} className="text-[#16A34A]" />
                <h2 className="text-sm font-semibold text-stone-700">Suggested for You</h2>
                <span className="text-xs text-stone-400">Based on your life events and financial data</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {scenarioSuggestions.map((sugg, i) => {
                  const tmplData = templates[sugg.scenario_type];
                  const IconComp = tmplData ? (ICONS[tmplData.icon] || Sparkles) : Sparkles;
                  return (
                    <button
                      key={i}
                      onClick={() => { setSelectedType(sugg.scenario_type); setResult(null); setParams({}); }}
                      className="flex items-start gap-3 p-3 rounded-lg bg-white border border-stone-200 hover:border-[#16A34A]/40 hover:shadow-sm transition-all text-left"
                    >
                      <div className="w-8 h-8 rounded-lg bg-[#16A34A]/10 flex items-center justify-center shrink-0">
                        <IconComp size={16} className="text-[#16A34A]" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-stone-800">{sugg.label}</p>
                        <p className="text-xs text-stone-500 mt-0.5">{sugg.reason}</p>
                        {sugg.source_detail && (
                          <p className="text-[10px] text-[#16A34A] mt-1">From: {sugg.source_detail}</p>
                        )}
                      </div>
                      <ChevronRight size={14} className="text-stone-300 shrink-0 mt-1" />
                    </button>
                  );
                })}
              </div>
            </Card>
          )}

          {/* Scenario Templates Grid */}
          {!selectedType && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(templates).map(([type, tmpl]) => {
                  const IconComp = ICONS[tmpl.icon] || Sparkles;
                  return (
                    <button
                      key={type}
                      onClick={() => selectTemplate(type)}
                      className="bg-white rounded-xl border border-stone-100 p-5 text-left hover:shadow-md hover:border-[#16A34A]/30 transition-all group"
                    >
                      <div className="w-10 h-10 rounded-lg bg-stone-100 group-hover:bg-[#16A34A]/10 flex items-center justify-center mb-3 transition-colors">
                        <IconComp size={20} className="text-stone-600 group-hover:text-[#16A34A] transition-colors" />
                      </div>
                      <p className="font-semibold text-sm text-stone-800">{tmpl.label}</p>
                      <p className="text-xs text-stone-400 mt-1">{tmpl.description}</p>
                    </button>
                  );
                })}
              </div>

              {/* Saved Scenarios */}
              {savedScenarios.length > 0 && (
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">Saved Scenarios</h2>
                  <div className="space-y-2">
                    {savedScenarios.map((s) => {
                      const v = s.verdict ? VERDICT_CONFIG[s.verdict] : null;
                      const VIcon = v?.icon || AlertTriangle;
                      const proj = yearProjections[s.id];
                      const mc = monteCarloResults[s.id];
                      const ret = retirementResults[s.id];
                      return (
                        <Card key={s.id} className={`${v?.bg || "bg-white"} border`}>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                checked={selectedScenarioIds.has(s.id)}
                                onChange={() => toggleScenarioSelection(s.id)}
                                className="rounded border-stone-300 text-[#16A34A] focus:ring-[#16A34A]/20"
                              />
                              <VIcon size={18} className={v?.color || "text-stone-400"} />
                              <div>
                                <p className="font-medium text-stone-800 text-sm">{s.name}</p>
                                <p className="text-xs text-stone-500">
                                  Score: {s.affordability_score?.toFixed(0) ?? "-"}/100
                                  {s.new_monthly_payment ? ` · ${formatCurrency(s.new_monthly_payment)}/mo` : ""}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <button
                                onClick={() => handleMultiYear(s.id)}
                                disabled={loadingProjection === s.id}
                                className="flex items-center gap-1 text-xs text-stone-600 hover:text-[#16A34A] disabled:opacity-60"
                                title="Multi-Year"
                              >
                                {loadingProjection === s.id ? <Loader2 size={12} className="animate-spin" /> : <TrendingUp size={12} />}
                                Multi-Year
                              </button>
                              <button
                                onClick={() => handleMonteCarlo(s.id)}
                                disabled={loadingMonteCarlo === s.id}
                                className="flex items-center gap-1 text-xs text-stone-600 hover:text-[#16A34A] disabled:opacity-60"
                                title="Monte Carlo"
                              >
                                {loadingMonteCarlo === s.id ? <Loader2 size={12} className="animate-spin" /> : <BarChart3 size={12} />}
                                Monte Carlo
                              </button>
                              <button
                                onClick={() => handleRetirementImpact(s.id)}
                                disabled={loadingRetirement === s.id}
                                className="flex items-center gap-1 text-xs text-stone-600 hover:text-[#16A34A] disabled:opacity-60"
                                title="Retirement Impact"
                              >
                                {loadingRetirement === s.id ? <Loader2 size={12} className="animate-spin" /> : <Target size={12} />}
                                Retirement
                              </button>
                              <button
                                onClick={() => handleAiAnalysis(s.id)}
                                disabled={loadingAiAnalysis === s.id}
                                className="flex items-center gap-1 text-xs text-[#16A34A] hover:text-[#15803D] disabled:opacity-60"
                                title="AI Analysis"
                              >
                                {loadingAiAnalysis === s.id ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                                AI Analysis
                              </button>
                              <span className={`text-xs font-semibold px-2 py-0.5 rounded ${v?.color || ""}`}>
                                {v?.label || s.verdict}
                              </span>
                              <button onClick={() => toggleFavorite(s)} className={`${s.is_favorite ? "text-amber-400" : "text-stone-300"} hover:text-amber-500`}>
                                <Star size={14} fill={s.is_favorite ? "currentColor" : "none"} />
                              </button>
                              <button onClick={() => handleDeleteScenario(s.id)} className="text-stone-300 hover:text-red-500">
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                          {proj && (
                            <div className="mt-3 pt-3 border-t border-stone-200 bg-stone-50 rounded-lg p-3">
                              <p className="text-xs font-semibold text-stone-600 mb-2">Multi-Year Projection (10 years)</p>
                              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 overflow-x-auto">
                                {proj.years.slice(0, 10).map((y) => (
                                  <div key={y.year} className="bg-white rounded p-2 text-xs">
                                    <p className="text-stone-500">Year {y.year}</p>
                                    <p className="font-medium text-stone-800">{formatCurrency(y.net_worth ?? 0)}</p>
                                    <p className="text-stone-400">{formatCurrency(y.cash_flow ?? 0)} CF</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {mc && (
                            <div className="mt-3 pt-3 border-t border-stone-200 bg-stone-50 rounded-lg p-3">
                              <p className="text-xs font-semibold text-stone-600 mb-2">Monte Carlo Outcomes ({mc.runs} runs)</p>
                              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                                {[
                                  { label: "P10", val: mc.p10 },
                                  { label: "P25", val: mc.p25 },
                                  { label: "P50", val: mc.p50 },
                                  { label: "P75", val: mc.p75 },
                                  { label: "P90", val: mc.p90 },
                                ].map(({ label, val }) => (
                                  <div key={label} className="bg-white rounded p-2 text-xs">
                                    <p className="text-stone-500">{label}</p>
                                    <p className="font-medium text-stone-800">{formatCurrency(val)}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {ret && (
                            <div className="mt-3 pt-3 border-t border-stone-200 bg-stone-50 rounded-lg p-3">
                              <p className="text-xs font-semibold text-stone-600 mb-2">Retirement Impact</p>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                <div>
                                  <p className="text-stone-500">Years delayed</p>
                                  <p className="font-medium text-stone-800">{ret.years_delayed}</p>
                                </div>
                                <div>
                                  <p className="text-stone-500">New retirement age</p>
                                  <p className="font-medium text-stone-800">{ret.new_retirement_age}</p>
                                </div>
                                <div>
                                  <p className="text-stone-500">New FIRE number</p>
                                  <p className="font-medium text-stone-800">{formatCurrency(ret.new_fire_number)}</p>
                                </div>
                                <div>
                                  <p className="text-stone-500">Current FIRE number</p>
                                  <p className="font-medium text-stone-800">{formatCurrency(ret.current_fire_number)}</p>
                                </div>
                              </div>
                            </div>
                          )}
                          {(aiAnalysisResults[s.id] || s.ai_analysis) && (
                            <div className="mt-3 pt-3 border-t border-stone-200 bg-green-50/50 rounded-lg p-3">
                              <div className="flex items-center gap-2 mb-2">
                                <Sparkles size={14} className="text-[#16A34A]" />
                                <p className="text-xs font-semibold text-[#16A34A]">Sir Henry&apos;s Analysis</p>
                              </div>
                              <div className="text-xs text-stone-700 leading-relaxed whitespace-pre-wrap">
                                {aiAnalysisResults[s.id] || s.ai_analysis}
                              </div>
                            </div>
                          )}
                        </Card>
                      );
                    })}
                  </div>

                  <div className="mt-4 space-y-4">
                    <div className="flex items-center gap-3 flex-wrap">
                      <button
                        onClick={handleComposeScenarios}
                        disabled={selectedScenarioIds.size === 0 || loadingCompose}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#16A34A] text-white text-sm font-medium hover:bg-[#15803D] disabled:opacity-60"
                      >
                        {loadingCompose ? <Loader2 size={14} className="animate-spin" /> : null}
                        Combine Scenarios
                      </button>
                      {selectedScenarioIds.size === 2 && (
                        <button
                          onClick={handleCompareScenarios}
                          disabled={loadingCompare}
                          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-stone-200 text-stone-700 text-sm font-medium hover:bg-stone-50 disabled:opacity-60"
                        >
                          {loadingCompare ? <Loader2 size={14} className="animate-spin" /> : <GitCompare size={14} />}
                          Compare
                        </button>
                      )}
                    </div>

                    {composeResult && (
                      <Card className="bg-stone-50 border-stone-200">
                        <h3 className="text-sm font-semibold text-stone-800 mb-3">Combined Result</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="bg-white rounded-lg p-3">
                            <p className="text-xs text-stone-500">Total Monthly Impact</p>
                            <p className="text-lg font-bold text-stone-800 font-mono tabular-nums">{formatCurrency(composeResult.combined_monthly_impact)}</p>
                          </div>
                          <div className="bg-white rounded-lg p-3">
                            <p className="text-xs text-stone-500">Savings Rate After</p>
                            <p className="text-lg font-bold text-stone-800 font-mono tabular-nums">{formatPercent(composeResult.combined_savings_rate_after ?? 0)}</p>
                          </div>
                          <div className="bg-white rounded-lg p-3">
                            <p className="text-xs text-stone-500">Affordability Score</p>
                            <p className="text-lg font-bold text-stone-800 font-mono tabular-nums">{composeResult.combined_affordability_score?.toFixed(0) ?? "-"}/100</p>
                          </div>
                          <div className="bg-white rounded-lg p-3">
                            <p className="text-xs text-stone-500">Verdict</p>
                            <p className="text-sm font-semibold text-stone-800">{composeResult.combined_verdict}</p>
                          </div>
                        </div>
                        {composeResult.scenarios?.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-stone-200">
                            <p className="text-xs text-stone-500 mb-1">Scenarios included</p>
                            <p className="text-xs text-stone-700">{composeResult.scenarios.map((s: { name: string }) => s.name).join(", ")}</p>
                          </div>
                        )}
                      </Card>
                    )}

                    {compareResult && (
                      <Card className="bg-stone-50 border-stone-200">
                        <h3 className="text-sm font-semibold text-stone-800 mb-3">Scenario Comparison</h3>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="bg-white rounded-lg p-4 border border-stone-100">
                            <p className="text-xs font-semibold text-stone-500 mb-2">{compareResult.scenario_a.name}</p>
                            <div className="space-y-1 text-xs">
                              {Object.entries(compareResult.scenario_a.metrics || {}).map(([k, v]) => (
                                <div key={k} className="flex justify-between">
                                  <span className="text-stone-500">{k.replace(/_/g, " ")}</span>
                                  <span className="font-medium tabular-nums">{typeof v === "number" ? (k.includes("pct") || k.includes("rate") ? formatPercent(v) : formatCurrency(v)) : String(v)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="bg-white rounded-lg p-4 border border-stone-100">
                            <p className="text-xs font-semibold text-stone-500 mb-2">{compareResult.scenario_b.name}</p>
                            <div className="space-y-1 text-xs">
                              {Object.entries(compareResult.scenario_b.metrics || {}).map(([k, v]) => (
                                <div key={k} className="flex justify-between">
                                  <span className="text-stone-500">{k.replace(/_/g, " ")}</span>
                                  <span className="font-medium tabular-nums">{typeof v === "number" ? (k.includes("pct") || k.includes("rate") ? formatPercent(v) : formatCurrency(v)) : String(v)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                        {compareResult.differences && Object.keys(compareResult.differences).length > 0 && (
                          <div className="mt-3 pt-3 border-t border-stone-200 bg-white rounded-lg p-3">
                            <p className="text-xs font-semibold text-stone-600 mb-2">Differences</p>
                            <div className="space-y-1 text-xs">
                              {Object.entries(compareResult.differences).map(([k, v]) => (
                                <div key={k} className="flex justify-between">
                                  <span className="text-stone-500">{k.replace(/_/g, " ")}</span>
                                  <span className="font-medium tabular-nums">{typeof v === "number" ? (k.includes("pct") || k.includes("rate") ? formatPercent(v) : formatCurrency(v)) : String(v)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </Card>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Scenario Calculator */}
          {selectedType && tmpl && (
            <>
              <button onClick={() => { setSelectedType(null); setResult(null); }} className="text-sm text-stone-500 hover:text-stone-700 flex items-center gap-1">
                &larr; Back to templates
              </button>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {/* Parameters */}
                <Card padding="lg">
                  <h3 className="text-sm font-semibold text-stone-800 mb-1">{tmpl.label}</h3>
                  <p className="text-xs text-stone-400 mb-4">{tmpl.description}</p>
                  <div className="space-y-3">
                    {Object.entries(tmpl.parameters).map(([key, def]) => (
                      <div key={key}>
                        <label className="block text-xs text-stone-500 mb-1">{def.label}</label>
                        {def.type === "text" ? (
                          <input value={params[key] || ""} onChange={(e) => setParams({ ...params, [key]: e.target.value })} className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                        ) : (
                          <input type="number" value={params[key] || 0} onChange={(e) => setParams({ ...params, [key]: Number(e.target.value) })} className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                        )}
                      </div>
                    ))}
                  </div>
                </Card>

                {/* Financial Context */}
                <Card padding="lg">
                  <h3 className="text-sm font-semibold text-stone-800 mb-4">Your Financial Snapshot</h3>
                  <div className="space-y-3">
                    {[
                      { label: "Annual Income", value: annualIncome, set: setAnnualIncome },
                      { label: "Monthly Take-Home", value: monthlyTakeHome, set: setMonthlyTakeHome },
                      { label: "Monthly Expenses", value: monthlyExpenses, set: setMonthlyExpenses },
                      { label: "Monthly Debt Payments", value: monthlyDebt, set: setMonthlyDebt },
                      { label: "Liquid Savings", value: savings, set: setSavings },
                      { label: "Investments", value: investments, set: setInvestments },
                    ].map(({ label, value, set }) => (
                      <div key={label}>
                        <label className="block text-xs text-stone-500 mb-1">{label}</label>
                        <input type="number" value={value} onChange={(e) => set(Number(e.target.value))} className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                      </div>
                    ))}
                  </div>
                  <button onClick={handleCalculate} disabled={calculating} className="w-full mt-4 flex items-center justify-center gap-2 bg-[#16A34A] text-white py-3 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm disabled:opacity-60">
                    {calculating ? <Loader2 size={14} className="animate-spin" /> : null}
                    {calculating ? "Calculating..." : "Can I Afford This?"}
                  </button>
                </Card>
              </div>

              {/* Results */}
              {result && verdict && (
                <div className={`rounded-xl border-2 ${verdict.bg} p-6`}>
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-full ${verdict.bg} flex items-center justify-center`}>
                        <verdict.icon size={24} className={verdict.color} />
                      </div>
                      <div>
                        <p className={`text-2xl font-bold ${verdict.color}`}>{verdict.label}</p>
                        <p className="text-sm text-stone-600">Affordability Score: {result.affordability_score}/100</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-stone-500">Score</p>
                      <div className="relative w-20 h-20">
                        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke={result.affordability_score >= 60 ? "#22c55e" : result.affordability_score >= 40 ? "#f59e0b" : "#ef4444"} strokeWidth="3" strokeDasharray={`${result.affordability_score}, 100`} />
                        </svg>
                        <span className="absolute inset-0 flex items-center justify-center text-lg font-bold">{Math.round(result.affordability_score)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-white/70 rounded-lg p-3">
                      <p className="text-xs text-stone-500">New Monthly Payment</p>
                      <p className="text-lg font-bold text-stone-800 font-mono tabular-nums">{formatCurrency(result.new_monthly_payment)}</p>
                    </div>
                    <div className="bg-white/70 rounded-lg p-3">
                      <p className="text-xs text-stone-500">Monthly Surplus After</p>
                      <p className={`text-lg font-bold font-mono tabular-nums ${result.monthly_surplus_after >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {formatCurrency(result.monthly_surplus_after)}
                      </p>
                    </div>
                    <div className="bg-white/70 rounded-lg p-3">
                      <p className="text-xs text-stone-500">Savings Rate After</p>
                      <p className="text-lg font-bold text-stone-800 font-mono tabular-nums">{formatPercent(result.savings_rate_after_pct)}</p>
                      <p className="text-xs text-stone-400">was {formatPercent(result.savings_rate_before_pct)}</p>
                    </div>
                    <div className="bg-white/70 rounded-lg p-3">
                      <p className="text-xs text-stone-500">Total Cost</p>
                      <p className="text-lg font-bold text-stone-800 font-mono tabular-nums">{formatCurrency(result.total_cost, true)}</p>
                    </div>
                  </div>

                  {result.breakdown && (
                    <div className="bg-white/70 rounded-lg p-4">
                      <p className="text-xs font-semibold text-stone-600 mb-2">Cost Breakdown</p>
                      <div className="grid grid-cols-2 gap-2">
                        {Object.entries(result.breakdown).map(([k, v]) => (
                          <div key={k} className="flex justify-between text-xs">
                            <span className="text-stone-500">{k.replace(/_/g, " ")}</span>
                            <span className="font-medium tabular-nums">{formatCurrency(v as number)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-3 mt-4">
                    <button onClick={handleSave} className="bg-stone-900 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-stone-800 shadow-sm">
                      Save This Scenario
                    </button>
                    <button onClick={() => setResult(null)} className="text-sm text-stone-500 hover:text-stone-700 px-3">
                      Adjust Parameters
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
