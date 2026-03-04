"use client";
import { useState, useCallback, useEffect } from "react";
import { ArrowLeft, ArrowRight, Check, Sparkles } from "lucide-react";
import StepHousehold from "./StepHousehold";
import StepAccounts from "./StepAccounts";
import StepBenefits from "./StepBenefits";
import StepInsurance from "./StepInsurance";
import StepLifeEvents from "./StepLifeEvents";
import StepBusiness from "./StepBusiness";
import StepComplete from "./StepComplete";
import type { HouseholdProfile } from "@/types/household";
import { getHouseholdProfiles } from "@/lib/api-household";
import { getAccounts } from "@/lib/api-accounts";
import { getInsurancePolicies } from "@/lib/api-insurance";
import { getLifeEvents } from "@/lib/api-life-events";
import { getBusinessEntities } from "@/lib/api-entities";
import type { Account } from "@/types/accounts";
import type { InsurancePolicy } from "@/types/insurance";
import type { LifeEvent } from "@/types/life-events";
import type { BusinessEntity } from "@/types/business";

export type SetupStep =
  | "household"
  | "accounts"
  | "benefits"
  | "insurance"
  | "life-events"
  | "business"
  | "complete";

const STEPS: { key: SetupStep; label: string }[] = [
  { key: "household", label: "Household" },
  { key: "accounts", label: "Accounts" },
  { key: "benefits", label: "Benefits" },
  { key: "insurance", label: "Insurance" },
  { key: "life-events", label: "Life Events" },
  { key: "business", label: "Business" },
  { key: "complete", label: "Done" },
];

export interface SetupData {
  household: HouseholdProfile | null;
  accounts: Account[];
  policies: InsurancePolicy[];
  lifeEvents: LifeEvent[];
  entities: BusinessEntity[];
}

export default function SetupWizard() {
  const [step, setStep] = useState<SetupStep>("household");
  const [data, setData] = useState<SetupData>({
    household: null,
    accounts: [],
    policies: [],
    lifeEvents: [],
    entities: [],
  });
  const [loading, setLoading] = useState(true);

  const loadExistingData = useCallback(async () => {
    try {
      const [profiles, accounts, policies, events, entities] = await Promise.all([
        getHouseholdProfiles().catch(() => []),
        getAccounts().catch(() => []),
        getInsurancePolicies().catch(() => []),
        getLifeEvents().catch(() => []),
        getBusinessEntities().catch(() => []),
      ]);
      setData({
        household: (profiles as HouseholdProfile[])[0] ?? null,
        accounts: accounts as Account[],
        policies: policies as InsurancePolicy[],
        lifeEvents: events as LifeEvent[],
        entities: entities as BusinessEntity[],
      });
    } catch {
      // Silent — we'll start fresh
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExistingData();
  }, [loadExistingData]);

  const currentIndex = STEPS.findIndex((s) => s.key === step);
  const visibleSteps = STEPS.filter((s) => s.key !== "complete");

  function goNext() {
    if (currentIndex < STEPS.length - 1) setStep(STEPS[currentIndex + 1].key);
  }
  function goBack() {
    if (currentIndex > 0) setStep(STEPS[currentIndex - 1].key);
  }
  function goTo(key: SetupStep) {
    setStep(key);
  }

  function refreshData() {
    loadExistingData();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-stone-400 text-sm">Loading your data...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      {step !== "complete" && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={18} className="text-[#16A34A]" />
            <span className="text-xs font-medium text-[#16A34A] uppercase tracking-wider">
              Setup
            </span>
          </div>
          <h1 className="text-2xl font-bold text-stone-900 font-display tracking-tight">
            Set up your financial profile
          </h1>
          <p className="text-stone-500 text-sm mt-1">
            This helps Sir Henry optimize your taxes, insurance, and wealth strategy.
          </p>
        </div>
      )}

      {/* Progress bar */}
      {step !== "complete" && (
        <div className="mb-8">
          <div className="flex gap-1.5">
            {visibleSteps.map((s, i) => {
              const isComplete = i < currentIndex;
              const isCurrent = s.key === step;
              return (
                <button
                  key={s.key}
                  onClick={() => goTo(s.key)}
                  className="flex-1 group"
                >
                  <div
                    className={`h-1.5 rounded-full transition-colors ${
                      isComplete
                        ? "bg-[#16A34A]"
                        : isCurrent
                        ? "bg-[#16A34A]/50"
                        : "bg-stone-200"
                    }`}
                  />
                  <span
                    className={`text-[10px] mt-1 block transition-colors ${
                      isCurrent
                        ? "text-stone-700 font-medium"
                        : isComplete
                        ? "text-[#16A34A]"
                        : "text-stone-400"
                    }`}
                  >
                    {s.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Step content */}
      <div className="mb-6">
        {step === "household" && (
          <StepHousehold data={data} onRefresh={refreshData} />
        )}
        {step === "accounts" && (
          <StepAccounts data={data} onRefresh={refreshData} />
        )}
        {step === "benefits" && (
          <StepBenefits data={data} onRefresh={refreshData} />
        )}
        {step === "insurance" && (
          <StepInsurance data={data} onRefresh={refreshData} />
        )}
        {step === "life-events" && (
          <StepLifeEvents data={data} onRefresh={refreshData} />
        )}
        {step === "business" && (
          <StepBusiness data={data} onRefresh={refreshData} />
        )}
        {step === "complete" && <StepComplete data={data} onGoTo={goTo} />}
      </div>

      {/* Navigation */}
      {step !== "complete" && (
        <div className="flex items-center justify-between pt-4 border-t border-stone-100">
          <button
            onClick={goBack}
            disabled={currentIndex === 0}
            className="flex items-center gap-1.5 px-4 py-2 text-sm text-stone-500 hover:text-stone-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ArrowLeft size={14} />
            Back
          </button>

          <div className="flex items-center gap-3">
            <button
              onClick={() => goTo("complete")}
              className="text-xs text-stone-400 hover:text-stone-600 transition-colors"
            >
              Skip to finish
            </button>

            <button
              onClick={goNext}
              className="flex items-center gap-1.5 bg-[#16A34A] text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm transition-colors"
            >
              {currentIndex === visibleSteps.length - 1 ? (
                <>
                  <Check size={14} />
                  Finish
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
