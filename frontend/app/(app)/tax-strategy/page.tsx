"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { AlertCircle, ClipboardList, Info, Loader2, Sparkles } from "lucide-react";
import { dismissStrategy, getTaxDeductionOpportunities, getTaxStrategies, getTaxStrategyProfile, runTaxAnalysis } from "@/lib/api";
import type { TaxDeductionInsights, TaxStrategy } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import { StrategyDashboard, DeductionOpportunities, StrategySimulators } from "@/components/tax-strategy";
import TaxStrategyInterview from "@/components/tax-strategy/TaxStrategyInterview";
import SirHenryName from "@/components/ui/SirHenryName";

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2];

const inputCls = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";
const btnCls = "bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60";

export default function TaxStrategyPage() {
  const [year, setYear] = useState(currentYear - 1);
  const [strategies, setStrategies] = useState<TaxStrategy[]>([]);
  const [deductions, setDeductions] = useState<TaxDeductionInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [simulatorTab, setSimulatorTab] = useState<string | undefined>(undefined);
  const [showInterview, setShowInterview] = useState(false);
  const [hasInterviewProfile, setHasInterviewProfile] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      getTaxStrategies(year).catch(() => []),
      getTaxDeductionOpportunities(year).catch(() => null),
      getTaxStrategyProfile().catch(() => ({ profile: null })),
    ]).then(([st, ded, interviewRes]) => {
      if (controller.signal.aborted) return;
      setStrategies(st);
      setDeductions(ded);
      setHasInterviewProfile(interviewRes.profile != null);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [year]);

  async function handleAnalyze() {
    setAnalyzing(true);
    try {
      await runTaxAnalysis(year);
      setStrategies(await getTaxStrategies(year));
    } finally {
      setAnalyzing(false);
    }
  }

  const handleInterviewComplete = useCallback(async () => {
    setShowInterview(false);
    setHasInterviewProfile(true);
    setStrategies(await getTaxStrategies(year));
  }, [year]);

  const handleDismiss = useCallback(async (id: number) => {
    await dismissStrategy(id);
    setStrategies((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const handleOpenSimulator = useCallback((key: string) => {
    setSimulatorTab(key);
    document.getElementById("strategy-simulators")?.scrollIntoView({ behavior: "smooth" });
  }, []);

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
            {hasInterviewProfile !== false && (
              <button onClick={() => setShowInterview(true)} className="flex items-center gap-2 whitespace-nowrap text-sm font-medium text-[#16A34A] border border-[#16A34A]/30 px-3 py-2 rounded-lg hover:bg-[#DCFCE7]/30">
                <ClipboardList size={15} />
                {hasInterviewProfile ? "Refine" : "Personalize"}
              </button>
            )}
            <button onClick={handleAnalyze} disabled={analyzing} className={`flex items-center gap-2 whitespace-nowrap ${btnCls}`}>
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

      {/* Interview CTA banner (shown if no profile yet and not currently in interview) */}
      {hasInterviewProfile === false && !showInterview && (
        <div className="bg-gradient-to-r from-[#DCFCE7] to-emerald-50 rounded-xl border border-[#16A34A]/20 px-5 py-4 flex items-center gap-4">
          <ClipboardList size={20} className="text-[#16A34A] flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-stone-800">Get personalized tax strategies</p>
            <p className="text-xs text-stone-500 mt-0.5">Answer 5 quick questions and <SirHenryName /> will generate strategies tailored to your situation.</p>
          </div>
          <button onClick={() => setShowInterview(true)} className={`whitespace-nowrap ${btnCls}`}>
            Start Interview
          </button>
        </div>
      )}

      {/* Interview wizard */}
      {showInterview && (
        <TaxStrategyInterview year={year} onComplete={handleInterviewComplete} />
      )}

      {deductions?.data_source === "setup_profile" && (
        <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-3 flex items-center gap-3">
          <Info size={16} className="text-blue-500 flex-shrink-0" />
          <p className="text-sm text-blue-700">
            Strategies based on your household profile.{" "}
            <Link href="/import" className="font-medium underline">Import tax documents</Link> for more precise recommendations.
          </p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-3 text-stone-400 justify-center h-32">
          <Loader2 className="animate-spin" size={20} /> Loading...
        </div>
      ) : (
        <>
          {deductions && <DeductionOpportunities deductions={deductions} onOpenSimulator={handleOpenSimulator} />}
          <StrategyDashboard strategies={strategies} onDismiss={handleDismiss} onOpenSimulator={handleOpenSimulator} />
        </>
      )}

      <StrategySimulators activeTab={simulatorTab} />
    </div>
  );
}
