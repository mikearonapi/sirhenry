"use client";
import { useEffect, useMemo, useState } from "react";
import { X, Check, Loader2, Eye, EyeOff, Building2 } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { BusinessEntity, Transaction, TransactionUpdateIn } from "@/types/api";

interface Props {
  tx: Transaction;
  entities: BusinessEntity[];
  entityMap: Map<number, BusinessEntity>;
  allCategories: string[];
  onClose: () => void;
  onSave: (id: number, update: TransactionUpdateIn) => Promise<void>;
}

export default function TransactionDetailPanel({
  tx, entities, entityMap, allCategories, onClose, onSave,
}: Props) {
  const [category, setCategory] = useState(tx.effective_category ?? "");
  const [segment, setSegment] = useState(tx.effective_segment ?? tx.segment);
  const [entityId, setEntityId] = useState<number | null>(
    tx.business_entity_override ?? tx.effective_business_entity_id ?? null
  );
  const [notes, setNotes] = useState(tx.notes ?? "");
  const [isExcluded, setIsExcluded] = useState(tx.is_excluded);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setCategory(tx.effective_category ?? "");
    setSegment(tx.effective_segment ?? tx.segment);
    setEntityId(tx.business_entity_override ?? tx.effective_business_entity_id ?? null);
    setNotes(tx.notes ?? "");
    setIsExcluded(tx.is_excluded);
  }, [tx]);

  const entityName = (() => {
    const eid = tx.effective_business_entity_id ?? tx.business_entity_id;
    if (!eid) return null;
    return entityMap.get(eid)?.name ?? null;
  })();

  const dropdownCategories = useMemo(() => {
    const set = new Set(allCategories);
    if (tx.effective_category) set.add(tx.effective_category);
    if (tx.category) set.add(tx.category);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [allCategories, tx.effective_category, tx.category]);

  const hasChanges = category !== (tx.effective_category ?? "")
    || segment !== (tx.effective_segment ?? tx.segment)
    || notes !== (tx.notes ?? "")
    || isExcluded !== tx.is_excluded
    || entityId !== (tx.business_entity_override ?? tx.effective_business_entity_id ?? null);

  async function handleSave() {
    setSaving(true);
    const update: TransactionUpdateIn = {};
    if (category !== (tx.effective_category ?? "")) update.category_override = category;
    if (segment !== (tx.effective_segment ?? tx.segment)) update.segment_override = segment;
    if (notes !== (tx.notes ?? "")) update.notes = notes;
    if (isExcluded !== tx.is_excluded) update.is_excluded = isExcluded;
    const currentEntityId = tx.business_entity_override ?? tx.effective_business_entity_id ?? null;
    if (entityId !== currentEntityId) update.business_entity_override = entityId;
    try {
      await onSave(tx.id, update);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white shadow-2xl border-l border-stone-200 overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-stone-100 px-5 py-3 flex items-center justify-between z-10">
          <h2 className="font-semibold text-stone-900 text-sm">Transaction Details</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg hover:bg-stone-100 text-stone-400">
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="text-center pb-3 border-b border-stone-100">
            <p className={`text-2xl font-bold tracking-tight ${tx.amount >= 0 ? "text-green-600" : "text-stone-900"}`}>
              {tx.amount >= 0 ? "+" : ""}{formatCurrency(tx.amount)}
            </p>
            <p className="text-sm text-stone-600 mt-1 font-medium">{tx.description}</p>
            <p className="text-xs text-stone-400 mt-0.5">{formatDate(tx.date)}</p>
          </div>

          {/* Mapping info */}
          {(tx.category || tx.ai_confidence !== null) && (
            <div className="bg-stone-50 rounded-lg p-3 space-y-1.5 text-xs">
              {tx.category && (
                <div className="flex justify-between">
                  <span className="text-stone-500">Original category</span>
                  <span className="text-stone-700 font-medium">{tx.category}</span>
                </div>
              )}
              {tx.category_override && (
                <div className="flex justify-between">
                  <span className="text-stone-500">User override</span>
                  <span className="text-violet-600 font-medium">{tx.category_override}</span>
                </div>
              )}
              {tx.ai_confidence !== null && (
                <div className="flex justify-between">
                  <span className="text-stone-500">AI confidence</span>
                  <span className="text-stone-700 font-medium">{(tx.ai_confidence * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={`w-full text-sm border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] bg-white ${
                !category ? "border-amber-300 text-amber-700" : "border-stone-200"
              }`}
            >
              <option value="">-- Select --</option>
              {dropdownCategories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">Tax Category</label>
            <p className="text-sm text-stone-600">{tx.effective_tax_category ?? <span className="text-stone-300 italic">None</span>}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-stone-500 mb-1">Segment</label>
              <select
                value={segment}
                onChange={(e) => setSegment(e.target.value as "personal" | "business" | "investment" | "reimbursable")}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] bg-white"
              >
                <option value="personal">Personal</option>
                <option value="business">Business</option>
                <option value="investment">Investment</option>
                <option value="reimbursable">Reimbursable</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-500 mb-1">Business Entity</label>
              <select
                value={entityId ?? ""}
                onChange={(e) => setEntityId(e.target.value ? Number(e.target.value) : null)}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] bg-white"
              >
                <option value="">None</option>
                {entities.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] resize-none"
              placeholder="Add notes..."
            />
          </div>

          <button
            onClick={() => setIsExcluded(!isExcluded)}
            className={`flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border transition-colors ${
              isExcluded
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-stone-200 bg-stone-50 text-stone-600 hover:bg-stone-100"
            }`}
          >
            {isExcluded ? <EyeOff size={14} /> : <Eye size={14} />}
            {isExcluded ? "Excluded from reports" : "Included in reports"}
          </button>

          {entityName && (
            <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
              <p className="text-xs font-medium text-blue-800 flex items-center gap-1">
                <Building2 size={12} /> Assigned Entity
              </p>
              <p className="text-sm text-blue-700 mt-0.5">{entityName}</p>
              {tx.reimbursement_status && (
                <p className="text-xs text-blue-600 mt-0.5">Reimbursement: {tx.reimbursement_status}</p>
              )}
            </div>
          )}

          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="w-full flex items-center justify-center gap-2 bg-[#16A34A] text-white text-sm font-medium py-2 rounded-lg hover:bg-[#15803D] disabled:opacity-40 transition-colors shadow-sm"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}
