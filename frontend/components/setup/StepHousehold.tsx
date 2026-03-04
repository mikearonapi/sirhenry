"use client";
import { useState } from "react";
import { User, Users, UserCheck, Home, Check, ChevronDown, ChevronUp, MessageCircle } from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData } from "./SetupWizard";
import type { OtherIncomeSource, OtherIncomeType } from "@/types/household";
import { createHouseholdProfile, updateHouseholdProfile } from "@/lib/api-household";
import { getErrorMessage } from "@/lib/errors";

const INPUT = "w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white";
const DOLLAR = "w-full rounded-lg border border-stone-200 pl-7 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

const FILING_OPTIONS = [
  { value: "single", label: "Single", icon: User, desc: "Unmarried, no dependents qualifying for HoH" },
  { value: "mfj", label: "Married Filing Jointly", icon: Users, desc: "Married, filing together (most common)" },
  { value: "mfs", label: "Married Filing Separately", icon: Users, desc: "Married, filing separate returns" },
  { value: "hh", label: "Head of Household", icon: UserCheck, desc: "Unmarried with qualifying dependent" },
];

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
  "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
  "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
];

// Non-W-2 income types for the toggle list
const OTHER_INCOME_TYPES = [
  {
    key: "k1" as const,
    otherType: "partnership_k1" as OtherIncomeType,
    label: "K-1 / Business",
    desc: "S-Corp, LLC, or partnership distributions",
    why: "Affects estimated tax payments and self-employment tax calculations",
  },
  {
    key: "1099" as const,
    otherType: "business_1099" as OtherIncomeType,
    label: "1099 / Self-Employment",
    desc: "Freelance, consulting, or contract work",
    why: "Requires quarterly estimated payments, eligible for SEP-IRA or Solo 401k",
  },
  {
    key: "rental" as const,
    otherType: "rental" as OtherIncomeType,
    label: "Rental Income",
    desc: "Investment property income (Schedule E)",
    why: "Different tax treatment — passive activity rules and depreciation deductions",
  },
  {
    key: "other" as const,
    otherType: "other" as OtherIncomeType,
    label: "Other Income",
    desc: "Dividends, interest, pension, social security, alimony, etc.",
    why: "Ensures accurate total income for tax bracket and threshold analysis",
  },
];

type SourceKey = "k1" | "1099" | "rental" | "other";

interface IncomeState {
  w2: string;
  employer: string;
  sources: Partial<Record<SourceKey, string>>;
  k1Entity: string;
}

// Map stored OtherIncomeType back to our UI source key
function typeToKey(type: OtherIncomeType): SourceKey | null {
  if (type === "partnership_k1" || type === "scorp_k1" || type === "trust_k1") return "k1";
  if (type === "business_1099" || type === "dividends_1099") return "1099";
  if (type === "rental") return "rental";
  return "other";
}

function parseExistingSources(json: string | null | undefined, spouse: string): Partial<Record<SourceKey, string>> {
  if (!json) return {};
  try {
    const sources: OtherIncomeSource[] = JSON.parse(json);
    const result: Partial<Record<SourceKey, string>> = {};
    for (const s of sources) {
      if (s.notes !== spouse) continue;
      const key = typeToKey(s.type);
      if (key) {
        // Sum amounts if multiple entries map to the same key
        const existing = parseFloat(result[key] || "0");
        result[key] = (existing + s.amount).toString();
      }
    }
    return result;
  } catch {
    return {};
  }
}

function parseK1Entity(json: string | null | undefined, spouse: string): string {
  if (!json) return "";
  try {
    const sources: OtherIncomeSource[] = JSON.parse(json);
    const k1 = sources.find(
      (s) => s.notes === spouse && (s.type === "partnership_k1" || s.type === "scorp_k1" || s.type === "trust_k1")
    );
    // Extract entity name from label like "Christine — K-1 / Business (AutoRev)"
    if (k1?.label) {
      const match = k1.label.match(/\(([^)]+)\)$/);
      if (match) return match[1];
    }
    return "";
  } catch {
    return "";
  }
}

function calcTotal(inc: IncomeState): number {
  let total = parseFloat(inc.w2) || 0;
  for (const amt of Object.values(inc.sources)) {
    total += parseFloat(amt || "0") || 0;
  }
  return total;
}

interface Props {
  data: SetupData;
  onRefresh: () => void;
}

export default function StepHousehold({ data, onRefresh }: Props) {
  const existing = data.household;

  const [filing, setFiling] = useState(existing?.filing_status || "");
  const [state, setState] = useState(existing?.state || "");
  const [nameA, setNameA] = useState(existing?.spouse_a_name || "");
  const [nameB, setNameB] = useState(existing?.spouse_b_name || "");

  const [incomeA, setIncomeA] = useState<IncomeState>(() => ({
    w2: existing?.spouse_a_income ? existing.spouse_a_income.toString() : "",
    employer: existing?.spouse_a_employer || "",
    sources: parseExistingSources(existing?.other_income_sources_json, "spouse_a"),
    k1Entity: parseK1Entity(existing?.other_income_sources_json, "spouse_a"),
  }));
  const [incomeB, setIncomeB] = useState<IncomeState>(() => ({
    w2: existing?.spouse_b_income ? existing.spouse_b_income.toString() : "",
    employer: existing?.spouse_b_employer || "",
    sources: parseExistingSources(existing?.other_income_sources_json, "spouse_b"),
    k1Entity: parseK1Entity(existing?.other_income_sources_json, "spouse_b"),
  }));

  const [dependents, setDependents] = useState(() => {
    try {
      return existing?.dependents_json ? JSON.parse(existing.dependents_json).length : 0;
    } catch { return 0; }
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const married = filing === "mfj" || filing === "mfs";
  const totalA = calcTotal(incomeA);
  const totalB = married ? calcTotal(incomeB) : 0;
  const grandTotal = totalA + totalB;

  function toggleSource(setter: React.Dispatch<React.SetStateAction<IncomeState>>, key: SourceKey) {
    setter(prev => {
      const next = { ...prev, sources: { ...prev.sources } };
      if (key in next.sources) {
        delete next.sources[key];
      } else {
        next.sources[key] = "";
      }
      return next;
    });
  }

  function setSourceAmount(setter: React.Dispatch<React.SetStateAction<IncomeState>>, key: SourceKey, val: string) {
    setter(prev => ({ ...prev, sources: { ...prev.sources, [key]: val } }));
  }

  function buildOtherSources(): OtherIncomeSource[] {
    const result: OtherIncomeSource[] = [];
    const add = (inc: IncomeState, spouse: string, spouseName: string) => {
      for (const src of OTHER_INCOME_TYPES) {
        const amt = inc.sources[src.key];
        if (amt === undefined) continue;
        const amount = parseFloat(amt) || 0;
        if (amount <= 0) continue;
        let label = `${spouseName} — ${src.label}`;
        // Include linked entity name for K-1
        if (src.key === "k1" && inc.k1Entity) {
          label += ` (${inc.k1Entity})`;
        }
        result.push({
          label,
          type: src.otherType,
          amount,
          notes: spouse,
        });
      }
    };
    add(incomeA, "spouse_a", nameA || "Spouse A");
    if (married) add(incomeB, "spouse_b", nameB || "Spouse B");
    return result;
  }

  async function handleSave() {
    if (!filing) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const otherSources = buildOtherSources();
      const otherTotal = otherSources.reduce((sum, s) => sum + s.amount, 0);

      const body = {
        name: nameA ? `${nameA} Household` : "My Household",
        filing_status: filing,
        state: state || null,
        spouse_a_name: nameA || null,
        spouse_a_income: parseFloat(incomeA.w2) || 0,
        spouse_a_employer: incomeA.employer || null,
        spouse_b_name: married ? nameB || null : null,
        spouse_b_income: married ? parseFloat(incomeB.w2) || 0 : 0,
        spouse_b_employer: married ? incomeB.employer || null : null,
        other_income_sources_json: otherSources.length > 0 ? JSON.stringify(otherSources) : null,
        other_income_annual: otherTotal > 0 ? otherTotal : null,
        dependents_json: dependents > 0
          ? JSON.stringify(Array.from({ length: dependents }, (_, i) => ({ name: `Dependent ${i + 1}` })))
          : null,
      };
      if (existing) {
        await updateHouseholdProfile(existing.id, body);
      } else {
        await createHouseholdProfile(body);
      }
      setSaved(true);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 font-display">Tell us about your household</h2>
        <p className="text-sm text-stone-500 mt-0.5">
          This drives your tax optimization, W-4 recommendations, and filing strategy.
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: Tax Strategy &middot; W-4 Optimization &middot; Insurance Gap Analysis
        </p>
      </div>

      {/* Filing status */}
      <div>
        <label className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-2 block">
          Filing Status
        </label>
        <div className="grid grid-cols-2 gap-2">
          {FILING_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const selected = filing === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => setFiling(opt.value)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  selected
                    ? "border-[#16A34A] bg-green-50 ring-1 ring-[#16A34A]/20"
                    : "border-stone-200 hover:border-stone-300 bg-white"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon size={16} className={selected ? "text-[#16A34A]" : "text-stone-400"} />
                  <span className={`text-sm font-medium ${selected ? "text-[#16A34A]" : "text-stone-700"}`}>
                    {opt.label}
                  </span>
                </div>
                <p className="text-[11px] text-stone-400 mt-0.5 ml-6">{opt.desc}</p>
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() => askHenry("Based on my income and family situation, which filing status saves me the most in taxes?")}
          className="flex items-center gap-1 mt-2 text-[11px] text-[#16A34A] hover:underline"
        >
          <MessageCircle size={10} />
          Not sure which to pick? Ask Sir Henry
        </button>
      </div>

      {/* State */}
      <div>
        <label className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-1.5 block">
          State of Residence
        </label>
        <p className="text-[11px] text-stone-400 mb-2">
          Used for state tax brackets and deduction eligibility.
        </p>
        <select value={state} onChange={(e) => setState(e.target.value)} className={INPUT}>
          <option value="">Select state...</option>
          {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Spouse A — Income */}
      <IncomeCard
        title={married ? `${nameA || "Spouse A"} (Primary)` : "Your Income"}
        name={nameA}
        onNameChange={setNameA}
        namePlaceholder="First name"
        nameLabel={married ? "Spouse A (Primary)" : "Your Name"}
        income={incomeA}
        setIncome={setIncomeA}
        onToggle={(k) => toggleSource(setIncomeA, k)}
        onAmountChange={(k, v) => setSourceAmount(setIncomeA, k, v)}
        total={totalA}
        entities={data.entities}
        spouseKey="spouse_a"
      />

      {/* Spouse B — Income (married only) */}
      {married && (
        <IncomeCard
          title={nameB || "Spouse B"}
          name={nameB}
          onNameChange={setNameB}
          namePlaceholder="First name"
          nameLabel="Spouse B"
          income={incomeB}
          setIncome={setIncomeB}
          onToggle={(k) => toggleSource(setIncomeB, k)}
          onAmountChange={(k, v) => setSourceAmount(setIncomeB, k, v)}
          total={totalB}
          entities={data.entities}
          spouseKey="spouse_b"
        />
      )}

      {/* Household total */}
      {grandTotal > 0 && (
        <div className="bg-stone-50 rounded-lg px-4 py-3 flex justify-between items-center">
          <span className="text-sm text-stone-600">Household Total Income</span>
          <span className="text-base font-bold font-mono text-stone-900">
            ${grandTotal.toLocaleString()}
          </span>
        </div>
      )}

      {/* Dependents */}
      <div>
        <label className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-1.5 block">
          Number of Dependents
        </label>
        <p className="text-[11px] text-stone-400 mb-2">
          Children or qualifying relatives. Affects Child Tax Credit ($2,000/child), Dependent Care FSA, and 529 planning.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setDependents(Math.max(0, dependents - 1))}
            className="w-9 h-9 rounded-lg border border-stone-200 flex items-center justify-center text-stone-500 hover:border-stone-300 transition-colors"
          >
            -
          </button>
          <span className="text-lg font-semibold text-stone-900 font-mono w-6 text-center">
            {dependents}
          </span>
          <button
            onClick={() => setDependents(dependents + 1)}
            className="w-9 h-9 rounded-lg border border-stone-200 flex items-center justify-center text-stone-500 hover:border-stone-300 transition-colors"
          >
            +
          </button>
        </div>
      </div>

      {/* Save */}
      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}

      <button
        onClick={handleSave}
        disabled={!filing || saving}
        className="w-full flex items-center justify-center gap-2 bg-[#16A34A] text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm disabled:opacity-50 transition-colors"
      >
        {saving ? "Saving..." : saved ? (
          <><Check size={14} /> Saved</>
        ) : (
          <><Home size={14} /> {existing ? "Update" : "Save"} Household Profile</>
        )}
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Per-spouse income card                                            */
/* ------------------------------------------------------------------ */

interface IncomeCardProps {
  title: string;
  name: string;
  onNameChange: (v: string) => void;
  namePlaceholder: string;
  nameLabel: string;
  income: IncomeState;
  setIncome: React.Dispatch<React.SetStateAction<IncomeState>>;
  onToggle: (key: SourceKey) => void;
  onAmountChange: (key: SourceKey, val: string) => void;
  total: number;
  entities: { id: number; name: string; owner: string | null }[];
  spouseKey: string;
}

function IncomeCard({ name, onNameChange, namePlaceholder, nameLabel, income, setIncome, onToggle, onAmountChange, total, entities, spouseKey }: IncomeCardProps) {
  // Filter entities to those owned by this spouse (or unassigned)
  const relevantEntities = entities.filter(
    (e) => !e.owner || e.owner === spouseKey || e.owner === "both"
  );
  const [showOther, setShowOther] = useState(() => Object.keys(income.sources).length > 0);
  const hasW2 = (parseFloat(income.w2) || 0) > 0;
  const otherCount = Object.keys(income.sources).length;

  return (
    <Card padding="md" className="space-y-4">
      {/* Name */}
      <div>
        <label className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-1.5 block">
          {nameLabel}
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder={namePlaceholder}
          className={INPUT}
        />
      </div>

      {/* W-2 Salary — always visible */}
      <div>
        <label className="text-xs font-medium text-stone-600 uppercase tracking-wide mb-1 block">
          W-2 Salary
        </label>
        <p className="text-[11px] text-stone-400 mb-2">
          Wages from an employer paycheck. Drives W-4 withholding optimization and 401k contribution limits.
        </p>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
          <input
            type="number"
            value={income.w2}
            onChange={(e) => setIncome(prev => ({ ...prev, w2: e.target.value }))}
            placeholder="0"
            className={DOLLAR}
          />
        </div>
        {/* Employer name — shown when W-2 income exists */}
        {hasW2 && (
          <div className="mt-2">
            <input
              type="text"
              value={income.employer}
              onChange={(e) => setIncome(prev => ({ ...prev, employer: e.target.value }))}
              placeholder="Employer name (optional — pre-fills Benefits step)"
              className={INPUT + " text-stone-500"}
            />
          </div>
        )}
      </div>

      {/* Other income toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowOther(!showOther)}
          className="flex items-center gap-2 text-sm text-stone-600 hover:text-stone-900 transition-colors"
        >
          {showOther ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          <span className="font-medium">
            Other income sources
          </span>
          {otherCount > 0 && !showOther && (
            <span className="text-[11px] text-[#16A34A] bg-green-50 px-1.5 py-0.5 rounded-full">
              {otherCount} added
            </span>
          )}
        </button>

        {showOther && (
          <div className="mt-3 space-y-2">
            <p className="text-[11px] text-stone-400">
              Check any that apply. Each income type has different tax treatment.
            </p>
            {OTHER_INCOME_TYPES.map((src) => {
              const enabled = src.key in income.sources;
              return (
                <div key={src.key}>
                  <button
                    type="button"
                    onClick={() => onToggle(src.key)}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${
                      enabled
                        ? "border-[#16A34A] bg-green-50/50 ring-1 ring-[#16A34A]/10"
                        : "border-stone-200 hover:border-stone-300 bg-white"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                        enabled ? "bg-[#16A34A] border-[#16A34A]" : "border-stone-300"
                      }`}>
                        {enabled && <Check size={10} className="text-white" />}
                      </div>
                      <div>
                        <span className={`text-sm font-medium ${enabled ? "text-stone-900" : "text-stone-700"}`}>
                          {src.label}
                        </span>
                        <span className="text-[11px] text-stone-400 ml-1.5">
                          {src.desc}
                        </span>
                      </div>
                    </div>
                  </button>
                  {enabled && (
                    <div className="ml-6 mt-2 space-y-1.5">
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">$</span>
                        <input
                          type="number"
                          value={income.sources[src.key] || ""}
                          onChange={(e) => onAmountChange(src.key, e.target.value)}
                          placeholder="Annual amount"
                          className={DOLLAR + " max-w-xs"}
                          autoFocus
                        />
                      </div>
                      {/* Entity link for K-1 */}
                      {src.key === "k1" && relevantEntities.length > 0 && (
                        <select
                          value={income.k1Entity || ""}
                          onChange={(e) => setIncome(prev => ({ ...prev, k1Entity: e.target.value }))}
                          className={INPUT + " max-w-xs text-stone-500"}
                        >
                          <option value="">Link to business entity (optional)</option>
                          {relevantEntities.map((ent) => (
                            <option key={ent.id} value={ent.name}>{ent.name}</option>
                          ))}
                        </select>
                      )}
                      {src.key === "k1" && relevantEntities.length === 0 && (
                        <p className="text-[11px] text-stone-400">
                          You can link this to a business entity in the Business step.
                        </p>
                      )}
                      <p className="text-[11px] text-[#16A34A]/80 italic">{src.why}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Per-person total */}
      {total > 0 && (
        <div className="pt-3 border-t border-stone-100 flex justify-between items-center">
          <span className="text-xs text-stone-500">Total income</span>
          <span className="text-sm font-semibold font-mono text-stone-900">
            ${total.toLocaleString()}
          </span>
        </div>
      )}
    </Card>
  );
}
