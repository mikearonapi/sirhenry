"use client";

import { useState } from "react";
import { ArrowRight, Check, RefreshCw, X, Sparkles } from "lucide-react";
import type { HouseholdUpdateSuggestion } from "@/types/smart-defaults";

interface DataUpdateBannerProps {
  suggestions: HouseholdUpdateSuggestion[];
  onApply: (updates: HouseholdUpdateSuggestion[]) => Promise<void>;
  onDismiss: () => void;
}

/**
 * Banner shown when cross-section data updates are available.
 * e.g. "We found updated data from your W-2" on the Household page.
 */
export function DataUpdateBanner({
  suggestions,
  onApply,
  onDismiss,
}: DataUpdateBannerProps) {
  const [expanded, setExpanded] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(suggestions.map((s) => s.field)),
  );

  if (suggestions.length === 0 || applied) return null;

  const toggleSelection = (field: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
  };

  const handleApply = async () => {
    setApplying(true);
    try {
      const toApply = suggestions.filter((s) => selected.has(s.field));
      await onApply(toApply);
      setApplied(true);
    } catch {
      // Error handled by parent
    } finally {
      setApplying(false);
    }
  };

  const formatValue = (val: number | string) => {
    if (typeof val === "number") {
      return val.toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      });
    }
    return val;
  };

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/80 overflow-hidden">
      {/* Collapsed banner */}
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-amber-100">
          <Sparkles size={16} className="text-amber-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-900">
            Updated data available
          </p>
          <p className="text-xs text-amber-700">
            {suggestions.length} field{suggestions.length !== 1 ? "s" : ""} can
            be updated from {suggestions[0]?.source || "imported documents"}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-amber-100 text-amber-800 hover:bg-amber-200 transition-colors"
          >
            {expanded ? "Hide" : "Review"}
          </button>
          {!expanded && (
            <button
              onClick={handleApply}
              disabled={applying}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {applying ? (
                <RefreshCw size={12} className="animate-spin" />
              ) : (
                "Apply All"
              )}
            </button>
          )}
          <button
            onClick={onDismiss}
            className="p-1 rounded-lg text-amber-400 hover:text-amber-600 hover:bg-amber-100 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Expanded detail view */}
      {expanded && (
        <div className="border-t border-amber-200 px-4 py-3 space-y-2">
          {suggestions.map((s) => (
            <label
              key={s.field}
              className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-amber-100/50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={selected.has(s.field)}
                onChange={() => toggleSelection(s.field)}
                className="w-4 h-4 rounded border-amber-300 text-accent focus:ring-accent"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary">{s.label}</p>
                <p className="text-xs text-text-secondary">{s.source}</p>
              </div>
              <div className="flex items-center gap-2 text-sm font-mono">
                <span className="text-text-muted">
                  {formatValue(s.current)}
                </span>
                <ArrowRight size={12} className="text-text-muted" />
                <span className="text-accent font-semibold">
                  {formatValue(s.suggested)}
                </span>
              </div>
            </label>
          ))}
          <div className="flex justify-end pt-2 border-t border-amber-100">
            <button
              onClick={handleApply}
              disabled={applying || selected.size === 0}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {applying ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  Applying...
                </>
              ) : (
                <>
                  <Check size={14} />
                  Apply {selected.size} Update{selected.size !== 1 ? "s" : ""}
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
