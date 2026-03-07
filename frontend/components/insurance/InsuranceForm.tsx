"use client";

import { Loader2, X, UserPlus } from "lucide-react";
import Card from "@/components/ui/Card";
import type { InsurancePolicyIn } from "@/types/api";
import { POLICY_TYPES } from "./constants";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InsuranceFormState {
  type: InsurancePolicyIn["policy_type"];
  provider: string;
  policyNumber: string;
  owner: "a" | "b" | "";
  coverage: string;
  deductible: string;
  oopMax: string;
  annualPremium: string;
  renewalDate: string;
  employerProvided: boolean;
  notes: string;
  beneficiaries: { name: string; relationship: string; percentage: string }[];
}

export const EMPTY_INSURANCE_FORM: InsuranceFormState = {
  type: "health",
  provider: "",
  policyNumber: "",
  owner: "",
  coverage: "",
  deductible: "",
  oopMax: "",
  annualPremium: "",
  renewalDate: "",
  employerProvided: false,
  notes: "",
  beneficiaries: [],
};

interface InsuranceFormProps {
  form: InsuranceFormState;
  onChange: (form: InsuranceFormState) => void;
  onSubmit: () => void;
  onCancel: () => void;
  saving: boolean;
  isEditing: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function InsuranceForm({
  form,
  onChange,
  onSubmit,
  onCancel,
  saving,
  isEditing,
}: InsuranceFormProps) {
  const inputCls = "w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20";

  function set<K extends keyof InsuranceFormState>(key: K, value: InsuranceFormState[K]) {
    onChange({ ...form, [key]: value });
  }

  function updateBeneficiary(index: number, field: string, value: string) {
    onChange({
      ...form,
      beneficiaries: form.beneficiaries.map((b, j) =>
        j === index ? { ...b, [field]: value } : b
      ),
    });
  }

  function addBeneficiary() {
    onChange({
      ...form,
      beneficiaries: [...form.beneficiaries, { name: "", relationship: "", percentage: "" }],
    });
  }

  function removeBeneficiary(index: number) {
    onChange({
      ...form,
      beneficiaries: form.beneficiaries.filter((_, j) => j !== index),
    });
  }

  return (
    <Card padding="lg">
      <h3 className="text-sm font-semibold text-text-primary mb-4">
        {isEditing ? "Edit Insurance Policy" : "Add Insurance Policy"}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="text-xs text-text-secondary">Policy Type</label>
          <select
            value={form.type}
            onChange={(e) => set("type", e.target.value as InsurancePolicyIn["policy_type"])}
            className={inputCls}
          >
            {POLICY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-secondary">Provider / Insurer</label>
          <input type="text" value={form.provider} onChange={(e) => set("provider", e.target.value)} placeholder="e.g. Aetna, State Farm" className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-text-secondary">Policy Number</label>
          <input type="text" value={form.policyNumber} onChange={(e) => set("policyNumber", e.target.value)} placeholder="Optional" className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-text-secondary">Policy Owner</label>
          <select value={form.owner} onChange={(e) => set("owner", e.target.value as "a" | "b" | "")} className={inputCls}>
            <option value="">Household / Joint</option>
            <option value="a">Spouse A</option>
            <option value="b">Spouse B</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-text-secondary">Coverage Amount</label>
          <input type="number" value={form.coverage} onChange={(e) => set("coverage", e.target.value)} placeholder="e.g. 500000" className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-text-secondary">Annual Premium</label>
          <input type="number" value={form.annualPremium} onChange={(e) => set("annualPremium", e.target.value)} placeholder="e.g. 1200" className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-text-secondary">Deductible</label>
          <input type="number" value={form.deductible} onChange={(e) => set("deductible", e.target.value)} placeholder="Optional" className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-text-secondary">OOP Max</label>
          <input type="number" value={form.oopMax} onChange={(e) => set("oopMax", e.target.value)} placeholder="Optional" className={inputCls} />
        </div>
        <div>
          <label className="text-xs text-text-secondary">Renewal Date</label>
          <input type="date" value={form.renewalDate} onChange={(e) => set("renewalDate", e.target.value)} className={inputCls} />
        </div>
        <div className="flex items-center gap-3 mt-1">
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
            <input type="checkbox" checked={form.employerProvided} onChange={(e) => set("employerProvided", e.target.checked)} className="rounded border-border" />
            Employer-provided
          </label>
        </div>
      </div>
      <div className="mt-4">
        <label className="text-xs text-text-secondary">Notes</label>
        <textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={2} className={inputCls} />
      </div>

      {/* Beneficiaries -- relevant for life, disability, LTC policies */}
      {(form.type === "life" || form.type === "disability" || form.type === "ltc") && (
        <div className="mt-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-text-secondary">Beneficiaries</p>
            <button type="button" onClick={addBeneficiary} className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover">
              <UserPlus size={12} /> Add Beneficiary
            </button>
          </div>
          {form.beneficiaries.length === 0 && (
            <p className="text-xs text-text-muted italic">No beneficiaries added yet.</p>
          )}
          <div className="space-y-2">
            {form.beneficiaries.map((b, i) => (
              <div key={i} className="grid grid-cols-3 gap-2 items-center">
                <input type="text" value={b.name} onChange={(e) => updateBeneficiary(i, "name", e.target.value)} placeholder="Full name" className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                <input type="text" value={b.relationship} onChange={(e) => updateBeneficiary(i, "relationship", e.target.value)} placeholder="Relationship" className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                <div className="flex items-center gap-2">
                  <input type="number" value={b.percentage} onChange={(e) => updateBeneficiary(i, "percentage", e.target.value)} placeholder="% share" className="flex-1 text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  <button type="button" onClick={() => removeBeneficiary(i)} className="text-text-muted hover:text-red-500">
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
          onClick={onSubmit}
          disabled={saving || !form.type}
          className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          {isEditing ? "Update Policy" : "Save Policy"}
        </button>
        <button onClick={onCancel} className="text-sm text-text-secondary hover:text-text-secondary">
          Cancel
        </button>
      </div>
    </Card>
  );
}
