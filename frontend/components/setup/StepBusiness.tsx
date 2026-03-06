"use client";
import { useState } from "react";
import { Building2, Check, Plus, Briefcase, MessageCircle } from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData } from "./SetupWizard";
import { createBusinessEntity } from "@/lib/api-entities";
import { getErrorMessage } from "@/lib/errors";
import SirHenryName from "@/components/ui/SirHenryName";

const INPUT = "w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#16A34A]/30 focus:border-[#16A34A] bg-white";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

const ENTITY_TYPES = [
  { value: "sole_proprietorship", label: "Sole Proprietorship", desc: "Schedule C — simplest, but full SE tax (15.3%)" },
  { value: "single_member_llc", label: "Single-Member LLC", desc: "Disregarded entity — same tax as sole prop, with liability protection" },
  { value: "multi_member_llc", label: "Multi-Member LLC", desc: "Partnership return (Form 1065) — K-1 distributions" },
  { value: "s_corp", label: "S-Corporation", desc: "Payroll + distributions — can save SE tax at $40k+ profit" },
  { value: "c_corp", label: "C-Corporation", desc: "Corporate return (Form 1120) — double taxation but capital deferral" },
  { value: "personal", label: "Personal", desc: "Track personal expenses separately from business" },
];

interface Props {
  data: SetupData;
  onRefresh: () => void;
}

export default function StepBusiness({ data, onRefresh }: Props) {
  const household = data.household;
  const married = household?.filing_status === "mfj" || household?.filing_status === "mfs";
  const [hasBusiness, setHasBusiness] = useState<boolean | null>(
    data.entities.length > 0 ? true : null
  );
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState("");
  const [owner, setOwner] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [savedEntities, setSavedEntities] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name) return;
    setSaving(true);
    setError(null);
    try {
      await createBusinessEntity({
        name,
        entity_type: entityType || "sole_proprietorship",
        tax_treatment: entityType === "s_corp" ? "s_corp" : entityType === "c_corp" ? "c_corp" : "pass_through",
        owner: owner || null,
      });
      setSavedEntities([...savedEntities, name]);
      setName("");
      setEntityType("");
      setOwner("");
      setShowForm(false);
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
        <h2 className="text-lg font-semibold text-stone-900 font-display">Business entities</h2>
        <p className="text-sm text-stone-500 mt-0.5">
          If you have business income (freelance, consulting, LLC, S-Corp), tracking it separately
          enables Schedule C optimization, SE tax planning, and entity-level reporting.
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: Business Expense Tracking &middot; Schedule C/K-1 Tax Planning
        </p>
      </div>

      {/* Initial question */}
      {hasBusiness === null && data.entities.length === 0 && (
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => { setHasBusiness(true); setShowForm(true); }}
            className="p-4 rounded-lg border border-stone-200 hover:border-[#16A34A] hover:bg-green-50/50 transition-all text-center"
          >
            <Briefcase size={24} className="mx-auto text-stone-400 mb-2" />
            <p className="text-sm font-medium text-stone-700">Yes, I have business income</p>
            <p className="text-[11px] text-stone-400 mt-1">Freelance, consulting, LLC, etc.</p>
          </button>
          <button
            onClick={() => setHasBusiness(false)}
            className="p-4 rounded-lg border border-stone-200 hover:border-stone-300 transition-all text-center"
          >
            <Building2 size={24} className="mx-auto text-stone-300 mb-2" />
            <p className="text-sm font-medium text-stone-700">No business income</p>
            <p className="text-[11px] text-stone-400 mt-1">W-2 employment only</p>
          </button>
        </div>
      )}

      {/* No business */}
      {hasBusiness === false && data.entities.length === 0 && (
        <Card padding="md" className="text-center">
          <Check size={24} className="mx-auto text-[#16A34A] mb-2" />
          <p className="text-sm text-stone-600">No business entities needed.</p>
          <p className="text-[11px] text-stone-400 mt-1">
            If you start freelancing or form a business later, you can add entities from the{" "}
            <a href="/business" className="text-[#16A34A] hover:underline">Business page</a>.
          </p>
          <button
            onClick={() => { setHasBusiness(true); setShowForm(true); }}
            className="mt-3 text-xs text-[#16A34A] hover:underline"
          >
            Actually, I do have business income
          </button>
          <button
            type="button"
            onClick={() => askHenry("I'm thinking about starting a business. Based on my income and tax situation, what structure would you recommend and what steps do I need to take?")}
            className="flex items-center gap-1 mt-2 mx-auto text-[11px] text-[#16A34A]/70 hover:underline"
          >
            <MessageCircle size={10} />
            Thinking about starting one? Ask <SirHenryName />
          </button>
        </Card>
      )}

      {/* Existing entities */}
      {(data.entities.length > 0 || savedEntities.length > 0) && (
        <Card padding="md">
          <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-2">
            Your entities
          </p>
          <div className="space-y-2">
            {data.entities.map((e) => (
              <div key={e.id} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2">
                  <Building2 size={14} className="text-[#16A34A]" />
                  <span className="text-sm text-stone-700">{e.name}</span>
                  <span className="text-[10px] text-stone-400 bg-stone-100 px-1.5 py-0.5 rounded">
                    {e.entity_type}
                  </span>
                  {e.owner && (
                    <span className="text-[10px] text-[#16A34A] bg-green-50 px-1.5 py-0.5 rounded">
                      {e.owner === "spouse_a" ? (household?.spouse_a_name || "Spouse A")
                        : e.owner === "spouse_b" ? (household?.spouse_b_name || "Spouse B")
                        : "Both"}
                    </span>
                  )}
                </div>
                <Check size={14} className="text-[#16A34A]" />
              </div>
            ))}
            {savedEntities.filter((n) => !data.entities.some((e) => e.name === n)).map((n, i) => (
              <div key={`new-${i}`} className="flex items-center gap-2 py-1.5">
                <Building2 size={14} className="text-[#16A34A]" />
                <span className="text-sm text-stone-700">{n}</span>
                <Check size={14} className="text-[#16A34A]" />
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Add form */}
      {showForm && (
        <Card padding="md" className="space-y-3">
          <p className="text-xs font-medium text-stone-600 uppercase tracking-wide">
            Add Business Entity
          </p>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Business name (e.g. Smith Consulting LLC)"
            className={INPUT}
            autoFocus
          />
          <div>
            <label className="text-xs text-stone-500 mb-1.5 block">Entity Type</label>
            <div className="space-y-1.5">
              {ENTITY_TYPES.map((et) => {
                const selected = entityType === et.value;
                return (
                  <button
                    key={et.value}
                    onClick={() => setEntityType(et.value)}
                    className={`w-full p-2.5 rounded-lg border text-left transition-all ${
                      selected
                        ? "border-[#16A34A] bg-green-50 ring-1 ring-[#16A34A]/20"
                        : "border-stone-200 hover:border-stone-300"
                    }`}
                  >
                    <span className={`text-sm font-medium ${selected ? "text-[#16A34A]" : "text-stone-700"}`}>
                      {et.label}
                    </span>
                    <p className="text-[11px] text-stone-400 mt-0.5">{et.desc}</p>
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => askHenry("I'm starting a business. Based on my income level and tax situation, should I form an LLC, S-Corp, or sole proprietorship? What are the tax implications of each?")}
              className="flex items-center gap-1 mt-2 text-[11px] text-[#16A34A] hover:underline"
            >
              <MessageCircle size={10} />
              Need help choosing? Ask <SirHenryName />
            </button>
          </div>
          {/* Owner — shown when married */}
          {married && (
            <div>
              <label className="text-xs text-stone-500 mb-1.5 block">Who owns this business?</label>
              <div className="flex gap-2">
                {[
                  { value: "spouse_a", label: household?.spouse_a_name || "Spouse A" },
                  { value: "spouse_b", label: household?.spouse_b_name || "Spouse B" },
                  { value: "both", label: "Both" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setOwner(opt.value)}
                    className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-all ${
                      owner === opt.value
                        ? "border-[#16A34A] bg-green-50 text-[#16A34A]"
                        : "border-stone-200 text-stone-600 hover:border-stone-300"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-stone-400 mt-1">
                Links this entity to the right spouse for K-1 and Schedule C tax attribution.
              </p>
            </div>
          )}

          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={!name || saving}
              className="flex items-center gap-1.5 bg-[#16A34A] text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-[#15803d] disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving..." : <><Plus size={14} /> Add Entity</>}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-3 py-2 text-sm text-stone-500 hover:text-stone-700 transition-colors"
            >
              Cancel
            </button>
          </div>
        </Card>
      )}

      {/* Add another */}
      {hasBusiness && !showForm && (
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 w-full p-3 rounded-lg border border-dashed border-stone-200 text-sm text-stone-500 hover:border-stone-300 hover:text-stone-600 transition-colors"
        >
          <Plus size={14} />
          Add another entity
        </button>
      )}
    </div>
  );
}
