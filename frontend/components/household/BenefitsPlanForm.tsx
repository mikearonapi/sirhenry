"use client";
import { Loader2 } from "lucide-react";
import Card from "@/components/ui/Card";

// ---------------------------------------------------------------------------
// BenefitsPlanForm — benefit plan entry/editing form for a single spouse
// ---------------------------------------------------------------------------

interface BenefitFormState {
  employer_name: string;
  has_401k: boolean;
  employer_match_pct: number;
  employer_match_limit_pct: number;
  has_roth_401k: boolean;
  has_mega_backdoor: boolean;
  annual_401k_contribution: number;
  has_hsa: boolean;
  hsa_employer_contribution: number;
  has_fsa: boolean;
  has_dep_care_fsa: boolean;
  health_premium_monthly: number;
  dental_vision_monthly: number;
  life_insurance_coverage: number;
  std_coverage_pct: number | null;
  ltd_coverage_pct: number | null;
  commuter_monthly_limit: number;
  tuition_reimbursement_annual: number;
  has_espp: boolean;
  espp_discount_pct: number;
  open_enrollment_start: string;
  open_enrollment_end: string;
  notes: string;
}

export interface BenefitsPlanFormProps {
  spouseName: string;
  form: BenefitFormState;
  setForm: React.Dispatch<React.SetStateAction<BenefitFormState>>;
  saving: boolean;
  onSave: () => void;
}

export default function BenefitsPlanForm({ spouseName, form, setForm, saving, onSave }: BenefitsPlanFormProps) {
  const field = (label: string, key: string, type: "text" | "number" | "checkbox" = "text") => {
    const val = (form as unknown as Record<string, unknown>)[key];
    if (type === "checkbox") {
      return (
        <label key={key} className="flex items-center gap-2 text-sm text-stone-700 cursor-pointer">
          <input type="checkbox" checked={Boolean(val)}
            onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.checked }))}
            className="rounded border-stone-300" />
          {label}
        </label>
      );
    }
    return (
      <div key={key}>
        <label className="text-xs text-stone-500">{label}</label>
        <input type={type} value={type === "number" ? (Number(val) || "") : String(val || "")}
          onChange={(e) => setForm((f) => ({ ...f, [key]: type === "number" ? (Number(e.target.value) || 0) : e.target.value }))}
          className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
      </div>
    );
  };

  return (
    <Card padding="lg">
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {field("Employer Name", "employer_name")}
          {field("Open Enrollment Start", "open_enrollment_start", "text")}
          {field("Open Enrollment End", "open_enrollment_end", "text")}
        </div>

        <div>
          <p className="text-xs font-semibold text-stone-700 uppercase tracking-wide mb-3">Retirement</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              {field("Has 401k", "has_401k", "checkbox")}
              {field("Has Roth 401k option", "has_roth_401k", "checkbox")}
              {field("Has Mega Backdoor Roth", "has_mega_backdoor", "checkbox")}
            </div>
            <div className="grid grid-cols-1 gap-3">
              {field("Employer Match %", "employer_match_pct", "number")}
              {field("Match Limit (% of salary)", "employer_match_limit_pct", "number")}
              {field("Current 401k Contribution", "annual_401k_contribution", "number")}
            </div>
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold text-stone-700 uppercase tracking-wide mb-3">Health & Savings</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              {field("Has HSA (High Deductible Plan)", "has_hsa", "checkbox")}
              {field("Has FSA", "has_fsa", "checkbox")}
              {field("Has Dependent Care FSA", "has_dep_care_fsa", "checkbox")}
            </div>
            <div className="grid grid-cols-1 gap-3">
              {field("HSA Employer Contribution", "hsa_employer_contribution", "number")}
              {field("Health Premium (monthly)", "health_premium_monthly", "number")}
              {field("Dental/Vision (monthly)", "dental_vision_monthly", "number")}
            </div>
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold text-stone-700 uppercase tracking-wide mb-3">Insurance & Other</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {field("Life Insurance Coverage (employer)", "life_insurance_coverage", "number")}
            {field("Short-Term Disability Coverage %", "std_coverage_pct", "number")}
            {field("Long-Term Disability Coverage %", "ltd_coverage_pct", "number")}
            {field("Commuter Benefit (monthly limit)", "commuter_monthly_limit", "number")}
            {field("Tuition Reimbursement (annual)", "tuition_reimbursement_annual", "number")}
            <div className="flex flex-col gap-2 mt-2">
              {field("Has ESPP", "has_espp", "checkbox")}
              {form.has_espp && field("ESPP Discount %", "espp_discount_pct", "number")}
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={onSave}
        disabled={saving}
        className="mt-6 flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803d] disabled:opacity-60"
      >
        {saving && <Loader2 size={14} className="animate-spin" />}
        Save {spouseName} Benefits
      </button>
    </Card>
  );
}
