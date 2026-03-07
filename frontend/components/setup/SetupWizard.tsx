"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import { ArrowLeft, ArrowRight, Check, Loader2 } from "lucide-react";
import StepAboutYou from "./StepAboutYou";
import StepConnect from "./StepConnect";
import StepBenefitsCoverage from "./StepBenefitsCoverage";
import StepLifeBusiness from "./StepLifeBusiness";
import StepFinish from "./StepFinish";
import { markSetupComplete } from "@/components/AppShell";
import { postSetupComplete } from "@/lib/api-setup";
import type { HouseholdProfile, OtherIncomeSource } from "@/types/household";
import { getHouseholdProfiles } from "@/lib/api-household";
import { getAccounts } from "@/lib/api-accounts";
import { getInsurancePolicies } from "@/lib/api-insurance";
import { getLifeEvents } from "@/lib/api-life-events";
import { getBusinessEntities } from "@/lib/api-entities";
import type { Account } from "@/types/accounts";
import type { InsurancePolicy } from "@/types/insurance";
import type { LifeEvent } from "@/types/life-events";
import type { BusinessEntity } from "@/types/business";
import { OB_CTA, OB_CTA_SECONDARY } from "./styles";

export type SetupStep =
  | "about-you"
  | "connect"
  | "benefits-coverage"
  | "life-business"
  | "finish";

const ALL_STEPS: { key: SetupStep; label: string }[] = [
  { key: "about-you", label: "About You" },
  { key: "connect", label: "Connect" },
  { key: "benefits-coverage", label: "Benefits" },
  { key: "life-business", label: "Life & Biz" },
  { key: "finish", label: "Finish" },
];

export interface SetupData {
  household: HouseholdProfile | null;
  accounts: Account[];
  policies: InsurancePolicy[];
  lifeEvents: LifeEvent[];
  entities: BusinessEntity[];
}

/** Steps call this to register their save function so the wizard can auto-save on Continue. */
export type RegisterSaveFn = (save: (() => Promise<void>) | null) => void;

interface SetupWizardProps {
  onComplete?: () => void;
}

export default function SetupWizard({ onComplete }: SetupWizardProps = {}) {
  const [step, setStep] = useState<SetupStep>("about-you");
  const [data, setData] = useState<SetupData>({
    household: null,
    accounts: [],
    policies: [],
    lifeEvents: [],
    entities: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [plaidSyncing, setPlaidSyncing] = useState(false);

  // Steps register their save function here so the wizard can auto-save on Continue
  const stepSaveRef = useRef<(() => Promise<void>) | null>(null);
  const registerSave: RegisterSaveFn = useCallback((fn) => {
    stepSaveRef.current = fn;
  }, []);

  // Clear registered save when step changes
  useEffect(() => {
    stepSaveRef.current = null;
  }, [step]);

  const loadExistingData = useCallback(async () => {
    try {
      const [profiles, accounts, policies, events, entities] = await Promise.all([
        getHouseholdProfiles().catch(() => []),
        getAccounts().catch(() => []),
        getInsurancePolicies().catch(() => []),
        getLifeEvents().catch(() => []),
        getBusinessEntities().catch(() => []),
      ]);
      const household = (profiles as HouseholdProfile[])[0] ?? null;
      const accts = accounts as Account[];
      const pols = policies as InsurancePolicy[];
      const evts = events as LifeEvent[];
      const ents = entities as BusinessEntity[];

      setData({ household, accounts: accts, policies: pols, lifeEvents: evts, entities: ents });

      // Auto-advance to first incomplete step on re-entry
      const income = (household?.spouse_a_income ?? 0) + (household?.spouse_b_income ?? 0);
      const activeAccounts = accts.filter((a) => a.is_active);
      if (household && income > 0) {
        if (activeAccounts.length > 0) {
          // Household + accounts done — check insurance/benefits
          const activePolicies = pols.filter((p) => p.is_active);
          if (activePolicies.length > 0) {
            // Household, accounts, benefits done
            setStep("life-business");
          } else {
            setStep("benefits-coverage");
          }
        } else {
          setStep("connect");
        }
      }
    } catch {
      // Silent — start fresh
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExistingData();
  }, [loadExistingData]);

  const currentIndex = ALL_STEPS.findIndex((s) => s.key === step);
  const progressPercent = ((currentIndex + 1) / ALL_STEPS.length) * 100;

  async function goNext() {
    // Auto-save the current step if it registered a save function
    if (stepSaveRef.current) {
      setSaving(true);
      try {
        await stepSaveRef.current();
      } catch {
        setSaving(false);
        return;
      }
      setSaving(false);
    }
    if (currentIndex < ALL_STEPS.length - 1) {
      setStep(ALL_STEPS[currentIndex + 1].key);
    }
  }

  function goBack() {
    if (currentIndex > 0) {
      setStep(ALL_STEPS[currentIndex - 1].key);
    }
  }

  function goTo(key: SetupStep) {
    setStep(key);
  }

  function refreshData() {
    loadExistingData();
  }

  async function handleFinish() {
    markSetupComplete();
    try {
      await postSetupComplete();
    } catch {
      // Non-critical — localStorage flag is the primary gate
    }
    if (onComplete) {
      onComplete();
    }
  }

  const hasTransactions = data.accounts.filter((a) => a.is_active).length > 0;
  const isLastStep = step === "finish";

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 bg-background flex items-center justify-center">
        <div className="animate-pulse text-text-muted text-sm">Loading your data...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-background flex flex-col">
      {/* ── Thin progress bar at top ── */}
      <div className="h-1 bg-border w-full flex-shrink-0">
        <div
          className="h-full bg-text-primary transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* ── Step dots / labels ── */}
      <div className="flex items-center justify-center gap-6 pt-5 pb-2 flex-shrink-0">
        {ALL_STEPS.map((s, i) => {
          const isComplete = i < currentIndex;
          const isCurrent = s.key === step;
          return (
            <button
              key={s.key}
              onClick={() => goTo(s.key)}
              className="flex items-center gap-1.5 group"
            >
              <div
                className={`w-2 h-2 rounded-full transition-colors ${
                  isComplete
                    ? "bg-text-primary"
                    : isCurrent
                    ? "bg-text-primary"
                    : "bg-text-muted"
                }`}
              />
              <span
                className={`text-xs transition-colors hidden sm:inline ${
                  isCurrent
                    ? "text-text-primary font-medium"
                    : isComplete
                    ? "text-text-secondary"
                    : "text-text-muted"
                }`}
              >
                {s.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Step content — scrollable area ── */}
      <div className="flex-1 overflow-y-auto pb-28">
        <div className="max-w-3xl mx-auto px-6 pt-6">
          <div
            key={step}
            className="animate-in fade-in slide-in-from-bottom-2 duration-300"
          >
            {step === "about-you" && (
              <StepAboutYou data={data} onRefresh={refreshData} registerSave={registerSave} />
            )}
            {step === "connect" && (
              <StepConnect data={data} onRefresh={refreshData} onSyncStateChange={setPlaidSyncing} />
            )}
            {step === "benefits-coverage" && (
              <StepBenefitsCoverage data={data} onRefresh={refreshData} registerSave={registerSave} />
            )}
            {step === "life-business" && (
              <StepLifeBusiness data={data} onRefresh={refreshData} registerSave={registerSave} />
            )}
            {step === "finish" && (
              <StepFinish data={data} hasTransactions={hasTransactions} onGoTo={goTo} />
            )}
          </div>
        </div>
      </div>

      {/* ── Fixed bottom navigation bar ── */}
      <div className="fixed bottom-0 inset-x-0 bg-card/80 backdrop-blur-sm border-t border-border px-6 py-4 z-10">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <button
            onClick={goBack}
            disabled={currentIndex === 0}
            className={`${OB_CTA_SECONDARY} ${
              currentIndex === 0 ? "opacity-0 pointer-events-none" : ""
            }`}
          >
            <ArrowLeft size={16} />
            Back
          </button>

          <div className="flex items-center gap-3">
            {/* Finish later on optional steps */}
            {(step === "benefits-coverage" || step === "life-business") && (
              <button
                onClick={handleFinish}
                className="text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                Finish later
              </button>
            )}

            {isLastStep ? (
              <button onClick={handleFinish} className={OB_CTA}>
                <Check size={16} />
                Go to Dashboard
              </button>
            ) : (
              <button onClick={goNext} disabled={saving || (step === "connect" && plaidSyncing)} className={OB_CTA}>
                {saving ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    Continue
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
