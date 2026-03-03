"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Building2, Plus, Pencil, Trash2, AlertCircle, Loader2, X,
  Zap, TrendingUp, FileText, Tag,
} from "lucide-react";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import {
  getBusinessEntities, createBusinessEntity, updateBusinessEntity, deleteBusinessEntity,
} from "@/lib/api";
import type { BusinessEntity, BusinessEntityCreateIn } from "@/types/api";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const ENTITY_TYPES = [
  { value: "sole_prop", label: "Sole Proprietorship" },
  { value: "llc", label: "LLC" },
  { value: "s_corp", label: "S-Corporation" },
  { value: "c_corp", label: "C-Corporation" },
  { value: "partnership", label: "Partnership" },
  { value: "other", label: "Other" },
];

const TAX_TREATMENTS = [
  { value: "schedule_c", label: "Schedule C (Sole Prop / Single-Member LLC)" },
  { value: "s_corp", label: "S-Corp (Form 1120-S)" },
  { value: "partnership", label: "Partnership (Form 1065)" },
  { value: "c_corp", label: "C-Corp (Form 1120)" },
  { value: "1099_nec", label: "1099-NEC / Board Income" },
  { value: "other", label: "Other" },
];

// What each tax treatment means for the user's broader finances
const TAX_CONNECTIONS: Record<string, { effect: string; connects: string; href: string }> = {
  schedule_c: {
    effect: "Business income / loss flows to Schedule C on your personal return.",
    connects: "Transactions tagged to this entity appear in your Schedule C expense summary.",
    href: "/tax-strategy",
  },
  s_corp: {
    effect: "Pay yourself a reasonable salary + distributions. QBI deduction may apply.",
    connects: "S-Corp payroll shows on W-2. Distributions tracked separately.",
    href: "/tax-strategy",
  },
  partnership: {
    effect: "Each partner's share passes through on Schedule K-1.",
    connects: "Import K-1 data via Documents to populate your tax summary.",
    href: "/import",
  },
  c_corp: {
    effect: "Corporate-level tax at 21% flat rate. Dividends are taxed again at distribution.",
    connects: "Dividends received appear as 1099-DIV income in your tax summary.",
    href: "/tax-strategy",
  },
  "1099_nec": {
    effect: "Board / director / contractor income. Self-employment tax applies.",
    connects: "1099-NEC income feeds into your self-employment tax estimate.",
    href: "/tax-strategy",
  },
  other: {
    effect: "Review tax obligations with your CPA.",
    connects: "Tag transactions to this entity to track income and expenses.",
    href: "/transactions",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BusinessPage() {
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingEntity, setEditingEntity] = useState<BusinessEntity | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [fName, setFName] = useState("");
  const [fEntityType, setFEntityType] = useState("sole_prop");
  const [fTaxTreatment, setFTaxTreatment] = useState("schedule_c");
  const [fEin, setFEin] = useState("");
  const [fActiveFrom, setFActiveFrom] = useState("");
  const [fActiveTo, setFActiveTo] = useState("");
  const [fNotes, setFNotes] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getBusinessEntities(showInactive);
      setEntities(Array.isArray(data) ? data : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  useEffect(() => { load(); }, [load]);

  function resetForm() {
    setFName(""); setFEntityType("sole_prop"); setFTaxTreatment("schedule_c");
    setFEin(""); setFActiveFrom(""); setFActiveTo(""); setFNotes("");
    setEditingEntity(null);
    setShowForm(false);
  }

  function openEdit(entity: BusinessEntity) {
    setEditingEntity(entity);
    setFName(entity.name);
    setFEntityType(entity.entity_type || "sole_prop");
    setFTaxTreatment(entity.tax_treatment || "schedule_c");
    setFEin(entity.ein || "");
    setFActiveFrom(entity.active_from || "");
    setFActiveTo(entity.active_to || "");
    setFNotes(entity.notes || "");
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSave() {
    if (!fName.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const body: BusinessEntityCreateIn = {
        name: fName.trim(),
        entity_type: fEntityType,
        tax_treatment: fTaxTreatment,
        ein: fEin || null,
        active_from: fActiveFrom || null,
        active_to: fActiveTo || null,
        notes: fNotes || null,
      };
      if (editingEntity) {
        await updateBusinessEntity(editingEntity.id, body);
      } else {
        await createBusinessEntity(body);
      }
      await load();
      resetForm();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this business entity? Transactions tagged to it will be untagged.")) return;
    try {
      await deleteBusinessEntity(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Business"
        subtitle="Manage business entities, track Schedule C expenses, and connect to Tax Strategy"
        actions={
          <button
            onClick={() => { if (showForm) resetForm(); else setShowForm(true); }}
            className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
          >
            {showForm ? <X size={14} /> : <Plus size={14} />}
            {showForm ? "Cancel" : "Add Business"}
          </button>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400"><X size={14} /></button>
        </div>
      )}

      {/* How this section connects to the rest of the app */}
      <div className="bg-stone-50 border border-stone-100 rounded-xl px-4 py-3">
        <p className="text-xs font-semibold text-stone-700">Why this matters</p>
        <p className="text-xs text-stone-500 mt-0.5">
          Business entities connect your financial data across the app.
          Transactions tagged to a business entity appear in Tax Strategy (Schedule C / QBI), in Reports (annual business expense detail), and can be filtered in Transactions.
        </p>
        <div className="flex gap-4 mt-2">
          <a href="/tax-strategy" className="text-xs font-medium text-[#16A34A] hover:underline flex items-center gap-1"><Zap size={11} /> Tax Strategy</a>
          <a href="/transactions" className="text-xs font-medium text-[#16A34A] hover:underline flex items-center gap-1"><Tag size={11} /> Transactions</a>
          <a href="/reports" className="text-xs font-medium text-[#16A34A] hover:underline flex items-center gap-1"><FileText size={11} /> Reports</a>
        </div>
      </div>

      {/* Add / Edit form */}
      {showForm && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-stone-900 mb-4">
            {editingEntity ? "Edit Business Entity" : "Add Business Entity"}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="text-xs text-stone-500">Business / Entity Name *</label>
              <input
                type="text"
                value={fName}
                onChange={(e) => setFName(e.target.value)}
                placeholder="e.g. Acme Consulting LLC"
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Entity Type</label>
              <select
                value={fEntityType}
                onChange={(e) => setFEntityType(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              >
                {ENTITY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-500">Tax Treatment</label>
              <select
                value={fTaxTreatment}
                onChange={(e) => setFTaxTreatment(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              >
                {TAX_TREATMENTS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-500">EIN (optional)</label>
              <input
                type="text"
                value={fEin}
                onChange={(e) => setFEin(e.target.value)}
                placeholder="XX-XXXXXXX"
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Active From</label>
              <input
                type="date"
                value={fActiveFrom}
                onChange={(e) => setFActiveFrom(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Active To (leave blank if still active)</label>
              <input
                type="date"
                value={fActiveTo}
                onChange={(e) => setFActiveTo(e.target.value)}
                className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
              />
            </div>
          </div>

          {/* Tax treatment context */}
          {fTaxTreatment && TAX_CONNECTIONS[fTaxTreatment] && (
            <div className="mt-4 p-3 bg-blue-50 border border-blue-100 rounded-lg">
              <p className="text-xs text-blue-800 font-medium">{TAX_CONNECTIONS[fTaxTreatment].effect}</p>
              <p className="text-xs text-blue-600 mt-0.5">{TAX_CONNECTIONS[fTaxTreatment].connects}</p>
            </div>
          )}

          <div className="mt-4">
            <label className="text-xs text-stone-500">Notes</label>
            <textarea
              value={fNotes}
              onChange={(e) => setFNotes(e.target.value)}
              rows={2}
              placeholder="State of incorporation, purpose, etc."
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
            />
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !fName.trim()}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              {editingEntity ? "Update Entity" : "Save Entity"}
            </button>
            <button onClick={resetForm} className="text-sm text-stone-500 hover:text-stone-700">Cancel</button>
          </div>
        </Card>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-stone-600 cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-stone-300"
          />
          Show inactive entities
        </label>
        <span className="ml-auto text-xs text-stone-400">{entities.length} entities</span>
      </div>

      {/* Entity list */}
      {loading ? (
        <div className="flex items-center gap-2 text-stone-500 text-sm py-8">
          <Loader2 size={16} className="animate-spin" /> Loading...
        </div>
      ) : entities.length === 0 ? (
        <Card padding="lg">
          <div className="text-center py-8">
            <Building2 size={32} className="mx-auto text-stone-300 mb-3" />
            <p className="text-sm text-stone-500">No business entities yet.</p>
            <p className="text-xs text-stone-400 mt-1">
              Add a business entity to start tracking Schedule C income and expenses, QBI deductions, and multi-entity reporting.
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {entities.map((entity) => {
            const typeLabel = ENTITY_TYPES.find((t) => t.value === entity.entity_type)?.label || entity.entity_type;
            const taxLabel = TAX_TREATMENTS.find((t) => t.value === entity.tax_treatment)?.label || entity.tax_treatment;
            const connection = TAX_CONNECTIONS[entity.tax_treatment] || TAX_CONNECTIONS.other;

            return (
              <Card key={entity.id} padding="md">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <Building2 size={20} className="text-stone-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-semibold text-stone-900">{entity.name}</h4>
                        {!entity.is_active && (
                          <span className="text-xs bg-stone-100 text-stone-400 px-2 py-0.5 rounded-full">Inactive</span>
                        )}
                        {entity.is_provisional && (
                          <span className="text-xs bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full">Provisional</span>
                        )}
                      </div>
                      <p className="text-xs text-stone-500 mt-0.5">{typeLabel}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => openEdit(entity)}
                      className="p-1.5 text-stone-400 hover:text-[#16A34A] rounded"
                      title="Edit"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={() => handleDelete(entity.id)}
                      className="p-1.5 text-stone-400 hover:text-red-500 rounded"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                <div className="mt-3 space-y-1 text-xs">
                  <div className="flex items-center gap-1 text-stone-500">
                    <FileText size={11} className="shrink-0" />
                    <span className="font-medium text-stone-700">{taxLabel}</span>
                  </div>
                  {entity.ein && (
                    <p className="text-stone-400">EIN: {entity.ein}</p>
                  )}
                  {entity.active_from && (
                    <p className="text-stone-400">
                      Active: {new Date(entity.active_from).toLocaleDateString()}{entity.active_to ? ` → ${new Date(entity.active_to).toLocaleDateString()}` : " → Present"}
                    </p>
                  )}
                </div>

                {/* Tax connection hint */}
                <div className="mt-3 pt-3 border-t border-stone-100">
                  <p className="text-xs text-stone-500">{connection.effect}</p>
                  <a href={connection.href} className="inline-flex items-center gap-1 mt-1 text-[10px] font-medium text-[#16A34A] hover:underline">
                    <TrendingUp size={10} /> View in app →
                  </a>
                </div>

                {entity.notes && (
                  <p className="text-xs text-stone-400 mt-2 italic">{entity.notes}</p>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
