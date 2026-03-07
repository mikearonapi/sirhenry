"use client";
import { useState, useCallback } from "react";
import { Building2, DollarSign, FileText, Pencil, Check, X, Loader2 } from "lucide-react";
import { formatCurrency, safeJsonParse } from "@/lib/utils";
import { updateTaxItem } from "@/lib/api";
import type { TaxItem, TaxSummary } from "@/types/api";
import Card from "@/components/ui/Card";

interface Props {
  items: TaxItem[];
  summary: TaxSummary | null;
  year: number;
  onItemUpdated?: (id: number, field: string, value: number | string | null) => void;
}

/** Inline-editable numeric cell for tax fields */
function EditableCell({
  itemId,
  field,
  value,
  onSaved,
}: {
  itemId: number;
  field: string;
  value: number | null;
  onSaved: (id: number, field: string, newValue: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [edited, setEdited] = useState(false);

  function startEdit() {
    setDraft(String(value ?? 0));
    setEditing(true);
  }

  async function save() {
    const newVal = Number(draft);
    if (isNaN(newVal)) return;
    setSaving(true);
    try {
      await updateTaxItem(itemId, { [field]: newVal });
      onSaved(itemId, field, newVal);
      setEdited(true);
      setEditing(false);
    } catch {
      // stay in edit mode on error
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") save();
    if (e.key === "Escape") cancel();
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
          className="w-28 text-sm border border-accent rounded px-2 py-0.5 text-right tabular-nums focus:outline-none focus:ring-1 focus:ring-accent"
        />
        {saving ? (
          <Loader2 size={12} className="animate-spin text-text-muted" />
        ) : (
          <>
            <button onClick={save} className="text-green-600 hover:text-green-700" title="Save">
              <Check size={12} />
            </button>
            <button onClick={cancel} className="text-text-muted hover:text-text-secondary" title="Cancel">
              <X size={12} />
            </button>
          </>
        )}
      </div>
    );
  }

  return (
    <span className="group inline-flex items-center gap-1 cursor-pointer" onClick={startEdit}>
      <span className="tabular-nums">{formatCurrency(value ?? 0)}</span>
      {edited && <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" title="Edited" />}
      <Pencil size={10} className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
    </span>
  );
}

export default function FormDetailsSection({ items, summary, year, onItemUpdated }: Props) {
  const [localItems, setLocalItems] = useState<TaxItem[]>(items);

  const handleSaved = useCallback((id: number, field: string, newValue: number) => {
    setLocalItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, [field]: newValue } : item))
    );
    onItemUpdated?.(id, field, newValue);
  }, [onItemUpdated]);

  const w2Items = localItems.filter((i) => i.form_type === "w2");
  const necItems = localItems.filter((i) => i.form_type === "1099_nec");
  const divItems = localItems.filter((i) => i.form_type === "1099_div");
  const bItems = localItems.filter((i) => i.form_type === "1099_b");
  const intItems = localItems.filter((i) => i.form_type === "1099_int");
  const k1Items = localItems.filter((i) => i.form_type === "k1");

  if (localItems.length === 0) return null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Form Details — {year}
        </h2>
        <span className="text-xs text-text-muted flex items-center gap-1 print:hidden">
          <Pencil size={9} /> Click any value to edit
        </span>
      </div>

      {/* W-2 table */}
      {w2Items.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-4">
            <Building2 size={18} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-text-primary">W-2 Forms ({w2Items.length})</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">W-2 forms for {year}</caption>
              <thead className="bg-surface">
                <tr>
                  <th className="text-left px-3 py-2 text-xs font-semibold text-text-secondary">Employer</th>
                  <th className="text-left px-3 py-2 text-xs font-semibold text-text-secondary">EIN</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-text-secondary">Wages</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-text-secondary">Fed W/H</th>
                  <th className="text-left px-3 py-2 text-xs font-semibold text-text-secondary">States</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-card-border">
                {w2Items.map((item) => {
                  const allocs = safeJsonParse<Array<{ state: string; wages: number; tax: number }>>(item.w2_state_allocations, []);
                  return (
                    <tr key={item.id}>
                      <td className="px-3 py-2 font-medium text-text-primary">{item.payer_name ?? "—"}</td>
                      <td className="px-3 py-2 text-text-secondary">{item.payer_ein ?? "—"}</td>
                      <td className="px-3 py-2 text-right">
                        <EditableCell itemId={item.id} field="w2_wages" value={item.w2_wages} onSaved={handleSaved} />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <EditableCell itemId={item.id} field="w2_federal_tax_withheld" value={item.w2_federal_tax_withheld} onSaved={handleSaved} />
                      </td>
                      <td className="px-3 py-2">
                        {allocs.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {allocs.map((a, i) => (
                              <span key={i} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded">
                                <strong>{a.state}</strong>: {formatCurrency(a.wages, true)} / {formatCurrency(a.tax, true)} w/h
                              </span>
                            ))}
                          </div>
                        ) : <span className="text-xs text-text-muted">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* 1099 sections */}
      {(necItems.length > 0 || divItems.length > 0 || intItems.length > 0 || bItems.length > 0) && (
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign size={18} className="text-green-500" />
            <h3 className="text-sm font-semibold text-text-primary">1099 Forms</h3>
          </div>
          <div className="space-y-4">
            {necItems.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">1099-NEC</h4>
                {necItems.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-sm py-2 border-b border-border-light last:border-0">
                    <div>
                      <p className="font-medium text-text-primary">{item.payer_name ?? "Unknown"}</p>
                      <p className="text-xs text-text-muted">EIN: {item.payer_ein ?? "N/A"}</p>
                    </div>
                    <div className="text-right">
                      <EditableCell itemId={item.id} field="nec_nonemployee_compensation" value={item.nec_nonemployee_compensation} onSaved={handleSaved} />
                      <p className="text-xs text-text-muted">W/H: {formatCurrency(item.nec_federal_tax_withheld ?? 0)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {divItems.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">1099-DIV</h4>
                {divItems.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-sm py-2 border-b border-border-light last:border-0">
                    <p className="font-medium text-text-primary">{item.payer_name ?? "Unknown"}</p>
                    <div className="text-right text-xs space-y-0.5">
                      <p className="flex items-center justify-end gap-1">
                        <span className="text-text-muted">Ordinary:</span>
                        <EditableCell itemId={item.id} field="div_total_ordinary" value={item.div_total_ordinary} onSaved={handleSaved} />
                      </p>
                      <p className="flex items-center justify-end gap-1">
                        <span className="text-text-muted">Qualified:</span>
                        <EditableCell itemId={item.id} field="div_qualified" value={item.div_qualified} onSaved={handleSaved} />
                      </p>
                      <p className="flex items-center justify-end gap-1">
                        <span className="text-text-muted">Cap. Gain:</span>
                        <EditableCell itemId={item.id} field="div_total_capital_gain" value={item.div_total_capital_gain} onSaved={handleSaved} />
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {intItems.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">1099-INT</h4>
                {intItems.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-sm py-2 border-b border-border-light last:border-0">
                    <p className="font-medium text-text-primary">{item.payer_name ?? "Unknown"}</p>
                    <EditableCell itemId={item.id} field="int_interest" value={item.int_interest} onSaved={handleSaved} />
                  </div>
                ))}
              </div>
            )}
            {bItems.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">1099-B (Capital Gains)</h4>
                <p className="text-sm text-text-secondary">
                  {bItems.length} form(s) on file — {summary ? formatCurrency(summary.capital_gains_long + summary.capital_gains_short) : "—"} total
                </p>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* K-1 section */}
      {k1Items.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center gap-2 mb-4">
            <FileText size={18} className="text-purple-500" />
            <h3 className="text-sm font-semibold text-text-primary">K-1 Forms ({k1Items.length})</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">K-1 forms for {year}</caption>
              <thead className="bg-surface">
                <tr>
                  <th className="text-left px-3 py-2 text-xs font-semibold text-text-secondary">Partnership / Entity</th>
                  <th className="text-left px-3 py-2 text-xs font-semibold text-text-secondary">EIN</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-text-secondary">Ordinary</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-text-secondary">Guaranteed</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-text-secondary">Rental</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-text-secondary">Distributions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-card-border">
                {k1Items.map((item) => (
                  <tr key={item.id}>
                    <td className="px-3 py-2 font-medium text-text-primary">{item.payer_name ?? "—"}</td>
                    <td className="px-3 py-2 text-text-secondary">{item.payer_ein ?? "—"}</td>
                    <td className="px-3 py-2 text-right">
                      <EditableCell itemId={item.id} field="k1_ordinary_income" value={item.k1_ordinary_income} onSaved={handleSaved} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <EditableCell itemId={item.id} field="k1_guaranteed_payments" value={item.k1_guaranteed_payments} onSaved={handleSaved} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <EditableCell itemId={item.id} field="k1_rental_income" value={item.k1_rental_income} onSaved={handleSaved} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <EditableCell itemId={item.id} field="k1_distributions" value={item.k1_distributions} onSaved={handleSaved} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
