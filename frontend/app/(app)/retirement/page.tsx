"use client";
import { useCallback, useEffect, useState } from "react";
import { Loader2, AlertCircle, Save, MessageCircle } from "lucide-react";
import { calculateRetirement, getRetirementProfiles, createRetirementProfile, getRetirementBudgetSnapshot, getSmartDefaults } from "@/lib/api";
import { getRetirementBudget } from "@/lib/api-retirement";
import type { RetirementResults, RetirementProfile, RetirementProfileInput, DebtPayoff, BudgetSnapshot, SmartDefaults } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import TabBar from "@/components/ui/TabBar";
import { useTabState } from "@/hooks/useTabState";
import SirHenryName from "@/components/ui/SirHenryName";
import RetirementBudgetTable from "@/components/retirement/RetirementBudgetTable";
import InputsTab from "@/components/retirement/InputsTab";
import ProjectionsTab from "@/components/retirement/ProjectionsTab";
import ScenariosTab from "@/components/retirement/ScenariosTab";
import { DEFAULT_INPUTS, TABS } from "@/components/retirement/constants";
import type { RetirementInputState, InputKey } from "@/components/retirement/constants";

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
  const [contextSeeded, setContextSeeded] = useState(false);
  const [autoFilledFields, setAutoFilledFields] = useState<Record<string, string>>({});
  const [retirementBudgetAnnual, setRetirementBudgetAnnual] = useState<number>(0);

  const [activeTab, setTab] = useTabState(TABS, "budget");

  /** Seed defaults from SmartDefaults engine */
  const seedFromContext = useCallback(async () => {
    try {
      const defaults = await getSmartDefaults().catch(() => null as SmartDefaults | null);
      if (!defaults) { setContextSeeded(true); return; }

      const filled: Record<string, string> = {};
      const patch: Partial<RetirementInputState> = {};

      if (defaults.age?.current_age) {
        patch.current_age = defaults.age.current_age;
        filled.current_age = "Date of Birth";
      }
      if (defaults.income?.combined > 0) {
        patch.current_annual_income = defaults.income.combined;
        filled.current_annual_income = defaults.data_sources?.has_w2 ? "W-2" : "Household Profile";
      }
      if (defaults.retirement?.total_savings > 0) {
        patch.current_retirement_savings = defaults.retirement.total_savings;
        filled.current_retirement_savings = "Retirement Accounts";
      }
      if (defaults.retirement?.monthly_contribution > 0) {
        patch.monthly_retirement_contribution = defaults.retirement.monthly_contribution;
        filled.monthly_retirement_contribution = defaults.data_sources?.has_w2 ? "W-2 Box 12" : "Account Data";
      }
      if (defaults.benefits?.match_pct > 0) {
        patch.employer_match_pct = defaults.benefits.match_pct;
        filled.employer_match_pct = "Benefits Package";
      }
      if (defaults.benefits?.match_limit_pct > 0) {
        patch.employer_match_limit_pct = defaults.benefits.match_limit_pct;
        filled.employer_match_limit_pct = "Benefits Package";
      }
      if (defaults.assets?.investment_total > 0) {
        patch.current_other_investments = defaults.assets.investment_total;
        filled.current_other_investments = "Investment Accounts";
      }

      const snapshot = await getRetirementBudgetSnapshot().catch(() => null);
      if (snapshot) setBudgetSnapshot(snapshot);
      if (snapshot && snapshot.annual_expenses > 0) {
        patch.current_annual_expenses = snapshot.annual_expenses;
        filled.current_annual_expenses = "Personal Budget";
      }

      if (defaults.debts?.length > 0) {
        const retDebts = defaults.debts.filter(
          (d: { retirement_relevant?: boolean }) => d.retirement_relevant !== false,
        );
        if (retDebts.length > 0) {
          const currentAge = patch.current_age || inputs.current_age;
          patch.debt_payoffs = retDebts.map(
            (d: { name: string; monthly_payment?: number; balance?: number }) => {
              let payoffAge = 65;
              if (d.monthly_payment && d.monthly_payment > 0 && d.balance) {
                const monthsLeft = Math.ceil(d.balance / d.monthly_payment);
                const yearsLeft = Math.ceil(monthsLeft / 12);
                payoffAge = Math.min(currentAge + yearsLeft, 90);
              }
              return { name: d.name, monthly_payment: d.monthly_payment || 0, payoff_age: payoffAge };
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
        setContextSeeded(true);
      } else {
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
    getRetirementBudget(inputs.retirement_age)
      .then((rb) => {
        if (rb.retirement_annual_total > 0) {
          setRetirementBudgetAnnual(rb.retirement_annual_total);
          setDirty(true);
        }
      })
      .catch(() => {});
  }, []);

  // Debounced calculation
  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const body: RetirementProfileInput = {
          ...inputs,
          desired_annual_retirement_income: inputs.desired_annual_retirement_income || null,
          current_annual_expenses: inputs.current_annual_expenses || null,
          retirement_budget_annual: retirementBudgetAnnual > 0 ? retirementBudgetAnnual : null,
        };
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Retirement Simulator"
        subtitle="Build your retirement budget, track your progress, and see what it takes to retire sooner"
        actions={
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "Am I on track for retirement? What should I change about my savings strategy?" } }))}
              className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
            >
              <MessageCircle size={14} />
              Ask <SirHenryName />
            </button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm disabled:opacity-60">
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

      <TabBar tabs={TABS} activeTab={activeTab} onChange={setTab} variant="underline" />

      {activeTab === "budget" && (
        <RetirementBudgetTable
          retirementAge={inputs.retirement_age}
          onTotalChange={(total) => setRetirementBudgetAnnual(total)}
        />
      )}

      {activeTab === "inputs" && (
        <InputsTab
          inputs={inputs}
          update={update}
          autoFilledFields={autoFilledFields}
          budgetSnapshot={budgetSnapshot}
          retirementBudgetAnnual={retirementBudgetAnnual}
          showAdvanced={showAdvanced}
          setShowAdvanced={setShowAdvanced}
          addDebtPayoff={addDebtPayoff}
          updateDebtPayoff={updateDebtPayoff}
          removeDebtPayoff={removeDebtPayoff}
          onApplyBudgetSnapshot={applyBudgetSnapshot}
          results={results}
        />
      )}

      {activeTab === "projections" && (
        <ProjectionsTab
          results={results}
          inputs={inputs}
          loading={loading}
        />
      )}

      {activeTab === "scenarios" && (
        <ScenariosTab
          inputs={inputs}
          results={results}
          retirementBudgetAnnual={retirementBudgetAnnual}
        />
      )}

      {loading && (
        <div className="fixed bottom-6 right-6 bg-text-primary text-white px-4 py-2 rounded-full text-xs flex items-center gap-2 shadow-lg">
          <Loader2 size={14} className="animate-spin" /> Calculating...
        </div>
      )}
    </div>
  );
}
