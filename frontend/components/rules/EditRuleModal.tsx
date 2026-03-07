"use client";
import { useEffect, useState } from "react";
import { X, Loader2 } from "lucide-react";
import type { CategoryRuleWithEntity } from "@/types/rules";
import type { BusinessEntity } from "@/types/business";
import { getBusinessEntities } from "@/lib/api-entities";
import { getRuleCategories } from "@/lib/api-rules";

const SEGMENTS = ["personal", "business", "investment", "reimbursable"];

interface EditRuleModalProps {
  rule: CategoryRuleWithEntity;
  onSave: (ruleId: number, data: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
}

export default function EditRuleModal({ rule, onSave, onClose }: EditRuleModalProps) {
  const [category, setCategory] = useState(rule.category || "");
  const [taxCategory, setTaxCategory] = useState(rule.tax_category || "");
  const [segment, setSegment] = useState(rule.segment || "personal");
  const [entityId, setEntityId] = useState<number | null>(rule.business_entity_id);
  const [effectiveFrom, setEffectiveFrom] = useState(rule.effective_from || "");
  const [effectiveTo, setEffectiveTo] = useState(rule.effective_to || "");
  const [saving, setSaving] = useState(false);

  // Loaded data for dropdowns
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [taxCategories, setTaxCategories] = useState<string[]>([]);

  useEffect(() => {
    getBusinessEntities().then(setEntities).catch(() => {});
    getRuleCategories()
      .then((res) => {
        setCategories(res.categories);
        setTaxCategories(res.tax_categories);
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(rule.id, {
        category: category || null,
        tax_category: taxCategory || null,
        segment: segment || null,
        business_entity_id: entityId,
        effective_from: effectiveFrom || null,
        effective_to: effectiveTo || null,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-5 pb-4 border-b border-card-border">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Edit Rule</h2>
            <p className="font-mono text-sm text-text-secondary mt-0.5">{rule.merchant_pattern}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface text-text-muted hover:text-text-secondary transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <div className="px-6 py-5 space-y-4">
          {/* Category */}
          <div>
            <label className="text-xs text-text-secondary block mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            >
              <option value="">— None —</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
              {/* Include current value if not in list */}
              {category && !categories.includes(category) && (
                <option value={category}>{category}</option>
              )}
            </select>
          </div>

          {/* Tax Category */}
          <div>
            <label className="text-xs text-text-secondary block mb-1">Tax Category</label>
            <select
              value={taxCategory}
              onChange={(e) => setTaxCategory(e.target.value)}
              className="w-full rounded-lg border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            >
              <option value="">— None —</option>
              {taxCategories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
              {taxCategory && !taxCategories.includes(taxCategory) && (
                <option value={taxCategory}>{taxCategory}</option>
              )}
            </select>
          </div>

          {/* Segment */}
          <div>
            <label className="text-xs text-text-secondary block mb-1">Segment</label>
            <select
              value={segment}
              onChange={(e) => {
                setSegment(e.target.value);
                if (e.target.value !== "business") setEntityId(null);
              }}
              className="w-full rounded-lg border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            >
              {SEGMENTS.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>

          {/* Business Entity (only when segment = business) */}
          {segment === "business" && (
            <div>
              <label className="text-xs text-text-secondary block mb-1">Business Entity</label>
              <select
                value={entityId ?? ""}
                onChange={(e) => setEntityId(e.target.value ? Number(e.target.value) : null)}
                className="w-full rounded-lg border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              >
                <option value="">— None —</option>
                {entities.map((ent) => (
                  <option key={ent.id} value={ent.id}>{ent.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Date Range */}
          <div>
            <label className="text-xs text-text-secondary block mb-1">Date Range (optional)</label>
            <div className="grid grid-cols-2 gap-3">
              <input
                type="date"
                value={effectiveFrom}
                onChange={(e) => setEffectiveFrom(e.target.value)}
                placeholder="From"
                className="w-full rounded-lg border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              />
              <input
                type="date"
                value={effectiveTo}
                onChange={(e) => setEffectiveTo(e.target.value)}
                placeholder="To"
                className="w-full rounded-lg border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              />
            </div>
            <p className="text-xs text-text-muted mt-1">Leave blank to apply to all transactions regardless of date</p>
          </div>

          {/* Info line */}
          <div className="flex items-center gap-4 pt-2 text-xs text-text-muted">
            <span>Matched {rule.match_count} transactions</span>
            <span>Source: {rule.source}</span>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-card-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}
