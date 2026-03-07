"use client";
import { useState, useEffect } from "react";
import {
  User, Users, UserCheck, Check, ChevronDown, ChevronUp, MessageCircle, ArrowLeft,
} from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData, RegisterSaveFn } from "./SetupWizard";
import type { OtherIncomeSource, OtherIncomeType } from "@/types/household";
import {
  createHouseholdProfile, updateHouseholdProfile,
  getFamilyMembers, createFamilyMember, updateFamilyMember,
} from "@/lib/api-household";
import { getErrorMessage } from "@/lib/errors";
import SirHenryName from "@/components/ui/SirHenryName";
import { OB_INPUT, OB_DOLLAR, OB_SELECT, OB_HEADING, OB_SUBTITLE, OB_LABEL } from "./styles";

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

const OTHER_INCOME_TYPES = [
  {
    key: "k1" as const,
    otherType: "partnership_k1" as OtherIncomeType,
    label: "K-1 / Business",
    desc: "S-Corp, LLC, or partnership distributions",
  },
  {
    key: "1099" as const,
    otherType: "business_1099" as OtherIncomeType,
    label: "1099 / Self-Employment",
    desc: "Freelance, consulting, or contract work",
  },
  {
    key: "rental" as const,
    otherType: "rental" as OtherIncomeType,
    label: "Rental Income",
    desc: "Investment property income (Schedule E)",
  },
  {
    key: "other" as const,
    otherType: "other" as OtherIncomeType,
    label: "Other Income",
    desc: "Dividends, interest, pension, etc.",
  },
];

type SourceKey = "k1" | "1099" | "rental" | "other";

interface IncomeState {
  w2: string;
  employer: string;
  sources: Partial<Record<SourceKey, string>>;
  k1Entity: string;
}

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
  registerSave?: RegisterSaveFn;
}

export default function StepAboutYou({ data, onRefresh, registerSave }: Props) {
  const existing = data.household;

  const [subStep, setSubStep] = useState<"personal" | "income">(() => {
    // Auto-advance to Part B if returning user already has personal data
    if (existing?.filing_status && existing.spouse_a_name) return "income";
    return "personal";
  });
  const [filing, setFiling] = useState(existing?.filing_status || "");
  const [state, setState] = useState(existing?.state || "");
  const [nameA, setNameA] = useState(existing?.spouse_a_name || "");
  const [nameB, setNameB] = useState(existing?.spouse_b_name || "");
  const [preferredName, setPreferredName] = useState(existing?.spouse_a_preferred_name || "");
  const [dobA, setDobA] = useState("");
  const [dobB, setDobB] = useState("");
  const [familyMemberSelfId, setFamilyMemberSelfId] = useState<number | null>(null);
  const [familyMemberSpouseId, setFamilyMemberSpouseId] = useState<number | null>(null);

  // Load existing FamilyMember records for DOB pre-fill
  useEffect(() => {
    if (!existing?.id) return;
    getFamilyMembers(existing.id).then((members) => {
      const self = members.find((m) => m.relationship === "self");
      const spouse = members.find((m) => m.relationship === "spouse");
      if (self) {
        setFamilyMemberSelfId(self.id);
        if (self.date_of_birth) setDobA(self.date_of_birth);
      }
      if (spouse) {
        setFamilyMemberSpouseId(spouse.id);
        if (spouse.date_of_birth) setDobB(spouse.date_of_birth);
      }
    }).catch(() => {});
  }, [existing?.id]);

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
        if (src.key === "k1" && inc.k1Entity) {
          label += ` (${inc.k1Entity})`;
        }
        result.push({ label, type: src.otherType, amount, notes: spouse });
      }
    };
    add(incomeA, "spouse_a", nameA || "Spouse A");
    if (married) add(incomeB, "spouse_b", nameB || "Spouse B");
    return result;
  }

  async function handleSave() {
    if (!filing) return;
    setError(null);
    try {
      const otherSources = buildOtherSources();
      const otherTotal = otherSources.reduce((sum, s) => sum + s.amount, 0);

      const body = {
        name: nameA ? `${nameA} Household` : "My Household",
        filing_status: filing,
        state: state || null,
        spouse_a_name: nameA || null,
        spouse_a_preferred_name: preferredName || null,
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
      let householdId: number;
      if (existing) {
        await updateHouseholdProfile(existing.id, body);
        householdId = existing.id;
      } else {
        const created = await createHouseholdProfile(body);
        householdId = created.id;
      }

      // Create or update FamilyMember records for DOB + earner data
      const selfData = {
        household_id: householdId,
        name: nameA || "Primary",
        relationship: "self" as const,
        date_of_birth: dobA || null,
        is_earner: true,
        income: parseFloat(incomeA.w2) || null,
        employer: incomeA.employer || null,
      };
      if (familyMemberSelfId) {
        await updateFamilyMember(familyMemberSelfId, selfData).catch(() => {});
      } else if (nameA) {
        const created = await createFamilyMember(selfData).catch(() => null);
        if (created) setFamilyMemberSelfId(created.id);
      }

      if (married && nameB) {
        const spouseData = {
          household_id: householdId,
          name: nameB,
          relationship: "spouse" as const,
          date_of_birth: dobB || null,
          is_earner: (parseFloat(incomeB.w2) || 0) > 0,
          income: parseFloat(incomeB.w2) || null,
          employer: incomeB.employer || null,
        };
        if (familyMemberSpouseId) {
          await updateFamilyMember(familyMemberSpouseId, spouseData).catch(() => {});
        } else {
          const created = await createFamilyMember(spouseData).catch(() => null);
          if (created) setFamilyMemberSpouseId(created.id);
        }
      }

      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
      throw e;
    }
  }

  useEffect(() => {
    if (!registerSave) return;

    if (subStep === "personal") {
      // Part A: validate filing status, then advance to Part B (throw to prevent wizard advancement)
      registerSave(filing ? async () => {
        setSubStep("income");
        throw new Error("__substep__");
      } : null);
    } else {
      // Part B: do the real API save
      registerSave(filing ? handleSave : null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registerSave, subStep, filing, nameA, nameB, state, incomeA, incomeB, dependents, preferredName, dobA, dobB]);

  return (
    <div className="space-y-8">
      {/* Sub-step indicator */}
      <div className="flex items-center justify-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full transition-colors ${subStep === "personal" ? "bg-accent" : "bg-accent/30"}`} />
          <span className={`text-xs transition-colors ${subStep === "personal" ? "text-accent font-medium" : "text-text-muted"}`}>Personal</span>
        </div>
        <div className="w-6 h-px bg-border" />
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full transition-colors ${subStep === "income" ? "bg-accent" : "bg-accent/30"}`} />
          <span className={`text-xs transition-colors ${subStep === "income" ? "text-accent font-medium" : "text-text-muted"}`}>Income</span>
        </div>
      </div>

      {/* ── Part A: Personal Info ──────────────────────────── */}
      {subStep === "personal" && (
        <>
          <div>
            <h2 className={OB_HEADING}>Tell us about you</h2>
            <p className={OB_SUBTITLE}>
              Filing status drives your tax strategy, W-4 optimization, and retirement projections.
            </p>
          </div>

          {/* Filing status */}
          <div>
            <label className={OB_LABEL}>Filing Status</label>
            <div className="grid grid-cols-2 gap-3">
              {FILING_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const selected = filing === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setFiling(opt.value)}
                    className={`p-4 rounded-xl text-left transition-all ${
                      selected
                        ? "border-2 border-accent bg-green-50 ring-1 ring-accent/20"
                        : "border-2 border-border hover:border-border bg-card"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon size={18} className={selected ? "text-accent" : "text-text-muted"} />
                      <span className={`text-sm font-semibold ${selected ? "text-text-primary" : "text-text-secondary"}`}>
                        {opt.label}
                      </span>
                    </div>
                    <p className="text-xs text-text-muted mt-1 ml-[30px]">{opt.desc}</p>
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => askHenry("Based on my income and family situation, which filing status saves me the most in taxes?")}
              className="flex items-center gap-1 mt-2.5 text-xs text-accent hover:underline"
            >
              <MessageCircle size={10} />
              Not sure? Ask <SirHenryName />
            </button>
          </div>

          {/* Name + Preferred Name row */}
          {filing && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={OB_LABEL}>Your Name</label>
                <input
                  type="text"
                  value={nameA}
                  onChange={(e) => setNameA(e.target.value)}
                  placeholder="Full legal name"
                  className={OB_INPUT}
                />
              </div>
              <div>
                <label className={OB_LABEL}>What should we call you?</label>
                <input
                  type="text"
                  value={preferredName}
                  onChange={(e) => setPreferredName(e.target.value)}
                  placeholder="e.g. Mike"
                  className={OB_INPUT}
                />
                <p className="text-xs text-text-muted mt-1">How <SirHenryName /> will address you in chat</p>
              </div>
            </div>
          )}

          {/* State + DOB row */}
          {filing && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={OB_LABEL}>State</label>
                <select value={state} onChange={(e) => setState(e.target.value)} className={OB_SELECT}>
                  <option value="">Select state...</option>
                  {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className={OB_LABEL}>Date of Birth</label>
                <input
                  type="date"
                  value={dobA}
                  onChange={(e) => setDobA(e.target.value)}
                  className={OB_INPUT}
                />
                <p className="text-xs text-text-muted mt-1">For retirement projections and milestone planning</p>
              </div>
            </div>
          )}

          {/* Spouse B name + DOB */}
          {married && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={OB_LABEL}>Spouse&apos;s Name</label>
                <input
                  type="text"
                  value={nameB}
                  onChange={(e) => setNameB(e.target.value)}
                  placeholder="Spouse full name"
                  className={OB_INPUT}
                />
              </div>
              <div>
                <label className={OB_LABEL}>Spouse&apos;s Date of Birth</label>
                <input
                  type="date"
                  value={dobB}
                  onChange={(e) => setDobB(e.target.value)}
                  className={OB_INPUT}
                />
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Part B: Income & Employment ────────────────────── */}
      {subStep === "income" && (
        <>
          <div>
            <div className="flex items-center justify-between">
              <div>
                <h2 className={OB_HEADING}>Income &amp; Employment</h2>
                <p className={OB_SUBTITLE}>
                  Your income determines contribution limits, tax bracket, and savings projections.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSubStep("personal")}
                className="text-xs text-accent hover:underline flex items-center gap-1"
              >
                <ArrowLeft size={12} />
                Back to Personal
              </button>
            </div>
          </div>

          {/* Income — Spouse A */}
          <IncomeCard
            label={married ? (nameA || "Your") + " Income" : "Your Income"}
            income={incomeA}
            setIncome={setIncomeA}
            onToggle={(k) => toggleSource(setIncomeA, k)}
            onAmountChange={(k, v) => setSourceAmount(setIncomeA, k, v)}
            total={totalA}
            entities={data.entities}
            spouseKey="spouse_a"
          />

          {/* Income — Spouse B */}
          {married && (
            <IncomeCard
              label={(nameB || "Spouse") + "'s Income"}
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
            <div className="bg-surface rounded-xl px-5 py-4 flex justify-between items-center">
              <span className="text-sm font-medium text-text-secondary">Household Total</span>
              <span className="text-lg font-bold font-mono text-text-primary">
                ${grandTotal.toLocaleString()}
              </span>
            </div>
          )}

          {/* Dependents */}
          <div>
            <label className={OB_LABEL}>Dependents</label>
            <p className="text-xs text-text-muted mb-3">
              Affects Child Tax Credit ($2,000/child), Dependent Care FSA, and 529 planning.
            </p>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setDependents(Math.max(0, dependents - 1))}
                className="w-10 h-10 rounded-xl border-2 border-border flex items-center justify-center text-text-secondary hover:border-border transition-colors text-lg"
              >
                &minus;
              </button>
              <span className="text-xl font-bold text-text-primary font-mono w-8 text-center">
                {dependents}
              </span>
              <button
                onClick={() => setDependents(dependents + 1)}
                className="w-10 h-10 rounded-xl border-2 border-border flex items-center justify-center text-text-secondary hover:border-border transition-colors text-lg"
              >
                +
              </button>
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{error}</p>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Per-spouse income card                                            */
/* ------------------------------------------------------------------ */

interface IncomeCardProps {
  label: string;
  income: IncomeState;
  setIncome: React.Dispatch<React.SetStateAction<IncomeState>>;
  onToggle: (key: SourceKey) => void;
  onAmountChange: (key: SourceKey, val: string) => void;
  total: number;
  entities: { id: number; name: string; owner: string | null }[];
  spouseKey: string;
}

function IncomeCard({ label, income, setIncome, onToggle, onAmountChange, total, entities, spouseKey }: IncomeCardProps) {
  const relevantEntities = entities.filter(
    (e) => !e.owner || e.owner === spouseKey || e.owner === "both"
  );
  const [showOther, setShowOther] = useState(() => Object.keys(income.sources).length > 0);
  const hasW2 = (parseFloat(income.w2) || 0) > 0;
  const otherCount = Object.keys(income.sources).length;

  return (
    <Card padding="md" className="space-y-5">
      <p className="text-sm font-semibold text-text-primary">{label}</p>

      {/* W-2 Salary */}
      <div>
        <label className={OB_LABEL}>W-2 Salary</label>
        <div className="relative">
          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
          <input
            type="number"
            value={income.w2}
            onChange={(e) => setIncome(prev => ({ ...prev, w2: e.target.value }))}
            placeholder="0"
            className={OB_DOLLAR}
          />
        </div>
        {hasW2 && (
          <input
            type="text"
            value={income.employer}
            onChange={(e) => setIncome(prev => ({ ...prev, employer: e.target.value }))}
            placeholder="Employer name (optional)"
            className={`${OB_INPUT} mt-3 text-text-secondary`}
          />
        )}
      </div>

      {/* Other income toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowOther(!showOther)}
          className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          {showOther ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          <span className="font-medium">Other income sources</span>
          {otherCount > 0 && !showOther && (
            <span className="text-xs text-accent bg-green-50 px-2 py-0.5 rounded-full">
              {otherCount} added
            </span>
          )}
        </button>

        {showOther && (
          <div className="mt-3 space-y-2">
            {OTHER_INCOME_TYPES.map((src) => {
              const enabled = src.key in income.sources;
              return (
                <div key={src.key}>
                  <button
                    type="button"
                    onClick={() => onToggle(src.key)}
                    className={`w-full p-3 rounded-xl border-2 text-left transition-all ${
                      enabled
                        ? "border-accent bg-green-50 ring-1 ring-accent/20"
                        : "border-border hover:border-border bg-card"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                        enabled ? "bg-accent border-accent" : "border-text-muted"
                      }`}>
                        {enabled && <Check size={10} className="text-white" />}
                      </div>
                      <div>
                        <span className={`text-sm font-medium ${enabled ? "text-text-primary" : "text-text-secondary"}`}>
                          {src.label}
                        </span>
                        <span className="text-xs text-text-muted ml-1.5">{src.desc}</span>
                      </div>
                    </div>
                  </button>
                  {enabled && (
                    <div className="ml-6 mt-2 space-y-2">
                      <div className="relative">
                        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
                        <input
                          type="number"
                          value={income.sources[src.key] || ""}
                          onChange={(e) => onAmountChange(src.key, e.target.value)}
                          placeholder="Annual amount"
                          className={`${OB_DOLLAR} max-w-xs`}
                          autoFocus
                        />
                      </div>
                      {src.key === "k1" && relevantEntities.length > 0 && (
                        <select
                          value={income.k1Entity || ""}
                          onChange={(e) => setIncome(prev => ({ ...prev, k1Entity: e.target.value }))}
                          className={`${OB_INPUT} max-w-xs text-text-secondary`}
                        >
                          <option value="">Link to business entity (optional)</option>
                          {relevantEntities.map((ent) => (
                            <option key={ent.id} value={ent.name}>{ent.name}</option>
                          ))}
                        </select>
                      )}
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
        <div className="pt-4 border-t border-card-border flex justify-between items-center">
          <span className="text-xs text-text-secondary">Total income</span>
          <span className="text-sm font-bold font-mono text-text-primary">
            ${total.toLocaleString()}
          </span>
        </div>
      )}
    </Card>
  );
}
