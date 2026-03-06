"use client";
import { useCallback, useEffect, useState } from "react";
import { Loader2, AlertCircle, Zap, Shield } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import {
  getHouseholdProfiles, deleteHouseholdProfile, optimizeHousehold,
  getHouseholdUpdates, applyHouseholdUpdates,
} from "@/lib/api";
import type { HouseholdProfile, HouseholdOptimizationResult, HouseholdUpdateSuggestion } from "@/types/api";
import { DataUpdateBanner } from "@/components/ui/DataUpdateBanner";
import StatCard from "@/components/ui/StatCard";
import PageHeader from "@/components/ui/PageHeader";
import {
  ProfileTab,
  BenefitsTab,
  TaxCoordinationTab,
  InsuranceTab,
  WealthTab,
  OptimizationResults,
} from "@/components/household";
import { TABS } from "@/components/household/constants";

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function HouseholdPage() {
  const [profiles, setProfiles] = useState<HouseholdProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("profile");
  const [optimizingId, setOptimizingId] = useState<number | null>(null);
  const [optimizationResult, setOptimizationResult] = useState<HouseholdOptimizationResult | null>(null);
  const [suggestions, setSuggestions] = useState<HouseholdUpdateSuggestion[]>([]);

  const loadProfiles = useCallback(async () => {
    try {
      const p = await getHouseholdProfiles();
      setProfiles(Array.isArray(p) ? p : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfiles();
    getHouseholdUpdates().then((r) => setSuggestions(r.suggestions)).catch(() => {});
  }, [loadProfiles]);

  const primaryProfile = profiles.find((p) => p.is_primary) || profiles[0] || null;

  async function handleDeleteProfile(id: number) {
    try {
      await deleteHouseholdProfile(id);
      if (optimizationResult?.household_id === id) setOptimizationResult(null);
      await loadProfiles();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleOptimize(profile: HouseholdProfile) {
    setOptimizingId(profile.id);
    setError(null);
    try {
      const result = await optimizeHousehold({ household_id: profile.id });
      setOptimizationResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOptimizingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Household Optimization"
        subtitle="Dual-income command center — benefits, taxes, insurance, and wealth"
        actions={
          primaryProfile ? (
            <button
              onClick={() => handleOptimize(primaryProfile)}
              disabled={optimizingId === primaryProfile.id}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm disabled:opacity-60"
            >
              {optimizingId === primaryProfile.id ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
              Full Optimization
            </button>
          ) : null
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {suggestions.length > 0 && (
        <DataUpdateBanner
          suggestions={suggestions}
          onApply={async (updates) => {
            await applyHouseholdUpdates(updates.map((u) => ({ field: u.field, suggested: u.suggested })));
            setSuggestions([]);
            await loadProfiles();
          }}
          onDismiss={() => setSuggestions([])}
        />
      )}

      {optimizationResult && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Annual Savings" value={formatCurrency(optimizationResult.total_annual_savings)} accent size="lg"
            trend={optimizationResult.total_annual_savings >= 0 ? "up" : "down"}
            trendValue={optimizationResult.total_annual_savings >= 0 ? "Identified" : "Review needed"} />
          <StatCard label="Optimal Filing" value={optimizationResult.optimal_filing_status.toUpperCase()} sub="vs alternatives" />
          <StatCard label="MFJ Tax" value={formatCurrency(optimizationResult.mfj_tax)} sub="Married Filing Jointly" />
          <StatCard label="Filing Savings" value={formatCurrency(optimizationResult.filing_savings)}
            trend={optimizationResult.filing_savings >= 0 ? "up" : "down"} />
        </div>
      )}

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-stone-200 overflow-x-auto">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === id
                ? "border-[#16A34A] text-[#16A34A]"
                : "border-transparent text-stone-500 hover:text-stone-700 hover:border-stone-300"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {/* Active tab context banner */}
      {(() => {
        const tab = TABS.find((t) => t.id === activeTab);
        if (!tab) return null;
        const isInsurance = tab.id === "insurance";
        return (
          <div className="bg-stone-50 border border-stone-100 rounded-xl px-4 py-3">
            <p className="text-xs font-semibold text-stone-700">{tab.subtitle}</p>
            <p className="text-xs text-stone-500 mt-0.5">{tab.connects}</p>
            {isInsurance && (
              <a href="/insurance" className="inline-flex items-center gap-1 mt-1.5 text-xs font-medium text-[#16A34A] hover:text-[#15803d]">
                <Shield size={11} /> View personal policies (life, auto, home, umbrella) →
              </a>
            )}
          </div>
        );
      })()}

      {/* Tab content */}
      <div>
        {activeTab === "profile" && (
          <ProfileTab
            profiles={profiles}
            loading={loading}
            error={error}
            onError={setError}
            onReload={loadProfiles}
            onDelete={handleDeleteProfile}
          />
        )}
        {activeTab === "benefits" && <BenefitsTab profile={primaryProfile} />}
        {activeTab === "tax" && <TaxCoordinationTab profile={primaryProfile} />}
        {activeTab === "insurance" && <InsuranceTab profile={primaryProfile} />}
        {activeTab === "wealth" && <WealthTab profile={primaryProfile} />}
      </div>

      {activeTab === "profile" && optimizationResult && (
        <OptimizationResults result={optimizationResult} />
      )}
    </div>
  );
}
