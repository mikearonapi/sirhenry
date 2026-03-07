"use client";
import { useState, useEffect } from "react";
import {
  Check, ChevronDown, ChevronUp, Plus, Sparkles, MessageCircle,
  Building2, Briefcase,
} from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData, RegisterSaveFn } from "./SetupWizard";
import { createLifeEvent } from "@/lib/api-life-events";
import { createBusinessEntity } from "@/lib/api-entities";
import { getErrorMessage } from "@/lib/errors";
import SirHenryName from "@/components/ui/SirHenryName";
import { OB_INPUT, OB_HEADING, OB_SUBTITLE, OB_LABEL } from "./styles";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

// ── Life event categories ──
interface EventOption { type: string; subtype: string; label: string; impacts: string[]; }
interface EventCategory { key: string; label: string; icon: string; color: string; events: EventOption[]; }

const CATEGORIES: EventCategory[] = [
  {
    key: "employment", label: "Employment Changes", icon: "💼", color: "bg-amber-50 border-amber-100",
    events: [
      { type: "employment", subtype: "job_change", label: "Changed jobs", impacts: ["W-4 optimization", "401k rollover within 60 days"] },
      { type: "employment", subtype: "promotion", label: "Got a promotion / raise", impacts: ["Higher tax bracket planning"] },
      { type: "employment", subtype: "layoff", label: "Job loss / layoff", impacts: ["Severance is taxable", "COBRA deadline (60 days)"] },
      { type: "employment", subtype: "start_business", label: "Started a business", impacts: ["Self-employment tax (15.3%)", "Quarterly estimated payments"] },
      { type: "employment", subtype: "retirement", label: "Retired", impacts: ["RMD planning at 73+", "Medicare enrollment at 65"] },
    ],
  },
  {
    key: "family", label: "Family Changes", icon: "👨‍👩‍👧", color: "bg-pink-50 border-pink-100",
    events: [
      { type: "family", subtype: "marriage", label: "Got married", impacts: ["Filing status changes to MFJ", "W-4 recalculation"] },
      { type: "family", subtype: "birth", label: "Had a baby", impacts: ["Child Tax Credit ($2,000)", "Life insurance increase needed"] },
      { type: "family", subtype: "adoption", label: "Adopted a child", impacts: ["Adoption Tax Credit (up to $16,810)"] },
      { type: "family", subtype: "divorce", label: "Got divorced", impacts: ["Filing status reverts", "Beneficiary updates needed"] },
    ],
  },
  {
    key: "real_estate", label: "Real Estate", icon: "🏠", color: "bg-blue-50 border-blue-100",
    events: [
      { type: "real_estate", subtype: "purchase", label: "Bought a home", impacts: ["Mortgage interest deduction", "Property tax deduction (SALT cap $10k)"] },
      { type: "real_estate", subtype: "sale", label: "Sold a home", impacts: ["Capital gains exclusion ($250k/$500k MFJ)"] },
      { type: "real_estate", subtype: "rental", label: "Started renting out property", impacts: ["Rental income on Schedule E", "Depreciation deductions"] },
      { type: "real_estate", subtype: "refinance", label: "Refinanced mortgage", impacts: ["Points amortized over loan term"] },
    ],
  },
  {
    key: "education", label: "Education", icon: "🎓", color: "bg-green-50 border-green-100",
    events: [
      { type: "education", subtype: "529_open", label: "Opened a 529 account", impacts: ["State tax deduction", "Tax-free growth for education"] },
      { type: "education", subtype: "college", label: "Child started college", impacts: ["American Opportunity Credit (up to $2,500/yr)"] },
    ],
  },
  {
    key: "estate", label: "Estate & Gifts", icon: "📜", color: "bg-purple-50 border-purple-100",
    events: [
      { type: "estate", subtype: "inheritance", label: "Received an inheritance", impacts: ["Step-up in cost basis", "Inherited IRA 10-year rule"] },
      { type: "estate", subtype: "gift", label: "Made a large gift", impacts: ["Annual exclusion: $19,000/person", "Form 709 if over exclusion"] },
    ],
  },
  {
    key: "medical", label: "Major Medical", icon: "🏥", color: "bg-red-50 border-red-100",
    events: [
      { type: "medical", subtype: "major", label: "Major medical event", impacts: ["Medical deduction if > 7.5% of AGI", "HSA reimbursement"] },
    ],
  },
];

// ── Business entity types ──
const ENTITY_TYPES = [
  { value: "sole_proprietorship", label: "Sole Proprietorship", desc: "Schedule C — simplest, full SE tax (15.3%)" },
  { value: "single_member_llc", label: "Single-Member LLC", desc: "Disregarded entity — same tax as sole prop, liability protection" },
  { value: "multi_member_llc", label: "Multi-Member LLC", desc: "Partnership return (Form 1065) — K-1 distributions" },
  { value: "s_corp", label: "S-Corporation", desc: "Payroll + distributions — can save SE tax at $40k+ profit" },
  { value: "c_corp", label: "C-Corporation", desc: "Corporate return (Form 1120) — double taxation but capital deferral" },
  { value: "personal", label: "Personal", desc: "Track personal expenses separately from business" },
];

interface Props {
  data: SetupData;
  onRefresh: () => void;
  registerSave?: RegisterSaveFn;
}

export default function StepLifeBusiness({ data, onRefresh, registerSave }: Props) {
  const household = data.household;
  const married = household?.filing_status === "mfj" || household?.filing_status === "mfs";

  // ── Life events state ──
  const [expanded, setExpanded] = useState<string | null>(null);
  const [addedEvents, setAddedEvents] = useState<string[]>([]);
  const [eventSaving, setEventSaving] = useState<string | null>(null);

  // ── Business state ──
  const [hasBusiness, setHasBusiness] = useState<boolean | null>(
    data.entities.length > 0 ? true : null
  );
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState("");
  const [owner, setOwner] = useState<string>("");
  const [savedEntities, setSavedEntities] = useState<string[]>([]);
  const [bizSaving, setBizSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const existingEventKeys = new Set(
    data.lifeEvents.map((e) => `${e.event_type}:${e.event_subtype}`)
  );

  async function handleAddEvent(event: EventOption) {
    const key = `${event.type}:${event.subtype}`;
    setEventSaving(key);
    setError(null);
    try {
      const today = new Date().toISOString().split("T")[0];
      await createLifeEvent({
        event_type: event.type, event_subtype: event.subtype,
        title: event.label, event_date: today, tax_year: new Date().getFullYear(),
        status: "completed", household_id: household?.id ?? null,
      });
      setAddedEvents([...addedEvents, key]);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setEventSaving(null);
    }
  }

  const isEventAdded = (type: string, subtype: string) => {
    const key = `${type}:${subtype}`;
    return existingEventKeys.has(key) || addedEvents.includes(key);
  };

  async function handleSaveBusiness() {
    if (!name) return;
    setBizSaving(true);
    setError(null);
    try {
      await createBusinessEntity({
        name, entity_type: entityType || "sole_proprietorship",
        tax_treatment: entityType === "s_corp" ? "s_corp" : entityType === "c_corp" ? "c_corp" : "pass_through",
        owner: owner || null,
      });
      setSavedEntities([...savedEntities, name]);
      setName(""); setEntityType(""); setOwner(""); setShowForm(false);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
      throw e;
    } finally {
      setBizSaving(false);
    }
  }

  useEffect(() => {
    if (registerSave) registerSave(name.trim() ? handleSaveBusiness : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registerSave, name, entityType, owner]);

  return (
    <div className="space-y-8">
      <div>
        <h2 className={OB_HEADING}>Life events & business</h2>
        <p className={OB_SUBTITLE}>
          Recent life changes and business income create tax and planning opportunities.
        </p>
      </div>

      {/* ── Section 1: Life Events ── */}
      <div className="space-y-4">
        <h3 className="text-base font-semibold text-text-primary">Recent Life Events</h3>
        <p className="text-sm text-text-secondary -mt-2">
          Select anything from the last 1-2 years. Each generates tax action items.
        </p>

        <div className="space-y-2">
          {CATEGORIES.map((cat) => {
            const isExpanded = expanded === cat.key;
            const catEventCount = cat.events.filter((e) => isEventAdded(e.type, e.subtype)).length;
            return (
              <div key={cat.key}>
                <button
                  onClick={() => setExpanded(isExpanded ? null : cat.key)}
                  className={`w-full p-3 rounded-xl border-2 transition-all text-left flex items-center gap-3 ${
                    catEventCount > 0
                      ? "border-accent/20 bg-green-50/30"
                      : "border-border bg-card hover:border-border"
                  }`}
                >
                  <span className="text-lg">{cat.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text-primary">{cat.label}</span>
                      {catEventCount > 0 && (
                        <span className="text-xs font-medium text-accent bg-green-100 px-1.5 py-0.5 rounded">
                          {catEventCount} logged
                        </span>
                      )}
                    </div>
                  </div>
                  {isExpanded ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
                </button>
                {isExpanded && (
                  <div className="ml-4 mt-1 space-y-1.5 mb-2">
                    {cat.events.map((event) => {
                      const key = `${event.type}:${event.subtype}`;
                      const added = isEventAdded(event.type, event.subtype);
                      const isSaving = eventSaving === key;
                      return (
                        <div key={key} className={`p-3 rounded-xl border-2 transition-all ${
                          added ? "border-accent/20 bg-green-50/50" : "border-border bg-card"
                        }`}>
                          <div className="flex items-start gap-2">
                            <div className="flex-1">
                              <p className="text-sm font-medium text-text-secondary">{event.label}</p>
                              <div className="mt-1 space-y-0.5">
                                {event.impacts.map((impact, i) => (
                                  <p key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
                                    <span className="text-text-muted mt-0.5">&#8226;</span>
                                    {impact}
                                  </p>
                                ))}
                              </div>
                            </div>
                            {added ? (
                              <div className="flex items-center gap-1 text-accent">
                                <Check size={14} />
                                <span className="text-xs font-medium">Logged</span>
                              </div>
                            ) : (
                              <button onClick={() => handleAddEvent(event)} disabled={isSaving}
                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface text-xs font-medium text-text-secondary hover:bg-surface-hover disabled:opacity-50 transition-colors flex-shrink-0">
                                {isSaving ? "..." : <><Plus size={12} /> Log</>}
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-xs text-text-muted">
          Nothing recent? No problem — skip this section.
        </p>
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* ── Section 2: Business ── */}
      <div className="space-y-5">
        <h3 className="text-base font-semibold text-text-primary">Business Income</h3>

        {/* Gate question */}
        {hasBusiness === null && data.entities.length === 0 && (
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => { setHasBusiness(true); setShowForm(true); }}
              className="p-5 rounded-xl border-2 border-border hover:border-accent hover:bg-green-50/50 transition-all text-center"
            >
              <Briefcase size={24} className="mx-auto text-text-muted mb-2" />
              <p className="text-sm font-semibold text-text-secondary">Yes, I have business income</p>
              <p className="text-xs text-text-muted mt-1">Freelance, consulting, LLC, etc.</p>
            </button>
            <button
              onClick={() => setHasBusiness(false)}
              className="p-5 rounded-xl border-2 border-border hover:border-border transition-all text-center"
            >
              <Building2 size={24} className="mx-auto text-text-muted mb-2" />
              <p className="text-sm font-semibold text-text-secondary">No business income</p>
              <p className="text-xs text-text-muted mt-1">W-2 employment only</p>
            </button>
          </div>
        )}

        {hasBusiness === false && data.entities.length === 0 && (
          <Card padding="md" className="text-center">
            <Check size={24} className="mx-auto text-accent mb-2" />
            <p className="text-sm text-text-secondary">No business entities needed.</p>
            <button onClick={() => { setHasBusiness(true); setShowForm(true); }}
              className="mt-2 text-xs text-accent hover:underline">
              Actually, I do have business income
            </button>
          </Card>
        )}

        {/* Existing entities */}
        {(data.entities.length > 0 || savedEntities.length > 0) && (
          <div className="space-y-1.5">
            {data.entities.map((e) => (
              <div key={e.id} className="flex items-center justify-between py-2 px-3 rounded-xl bg-surface">
                <div className="flex items-center gap-2">
                  <Building2 size={14} className="text-accent" />
                  <span className="text-sm text-text-secondary">{e.name}</span>
                  <span className="text-xs text-text-muted bg-border/50 px-1.5 py-0.5 rounded">{e.entity_type}</span>
                </div>
                <Check size={14} className="text-accent" />
              </div>
            ))}
            {savedEntities.filter((n) => !data.entities.some((e) => e.name === n)).map((n, i) => (
              <div key={`new-${i}`} className="flex items-center gap-2 py-2 px-3 rounded-xl bg-surface">
                <Building2 size={14} className="text-accent" />
                <span className="text-sm text-text-secondary">{n}</span>
                <Check size={14} className="text-accent" />
              </div>
            ))}
          </div>
        )}

        {/* Add entity form */}
        {showForm && (
          <Card padding="md" className="space-y-4">
            <input type="text" value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Business name (e.g. Smith Consulting LLC)" className={OB_INPUT} autoFocus />
            <div>
              <label className={OB_LABEL}>Entity Type</label>
              <div className="space-y-1.5">
                {ENTITY_TYPES.map((et) => {
                  const selected = entityType === et.value;
                  return (
                    <button key={et.value} onClick={() => setEntityType(et.value)}
                      className={`w-full p-3 rounded-xl text-left transition-all ${
                        selected ? "border-2 border-accent bg-green-50 ring-1 ring-accent/20"
                          : "border-2 border-border hover:border-border"
                      }`}>
                      <span className={`text-sm font-medium ${selected ? "text-accent" : "text-text-secondary"}`}>{et.label}</span>
                      <p className="text-xs text-text-muted mt-0.5">{et.desc}</p>
                    </button>
                  );
                })}
              </div>
              <button type="button"
                onClick={() => askHenry("I'm starting a business. Based on my income level, should I form an LLC, S-Corp, or sole proprietorship?")}
                className="flex items-center gap-1 mt-2 text-xs text-accent hover:underline">
                <MessageCircle size={10} />
                Need help choosing? Ask <SirHenryName />
              </button>
            </div>
            {married && (
              <div>
                <label className={OB_LABEL}>Owner</label>
                <div className="flex gap-2">
                  {[
                    { value: "spouse_a", label: household?.spouse_a_name || "Spouse A" },
                    { value: "spouse_b", label: household?.spouse_b_name || "Spouse B" },
                    { value: "both", label: "Both" },
                  ].map((opt) => (
                    <button key={opt.value} onClick={() => setOwner(opt.value)}
                      className={`flex-1 py-2.5 px-3 rounded-xl text-sm font-medium border-2 transition-all ${
                        owner === opt.value ? "border-accent bg-green-50 text-accent" : "border-border text-text-secondary hover:border-border"
                      }`}>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <button onClick={handleSaveBusiness} disabled={!name || bizSaving}
                className="flex items-center gap-1.5 bg-accent text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors">
                {bizSaving ? "Saving..." : <><Plus size={14} /> Add Entity</>}
              </button>
              <button onClick={() => setShowForm(false)}
                className="px-4 py-2.5 text-sm text-text-secondary hover:text-text-secondary transition-colors">
                Cancel
              </button>
            </div>
          </Card>
        )}

        {hasBusiness && !showForm && (
          <button onClick={() => setShowForm(true)}
            className="flex items-center gap-2 w-full p-4 rounded-xl border-2 border-dashed border-border text-sm text-text-secondary hover:border-border hover:text-text-secondary transition-colors">
            <Plus size={14} /> Add another entity
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{error}</p>}
    </div>
  );
}
