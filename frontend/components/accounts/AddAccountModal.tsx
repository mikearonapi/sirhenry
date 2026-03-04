"use client";

import { ArrowLeft, X, Loader2, Link2, FileText, Home, Car, TrendingUp, Package, Landmark } from "lucide-react";
import type { ManualAsset, ManualAssetType, TaxTreatment, ContributionType } from "@/types/api";
import {
  type AssetFormState,
  type AddFlowStep,
  MANUAL_ASSET_CONFIG,
  INVESTMENT_SUBTYPES,
} from "./accounts-types";

// ---------------------------------------------------------------------------
// Modal-only constants
// ---------------------------------------------------------------------------
const ADD_ACCOUNT_OPTIONS: { type: ManualAssetType; label: string; subtitle: string; icon: React.ReactNode; color: string }[] = [
  { type: "real_estate",      label: "Real Estate",       subtitle: "Home, rental property, land",    icon: <Home size={22} />,     color: "text-blue-500 bg-blue-50" },
  { type: "vehicle",          label: "Vehicle",           subtitle: "Car, truck, boat, RV",           icon: <Car size={22} />,      color: "text-cyan-500 bg-cyan-50" },
  { type: "investment",       label: "Investment",        subtitle: "Brokerage, IRA, 401k, crypto",   icon: <TrendingUp size={22} />, color: "text-indigo-500 bg-indigo-50" },
  { type: "other_asset",      label: "Other Asset",       subtitle: "Jewelry, collectibles, etc.",     icon: <Package size={22} />,  color: "text-emerald-500 bg-emerald-50" },
  { type: "mortgage",         label: "Mortgage",          subtitle: "Home loan balance",              icon: <Home size={22} />,     color: "text-red-400 bg-red-50" },
  { type: "loan",             label: "Loan",              subtitle: "Auto, student, personal",        icon: <Landmark size={22} />, color: "text-red-400 bg-red-50" },
  { type: "other_liability",  label: "Other Liability",   subtitle: "HELOC, margin, other debt",      icon: <Landmark size={22} />, color: "text-red-300 bg-red-50" },
];

const PLACEHOLDER_MAP: Partial<Record<ManualAssetType, string>> = {
  real_estate: "e.g., Primary Residence",
  vehicle: "e.g., 2023 Toyota Highlander",
  investment: "e.g., Vanguard Roth IRA",
  other_asset: "e.g., Gold Coins",
  mortgage: "e.g., Home Mortgage",
  loan: "e.g., Auto Loan — Chase",
  other_liability: "e.g., HELOC",
};

const TAX_TREATMENTS: { value: TaxTreatment; label: string }[] = [
  { value: "tax_deferred", label: "Tax-Deferred (Traditional 401k, IRA)" },
  { value: "tax_free", label: "Tax-Free (Roth)" },
  { value: "taxable", label: "Taxable (Brokerage, Trust)" },
];

const CONTRIBUTION_TYPES: { value: ContributionType; label: string }[] = [
  { value: "pre_tax", label: "Pre-Tax" },
  { value: "roth", label: "Roth" },
  { value: "after_tax", label: "After-Tax" },
  { value: "mixed", label: "Mixed" },
];

const INPUT_CLS = "w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A]";
const DOLLAR_CLS = "w-full rounded-lg border border-stone-200 pl-7 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A]";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface AddAccountModalProps {
  addFlowStep: AddFlowStep | null;
  editingAsset: ManualAsset | null;
  assetForm: AssetFormState;
  savingAsset: boolean;
  connectingPlaid: boolean;
  onSetAssetForm: (value: AssetFormState | ((prev: AssetFormState) => AssetFormState)) => void;
  onPickManualType: (type: ManualAssetType) => void;
  onConnectPlaid: () => void;
  onSave: () => void;
  onClose: () => void;
  onBack: () => void;
}

export default function AddAccountModal({
  addFlowStep,
  editingAsset,
  assetForm,
  savingAsset,
  connectingPlaid,
  onSetAssetForm,
  onPickManualType,
  onConnectPlaid,
  onSave,
  onClose,
  onBack,
}: AddAccountModalProps) {
  if (addFlowStep === null) return null;

  const showingForm = addFlowStep === "manual-form";
  const formConfig = MANUAL_ASSET_CONFIG[assetForm.asset_type];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100">
          <div className="flex items-center gap-2">
            {showingForm && !editingAsset && (
              <button onClick={onBack} className="p-1 rounded-lg hover:bg-stone-100 text-stone-400 mr-1">
                <ArrowLeft size={18} />
              </button>
            )}
            <h2 className="text-lg font-semibold text-stone-900">
              {editingAsset
                ? `Edit ${MANUAL_ASSET_CONFIG[editingAsset.asset_type]?.label ?? "Asset"}`
                : showingForm
                  ? `Add ${MANUAL_ASSET_CONFIG[assetForm.asset_type]?.label ?? "Asset"}`
                  : "Add Account"}
            </h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-stone-100 text-stone-400">
            <X size={18} />
          </button>
        </div>

        {/* Step 1: Type picker */}
        {addFlowStep === "choose" && (
          <div className="px-6 py-5 space-y-5">
            <div>
              <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Connect automatically</p>
              <button
                onClick={onConnectPlaid}
                disabled={connectingPlaid}
                className="w-full flex items-center gap-4 p-4 rounded-xl border border-stone-200 hover:border-[#16A34A]/40 hover:bg-green-50/30 transition-all group"
              >
                <div className="w-11 h-11 rounded-xl bg-[#16A34A]/10 flex items-center justify-center text-[#16A34A] shrink-0 group-hover:bg-[#16A34A]/20 transition-colors">
                  <Link2 size={22} />
                </div>
                <div className="text-left flex-1">
                  <p className="text-sm font-semibold text-stone-800">Link bank or brokerage</p>
                  <p className="text-xs text-stone-500">Checking, savings, credit cards, investments, loans</p>
                </div>
                {connectingPlaid && <Loader2 size={16} className="animate-spin text-stone-400" />}
              </button>
            </div>

            <div>
              <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Add manually</p>
              <div className="grid grid-cols-2 gap-2.5">
                {ADD_ACCOUNT_OPTIONS.map((opt) => (
                  <button
                    key={opt.type}
                    onClick={() => onPickManualType(opt.type)}
                    className="flex items-center gap-3 p-3.5 rounded-xl border border-stone-200 hover:border-stone-300 hover:bg-stone-50 transition-all text-left"
                  >
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${opt.color}`}>
                      {opt.icon}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-stone-800">{opt.label}</p>
                      <p className="text-[11px] text-stone-400 truncate">{opt.subtitle}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-stone-100 pt-4">
              <a
                href="/import"
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-stone-50 transition-colors text-stone-500 hover:text-stone-700"
              >
                <FileText size={18} />
                <span className="text-sm">Import from CSV file instead</span>
              </a>
            </div>
          </div>
        )}

        {/* Step 2: Manual entry form */}
        {showingForm && (
          <>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">Name</label>
                <input
                  type="text"
                  value={assetForm.name}
                  onChange={(e) => onSetAssetForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={PLACEHOLDER_MAP[assetForm.asset_type] ?? "Name"}
                  className={INPUT_CLS}
                  autoFocus
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">
                    {formConfig?.isLiability ? "Balance Owed" : "Current Value"}
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={assetForm.current_value}
                      onChange={(e) => onSetAssetForm((f) => ({ ...f, current_value: e.target.value }))}
                      placeholder="0.00"
                      className={DOLLAR_CLS}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">
                    {formConfig?.isLiability ? "Original Amount" : assetForm.asset_type === "investment" ? "Original Cost Basis" : "Purchase Price"}
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={assetForm.purchase_price}
                      onChange={(e) => onSetAssetForm((f) => ({ ...f, purchase_price: e.target.value }))}
                      placeholder={assetForm.asset_type === "investment" ? "Total amount invested" : "Optional"}
                      className={DOLLAR_CLS}
                    />
                  </div>
                  {assetForm.asset_type === "investment" && (
                    <p className="text-xs text-stone-400 mt-1">Used to calculate total gain/loss on your portfolio</p>
                  )}
                </div>
              </div>
              {(assetForm.asset_type === "real_estate" || editingAsset?.asset_type === "real_estate") && (
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Address</label>
                  <input
                    type="text"
                    value={assetForm.address}
                    onChange={(e) => onSetAssetForm((f) => ({ ...f, address: e.target.value }))}
                    placeholder="123 Main St, City, State"
                    className={INPUT_CLS}
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">
                  {formConfig?.isLiability ? "Lender / Institution" : "Institution / Brokerage"}
                </label>
                <input
                  type="text"
                  value={assetForm.institution}
                  onChange={(e) => onSetAssetForm((f) => ({ ...f, institution: e.target.value }))}
                  placeholder={formConfig?.isLiability ? "e.g., Wells Fargo" : "e.g., Fidelity, Vanguard"}
                  className={INPUT_CLS}
                />
              </div>

              {/* Investment-specific fields */}
              {assetForm.asset_type === "investment" && (
                <div className="space-y-4 border-t border-stone-100 pt-4">
                  <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Investment Details</p>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Owner</label>
                      <select
                        value={assetForm.owner}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, owner: e.target.value }))}
                        className={INPUT_CLS}
                      >
                        <option value="">Select...</option>
                        <option value="Mike">Mike</option>
                        <option value="Christine">Christine</option>
                        <option value="Joint">Joint</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Account Type</label>
                      <select
                        value={assetForm.account_subtype}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, account_subtype: e.target.value }))}
                        className={INPUT_CLS}
                      >
                        <option value="">Select...</option>
                        {INVESTMENT_SUBTYPES.map((s) => (
                          <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Tax Treatment</label>
                      <select
                        value={assetForm.tax_treatment}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, tax_treatment: e.target.value }))}
                        className={INPUT_CLS}
                      >
                        <option value="">Select...</option>
                        {TAX_TREATMENTS.map((t) => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Custodian</label>
                      <input
                        type="text"
                        value={assetForm.custodian}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, custodian: e.target.value }))}
                        placeholder="e.g., Merrill Lynch, Fidelity"
                        className={INPUT_CLS}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Employer</label>
                      <input
                        type="text"
                        value={assetForm.employer}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, employer: e.target.value }))}
                        placeholder="For employer-sponsored plans"
                        className={INPUT_CLS}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Beneficiary</label>
                      <input
                        type="text"
                        value={assetForm.beneficiary}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, beneficiary: e.target.value }))}
                        placeholder="e.g., Spouse name"
                        className={INPUT_CLS}
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={assetForm.is_retirement_account}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, is_retirement_account: e.target.checked }))}
                        className="rounded border-stone-300 text-[#16A34A] focus:ring-[#16A34A]/30"
                      />
                      <span className="text-sm text-stone-700">Retirement account</span>
                    </label>
                  </div>

                  <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider pt-2">Contributions & Performance</p>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Contribution Type</label>
                      <select
                        value={assetForm.contribution_type}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, contribution_type: e.target.value }))}
                        className={INPUT_CLS}
                      >
                        <option value="">Select...</option>
                        {CONTRIBUTION_TYPES.map((c) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Contribution Rate %</label>
                      <input
                        type="number"
                        value={assetForm.contribution_rate_pct}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, contribution_rate_pct: e.target.value }))}
                        placeholder="e.g., 6"
                        min="0" max="100" step="0.5"
                        className={INPUT_CLS}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Employee Contributions YTD</label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
                        <input
                          type="number"
                          value={assetForm.employee_contribution_ytd}
                          onChange={(e) => onSetAssetForm((f) => ({ ...f, employee_contribution_ytd: e.target.value }))}
                          placeholder="0"
                          min="0"
                          className={DOLLAR_CLS}
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Employer Contributions YTD</label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
                        <input
                          type="number"
                          value={assetForm.employer_contribution_ytd}
                          onChange={(e) => onSetAssetForm((f) => ({ ...f, employer_contribution_ytd: e.target.value }))}
                          placeholder="0"
                          min="0"
                          className={DOLLAR_CLS}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Employer Match %</label>
                      <input
                        type="number"
                        value={assetForm.employer_match_pct}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, employer_match_pct: e.target.value }))}
                        placeholder="e.g., 100"
                        min="0" max="200" step="1"
                        className={INPUT_CLS}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Match Limit (% of salary)</label>
                      <input
                        type="number"
                        value={assetForm.employer_match_limit_pct}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, employer_match_limit_pct: e.target.value }))}
                        placeholder="e.g., 6"
                        min="0" max="100" step="0.5"
                        className={INPUT_CLS}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Annual Return %</label>
                      <input
                        type="number"
                        value={assetForm.annual_return_pct}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, annual_return_pct: e.target.value }))}
                        placeholder="e.g., 21.62"
                        step="0.01"
                        className={INPUT_CLS}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 mb-1">Balance As-Of Date</label>
                      <input
                        type="date"
                        value={assetForm.as_of_date}
                        onChange={(e) => onSetAssetForm((f) => ({ ...f, as_of_date: e.target.value }))}
                        className={INPUT_CLS}
                      />
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">Notes</label>
                <textarea
                  value={assetForm.notes}
                  onChange={(e) => onSetAssetForm((f) => ({ ...f, notes: e.target.value }))}
                  rows={2}
                  placeholder="Optional notes..."
                  className={`${INPUT_CLS} resize-none`}
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-stone-100 bg-stone-50/50 rounded-b-2xl">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-stone-600 hover:text-stone-800"
              >
                Cancel
              </button>
              <button
                onClick={onSave}
                disabled={savingAsset || !assetForm.name.trim() || !assetForm.current_value}
                className="flex items-center gap-2 bg-[#16A34A] text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60 shadow-sm"
              >
                {savingAsset && <Loader2 size={14} className="animate-spin" />}
                {editingAsset ? "Save Changes" : `Add ${formConfig?.label ?? "Asset"}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
