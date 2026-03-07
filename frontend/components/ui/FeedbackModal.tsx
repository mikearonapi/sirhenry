"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import {
  MessageSquarePlus,
  X,
  Loader2,
  CheckCircle2,
  Bug,
  Lightbulb,
  MessageCircle,
} from "lucide-react";
import { submitFeedback } from "@/app/actions/feedback";

type FeedbackType = "bug" | "feature" | "general";

const FEEDBACK_TYPES: {
  value: FeedbackType;
  label: string;
  icon: typeof Bug;
  placeholder: string;
  selectedClass: string;
  defaultClass: string;
}[] = [
  {
    value: "bug",
    label: "Bug",
    icon: Bug,
    placeholder: "What happened? What did you expect instead?",
    selectedClass: "border-red-300 bg-red-50 text-red-700",
    defaultClass: "border-border text-text-secondary hover:border-border hover:text-text-secondary",
  },
  {
    value: "feature",
    label: "Feature",
    icon: Lightbulb,
    placeholder: "What would you like to see? How would it help you?",
    selectedClass: "border-amber-300 bg-amber-50 text-amber-700",
    defaultClass: "border-border text-text-secondary hover:border-border hover:text-text-secondary",
  },
  {
    value: "general",
    label: "Feedback",
    icon: MessageCircle,
    placeholder: "Tell us what you think...",
    selectedClass: "border-blue-300 bg-blue-50 text-blue-700",
    defaultClass: "border-border text-text-secondary hover:border-border hover:text-text-secondary",
  },
];

export default function FeedbackModal({ onClose }: { onClose: () => void }) {
  const pathname = usePathname();
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("general");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Auto-close after success
  useEffect(() => {
    if (!submitted) return;
    const timer = setTimeout(onClose, 2000);
    return () => clearTimeout(timer);
  }, [submitted, onClose]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    setSubmitting(true);
    try {
      const result = await submitFeedback({
        feedback_type: feedbackType,
        message,
        email,
        page_url: pathname,
      });
      if (result.success) {
        setSubmitted(true);
      } else {
        setError(result.message);
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }, [feedbackType, message, email, pathname]);

  const activeType = FEEDBACK_TYPES.find((t) => t.value === feedbackType)!;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-2xl shadow-2xl w-full max-w-lg mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {submitted ? (
          /* ── Success state ── */
          <div className="flex flex-col items-center py-12 px-6">
            <CheckCircle2 size={40} className="text-accent mb-3" />
            <h3
              className="text-lg font-semibold text-text-primary"
              style={{ fontFamily: "var(--font-display, sans-serif)" }}
            >
              Thank you!
            </h3>
            <p className="text-sm text-text-secondary mt-1">
              Your feedback helps us build a better SirHENRY.
            </p>
          </div>
        ) : (
          <>
            {/* ── Header ── */}
            <div className="flex items-center gap-3 px-6 pt-5 pb-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-50">
                <MessageSquarePlus size={18} className="text-emerald-600" />
              </div>
              <div className="flex-1">
                <h3
                  className="text-base font-semibold text-text-primary"
                  style={{ fontFamily: "var(--font-display, sans-serif)" }}
                >
                  Send Feedback
                </h3>
                <p className="text-xs text-text-muted">
                  Help us improve SirHENRY
                </p>
              </div>
              <button
                onClick={onClose}
                className="rounded-lg p-1.5 text-text-muted hover:bg-surface hover:text-text-secondary transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* ── Body ── */}
            <div className="px-6 pb-2 space-y-4">
              {/* Type selector */}
              <div>
                <label className="text-xs text-text-secondary block mb-1.5">
                  What kind of feedback?
                </label>
                <div className="flex gap-2">
                  {FEEDBACK_TYPES.map((t) => {
                    const Icon = t.icon;
                    const isSelected = feedbackType === t.value;
                    return (
                      <button
                        key={t.value}
                        onClick={() => setFeedbackType(t.value)}
                        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                          isSelected ? t.selectedClass : t.defaultClass
                        }`}
                      >
                        <Icon size={14} />
                        {t.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Message */}
              <div>
                <label className="text-xs text-text-secondary block mb-1.5">
                  Message
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder={activeType.placeholder}
                  rows={4}
                  className="w-full rounded-lg border border-border px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                />
              </div>

              {/* Email */}
              <div>
                <label className="text-xs text-text-secondary block mb-1.5">
                  Email
                  <span className="text-text-muted ml-1">
                    — optional, so we can follow up
                  </span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-lg border border-border px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                />
              </div>

              {/* Error */}
              {error && (
                <p className="text-xs text-red-600">{error}</p>
              )}
            </div>

            {/* ── Footer ── */}
            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-card-border">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!message.trim() || submitting}
                className="flex items-center gap-1.5 bg-accent text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {submitting && <Loader2 size={14} className="animate-spin" />}
                Send Feedback
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
