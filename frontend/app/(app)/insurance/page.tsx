"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ShieldCheck, Plus, AlertCircle, Loader2, Clock, X,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import StatCard from "@/components/ui/StatCard";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import {
  getInsurancePolicies, createInsurancePolicy, updateInsurancePolicy, deleteInsurancePolicy,
  getInsuranceGapAnalysis, getHouseholdProfiles,
} from "@/lib/api";
import { getManualAssets } from "@/lib/api-assets";
import type { InsurancePolicy, InsurancePolicyIn, InsuranceGapAnalysis, HouseholdProfile } from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";
import {
  InsuranceForm, InsurancePolicyCard, GapAnalysisCard,
  POLICY_TYPES, getPolicyConfig, EMPTY_INSURANCE_FORM,
} from "@/components/insurance";
import type { InsuranceFormState } from "@/components/insurance";

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
  const [form, setForm] = useState<InsuranceFormState>(EMPTY_INSURANCE_FORM);
  const [confirmDelete, setConfirmDelete] = useState<{ open: boolean; policyId: number | null }>({ open: false, policyId: null });

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

  useEffect(() => { loadData(); }, [loadData]);

  async function runGapAnalysis() {
    setGapLoading(true);
    setError(null);
    try {
      const primary = profiles.find((p) => p.is_primary) || profiles[0];
      const assets = await getManualAssets().catch(() => [] as ManualAsset[]);
      const totalAssets = assets.filter((a) => !a.is_liability && a.is_active !== false).reduce((sum, a) => sum + (a.current_value ?? 0), 0);
      const totalDebt = assets.filter((a) => a.is_liability && a.is_active !== false).reduce((sum, a) => sum + (a.current_value ?? 0), 0);
      const body = primary
        ? { household_id: primary.id, spouse_a_income: primary.spouse_a_income, spouse_b_income: primary.spouse_b_income, net_worth: Math.max(0, totalAssets - totalDebt), total_debt: totalDebt }
        : {};
      setGapAnalysis(await getInsuranceGapAnalysis(body));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGapLoading(false);
    }
  }

  function resetForm() {
    setForm(EMPTY_INSURANCE_FORM);
    setEditingPolicy(null);
    setShowForm(false);
  }

  function openEditPolicy(policy: InsurancePolicy) {
    setEditingPolicy(policy);
    let beneficiaries: { name: string; relationship: string; percentage: string }[] = [];
    try {
      const bens = policy.beneficiaries_json ? JSON.parse(policy.beneficiaries_json) : [];
      beneficiaries = Array.isArray(bens) ? bens : [];
    } catch { /* ignore */ }
    setForm({
      type: policy.policy_type,
      provider: policy.provider || "",
      policyNumber: policy.policy_number || "",
      owner: (policy.owner_spouse as "a" | "b") || "",
      coverage: policy.coverage_amount != null ? String(policy.coverage_amount) : "",
      deductible: policy.deductible != null ? String(policy.deductible) : "",
      oopMax: policy.oop_max != null ? String(policy.oop_max) : "",
      annualPremium: policy.annual_premium != null ? String(policy.annual_premium) : "",
      renewalDate: policy.renewal_date || "",
      employerProvided: policy.employer_provided,
      notes: policy.notes || "",
      beneficiaries,
    });
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function buildBody(isActive: boolean): InsurancePolicyIn {
    return {
      policy_type: form.type,
      provider: form.provider || null,
      policy_number: form.policyNumber || null,
      owner_spouse: (form.owner as "a" | "b") || null,
      coverage_amount: form.coverage ? Number(form.coverage) : null,
      deductible: form.deductible ? Number(form.deductible) : null,
      oop_max: form.oopMax ? Number(form.oopMax) : null,
      annual_premium: form.annualPremium ? Number(form.annualPremium) : null,
      renewal_date: form.renewalDate || null,
      employer_provided: form.employerProvided,
      is_active: isActive,
      notes: form.notes || null,
      household_id: profiles.find((p) => p.is_primary)?.id || profiles[0]?.id || null,
      beneficiaries_json: form.beneficiaries.length > 0
        ? JSON.stringify(form.beneficiaries.filter((b) => b.name))
        : null,
    };
  }

  async function handleSubmit() {
    setSaving(true);
    setError(null);
    try {
      if (editingPolicy) {
        await updateInsurancePolicy(editingPolicy.id, buildBody(editingPolicy.is_active));
      } else {
        await createInsurancePolicy(buildBody(true));
      }
      await loadData();
      resetForm();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  function handleDelete(id: number) {
    setConfirmDelete({ open: true, policyId: id });
  }

  async function confirmDeletePolicy() {
    if (confirmDelete.policyId == null) return;
    try {
      await deleteInsurancePolicy(confirmDelete.policyId);
      setConfirmDelete({ open: false, policyId: null });
      await loadData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const filtered = filterType ? policies.filter((p) => p.policy_type === filterType) : policies;
  const totalAnnualPremium = filtered.reduce((s, p) => s + (p.annual_premium || 0), 0);
  const byType = policies.reduce<Record<string, number>>((acc, p) => { acc[p.policy_type] = (acc[p.policy_type] || 0) + 1; return acc; }, {});
  const today = new Date();
  const renewingSoon = policies.filter((p) => {
    if (!p.renewal_date) return false;
    const diff = (new Date(p.renewal_date).getTime() - today.getTime()) / (1000 * 60 * 60 * 24);
    return diff >= 0 && diff <= 60;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Insurance & Benefits Hub"
        subtitle="Track all insurance policies, coverage gaps, and renewal deadlines"
        actions={
          <button
            onClick={() => { if (showForm) resetForm(); else setShowForm(true); }}
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

      {!loading && policies.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Active Policies" value={String(policies.length)} sub="across all types" />
          <StatCard label="Annual Premiums" value={formatCurrency(totalAnnualPremium)} sub={`${formatCurrency(totalAnnualPremium / 12)}/mo`} />
          <StatCard label="Renewing Soon" value={String(renewingSoon.length)} sub="within 60 days" trend={renewingSoon.length > 0 ? "down" : undefined} trendValue={renewingSoon.length > 0 ? "Action needed" : undefined} />
          <StatCard label="Policy Types" value={String(Object.keys(byType).length)} sub="of 11 types covered" />
        </div>
      )}

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

      <GapAnalysisCard gapAnalysis={gapAnalysis} loading={gapLoading} onRun={runGapAnalysis} />

      {showForm && (
        <InsuranceForm form={form} onChange={setForm} onSubmit={handleSubmit} onCancel={resetForm} saving={saving} isEditing={!!editingPolicy} />
      )}

      <div className="flex flex-wrap items-center gap-3">
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="text-sm border border-border rounded-lg px-3 py-2 bg-card focus:outline-none focus:ring-2 focus:ring-accent/20">
          <option value="">All Types</option>
          {POLICY_TYPES.map((t) => <option key={t.value} value={t.value}>{t.icon} {t.label}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} className="rounded border-border" />
          Show inactive
        </label>
        <span className="ml-auto text-xs text-text-muted">{filtered.length} policies</span>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-text-secondary text-sm py-8">
          <Loader2 size={16} className="animate-spin" /> Loading policies...
        </div>
      ) : filtered.length === 0 ? (
        <Card padding="lg">
          <div className="text-center py-8">
            <ShieldCheck size={32} className="mx-auto text-text-muted mb-3" />
            <p className="text-sm text-text-secondary">No insurance policies added yet.</p>
            <p className="text-xs text-text-muted mt-1">Track health, life, disability, auto, home, and umbrella policies in one place.</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((policy) => (
            <InsurancePolicyCard key={policy.id} policy={policy} onEdit={openEditPolicy} onDelete={handleDelete} />
          ))}
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete.open}
        title="Delete Insurance Policy"
        message="Delete this insurance policy? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDeletePolicy}
        onCancel={() => setConfirmDelete({ open: false, policyId: null })}
      />
    </div>
  );
}
