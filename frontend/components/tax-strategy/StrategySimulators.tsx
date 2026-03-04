"use client";
import { useEffect, useMemo, useState } from "react";
import { getHouseholdProfiles, getHouseholdBenefits } from "@/lib/api-household";
import { getBusinessEntities } from "@/lib/api-entities";
import { getTaxStrategyProfile } from "@/lib/api-tax";
import type { HouseholdProfile, BenefitPackageType } from "@/types/household";
import type { TaxStrategyProfile } from "@/types/api";
import RothConversionSim from "./simulators/RothConversionSim";
import SCorpAnalysisSim from "./simulators/SCorpAnalysisSim";
import EstimatedPaymentsSim from "./simulators/EstimatedPaymentsSim";
import DAFBunchingSim from "./simulators/DAFBunchingSim";
import StudentLoanSim from "./simulators/StudentLoanSim";
import MultiYearProjectionSim from "./simulators/MultiYearProjectionSim";
import TaxLossHarvestSim from "./simulators/TaxLossHarvestSim";
import MegaBackdoorRothSim from "./simulators/MegaBackdoorRothSim";
import DefinedBenefitSim from "./simulators/DefinedBenefitSim";
import RealEstateSTRSim from "./simulators/RealEstateSTRSim";
import Section179Sim from "./simulators/Section179Sim";
import EquityCompTaxSim from "./simulators/EquityCompTaxSim";
import HSAMaxSim from "./simulators/HSAMaxSim";
import FilingStatusSim from "./simulators/FilingStatusSim";
import QBIDeductionSim from "./simulators/QBIDeductionSim";
import StateComparisonSim from "./simulators/StateComparisonSim";

const ALL_TABS = [
  { key: "equity-comp", label: "Equity Comp Tax" },
  { key: "roth-conversion", label: "Reduce Retirement Tax" },
  { key: "scorp-analysis", label: "Reduce Self-Employment Tax" },
  { key: "hsa-max", label: "Health Savings (HSA)" },
  { key: "filing-status", label: "Joint vs Separate Filing" },
  { key: "section-179", label: "Equipment Tax Deduction" },
  { key: "tax-loss-harvest", label: "Harvest Tax Losses" },
  { key: "mega-backdoor", label: "Mega Backdoor Roth" },
  { key: "real-estate-str", label: "Short-Term Rental" },
  { key: "defined-benefit", label: "Defined Benefit Plan" },
  { key: "daf-bunching", label: "Optimize Charitable Giving" },
  { key: "estimated-payments", label: "Plan Quarterly Payments" },
  { key: "qbi-deduction", label: "Business Income Deduction" },
  { key: "state-comparison", label: "State Tax Comparison" },
  { key: "student-loans", label: "Student Loan Strategy" },
  { key: "multi-year", label: "Project Future Taxes" },
] as const;

type TabKey = (typeof ALL_TABS)[number]["key"];

/** Compute recommended simulator keys from interview profile */
function computeRecommended(profile: TaxStrategyProfile | null, hasSCorp: boolean): Set<string> {
  const rec = new Set<string>();
  if (!profile) return rec;

  // Equity comp → equity-comp sim + harvest
  if (profile.has_equity_comp) {
    rec.add("equity-comp");
    rec.add("tax-loss-harvest");
  }
  // Traditional IRA → Roth conversion
  if (profile.has_traditional_ira) {
    rec.add("roth-conversion");
  }
  // Self-employed or mixed → business-related sims
  if (profile.income_type === "self_employed" || profile.income_type === "mixed") {
    rec.add("scorp-analysis");
    rec.add("defined-benefit");
    rec.add("section-179");
    rec.add("estimated-payments");
    rec.add("qbi-deduction");
  }
  // After-tax 401k available → mega backdoor
  if (profile.employer_allows_after_tax_401k) {
    rec.add("mega-backdoor");
  }
  // Rental property or interested in real estate
  if (profile.has_rental_property || profile.open_to_real_estate) {
    rec.add("real-estate-str");
  }
  // Student loans → student loan sim + filing status (MFS + IDR strategy)
  if (profile.has_student_loans) {
    rec.add("student-loans");
    rec.add("filing-status");
  }
  // HSA is recommended for everyone (universal benefit)
  rec.add("hsa-max");
  // Investment accounts → tax-loss harvesting
  if (profile.has_investment_accounts) {
    rec.add("tax-loss-harvest");
  }
  // Multi-state → state comparison
  if (profile.multi_state) {
    rec.add("state-comparison");
  }
  // S-Corp entity detected
  if (hasSCorp) {
    rec.add("scorp-analysis");
  }
  return rec;
}

export default function StrategySimulators({ activeTab }: { activeTab?: string }) {
  const [tab, setTab] = useState<TabKey>((activeTab as TabKey) || "roth-conversion");
  const [hasSCorp, setHasSCorp] = useState(false);
  const [interviewProfile, setInterviewProfile] = useState<TaxStrategyProfile | null>(null);

  // Pre-populated defaults from household data
  const [defaults, setDefaults] = useState({
    income: "", monthlyIncome: "", filingStatus: "mfj", traditionalBalance: "",
  });

  useEffect(() => {
    if (activeTab && ALL_TABS.some((t) => t.key === activeTab)) {
      setTab(activeTab as TabKey);
    }
  }, [activeTab]);

  // Load household context + interview profile
  useEffect(() => {
    Promise.all([
      getHouseholdProfiles().catch(() => [] as HouseholdProfile[]),
      getBusinessEntities().catch(() => []),
      getTaxStrategyProfile().catch(() => ({ profile: null })),
    ]).then(([profiles, entities, interviewRes]) => {
      const primary = profiles.find((p) => p.is_primary) ?? profiles[0] ?? null;
      if (primary) {
        const combined = String(Math.round(primary.combined_income || 0));
        const monthlyIncome = String(Math.round((primary.combined_income || 0) / 12));
        const filing = primary.filing_status || "mfj";

        setDefaults((prev) => ({ ...prev, income: combined, monthlyIncome, filingStatus: filing }));

        getHouseholdBenefits(primary.id).catch(() => [] as BenefitPackageType[]).then((benefits) => {
          const totalContributions = benefits.reduce((sum, b) => sum + (b.annual_401k_contribution ?? 0), 0);
          if (totalContributions > 0) {
            setDefaults((prev) => ({ ...prev, traditionalBalance: String(Math.round(totalContributions)) }));
          }
        });
      }

      const scorp = entities.find((e) => e.entity_type === "s_corp" || e.tax_treatment === "s_corp");
      if (scorp) {
        setHasSCorp(true);
        if (!activeTab) setTab("scorp-analysis");
      }

      setInterviewProfile(interviewRes.profile);
    }).catch(() => {});
  }, [activeTab]);

  const recommended = useMemo(
    () => computeRecommended(interviewProfile, hasSCorp),
    [interviewProfile, hasSCorp],
  );

  // Sort tabs: recommended first (preserve relative order), then the rest
  const sortedTabs = useMemo(() => {
    if (recommended.size === 0) return ALL_TABS;
    const recTabs = ALL_TABS.filter((t) => recommended.has(t.key));
    const otherTabs = ALL_TABS.filter((t) => !recommended.has(t.key));
    return [...recTabs, ...otherTabs];
  }, [recommended]);

  return (
    <div id="strategy-simulators">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-3">
        Strategy Simulators
        {recommended.size > 0 && (
          <span className="ml-2 text-[10px] font-normal normal-case tracking-normal text-stone-400">
            · <span className="text-[#16A34A]">●</span> recommended for you
          </span>
        )}
      </h2>
      <div className="flex bg-stone-100 rounded-lg p-0.5 overflow-x-auto mb-4">
        {sortedTabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors ${
              tab === t.key ? "bg-white shadow-sm text-stone-900" : "text-stone-500 hover:text-stone-700"
            }`}
          >
            {recommended.has(t.key) && <span className="text-[#16A34A] mr-1">●</span>}
            {t.label}
          </button>
        ))}
      </div>

      {tab === "equity-comp" && <EquityCompTaxSim />}
      {tab === "hsa-max" && <HSAMaxSim />}
      {tab === "filing-status" && <FilingStatusSim />}
      {tab === "roth-conversion" && (
        <RothConversionSim defaultIncome={defaults.income} defaultTraditional={defaults.traditionalBalance} />
      )}
      {tab === "scorp-analysis" && <SCorpAnalysisSim />}
      {tab === "section-179" && <Section179Sim />}
      {tab === "tax-loss-harvest" && <TaxLossHarvestSim />}
      {tab === "mega-backdoor" && <MegaBackdoorRothSim />}
      {tab === "real-estate-str" && <RealEstateSTRSim />}
      {tab === "defined-benefit" && <DefinedBenefitSim />}
      {tab === "daf-bunching" && <DAFBunchingSim />}
      {tab === "estimated-payments" && <EstimatedPaymentsSim />}
      {tab === "qbi-deduction" && <QBIDeductionSim />}
      {tab === "state-comparison" && <StateComparisonSim />}
      {tab === "student-loans" && (
        <StudentLoanSim defaultMonthlyIncome={defaults.monthlyIncome} defaultFilingStatus={defaults.filingStatus} />
      )}
      {tab === "multi-year" && (
        <MultiYearProjectionSim defaultIncome={defaults.income} defaultFilingStatus={defaults.filingStatus} />
      )}
    </div>
  );
}
