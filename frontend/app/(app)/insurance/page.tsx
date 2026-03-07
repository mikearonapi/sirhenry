"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ShieldCheck, Plus, Trash2,
  AlertCircle, Loader2, AlertTriangle, CheckCircle2, Clock, Pencil, X, UserPlus,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import StatCard from "@/components/ui/StatCard";
import PageHeader from "@/components/ui/PageHeader";
import {
  getInsurancePolicies, createInsurancePolicy, updateInsurancePolicy, deleteInsurancePolicy,
  getInsuranceGapAnalysis, getHouseholdProfiles,
} from "@/lib/api";
import { getManualAssets } from "@/lib/api-assets";
import type { InsurancePolicy, InsurancePolicyIn, InsuranceGapAnalysis, HouseholdProfile } from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const POLICY_TYPES = [
  { value: "health", label: "Health", icon: "🏥", color: "bg-red-50 text-red-700 border-red-100" },
  { value: "life", label: "Life", icon: "❤️", color: "bg-pink-50 text-pink-700 border-pink-100" },
  { value: "disability", label: "Disability", icon: "🦺", color: "bg-orange-50 text-orange-700 border-orange-100" },
  { value: "auto", label: "Auto", icon: "🚗", color: "bg-blue-50 text-blue-700 border-blue-100" },
  { value: "home", label: "Home", icon: "🏠", color: "bg-green-50 text-green-700 border-green-100" },
  { value: "umbrella", label: "Umbrella", icon: "☂️", color: "bg-indigo-50 text-indigo-700 border-indigo-100" },
  { value: "vision", label: "Vision", icon: "👁️", color: "bg-cyan-50 text-cyan-700 border-cyan-100" },
  { value: "dental", label: "Dental", icon: "🦷", color: "bg-teal-50 text-teal-700 border-teal-100" },
  { value: "ltc", label: "Long-Term Care", icon: "🏨", color: "bg-purple-50 text-purple-700 border-purple-100" },
  { value: "pet", label: "Pet", icon: "🐾", color: "bg-amber-50 text-amber-700 border-amber-100" },
  { value: "other", label: "Other", icon: "📋", color: "bg-surface text-text-secondary border-border" },
];

function getPolicyConfig(type: string) {
  return POLICY_TYPES.find((p) => p.value === type) || POLICY_TYPES[POLICY_TYPES.length - 1];
}

const SEVERITY_CONFIG = {
  high: { label: "High Priority", color: "text-red-600", bg: "bg-red-50 border-red-100", icon: AlertTriangle },
  medium: { label: "Review Needed", color: "text-amber-600", bg: "bg-amber-50 border-amber-100", icon: AlertCircle },
  low: { label: "OK", color: "text-green-600", bg: "bg-green-50 border-green-100", icon: CheckCircle2 },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function InsurancePage() {
  const [policies, setPolicies] = useState<InsurancePolicy[]>([]);
  const [profiles, setProfiles] = useState<HouseholdProfile[]>([]);
  const [gapAnalysis, setGapAnalysis] = useState<InsuranceGapAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [gapLoading, setGapLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [filterType, setFilterType] = useState<string>("");
  const [showInactive, setShowInactive] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<InsurancePolicy | null>(null);

  // Form state
  const [fType, setFType] = useState<InsurancePolicyIn["policy_type"]>("health");
  const [fProvider, setFProvider] = useState("");
  const [fPolicyNumber, setFPolicyNumber] = useState("");
  const [fOwner, setFOwner] = useState<"a" | "b" | "">("");
  const [fCoverage, setFCoverage] = useState("");
  const [fDeductible, setFDeductible] = useState("");
  const [fOopMax, setFOopMax] = useState("");
  const [fAnnualPremium, setFAnnualPremium] = useState("");
  const [fRenewalDate, setFRenewalDate] = useState("");
  const [fEmployerProvided, setFEmployerProvided] = useState(false);
  const [fNotes, setFNotes] = useState("");
  const [fBeneficiaries, setFBeneficiaries] = useState<{ name: string; relationship: string; percentage: string }[]>([]);

  const loadData = useCallback(async () => {
    try {
      const [p, prof] = await Promise.all([
        getInsurancePolicies({ is_active: showInactive ? undefined : true }),
        getHouseholdProfiles(),
      ]);
      setPolicies(Array.isArray(p) ? p : []);
      setProfiles(Array.isArray(prof) ? prof : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function runGapAnalysis() {
    setGapLoading(true);
    setError(null);
    try {
      const primary = profiles.find((p) => p.is_primary) || profiles[0];
      const assets = await getManualAssets().catch(() => [] as ManualAsset[]);
      const totalAssets = assets
        .filter((a) => !a.is_liability && a.is_active !== false)
        .reduce((sum, a) => sum + (a.current_value ?? 0), 0);
      const totalDebt = assets
        .filter((a) => a.is_liability && a.is_active !== false)
        .reduce((sum, a) => sum + (a.current_value ?? 0), 0);
      const netWorth = totalAssets - totalDebt;
      const body = primary
        ? {
            household_id: primary.id,
            spouse_a_income: primary.spouse_a_income,
            spouse_b_income: primary.spouse_b_income,
            net_worth: Math.max(0, netWorth),
            total_debt: totalDebt,
          }
        : {};
      const result = await getInsuranceGapAnalysis(body);
      setGapAnalysis(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGapLoading(false);
    }
  }

  function resetPolicyForm() {
    setFType("health");
    setFProvider("");
    setFPolicyNumber("");
    setFOwner("");
    setFCoverage("");
    setFDeductible("");
    setFOopMax("");
    setFAnnualPremium("");
    setFRenewalDate("");
    setFEmployerProvided(false);
    setFNotes("");
    setFBeneficiaries([]);
    setEditingPolicy(null);
    setShowForm(false);
  }

  function openEditPolicy(policy: InsurancePolicy) {
    setEditingPolicy(policy);
    setFType(policy.policy_type);
    setFProvider(policy.provider || "");
    setFPolicyNumber(policy.policy_number || "");
    setFOwner((policy.owner_spouse as "a" | "b") || "");
    setFCoverage(policy.coverage_amount != null ? String(policy.coverage_amount) : "");
    setFDeductible(policy.deductible != null ? String(policy.deductible) : "");
    setFOopMax(policy.oop_max != null ? String(policy.oop_max) : "");
    setFAnnualPremium(policy.annual_premium != null ? String(policy.annual_premium) : "");
    setFRenewalDate(policy.renewal_date || "");
    setFEmployerProvided(policy.employer_provided);
    setFNotes(policy.notes || "");
    try {
      const bens = policy.beneficiaries_json ? JSON.parse(policy.beneficiaries_json) : [];
      setFBeneficiaries(Array.isArray(bens) ? bens : []);
    } catch {
      setFBeneficiaries([]);
    }
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function buildBody(isActive: boolean): InsurancePolicyIn {
    return {
      policy_type: fType,
      provider: fProvider || null,
      policy_number: fPolicyNumber || null,
      owner_spouse: (fOwner as "a" | "b") || null,
      coverage_amount: fCoverage ? Number(fCoverage) : null,
      deductible: fDeductible ? Number(fDeductible) : null,
      oop_max: fOopMax ? Number(fOopMax) : null,
      annual_premium: fAnnualPremium ? Number(fAnnualPremium) : null,
      renewal_date: fRenewalDate || null,
      employer_provided: fEmployerProvided,
      is_active: isActive,
      notes: fNotes || null,
      household_id: profiles.find((p) => p.is_primary)?.id || profiles[0]?.id || null,
      beneficiaries_json: fBeneficiaries.length > 0
        ? JSON.stringify(fBeneficiaries.filter((b) => b.name))
        : null,
    };
  }

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      await createInsurancePolicy(buildBody(true));
      await loadData();
      resetPolicyForm();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate() {
    if (!editingPolicy) return;
    setSaving(true);
    setError(null);
    try {
      await updateInsurancePolicy(editingPolicy.id, buildBody(editingPolicy.is_active));
      await loadData();
      resetPolicyForm();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this insurance policy?")) return;
    try {
      await deleteInsurancePolicy(id);
      await loadData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const filtered = filterType ? policies.filter((p) => p.policy_type === filterType) : policies;
  const totalAnnualPremium = filtered.reduce((s, p) => s + (p.annual_premium || 0), 0);
  const byType = policies.reduce<Record<string, number>>((acc, p) => {
    acc[p.policy_type] = (acc[p.policy_type] || 0) + 1;
    return acc;
  }, {});

  // Policies renewing in next 60 days
  const today = new Date();
  const renewingSoon = policies.filter((p) => {
    if (!p.renewal_date) return false;
    const rd = new Date(p.renewal_date);
    const diff = (rd.getTime() - today.getTime()) / (1000 * 60 * 60 * 24);
    return diff >= 0 && diff <= 60;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Insurance & Benefits Hub"
        subtitle="Track all insurance policies, coverage gaps, and renewal deadlines"
        actions={
          <button
            onClick={() => { if (showForm) resetPolicyForm(); else setShowForm(true); }}
            className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm"
          >
            {showForm ? <X size={14} /> : <Plus size={14} />}
            {showForm ? "Cancel" : "Add Policy"}
          </button>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {/* Summary stats */}
      {!loading && policies.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Active Policies" value={String(policies.length)} sub="across all types" />
          <StatCard label="Annual Premiums" value={formatCurrency(totalAnnualPremium)} sub={`${formatCurrency(totalAnnualPremium / 12)}/mo`} />
          <StatCard
            label="Renewing Soon"
            value={String(renewingSoon.length)}
            sub="within 60 days"
            trend={renewingSoon.length > 0 ? "down" : undefined}
            trendValue={renewingSoon.length > 0 ? "Action needed" : undefined}
          />
          <StatCard label="Policy Types" value={String(Object.keys(byType).length)} sub="of 11 types covered" />
        </div>
      )}

      {/* Renewing soon alert */}
      {renewingSoon.length > 0 && (
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Clock size={16} className="text-amber-600" />
            <h4 className="text-sm font-semibold text-amber-800">Renewing Within 60 Days</h4>
          </div>
          <div className="space-y-1">
            {renewingSoon.map((p) => {
              const rd = new Date(p.renewal_date!);
              const days = Math.round((rd.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
              return (
                <p key={p.id} className="text-xs text-amber-700">
                  <span className="font-medium">{getPolicyConfig(p.policy_type).icon} {p.policy_type.charAt(0).toUpperCase() + p.policy_type.slice(1)}</span>
                  {p.provider ? ` — ${p.provider}` : ""}: renews {rd.toLocaleDateString("en-US", { month: "short", day: "numeric" })} ({days} days)
                </p>
              );
            })}
          </div>
        </div>
      )}

      {/* Coverage gap analysis */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Coverage Gap Analysis</h3>
            <p className="text-xs text-text-secondary mt-0.5">Compare your coverage against recommended levels</p>
          </div>
          <button
            onClick={runGapAnalysis}
            disabled={gapLoading}
            className="flex items-center gap-2 bg-text-primary text-white px-3 py-2 rounded-lg text-xs font-medium hover:bg-text-secondary disabled:opacity-60"
          >
            {gapLoading ? <Loader2 size={13} className="animate-spin" /> : <ShieldCheck size={13} />}
            Run Analysis
          </button>
        </div>

        {gapAnalysis ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div className="text-center p-3 bg-surface rounded-xl">
                <p className="text-xl font-bold text-text-primary">{gapAnalysis.total_policies}</p>
                <p className="text-xs text-text-secondary">Active Policies</p>
              </div>
              <div className="text-center p-3 bg-surface rounded-xl">
                <p className="text-xl font-bold text-text-primary">{formatCurrency(gapAnalysis.total_monthly_premium)}</p>
                <p className="text-xs text-text-secondary">Monthly Cost</p>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-xl">
                <p className="text-xl font-bold text-red-600">{gapAnalysis.high_severity_gaps}</p>
                <p className="text-xs text-red-500">Critical Gaps</p>
              </div>
              <div className="text-center p-3 bg-amber-50 rounded-xl">
                <p className="text-xl font-bold text-amber-600">{gapAnalysis.medium_severity_gaps}</p>
                <p className="text-xs text-amber-500">Review Needed</p>
              </div>
            </div>

            {gapAnalysis.gaps.map((gap) => {
              const cfg = SEVERITY_CONFIG[gap.severity];
              const Icon = cfg.icon;
              return (
                <div key={gap.type} className={`p-4 rounded-xl border ${cfg.bg}`}>
                  <div className="flex items-start gap-3">
                    <Icon size={16} className={`mt-0.5 shrink-0 ${cfg.color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-text-primary">{gap.label}</p>
                        <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                      </div>
                      <p className="text-xs text-text-secondary mt-1">{gap.note}</p>
                      {gap.gap > 0 && (
                        <div className="mt-2 flex items-center gap-4 text-xs">
                          <span className="text-text-secondary">Current: <span className="font-medium text-text-secondary">{formatCurrency(gap.current_coverage)}</span></span>
                          <span className="text-text-secondary">Recommended: <span className="font-medium text-text-secondary">{formatCurrency(gap.recommended_coverage)}</span></span>
                          <span className="text-text-secondary">Gap: <span className="font-medium text-red-600">{formatCurrency(gap.gap)}</span></span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-text-muted text-center py-4">Run the analysis to see coverage gaps and recommendations.</p>
        )}
      </Card>

      {/* Add / Edit policy form */}
      {showForm && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">
            {editingPolicy ? "Edit Insurance Policy" : "Add Insurance Policy"}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-text-secondary">Policy Type</label>
              <select
                value={fType}
                onChange={(e) => setFType(e.target.value as InsurancePolicyIn["policy_type"])}
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              >
                {POLICY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-text-secondary">Provider / Insurer</label>
              <input
                type="text"
                value={fProvider}
                onChange={(e) => setFProvider(e.target.value)}
                placeholder="e.g. Aetna, State Farm"
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="text-xs text-text-secondary">Policy Number</label>
              <input
                type="text"
                value={fPolicyNumber}
                onChange={(e) => setFPolicyNumber(e.target.value)}
                placeholder="Optional"
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="text-xs text-text-secondary">Policy Owner</label>
              <select
                value={fOwner}
                onChange={(e) => setFOwner(e.target.value as "a" | "b" | "")}
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              >
                <option value="">Household / Joint</option>
                <option value="a">Spouse A</option>
                <option value="b">Spouse B</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-text-secondary">Coverage Amount</label>
              <input
                type="number"
                value={fCoverage}
                onChange={(e) => setFCoverage(e.target.value)}
                placeholder="e.g. 500000"
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="text-xs text-text-secondary">Annual Premium</label>
              <input
                type="number"
                value={fAnnualPremium}
                onChange={(e) => setFAnnualPremium(e.target.value)}
                placeholder="e.g. 1200"
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="text-xs text-text-secondary">Deductible</label>
              <input
                type="number"
                value={fDeductible}
                onChange={(e) => setFDeductible(e.target.value)}
                placeholder="Optional"
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="text-xs text-text-secondary">OOP Max</label>
              <input
                type="number"
                value={fOopMax}
                onChange={(e) => setFOopMax(e.target.value)}
                placeholder="Optional"
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="text-xs text-text-secondary">Renewal Date</label>
              <input
                type="date"
                value={fRenewalDate}
                onChange={(e) => setFRenewalDate(e.target.value)}
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div className="flex items-center gap-3 mt-1">
              <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
                <input
                  type="checkbox"
                  checked={fEmployerProvided}
                  onChange={(e) => setFEmployerProvided(e.target.checked)}
                  className="rounded border-border"
                />
                Employer-provided
              </label>
            </div>
          </div>
          <div className="mt-4">
            <label className="text-xs text-text-secondary">Notes</label>
            <textarea
              value={fNotes}
              onChange={(e) => setFNotes(e.target.value)}
              rows={2}
              className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20"
            />
          </div>

          {/* Beneficiaries — relevant for life, disability, LTC policies */}
          {(fType === "life" || fType === "disability" || fType === "ltc") && (
            <div className="mt-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-text-secondary">Beneficiaries</p>
                <button
                  type="button"
                  onClick={() => setFBeneficiaries((prev) => [...prev, { name: "", relationship: "", percentage: "" }])}
                  className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover"
                >
                  <UserPlus size={12} /> Add Beneficiary
                </button>
              </div>
              {fBeneficiaries.length === 0 && (
                <p className="text-xs text-text-muted italic">No beneficiaries added yet.</p>
              )}
              <div className="space-y-2">
                {fBeneficiaries.map((b, i) => (
                  <div key={i} className="grid grid-cols-3 gap-2 items-center">
                    <input
                      type="text"
                      value={b.name}
                      onChange={(e) => setFBeneficiaries((prev) => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                      placeholder="Full name"
                      className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20"
                    />
                    <input
                      type="text"
                      value={b.relationship}
                      onChange={(e) => setFBeneficiaries((prev) => prev.map((x, j) => j === i ? { ...x, relationship: e.target.value } : x))}
                      placeholder="Relationship"
                      className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20"
                    />
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={b.percentage}
                        onChange={(e) => setFBeneficiaries((prev) => prev.map((x, j) => j === i ? { ...x, percentage: e.target.value } : x))}
                        placeholder="% share"
                        className="flex-1 text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20"
                      />
                      <button
                        type="button"
                        onClick={() => setFBeneficiaries((prev) => prev.filter((_, j) => j !== i))}
                        className="text-text-muted hover:text-red-500"
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={editingPolicy ? handleUpdate : handleCreate}
              disabled={saving || !fType}
              className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              {editingPolicy ? "Update Policy" : "Save Policy"}
            </button>
            <button onClick={resetPolicyForm} className="text-sm text-text-secondary hover:text-text-secondary">
              Cancel
            </button>
          </div>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="text-sm border border-border rounded-lg px-3 py-2 bg-card focus:outline-none focus:ring-2 focus:ring-accent/20"
        >
          <option value="">All Types</option>
          {POLICY_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-border"
          />
          Show inactive
        </label>
        <span className="ml-auto text-xs text-text-muted">{filtered.length} policies</span>
      </div>

      {/* Policy list */}
      {loading ? (
        <div className="flex items-center gap-2 text-text-secondary text-sm py-8">
          <Loader2 size={16} className="animate-spin" />
          Loading policies...
        </div>
      ) : filtered.length === 0 ? (
        <Card padding="lg">
          <div className="text-center py-8">
            <ShieldCheck size={32} className="mx-auto text-text-muted mb-3" />
            <p className="text-sm text-text-secondary">No insurance policies added yet.</p>
            <p className="text-xs text-text-muted mt-1">
              Track health, life, disability, auto, home, and umbrella policies in one place.
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((policy) => {
            const cfg = getPolicyConfig(policy.policy_type);
            const rd = policy.renewal_date ? new Date(policy.renewal_date) : null;
            const daysUntil = rd ? Math.round((rd.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)) : null;
            const renewingUrgent = daysUntil !== null && daysUntil >= 0 && daysUntil <= 30;

            return (
              <Card key={policy.id} padding="md">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{cfg.icon}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-semibold text-text-primary">
                          {policy.provider || cfg.label}
                        </h4>
                        {policy.employer_provided && (
                          <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full border border-blue-100">Employer</span>
                        )}
                        {!policy.is_active && (
                          <span className="text-xs bg-surface text-text-muted px-2 py-0.5 rounded-full">Inactive</span>
                        )}
                      </div>
                      <p className="text-xs text-text-secondary mt-0.5">{cfg.label}{policy.owner_spouse ? ` — Spouse ${policy.owner_spouse.toUpperCase()}` : ""}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => openEditPolicy(policy)}
                    className="p-1.5 text-text-muted hover:text-accent rounded"
                    title="Edit policy"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    onClick={() => handleDelete(policy.id)}
                    className="p-1.5 text-text-muted hover:text-red-500 rounded"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  {policy.coverage_amount != null && (
                    <div>
                      <span className="text-text-muted">Coverage: </span>
                      <span className="font-medium text-text-secondary">{formatCurrency(policy.coverage_amount)}</span>
                    </div>
                  )}
                  {policy.annual_premium != null && (
                    <div>
                      <span className="text-text-muted">Premium: </span>
                      <span className="font-medium text-text-secondary">{formatCurrency(policy.annual_premium)}/yr</span>
                    </div>
                  )}
                  {policy.deductible != null && (
                    <div>
                      <span className="text-text-muted">Deductible: </span>
                      <span className="font-medium text-text-secondary">{formatCurrency(policy.deductible)}</span>
                    </div>
                  )}
                  {policy.oop_max != null && (
                    <div>
                      <span className="text-text-muted">OOP Max: </span>
                      <span className="font-medium text-text-secondary">{formatCurrency(policy.oop_max)}</span>
                    </div>
                  )}
                  {rd && (
                    <div className={renewingUrgent ? "text-amber-600 font-medium" : ""}>
                      <span className="text-text-muted">Renews: </span>
                      <span className={renewingUrgent ? "font-medium" : "font-medium text-text-secondary"}>
                        {rd.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                        {daysUntil !== null && daysUntil >= 0 && daysUntil <= 60 && (
                          <span className="ml-1 text-amber-500">({daysUntil}d)</span>
                        )}
                      </span>
                    </div>
                  )}
                </div>

                {policy.notes && (
                  <p className="text-xs text-text-muted mt-2 italic">{policy.notes}</p>
                )}
                {policy.beneficiaries_json && (() => {
                  try {
                    const bens: { name: string; relationship: string; percentage: string }[] = JSON.parse(policy.beneficiaries_json);
                    return bens.length > 0 ? (
                      <div className="mt-2 pt-2 border-t border-card-border">
                        <p className="text-xs text-text-muted mb-1">Beneficiaries</p>
                        {bens.map((b, i) => (
                          <p key={i} className="text-xs text-text-secondary">
                            {b.name}{b.relationship ? ` (${b.relationship})` : ""}{b.percentage ? ` — ${b.percentage}%` : ""}
                          </p>
                        ))}
                      </div>
                    ) : null;
                  } catch { return null; }
                })()}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
