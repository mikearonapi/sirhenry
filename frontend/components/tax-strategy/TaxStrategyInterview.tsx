"use client";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, ClipboardList, Loader2 } from "lucide-react";
import { getTaxStrategyProfile, saveTaxStrategyProfile, runTaxAnalysis } from "@/lib/api";
import type { TaxStrategyProfile } from "@/types/api";

const STEPS = [
  "Income Profile",
  "Tax Situation",
  "Assets & Accounts",
  "Goals & Appetite",
  "Review & Generate",
] as const;

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

const DEFAULTS: TaxStrategyProfile = {
  income_type: "w2",
  combined_income: 0,
  investment_income: 0,
  filing_status: "mfj",
  owed_or_refund: "unsure",
  itemizes: false,
  multi_state: false,
  age_over_50: false,
  has_rental_property: false,
  has_investment_accounts: false,
  has_equity_comp: false,
  has_traditional_ira: false,
  employer_allows_after_tax_401k: false,
  priorities: ["reduce_now"],
  complexity_preference: "medium",
  open_to_business: false,
  open_to_real_estate: false,
  has_student_loans: false,
};

function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="rounded border-stone-300 text-[#16A34A] focus:ring-[#16A34A]" />
      <span className="text-sm text-stone-700">{label}</span>
    </label>
  );
}

function Radio({ label, value, selected, onChange }: { label: string; value: string; selected: boolean; onChange: (v: string) => void }) {
  return (
    <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selected ? "border-[#16A34A] bg-[#DCFCE7]/30" : "border-stone-200 hover:border-stone-300"}`}>
      <input type="radio" checked={selected} onChange={() => onChange(value)} className="text-[#16A34A] focus:ring-[#16A34A]" />
      <span className="text-sm text-stone-700">{label}</span>
    </label>
  );
}

export default function TaxStrategyInterview({ onComplete, year }: {
  onComplete: () => void;
  year: number;
}) {
  const [step, setStepRaw] = useState(0);
  const [profile, setProfile] = useState<TaxStrategyProfile>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Persist step in localStorage so the interview resumes if abandoned
  function setStep(s: number) {
    setStepRaw(s);
    try { localStorage.setItem("tax-interview-step", String(s)); } catch { /* noop */ }
  }

  useEffect(() => {
    getTaxStrategyProfile().then((res) => {
      if (res.profile) {
        setProfile({ ...DEFAULTS, ...res.profile });
        // Resume at the saved step if user previously abandoned
        try {
          const saved = localStorage.getItem("tax-interview-step");
          if (saved) {
            const parsed = parseInt(saved, 10);
            if (parsed >= 0 && parsed < STEPS.length) setStepRaw(parsed);
          }
        } catch { /* noop */ }
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  function update(partial: Partial<TaxStrategyProfile>) {
    setProfile((prev) => ({ ...prev, ...partial }));
  }

  async function handleFinish() {
    setSaving(true);
    try {
      await saveTaxStrategyProfile(profile);
      await runTaxAnalysis(year);
      try { localStorage.removeItem("tax-interview-step"); } catch { /* noop */ }
      onComplete();
    } catch {
      // Error handled by UI staying on review step
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-3 text-stone-400 justify-center h-32">
        <Loader2 className="animate-spin" size={20} /> Loading...
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-stone-100 shadow-sm">
      {/* Progress */}
      <div className="px-6 pt-5 pb-3">
        <div className="flex items-center gap-2 mb-4">
          <ClipboardList size={18} className="text-[#16A34A]" />
          <h3 className="text-sm font-semibold text-stone-800">Tax Strategy Interview</h3>
          <span className="text-xs text-stone-400 ml-auto">Step {step + 1} of {STEPS.length}</span>
        </div>
        <div className="flex gap-1">
          {STEPS.map((_, i) => (
            <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= step ? "bg-[#16A34A]" : "bg-stone-200"}`} />
          ))}
        </div>
        <p className="text-xs text-stone-500 mt-2">{STEPS[step]}</p>
      </div>

      {/* Content */}
      <div className="px-6 py-4 min-h-[260px]">
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-stone-500 mb-2">Income Type</label>
              <div className="grid grid-cols-3 gap-2">
                <Radio label="W-2 Employee" value="w2" selected={profile.income_type === "w2"} onChange={(v) => update({ income_type: v as TaxStrategyProfile["income_type"] })} />
                <Radio label="Self-Employed" value="self_employed" selected={profile.income_type === "self_employed"} onChange={(v) => update({ income_type: v as TaxStrategyProfile["income_type"] })} />
                <Radio label="Both" value="mixed" selected={profile.income_type === "mixed"} onChange={(v) => update({ income_type: v as TaxStrategyProfile["income_type"] })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-stone-500 mb-1">Combined Household Income</label>
                <input type="number" value={profile.combined_income || ""} onChange={(e) => update({ combined_income: Number(e.target.value) })} placeholder="250000" className={INPUT_CLS} />
              </div>
              <div>
                <label className="block text-xs text-stone-500 mb-1">Investment Income</label>
                <input type="number" value={profile.investment_income || ""} onChange={(e) => update({ investment_income: Number(e.target.value) })} placeholder="0" className={INPUT_CLS} />
              </div>
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
              <select value={profile.filing_status} onChange={(e) => update({ filing_status: e.target.value })} className={INPUT_CLS}>
                <option value="single">Single</option>
                <option value="mfj">Married Filing Jointly</option>
                <option value="mfs">Married Filing Separately</option>
                <option value="hh">Head of Household</option>
              </select>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-stone-500 mb-2">Last Year Tax Result</label>
              <div className="grid grid-cols-3 gap-2">
                <Radio label="Owed taxes" value="owed" selected={profile.owed_or_refund === "owed"} onChange={(v) => update({ owed_or_refund: v as TaxStrategyProfile["owed_or_refund"] })} />
                <Radio label="Got a refund" value="refund" selected={profile.owed_or_refund === "refund"} onChange={(v) => update({ owed_or_refund: v as TaxStrategyProfile["owed_or_refund"] })} />
                <Radio label="Not sure" value="unsure" selected={profile.owed_or_refund === "unsure"} onChange={(v) => update({ owed_or_refund: v as TaxStrategyProfile["owed_or_refund"] })} />
              </div>
            </div>
            <div className="space-y-3">
              <Checkbox label="I itemize deductions (instead of standard deduction)" checked={profile.itemizes} onChange={(v) => update({ itemizes: v })} />
              <Checkbox label="I earn income in multiple states" checked={profile.multi_state} onChange={(v) => update({ multi_state: v })} />
              <Checkbox label="I'm 50 or older (or will be this year)" checked={profile.age_over_50} onChange={(v) => update({ age_over_50: v })} />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <p className="text-xs text-stone-500 mb-2">Check all that apply:</p>
            <Checkbox label="I own rental property" checked={profile.has_rental_property} onChange={(v) => update({ has_rental_property: v })} />
            <Checkbox label="I have investment/brokerage accounts" checked={profile.has_investment_accounts} onChange={(v) => update({ has_investment_accounts: v })} />
            <Checkbox label="I receive equity compensation (stock grants, options, or employee stock purchase plan)" checked={profile.has_equity_comp} onChange={(v) => update({ has_equity_comp: v })} />
            <Checkbox label="I have a traditional Individual Retirement Account (IRA) balance" checked={profile.has_traditional_ira} onChange={(v) => update({ has_traditional_ira: v })} />
            <Checkbox label="My employer allows after-tax 401(k) contributions" checked={profile.employer_allows_after_tax_401k} onChange={(v) => update({ employer_allows_after_tax_401k: v })} />
            <Checkbox label="I have student loans" checked={profile.has_student_loans} onChange={(v) => update({ has_student_loans: v })} />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-stone-500 mb-2">Top Priority</label>
              <div className="grid grid-cols-3 gap-2">
                <Radio label="Reduce taxes now" value="reduce_now" selected={profile.priorities[0] === "reduce_now"} onChange={() => update({ priorities: ["reduce_now"] })} />
                <Radio label="Build long-term wealth" value="build_wealth" selected={profile.priorities[0] === "build_wealth"} onChange={() => update({ priorities: ["build_wealth"] })} />
                <Radio label="Simplify my taxes" value="simplify" selected={profile.priorities[0] === "simplify"} onChange={() => update({ priorities: ["simplify"] })} />
              </div>
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-2">Complexity Comfort Level</label>
              <div className="grid grid-cols-3 gap-2">
                <Radio label="Keep it simple" value="low" selected={profile.complexity_preference === "low"} onChange={(v) => update({ complexity_preference: v as TaxStrategyProfile["complexity_preference"] })} />
                <Radio label="Moderate is fine" value="medium" selected={profile.complexity_preference === "medium"} onChange={(v) => update({ complexity_preference: v as TaxStrategyProfile["complexity_preference"] })} />
                <Radio label="Maximize savings" value="high" selected={profile.complexity_preference === "high"} onChange={(v) => update({ complexity_preference: v as TaxStrategyProfile["complexity_preference"] })} />
              </div>
            </div>
            <div className="space-y-3">
              <Checkbox label="I'm open to starting a business (or already have one)" checked={profile.open_to_business} onChange={(v) => update({ open_to_business: v })} />
              <Checkbox label="I'm interested in real estate investing" checked={profile.open_to_real_estate} onChange={(v) => update({ open_to_real_estate: v })} />
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            <p className="text-sm text-stone-700 mb-3">Review your answers. Sir Henry will use this to generate personalized tax strategies.</p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-stone-50 rounded-lg p-3">
                <p className="text-xs text-stone-500 mb-1">Income</p>
                <p className="font-medium text-stone-800 font-mono tabular-nums">${(profile.combined_income || 0).toLocaleString()}</p>
                <p className="text-xs text-stone-500 mt-1">{profile.income_type === "w2" ? "W-2" : profile.income_type === "self_employed" ? "Self-employed" : "Mixed"} · {profile.filing_status === "mfj" ? "Filing Jointly" : profile.filing_status === "mfs" ? "Filing Separately" : profile.filing_status === "hh" ? "Head of Household" : "Single"}</p>
              </div>
              <div className="bg-stone-50 rounded-lg p-3">
                <p className="text-xs text-stone-500 mb-1">Tax Situation</p>
                <p className="text-xs text-stone-700">
                  {profile.owed_or_refund === "owed" ? "Owed taxes" : profile.owed_or_refund === "refund" ? "Got refund" : "Unsure"}
                  {profile.itemizes ? " · Itemizes" : ""}
                  {profile.multi_state ? " · Multi-state" : ""}
                </p>
              </div>
              <div className="bg-stone-50 rounded-lg p-3">
                <p className="text-xs text-stone-500 mb-1">Assets</p>
                <p className="text-xs text-stone-700">
                  {[
                    profile.has_rental_property && "Rental property",
                    profile.has_investment_accounts && "Investments",
                    profile.has_equity_comp && "Equity compensation",
                    profile.has_traditional_ira && "Traditional retirement account",
                    profile.has_student_loans && "Student loans",
                  ].filter(Boolean).join(", ") || "None selected"}
                </p>
              </div>
              <div className="bg-stone-50 rounded-lg p-3">
                <p className="text-xs text-stone-500 mb-1">Goals</p>
                <p className="text-xs text-stone-700">
                  {profile.priorities[0] === "reduce_now" ? "Reduce taxes now" : profile.priorities[0] === "build_wealth" ? "Build wealth" : "Simplify"}
                  {" · "}
                  {profile.complexity_preference === "low" ? "Simple" : profile.complexity_preference === "medium" ? "Moderate" : "Maximize"}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="px-6 pb-5 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setStep(step - 1)}
          disabled={step === 0}
          className="flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-800 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ArrowLeft size={14} /> Back
        </button>
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep(step + 1)}
            className="flex items-center gap-1.5 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D]"
          >
            Next <ArrowRight size={14} />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleFinish}
            disabled={saving}
            className="flex items-center gap-1.5 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60"
          >
            {saving ? (
              <><Loader2 size={14} className="animate-spin" /> Generating Strategies...</>
            ) : (
              <><Check size={14} /> Generate My Strategies</>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
