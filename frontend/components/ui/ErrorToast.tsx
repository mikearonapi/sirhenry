"use client";
import { useState } from "react";
import { AlertCircle, X, Send, Loader2, CheckCircle2 } from "lucide-react";
import type { CapturedError } from "@/types/errors";
import { submitErrorReport } from "@/lib/api-errors";

interface ErrorToastProps {
  error: CapturedError;
  onDismiss: (id: string) => void;
}

export default function ErrorToast({ error, onDismiss }: ErrorToastProps) {
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [userNote, setUserNote] = useState("");
  const [showDetail, setShowDetail] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submitErrorReport({
        error_type: error.error_type,
        message: error.message,
        stack_trace: error.stack,
        source_url: error.source_url,
        user_note: userNote || undefined,
        context: error.context,
      });
      setSubmitted(true);
      setTimeout(() => onDismiss(error.id), 1500);
    } catch {
      // If error reporting itself fails, just dismiss
      onDismiss(error.id);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 w-96 max-w-[calc(100vw-2rem)] animate-in slide-in-from-bottom-2">
      <div className="bg-card border border-red-200 rounded-xl shadow-lg overflow-hidden">
        {/* Header */}
        <div className="flex items-start gap-3 px-4 pt-3 pb-2">
          <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text-primary">Something went wrong</p>
            <p className="text-xs text-text-secondary mt-0.5 truncate">
              {error.message || "An unexpected error occurred"}
            </p>
          </div>
          <button
            onClick={() => onDismiss(error.id)}
            className="p-1 rounded text-text-muted hover:text-text-secondary transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* Expandable detail */}
        {!submitted && (
          <div className="px-4 pb-3">
            <button
              onClick={() => setShowDetail(!showDetail)}
              className="text-xs text-text-muted hover:text-text-secondary transition-colors"
            >
              {showDetail ? "Hide details" : "Show details"}
            </button>
            {showDetail && (
              <div className="mt-2 space-y-2">
                <textarea
                  value={userNote}
                  onChange={(e) => setUserNote(e.target.value)}
                  placeholder="What were you doing? (optional)"
                  rows={2}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-primary placeholder:text-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                />
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-2.5 bg-surface/50 border-t border-card-border">
          {submitted ? (
            <div className="flex items-center gap-1.5 text-xs text-accent">
              <CheckCircle2 size={14} />
              Submitted — thank you!
            </div>
          ) : (
            <>
              <button
                onClick={() => onDismiss(error.id)}
                className="px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
              >
                Dismiss
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="flex items-center gap-1.5 bg-red-500 hover:bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-60 transition-colors"
              >
                {submitting ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Send size={12} />
                )}
                Submit Error Log
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
