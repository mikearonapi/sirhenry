"use client";
import { Loader2 } from "lucide-react";
import type { OtherIncomeSource } from "@/types/api";
import OtherIncomeWidget from "./OtherIncomeWidget";
import { FILING_OPTIONS } from "./constants";

// ---------------------------------------------------------------------------
// HouseholdProfileForm — the profile editing form fields
// ---------------------------------------------------------------------------

export interface HouseholdProfileFormProps {
  formName: string;
  formFilingStatus: string;
  formState: string;
  otherSources: OtherIncomeSource[];
  showOtherIncome: boolean;
  saving: boolean;
  onFormNameChange: (v: string) => void;
  onFilingStatusChange: (v: string) => void;
  onStateChange: (v: string) => void;
  onOtherSourcesChange: (sources: OtherIncomeSource[]) => void;
  onSave: () => void;
  onCancel: () => void;
}

export default function HouseholdProfileForm({
  formName,
  formFilingStatus,
  formState,
  otherSources,
  showOtherIncome,
  saving,
  onFormNameChange,
  onFilingStatusChange,
  onStateChange,
  onOtherSourcesChange,
  onSave,
  onCancel,
}: HouseholdProfileFormProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-text-secondary">Household Name</label>
          <input type="text" value={formName} onChange={(e) => onFormNameChange(e.target.value)}
            placeholder="e.g. Smith Family"
            className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
        </div>
        <div>
          <label className="text-xs text-text-secondary">Filing Status</label>
          <select value={formFilingStatus} onChange={(e) => onFilingStatusChange(e.target.value)}
            className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20">
            {FILING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-secondary">Home State</label>
          <input type="text" value={formState} onChange={(e) => onStateChange(e.target.value)} placeholder="e.g. CA" maxLength={2}
            className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 uppercase" />
        </div>
      </div>

      {showOtherIncome && (
        <div className="p-4 bg-purple-50 border border-purple-100 rounded-xl">
          <div className="flex items-start gap-2 mb-3">
            <div className="flex-1">
              <p className="text-xs font-semibold text-purple-800 uppercase tracking-wide">Non-W2 / Other Income</p>
              <p className="text-xs text-purple-600 mt-0.5">
                Trust K-1s, rental, 1099 income — <strong>not</strong> bonuses or W-2 wages.
                This auto-fills the &quot;Other Income&quot; field in the W-4 optimizer and tax threshold tools.
              </p>
            </div>
          </div>
          <OtherIncomeWidget sources={otherSources} onChange={onOtherSourcesChange} />
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={onSave} disabled={saving}
          className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60">
          {saving && <Loader2 size={14} className="animate-spin" />} Save
        </button>
        <button onClick={onCancel} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary">Cancel</button>
      </div>
    </div>
  );
}
