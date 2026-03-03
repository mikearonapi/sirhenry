"use client";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import Card from "@/components/ui/Card";
import type { LifeEvent, LifeEventIn } from "@/types/api";
import {
  EVENT_TYPES, getAmountFields, getEventConfig, parseAmounts,
} from "./constants";

const CURRENT_YEAR = new Date().getFullYear();

interface Props {
  editingEvent: LifeEvent | null;
  onSave: (body: LifeEventIn) => Promise<void>;
  onCancel: () => void;
}

export default function LifeEventForm({ editingEvent, onSave, onCancel }: Props) {
  const [fType, setFType] = useState(editingEvent?.event_type ?? "real_estate");
  const [fSubtype, setFSubtype] = useState(editingEvent?.event_subtype ?? "");
  const [fTitle, setFTitle] = useState(editingEvent?.title ?? "");
  const [fDate, setFDate] = useState(editingEvent?.event_date ?? "");
  const [fTaxYear, setFTaxYear] = useState(
    editingEvent?.tax_year ? String(editingEvent.tax_year) : String(CURRENT_YEAR)
  );
  const [fStatus, setFStatus] = useState(editingEvent?.status ?? "completed");
  const [fAmounts, setFAmounts] = useState<Record<string, string>>(
    editingEvent ? parseAmounts(editingEvent.amounts_json) : {}
  );
  const [fNotes, setFNotes] = useState(editingEvent?.notes ?? "");
  const [saving, setSaving] = useState(false);

  const subtypes = getEventConfig(fType).subtypes;
  const amountFields = getAmountFields(fType, fSubtype);

  function buildAmountsJson(): string | null {
    const filled = Object.fromEntries(
      Object.entries(fAmounts).filter(([, v]) => v !== "" && v !== undefined)
    );
    return Object.keys(filled).length > 0 ? JSON.stringify(filled) : null;
  }

  async function handleSubmit() {
    setSaving(true);
    try {
      await onSave({
        event_type: fType,
        event_subtype: fSubtype || null,
        title: fTitle || `${getEventConfig(fType).label}${fSubtype ? ` — ${fSubtype}` : ""}`,
        event_date: fDate || null,
        tax_year: fTaxYear ? Number(fTaxYear) : null,
        amounts_json: buildAmountsJson(),
        status: fStatus,
        notes: fNotes || null,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card padding="lg">
      <h3 className="text-sm font-semibold text-stone-900 mb-4">
        {editingEvent ? "Edit Life Event" : "Add Life Event"}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="text-xs text-stone-500">Event Category</label>
          <select
            value={fType}
            onChange={(e) => { setFType(e.target.value); setFSubtype(""); }}
            className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
          >
            {EVENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
            ))}
          </select>
        </div>
        {subtypes.length > 0 && (
          <div>
            <label className="text-xs text-stone-500">Subtype</label>
            <select
              value={fSubtype}
              onChange={(e) => setFSubtype(e.target.value)}
              className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
            >
              <option value="">— Select subtype —</option>
              {subtypes.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="text-xs text-stone-500">Title</label>
          <input
            type="text"
            value={fTitle}
            onChange={(e) => setFTitle(e.target.value)}
            placeholder="e.g. Purchased home at 123 Main St"
            className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
          />
        </div>
        <div>
          <label className="text-xs text-stone-500">Status</label>
          <select
            value={fStatus}
            onChange={(e) => setFStatus(e.target.value as "completed" | "upcoming" | "needs_documentation")}
            className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
          >
            <option value="completed">Completed</option>
            <option value="upcoming">Upcoming</option>
            <option value="needs_documentation">Needs Documentation</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-stone-500">Event Date</label>
          <input type="date" value={fDate} onChange={(e) => setFDate(e.target.value)} className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
        </div>
        <div>
          <label className="text-xs text-stone-500">Tax Year Affected</label>
          <input type="number" value={fTaxYear} onChange={(e) => setFTaxYear(e.target.value)} className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
        </div>
      </div>

      {amountFields.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-stone-600 mb-2">Financial Amounts</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {amountFields.map((field) => (
              <div key={field.key}>
                <label className="text-xs text-stone-500">{field.label}</label>
                <input
                  type="number"
                  value={fAmounts[field.key] || ""}
                  onChange={(e) => setFAmounts((prev) => ({ ...prev, [field.key]: e.target.value }))}
                  placeholder={field.placeholder}
                  className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4">
        <label className="text-xs text-stone-500">Notes</label>
        <textarea
          value={fNotes}
          onChange={(e) => setFNotes(e.target.value)}
          rows={2}
          placeholder="Any additional context..."
          className="w-full mt-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
        />
      </div>

      {!editingEvent && (
        <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-100">
          <p className="text-xs text-amber-700">
            Action items will be auto-generated based on the event type. You can check them off as you complete each step.
          </p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={handleSubmit}
          disabled={saving}
          className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          {editingEvent ? "Update Event" : "Save Event"}
        </button>
        <button onClick={onCancel} className="text-sm text-stone-500 hover:text-stone-700">
          Cancel
        </button>
      </div>
    </Card>
  );
}
