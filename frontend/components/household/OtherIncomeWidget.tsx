"use client";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { OtherIncomeSource, OtherIncomeType } from "@/types/api";
import { OTHER_INCOME_TYPES } from "./constants";

// ---------------------------------------------------------------------------
// OtherIncomeWidget — inline editor for non-W2 income sources
// ---------------------------------------------------------------------------

export interface OtherIncomeWidgetProps {
  sources: OtherIncomeSource[];
  onChange: (sources: OtherIncomeSource[]) => void;
}

export default function OtherIncomeWidget({ sources, onChange }: OtherIncomeWidgetProps) {
  const [showAdd, setShowAdd] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newType, setNewType] = useState<OtherIncomeType>("trust_k1");
  const [newAmount, setNewAmount] = useState<number | "">("");
  const [newNotes, setNewNotes] = useState("");

  function addSource() {
    if (!newLabel || !newAmount) return;
    onChange([...sources, { label: newLabel, type: newType, amount: Number(newAmount), notes: newNotes || undefined }]);
    setNewLabel(""); setNewType("trust_k1"); setNewAmount(""); setNewNotes(""); setShowAdd(false);
  }

  function removeSource(idx: number) {
    onChange(sources.filter((_, i) => i !== idx));
  }

  const total = sources.reduce((s, x) => s + x.amount, 0);
  const hint = OTHER_INCOME_TYPES.find((t) => t.value === newType)?.hint;

  return (
    <div className="space-y-2">
      {sources.length === 0 && !showAdd && (
        <p className="text-xs text-text-muted italic">No other income sources saved.</p>
      )}

      {sources.map((s, i) => (
        <div key={i} className="flex items-center justify-between text-xs bg-surface rounded-lg px-3 py-2 border border-card-border">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-medium text-text-secondary truncate">{s.label}</span>
            <span className="text-text-muted shrink-0">
              {OTHER_INCOME_TYPES.find((t) => t.value === s.type)?.label}
            </span>
            {s.notes && <span className="text-text-muted truncate hidden md:inline">{s.notes}</span>}
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            <span className="font-semibold text-text-primary">{formatCurrency(s.amount)}</span>
            <button onClick={() => removeSource(i)} className="text-text-muted hover:text-red-400">
              <Trash2 size={11} />
            </button>
          </div>
        </div>
      ))}

      {sources.length > 1 && (
        <div className="flex items-center justify-between text-xs px-3 py-1 text-text-secondary font-semibold border-t border-border">
          <span>Total other income</span>
          <span className="text-text-primary">{formatCurrency(total)}/yr</span>
        </div>
      )}

      {showAdd ? (
        <div className="p-3 bg-blue-50 border border-blue-100 rounded-xl space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-text-secondary">Label</label>
              <input type="text" value={newLabel} onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g. Ripley Trust"
                className="w-full mt-0.5 text-xs border border-border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20" />
            </div>
            <div>
              <label className="text-xs text-text-secondary">Type</label>
              <select value={newType} onChange={(e) => setNewType(e.target.value as OtherIncomeType)}
                className="w-full mt-0.5 text-xs border border-border rounded-lg px-2 py-1.5 bg-card focus:outline-none">
                {OTHER_INCOME_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>
          {hint && <p className="text-xs text-blue-600">{hint}</p>}
          {newType === "partnership_k1" && (
            <div className="text-xs bg-amber-50 border border-amber-100 rounded-lg px-2 py-1.5 text-amber-700">
              Self-employment tax (15.3%) may apply. No withholding — use quarterly estimated payments (Form 1040-ES).
            </div>
          )}
          {newType === "business_1099" && (
            <div className="text-xs bg-amber-50 border border-amber-100 rounded-lg px-2 py-1.5 text-amber-700">
              SE tax ~15.3% on net income. No withholding — use quarterly estimated payments.
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-text-secondary">Annual Amount</label>
              <input type="number" value={newAmount}
                onChange={(e) => setNewAmount(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="0"
                className="w-full mt-0.5 text-xs border border-border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20" />
            </div>
            <div>
              <label className="text-xs text-text-secondary">Notes (optional)</label>
              <input type="text" value={newNotes} onChange={(e) => setNewNotes(e.target.value)}
                placeholder="e.g. ordinary income portion"
                className="w-full mt-0.5 text-xs border border-border rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-accent/20" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={addSource} disabled={!newLabel || !newAmount}
              className="flex items-center gap-1.5 text-xs bg-accent text-white px-3 py-1.5 rounded-lg font-medium hover:bg-accent-hover disabled:opacity-60">
              <Plus size={11} /> Add
            </button>
            <button onClick={() => setShowAdd(false)} className="text-xs text-text-secondary hover:text-text-primary px-2">Cancel</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover font-medium">
          <Plus size={12} /> Add income source
        </button>
      )}
    </div>
  );
}
