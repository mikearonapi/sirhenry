"use client";
import { useEffect, useState } from "react";
import {
  AlertCircle, Loader2, Sparkles, ChevronDown, ChevronUp,
  DollarSign, X, Lightbulb, TrendingDown,
  Car, Monitor, PiggyBank, Home, Heart, GraduationCap, ShieldCheck,
} from "lucide-react";
import {
  dismissStrategy, getTaxDeductionOpportunities, getTaxStrategies,
  modelDAFBunching, modelEstimatedPayments, modelMultiYearTax,
  modelRothConversion, modelSCorp, modelStudentLoan, runTaxAnalysis,
} from "@/lib/api";
import { getHouseholdProfiles, getHouseholdBenefits } from "@/lib/api-household";
import { getBusinessEntities } from "@/lib/api-entities";
import { formatCurrency, priorityColor, priorityLabel } from "@/lib/utils";
import type {
  DeductionOpportunity, MultiYearTaxProjection, RothConversionResult,
  SCorpAnalysisResult, StudentLoanResult, TaxDeductionInsights, TaxStrategy,
} from "@/types/api";
import type { HouseholdProfile, BenefitPackageType } from "@/types/household";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/ui/PageHeader";

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2];

const OPPORTUNITY_ICONS: Record<string, typeof Car> = {
  vehicle: Car, equipment: Monitor, retirement: PiggyBank,
  home_office: Home, charitable: Heart, education: GraduationCap, other: ShieldCheck,
};
const URGENCY_COLORS: Record<string, string> = {
  high: "bg-red-50 text-red-700 border-red-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-blue-50 text-blue-700 border-blue-200",
};

const STRATEGY_TABS = ["Roth Conversion", "S-Corp Analysis", "Estimated Payments", "DAF Bunching", "Student Loans", "Multi-Year"];

export default function TaxStrategyPage() {
  const [year, setYear] = useState(currentYear - 1);
  const [strategies, setStrategies] = useState<TaxStrategy[]>([]);
  const [deductions, setDeductions] = useState<TaxDeductionInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [expandedOpp, setExpandedOpp] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [labTab, setLabTab] = useState(0);

  // Strategy Lab state
  const [rothTraditional, setRothTraditional] = useState("");
  const [rothCurrentIncome, setRothCurrentIncome] = useState("");
  const [rothYears, setRothYears] = useState(10);
  const [rothTargetBracket, setRothTargetBracket] = useState("");
  const [rothResult, setRothResult] = useState<RothConversionResult | null>(null);
  const [rothLoading, setRothLoading] = useState(false);
  const [scorpGross, setScorpGross] = useState("");
  const [scorpSalary, setScorpSalary] = useState("");
  const [scorpExpenses, setScorpExpenses] = useState("");
  const [scorpResult, setScorpResult] = useState<SCorpAnalysisResult | null>(null);
  const [scorpLoading, setScorpLoading] = useState(false);
  const [estUnderwithholding, setEstUnderwithholding] = useState("");
  const [estPriorTax, setEstPriorTax] = useState("");
  const [estCurrentWithholding, setEstCurrentWithholding] = useState("");
  const [estResult, setEstResult] = useState<{ quarterly_payments: Array<{ quarter: number; due_date: string; amount: number }> } | null>(null);
  const [estLoading, setEstLoading] = useState(false);
  const [dafAnnual, setDafAnnual] = useState("");
  const [dafStandard, setDafStandard] = useState("");
  const [dafItemizedExcl, setDafItemizedExcl] = useState("");
  const [dafBunchYears, setDafBunchYears] = useState(2);
  const [dafResult, setDafResult] = useState<{ annual_tax: number; bunched_tax: number; savings: number } | null>(null);
  const [dafLoading, setDafLoading] = useState(false);
  const [loanBalance, setLoanBalance] = useState("");
  const [loanRate, setLoanRate] = useState("");
  const [loanMonthlyIncome, setLoanMonthlyIncome] = useState("");
  const [loanFilingStatus, setLoanFilingStatus] = useState("single");
  const [loanPslf, setLoanPslf] = useState(false);
  const [loanResult, setLoanResult] = useState<StudentLoanResult | null>(null);
  const [loanLoading, setLoanLoading] = useState(false);
  const [multiIncome, setMultiIncome] = useState("");
  const [multiGrowth, setMultiGrowth] = useState("");
  const [multiFilingStatus, setMultiFilingStatus] = useState("mfj");
  const [multiStateRate, setMultiStateRate] = useState("");
  const [multiYears, setMultiYears] = useState(5);
  const [multiResult, setMultiResult] = useState<MultiYearTaxProjection | null>(null);
  const [multiLoading, setMultiLoading] = useState(false);
  const [hasSCorp, setHasSCorp] = useState(false);

  // Load household context to pre-populate Strategy Lab forms
  useEffect(() => {
    Promise.all([
      getHouseholdProfiles().catch(() => [] as HouseholdProfile[]),
      getBusinessEntities().catch(() => []),
    ]).then(([profiles, entities]) => {
      const primary = profiles.find((p) => p.is_primary) ?? profiles[0] ?? null;
      if (primary) {
        const combined = String(Math.round(primary.combined_income || 0));
        const monthlyIncome = String(Math.round((primary.combined_income || 0) / 12));
        // Roth Conversion: seed income
        setRothCurrentIncome(combined || "");
        // Multi-year: seed income + filing status + state rate
        setMultiIncome(combined || "");
        setMultiFilingStatus(primary.filing_status || "mfj");
        // Loan: seed monthly income + filing status
        setLoanMonthlyIncome(monthlyIncome);
        setLoanFilingStatus(primary.filing_status === "single" ? "single" : "mfj");

        // Seed 401k traditional balance from benefits for Roth ladder
        getHouseholdBenefits(primary.id).catch(() => [] as BenefitPackageType[]).then((benefits) => {
          const totalContributions = benefits.reduce((sum, b) => sum + (b.annual_401k_contribution ?? 0), 0);
          if (totalContributions > 0) setRothTraditional(String(Math.round(totalContributions)));
        });
      }

      // Detect S-Corp — auto-switch to that tab
      const scorp = entities.find((e) => e.entity_type === "s_corp" || e.tax_treatment === "s_corp");
      if (scorp) {
        setHasSCorp(true);
        setLabTab(1); // S-Corp Analysis tab index
      }
    }).catch(() => {});
  }, []);

  async function load(y: number, signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    try {
      const [st, ded] = await Promise.all([
        getTaxStrategies(y).catch(() => []),
        getTaxDeductionOpportunities(y).catch(() => null),
      ]);
      if (signal?.aborted) return;
      setStrategies(st);
      setDeductions(ded);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    load(year, controller.signal);
    return () => controller.abort();
  }, [year]);

  async function handleAnalyze() {
    setAnalyzing(true);
    try {
      await runTaxAnalysis(year);
      const updated = await getTaxStrategies(year);
      setStrategies(updated);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleDismiss(id: number) {
    await dismissStrategy(id);
    setStrategies((prev) => prev.filter((s) => s.id !== id));
  }

  const inputCls = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";
  const btnCls = "bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60";

  return (
    <div className="space-y-8">
      <PageHeader
        title="Tax Strategy"
        subtitle="Optimize your taxes — find deductions, model scenarios, minimize what you pay"
        actions={
          <div className="flex items-center gap-3">
            <select value={year} onChange={(e) => setYear(Number(e.target.value))} className={inputCls}>
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button onClick={handleAnalyze} disabled={analyzing} className={`flex items-center gap-2 ${btnCls}`}>
              {analyzing ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
              {analyzing ? "Analyzing..." : "Run AI Analysis"}
            </button>
          </div>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} /><p className="text-sm">{error}</p>
        </div>
      )}

      {/* AI Strategies */}
      {loading ? (
        <div className="flex items-center gap-3 text-stone-400 justify-center h-32">
          <Loader2 className="animate-spin" size={20} /> Loading...
        </div>
      ) : (
        <>
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-3">
              AI Tax Strategies ({strategies.length})
            </h2>
            {strategies.length === 0 ? (
              <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-8 text-center">
                <DollarSign className="mx-auto text-stone-200 mb-3" size={36} />
                <p className="text-stone-500 text-sm">No strategies yet. Click &quot;Run AI Analysis&quot; to generate personalized tax strategies.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {strategies.map((s) => (
                  <div key={s.id} className="bg-white rounded-xl border border-stone-100 shadow-sm">
                    <div className="flex items-center gap-4 p-5 cursor-pointer" onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
                      <Badge className={priorityColor(s.priority)}>{priorityLabel(s.priority)}</Badge>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-stone-800">{s.title}</p>
                        <p className="text-xs text-stone-500 mt-0.5 capitalize">{s.strategy_type.replace("_", " ")}</p>
                      </div>
                      {(s.estimated_savings_low || s.estimated_savings_high) && (
                        <div className="text-right text-sm">
                          <p className="font-semibold text-green-600">
                            {s.estimated_savings_low != null && s.estimated_savings_high != null
                              ? `${formatCurrency(s.estimated_savings_low, true)}–${formatCurrency(s.estimated_savings_high, true)}`
                              : formatCurrency(s.estimated_savings_high ?? s.estimated_savings_low ?? 0, true)}
                          </p>
                          <p className="text-xs text-stone-400">est. savings</p>
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        {s.deadline && <span className="text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded">{s.deadline}</span>}
                        {expanded === s.id ? <ChevronUp size={16} className="text-stone-400" /> : <ChevronDown size={16} className="text-stone-400" />}
                        <button onClick={(e) => { e.stopPropagation(); handleDismiss(s.id); }} className="p-1 rounded hover:bg-stone-100 text-stone-300 hover:text-stone-500" aria-label="Dismiss strategy"><X size={14} /></button>
                      </div>
                    </div>
                    {expanded === s.id && (
                      <div className="px-5 pb-5 border-t border-stone-50">
                        <p className="text-sm text-stone-700 mt-3 leading-relaxed">{s.description}</p>
                        {s.action_required && (
                          <div className="mt-3 bg-[#DCFCE7] rounded-lg p-3">
                            <p className="text-xs font-semibold text-[#16A34A] mb-1">Action Required</p>
                            <p className="text-sm text-[#16A34A]">{s.action_required}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Deduction Opportunities */}
          {deductions && deductions.opportunities.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400">Deduction Opportunities</h2>
                  <Lightbulb size={14} className="text-amber-400" />
                </div>
                {deductions.estimated_balance_due > 0 && (
                  <span className="text-sm text-red-600 font-medium">Est. balance due: {formatCurrency(deductions.estimated_balance_due)}</span>
                )}
              </div>
              <div className="bg-gradient-to-r from-[#DCFCE7] to-blue-50 rounded-xl border border-[#16A34A]/20 p-4 mb-4">
                <div className="flex items-start gap-3">
                  <TrendingDown size={20} className="text-[#16A34A] mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm text-indigo-900 leading-relaxed">{deductions.summary}</p>
                    <div className="flex gap-4 mt-2 text-xs text-[#16A34A]">
                      <span>Marginal Rate: <strong>{deductions.marginal_rate}%</strong></span>
                      <span>Effective Rate: <strong>{deductions.effective_rate}%</strong></span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                {deductions.opportunities.map((opp) => {
                  const Icon = OPPORTUNITY_ICONS[opp.category] ?? DollarSign;
                  const isExp = expandedOpp === opp.id;
                  return (
                    <div key={opp.id} className="bg-white rounded-xl border border-stone-100 shadow-sm">
                      <div className="flex items-center gap-4 p-4 cursor-pointer hover:bg-stone-50/50 transition-colors rounded-xl" onClick={() => setExpandedOpp(isExp ? null : opp.id)}>
                        <div className="w-9 h-9 rounded-lg bg-[#DCFCE7] flex items-center justify-center flex-shrink-0"><Icon size={18} className="text-[#16A34A]" /></div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-stone-800 text-sm">{opp.title}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={`text-xs px-1.5 py-0.5 rounded border ${URGENCY_COLORS[opp.urgency]}`}>{opp.urgency}</span>
                            {opp.deadline && <span className="text-xs text-stone-400">{opp.deadline}</span>}
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="font-semibold text-green-600 text-sm">{formatCurrency(opp.estimated_tax_savings_low, true)}–{formatCurrency(opp.estimated_tax_savings_high, true)}</p>
                          <p className="text-xs text-stone-400">tax savings</p>
                        </div>
                        {isExp ? <ChevronUp size={16} className="text-stone-400" /> : <ChevronDown size={16} className="text-stone-400" />}
                      </div>
                      {isExp && (
                        <div className="px-4 pb-4 border-t border-stone-50">
                          <p className="text-sm text-stone-700 mt-3 leading-relaxed">{opp.description}</p>
                          {opp.estimated_cost != null && opp.estimated_cost > 0 && (
                            <div className="mt-3 flex gap-4">
                              <div className="bg-stone-50 rounded-lg p-3 flex-1"><p className="text-xs text-stone-500">Estimated Cost</p><p className="font-semibold text-stone-800 mt-0.5">{formatCurrency(opp.estimated_cost)}</p></div>
                              <div className="bg-green-50 rounded-lg p-3 flex-1"><p className="text-xs text-green-600">Tax Savings</p><p className="font-semibold text-green-700 mt-0.5">{formatCurrency(opp.estimated_tax_savings_low)}–{formatCurrency(opp.estimated_tax_savings_high)}</p></div>
                            </div>
                          )}
                          <div className="mt-3 bg-blue-50 rounded-lg p-3">
                            <p className="text-xs font-semibold text-blue-700 mb-1">Bottom Line</p>
                            <p className="text-sm text-blue-800">{opp.net_benefit_explanation}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Strategy Lab */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-3">Strategy Lab</h2>
        <div className="flex bg-stone-100 rounded-lg p-0.5 overflow-x-auto mb-4">
          {STRATEGY_TABS.map((label, i) => (
            <button key={label} onClick={() => setLabTab(i)} className={`px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors ${labTab === i ? "bg-white shadow-sm text-stone-900" : "text-stone-500 hover:text-stone-700"}`}>
              {label}{hasSCorp && i === 1 ? " ●" : ""}
            </button>
          ))}
        </div>

        {labTab === 0 && (
          <LabCard title="Roth Conversion Ladder">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <LabeledInput label="Traditional Balance" value={rothTraditional} onChange={setRothTraditional} />
              <LabeledInput label="Current Income" value={rothCurrentIncome} onChange={setRothCurrentIncome} />
              <div><label className="block text-xs text-stone-500 mb-1">Years (1-20): {rothYears}</label><input type="range" min={1} max={20} value={rothYears} onChange={(e) => setRothYears(Number(e.target.value))} className="w-full" /></div>
              <LabeledInput label="Target Bracket Rate (%)" value={rothTargetBracket} onChange={setRothTargetBracket} />
            </div>
            <CalcButton loading={rothLoading} onClick={async () => { setRothLoading(true); setRothResult(null); try { setRothResult(await modelRothConversion({ traditional_balance: Number(rothTraditional), current_income: Number(rothCurrentIncome), years: rothYears, target_bracket_rate: Number(rothTargetBracket || 0) / 100 })); } catch {} finally { setRothLoading(false); } }} />
            {rothResult && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm"><caption className="sr-only">Roth conversion projection</caption>
                  <thead className="bg-stone-50"><tr>{["Year","Conversion","Tax","Marginal Rate","Remaining Trad.","Roth Balance"].map(h=><th key={h} className={`${h==="Year"?"text-left":"text-right"} px-3 py-2 text-xs font-semibold text-stone-500`}>{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-stone-100">{rothResult.year_by_year.map(r=>(<tr key={r.year}><td className="px-3 py-2 font-medium">{r.year}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.conversion_amount)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.tax_on_conversion)}</td><td className="px-3 py-2 text-right tabular-nums">{(r.marginal_rate*100).toFixed(1)}%</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.remaining_traditional)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.roth_balance)}</td></tr>))}</tbody>
                </table>
                <div className="mt-3 flex gap-4 text-sm"><span>Total Converted: {formatCurrency(rothResult.total_converted)}</span><span>Total Tax: {formatCurrency(rothResult.total_tax_paid)}</span><span>Projected Roth: {formatCurrency(rothResult.projected_roth_at_retirement)}</span></div>
              </div>
            )}
          </LabCard>
        )}

        {labTab === 1 && (
          <LabCard title="S-Corp Election Analysis">
            <div className="grid grid-cols-3 gap-4">
              <LabeledInput label="Gross 1099 Income" value={scorpGross} onChange={setScorpGross} />
              <LabeledInput label="Reasonable Salary" value={scorpSalary} onChange={setScorpSalary} />
              <LabeledInput label="Expenses" value={scorpExpenses} onChange={setScorpExpenses} />
            </div>
            <CalcButton loading={scorpLoading} onClick={async () => { setScorpLoading(true); setScorpResult(null); try { setScorpResult(await modelSCorp({ gross_1099_income: Number(scorpGross), reasonable_salary: Number(scorpSalary), business_expenses: Number(scorpExpenses) })); } catch {} finally { setScorpLoading(false); } }} />
            {scorpResult && (
              <div className="mt-4 grid grid-cols-2 gap-4">
                <ResultBox label="Schedule C Tax" value={formatCurrency(scorpResult.schedule_c_tax)} />
                <ResultBox label="S-Corp Tax" value={formatCurrency(scorpResult.scorp_tax)} />
                <ResultBox label="SE Tax Savings" value={formatCurrency(scorpResult.se_tax_savings)} color="green" />
                <ResultBox label="Total Savings" value={formatCurrency(scorpResult.total_savings)} />
              </div>
            )}
          </LabCard>
        )}

        {labTab === 2 && (
          <LabCard title="Estimated Quarterly Payments">
            <div className="grid grid-cols-3 gap-4">
              <LabeledInput label="Total Underwithholding" value={estUnderwithholding} onChange={setEstUnderwithholding} />
              <LabeledInput label="Prior Year Tax" value={estPriorTax} onChange={setEstPriorTax} />
              <LabeledInput label="Current Withholding" value={estCurrentWithholding} onChange={setEstCurrentWithholding} />
            </div>
            <CalcButton loading={estLoading} onClick={async () => { setEstLoading(true); setEstResult(null); try { setEstResult(await modelEstimatedPayments({ total_underwithholding: Number(estUnderwithholding), prior_year_tax: Number(estPriorTax), current_withholding: Number(estCurrentWithholding) })); } catch {} finally { setEstLoading(false); } }} />
            {estResult && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm"><caption className="sr-only">Quarterly payments</caption>
                  <thead className="bg-stone-50"><tr><th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">Quarter</th><th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">Due Date</th><th className="text-right px-3 py-2 text-xs font-semibold text-stone-500">Amount</th></tr></thead>
                  <tbody className="divide-y divide-stone-100">{estResult.quarterly_payments.map(q=>(<tr key={q.quarter}><td className="px-3 py-2 font-medium">Q{q.quarter}</td><td className="px-3 py-2">{q.due_date}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(q.amount)}</td></tr>))}</tbody>
                </table>
              </div>
            )}
          </LabCard>
        )}

        {labTab === 3 && (
          <LabCard title="DAF Charitable Bunching">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <LabeledInput label="Annual Charitable" value={dafAnnual} onChange={setDafAnnual} />
              <LabeledInput label="Standard Deduction" value={dafStandard} onChange={setDafStandard} />
              <LabeledInput label="Itemized excl. Charitable" value={dafItemizedExcl} onChange={setDafItemizedExcl} />
              <LabeledInput label="Bunch Years" value={String(dafBunchYears)} onChange={(v) => setDafBunchYears(Number(v) || 2)} type="number" />
            </div>
            <CalcButton loading={dafLoading} onClick={async () => { setDafLoading(true); setDafResult(null); try { setDafResult(await modelDAFBunching({ annual_charitable: Number(dafAnnual), standard_deduction: Number(dafStandard), itemized_deductions_excl_charitable: Number(dafItemizedExcl), bunch_years: dafBunchYears })); } catch {} finally { setDafLoading(false); } }} />
            {dafResult && (
              <div className="mt-4 grid grid-cols-3 gap-4">
                <ResultBox label="Annual Tax" value={formatCurrency(dafResult.annual_tax)} />
                <ResultBox label="Bunched Tax" value={formatCurrency(dafResult.bunched_tax)} />
                <ResultBox label="Savings" value={formatCurrency(dafResult.savings)} color="green" />
              </div>
            )}
          </LabCard>
        )}

        {labTab === 4 && (
          <LabCard title="Student Loan Optimizer">
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
              <LabeledInput label="Balance" value={loanBalance} onChange={setLoanBalance} />
              <LabeledInput label="Interest Rate (%)" value={loanRate} onChange={setLoanRate} />
              <LabeledInput label="Monthly Income" value={loanMonthlyIncome} onChange={setLoanMonthlyIncome} />
              <div><label className="block text-xs text-stone-500 mb-1">Filing Status</label><select value={loanFilingStatus} onChange={(e) => setLoanFilingStatus(e.target.value)} className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"><option value="single">Single</option><option value="mfj">MFJ</option><option value="mfs">MFS</option><option value="hh">HoH</option></select></div>
              <div className="flex items-center gap-2"><input type="checkbox" id="pslf" checked={loanPslf} onChange={(e) => setLoanPslf(e.target.checked)} className="rounded border-stone-300" /><label htmlFor="pslf" className="text-sm text-stone-600">PSLF Eligible</label></div>
            </div>
            <CalcButton loading={loanLoading} onClick={async () => { setLoanLoading(true); setLoanResult(null); try { setLoanResult(await modelStudentLoan({ loan_balance: Number(loanBalance), interest_rate: Number(loanRate), monthly_income: Number(loanMonthlyIncome), filing_status: loanFilingStatus, pslf_eligible: loanPslf })); } catch {} finally { setLoanLoading(false); } }} />
            {loanResult && (
              <div className="mt-4 space-y-3">
                <table className="w-full text-sm"><caption className="sr-only">Repayment strategies</caption>
                  <thead className="bg-stone-50"><tr>{["Strategy","Monthly","Total Paid","Interest","Payoff Yrs","Forgiveness"].map(h=><th key={h} className={`${h==="Strategy"?"text-left":"text-right"} px-3 py-2 text-xs font-semibold text-stone-500`}>{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-stone-100">{loanResult.strategies.map((s,i)=>(<tr key={i}><td className="px-3 py-2 font-medium">{s.name}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.monthly_payment)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.total_paid)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.total_interest)}</td><td className="px-3 py-2 text-right tabular-nums">{s.payoff_years}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.forgiveness_amount)}</td></tr>))}</tbody>
                </table>
                {loanResult.recommendation && <p className="text-sm text-stone-700 bg-blue-50 rounded-lg p-3">{loanResult.recommendation}</p>}
              </div>
            )}
          </LabCard>
        )}

        {labTab === 5 && (
          <LabCard title="Multi-Year Tax Projection">
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
              <LabeledInput label="Current Income" value={multiIncome} onChange={setMultiIncome} />
              <LabeledInput label="Growth Rate (%)" value={multiGrowth} onChange={setMultiGrowth} />
              <div><label className="block text-xs text-stone-500 mb-1">Filing Status</label><select value={multiFilingStatus} onChange={(e) => setMultiFilingStatus(e.target.value)} className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"><option value="single">Single</option><option value="mfj">MFJ</option><option value="mfs">MFS</option><option value="hh">HoH</option></select></div>
              <LabeledInput label="State Rate (%)" value={multiStateRate} onChange={setMultiStateRate} />
              <LabeledInput label="Years" value={String(multiYears)} onChange={(v) => setMultiYears(Number(v) || 5)} type="number" />
            </div>
            <CalcButton loading={multiLoading} onClick={async () => { setMultiLoading(true); setMultiResult(null); try { setMultiResult(await modelMultiYearTax({ current_income: Number(multiIncome), income_growth_rate: Number(multiGrowth || 0) / 100, filing_status: multiFilingStatus, state_rate: Number(multiStateRate || 0) / 100, years: multiYears })); } catch {} finally { setMultiLoading(false); } }} />
            {multiResult && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm"><caption className="sr-only">Multi-year projection</caption>
                  <thead className="bg-stone-50"><tr>{["Year","Income","Federal","State","FICA","Total Tax","Effective %"].map(h=><th key={h} className={`${h==="Year"?"text-left":"text-right"} px-3 py-2 text-xs font-semibold text-stone-500`}>{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-stone-100">{multiResult.years.map(r=>(<tr key={r.year}><td className="px-3 py-2 font-medium">{r.year}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.income)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.federal_tax)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.state_tax)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.fica)}</td><td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.total_tax)}</td><td className="px-3 py-2 text-right tabular-nums">{(r.effective_rate*100).toFixed(1)}%</td></tr>))}</tbody>
                </table>
              </div>
            )}
          </LabCard>
        )}
      </div>
    </div>
  );
}

function LabCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5 space-y-4">
      <h3 className="text-sm font-semibold text-stone-700">{title}</h3>
      {children}
    </div>
  );
}

function LabeledInput({ label, value, onChange, type = "number" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label className="block text-xs text-stone-500 mb-1">{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder="0" className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
    </div>
  );
}

function CalcButton({ loading, onClick }: { loading: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} disabled={loading} className="bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60">
      {loading ? <span className="flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Calculating...</span> : "Calculate"}
    </button>
  );
}

function ResultBox({ label, value, color }: { label: string; value: string; color?: "green" }) {
  return (
    <div className={`${color === "green" ? "bg-green-50" : "bg-stone-50"} rounded-lg p-4`}>
      <p className={`text-xs ${color === "green" ? "text-green-600" : "text-stone-500"} mb-1`}>{label}</p>
      <p className={`font-semibold ${color === "green" ? "text-green-700" : "text-stone-800"}`}>{value}</p>
    </div>
  );
}
