"use client";
import { useState } from "react";
import { Loader2, RotateCcw, MessageSquare, X } from "lucide-react";
import type { OutlierTransaction, OutlierClassification } from "@/types/api";
import { CLASSIFICATION_CONFIG } from "@/components/insights/constants";

interface Props {
  tx: OutlierTransaction;
  onClassify: (tx: OutlierTransaction, classification: OutlierClassification, note?: string) => Promise<void>;
  onUndo: (tx: OutlierTransaction) => Promise<void>;
}

export default function OutlierFeedbackForm({ tx, onClassify, onUndo }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [showNote, setShowNote] = useState(false);
  const [noteText, setNoteText] = useState("");

  const hasFeedback = !!tx.feedback;

  const handleClassify = async (classification: OutlierClassification) => {
    setSubmitting(true);
    try {
      const note = showNote && noteText.trim() ? noteText.trim() : undefined;
      await onClassify(tx, classification, note);
      setShowNote(false);
      setNoteText("");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUndo = async () => {
    if (!tx.feedback) return;
    setSubmitting(true);
    try {
      await onUndo(tx);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="mt-3 flex items-center gap-2 flex-wrap">
        {hasFeedback ? (
          <button
            onClick={handleUndo}
            disabled={submitting}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-text-muted bg-surface rounded-lg hover:bg-surface-hover transition-colors disabled:opacity-50"
          >
            <RotateCcw size={12} /> Undo
          </button>
        ) : (
          <>
            {(Object.entries(CLASSIFICATION_CONFIG) as [OutlierClassification, typeof CLASSIFICATION_CONFIG[OutlierClassification]][]).map(
              ([key, cfg]) => (
                <button
                  key={key}
                  onClick={() => handleClassify(key)}
                  disabled={submitting}
                  className={`flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-colors disabled:opacity-50 ${cfg.bg} ${cfg.text} ${cfg.border} hover:opacity-80`}
                >
                  {submitting ? <Loader2 size={12} className="animate-spin" /> : cfg.icon}
                  {cfg.label}
                </button>
              )
            )}
          </>
        )}

        {/* Note toggle */}
        {!hasFeedback && (
          <button
            onClick={() => {
              setShowNote(!showNote);
              setNoteText("");
            }}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-text-muted rounded-lg hover:bg-surface transition-colors"
          >
            <MessageSquare size={12} />
            {showNote ? "Cancel note" : "Add note"}
          </button>
        )}
      </div>

      {/* Note Input */}
      {showNote && !hasFeedback && (
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="e.g. Annual school tuition, paid every July"
            className="flex-1 text-xs border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setShowNote(false);
                setNoteText("");
              }
            }}
          />
          <button
            onClick={() => { setShowNote(false); setNoteText(""); }}
            className="p-1.5 text-text-muted hover:text-text-secondary"
          >
            <X size={14} />
          </button>
        </div>
      )}
    </>
  );
}
