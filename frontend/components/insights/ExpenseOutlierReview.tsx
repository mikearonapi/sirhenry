"use client";
import { useState } from "react";
import {
  Loader2, ChevronDown, ChevronUp,
  Calendar, Ban, CheckCircle2, MessageSquare, X, Check,
  ClipboardCheck, Eye, RotateCcw,
} from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { OutlierTransaction, OutlierClassification, OutlierReviewSummary } from "@/types/api";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { CLASSIFICATION_CONFIG } from "./constants";

type ReviewFilter = "all" | "pending" | "recurring" | "one_time" | "not_outlier";

interface Props {
  expenseOutliers: OutlierTransaction[];
  outlierReview: OutlierReviewSummary | null;
  onClassify: (tx: OutlierTransaction, classification: OutlierClassification, note?: string) => Promise<void>;
  onUndo: (tx: OutlierTransaction) => Promise<void>;
  onError: (msg: string) => void;
}

export default function ExpenseOutlierReview({
  expenseOutliers, outlierReview, onClassify, onUndo, onError,
}: Props) {
  const [reviewMode, setReviewMode] = useState(false);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [expandedOutliers, setExpandedOutliers] = useState(false);
  const [activeNoteId, setActiveNoteId] = useState<number | null>(null);
  const [noteText, setNoteText] = useState("");
  const [submitting, setSubmitting] = useState<number | null>(null);

  const review = outlierReview ?? { total_outliers: 0, reviewed: 0, recurring: 0, one_time: 0, not_outlier: 0 };
  const pendingCount = expenseOutliers.filter((tx) => !tx.feedback).length;
  const reviewPct = review.total_outliers > 0 ? Math.round((review.reviewed / review.total_outliers) * 100) : 0;

  const filteredExpenseOutliers = expenseOutliers.filter((tx) => {
    if (reviewFilter === "all") return true;
    if (reviewFilter === "pending") return !tx.feedback;
    return tx.feedback?.classification === reviewFilter;
  });

  const visibleOutliers = reviewMode
    ? filteredExpenseOutliers
    : expandedOutliers
      ? expenseOutliers
      : expenseOutliers.slice(0, 5);

  const handleClassify = async (tx: OutlierTransaction, classification: OutlierClassification) => {
    setSubmitting(tx.id);
    try {
      const note = activeNoteId === tx.id && noteText.trim() ? noteText.trim() : undefined;
      await onClassify(tx, classification, note);
      setActiveNoteId(null);
      setNoteText("");
    } catch {
      onError("Failed to save feedback");
    } finally {
      setSubmitting(null);
    }
  };

  const handleUndo = async (tx: OutlierTransaction) => {
    if (!tx.feedback) return;
    setSubmitting(tx.id);
    try {
      await onUndo(tx);
    } catch {
      onError("Failed to remove feedback");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <Card padding="none">
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-stone-700">Expense Outlier Review</h2>
            <p className="text-xs text-stone-400 mt-0.5">
              Classify each flagged transaction so the system learns your spending patterns
            </p>
          </div>
          <div className="flex items-center gap-2">
            {pendingCount > 0 && (
              <Badge variant="warning" dot>{pendingCount} pending</Badge>
            )}
            {reviewPct === 100 && review.total_outliers > 0 && (
              <Badge variant="success" dot>All reviewed</Badge>
            )}
            <button
              onClick={() => { setReviewMode(!reviewMode); setReviewFilter("all"); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                reviewMode
                  ? "bg-[#16A34A] text-white"
                  : "bg-stone-100 text-stone-600 hover:bg-stone-200"
              }`}
            >
              {reviewMode ? <><Eye size={13} /> Exit Review</> : <><ClipboardCheck size={13} /> Review Outliers</>}
            </button>
          </div>
        </div>

        {review.total_outliers > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-stone-500">
                {review.reviewed} of {review.total_outliers} reviewed
              </span>
              <span className="text-xs font-medium text-stone-600">{reviewPct}%</span>
            </div>
            <div className="w-full h-2 bg-stone-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${reviewPct}%`,
                  background: reviewPct === 100
                    ? "#22c55e"
                    : "linear-gradient(90deg, #3b82f6, #16A34A)",
                }}
              />
            </div>
            {review.reviewed > 0 && (
              <div className="flex items-center gap-4 mt-2">
                {review.recurring > 0 && (
                  <span className="text-[11px] text-blue-600 flex items-center gap-1">
                    <Calendar size={11} /> {review.recurring} recurring
                  </span>
                )}
                {review.one_time > 0 && (
                  <span className="text-[11px] text-amber-600 flex items-center gap-1">
                    <Ban size={11} /> {review.one_time} one-time
                  </span>
                )}
                {review.not_outlier > 0 && (
                  <span className="text-[11px] text-green-600 flex items-center gap-1">
                    <CheckCircle2 size={11} /> {review.not_outlier} not outliers
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {reviewMode && (
          <div className="flex items-center gap-1 mt-4 p-1 bg-stone-50 rounded-lg">
            {([
              ["all", `All (${expenseOutliers.length})`],
              ["pending", `Pending (${pendingCount})`],
              ["recurring", `Recurring (${review.recurring})`],
              ["one_time", `One-Time (${review.one_time})`],
              ["not_outlier", `Not Outlier (${review.not_outlier})`],
            ] as [ReviewFilter, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setReviewFilter(key)}
                className={`flex-1 py-1.5 text-[11px] font-medium rounded-md transition-colors ${
                  reviewFilter === key
                    ? "bg-white text-stone-800 shadow-sm"
                    : "text-stone-500 hover:text-stone-700"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {expenseOutliers.length === 0 ? (
        <p className="text-stone-400 text-sm text-center py-8 px-5">No expense outliers detected.</p>
      ) : (
        <>
          <div className="divide-y divide-stone-100">
            {visibleOutliers.map((tx: OutlierTransaction) => {
              const isActive = submitting === tx.id;
              const hasFeedback = !!tx.feedback;
              const fbConfig = hasFeedback
                ? CLASSIFICATION_CONFIG[tx.feedback!.classification]
                : null;

              return (
                <div
                  key={tx.id}
                  className={`px-5 py-4 transition-colors ${
                    hasFeedback && !reviewMode ? "bg-stone-50/30" : "hover:bg-stone-50/50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-stone-800 truncate">{tx.description}</p>
                        {hasFeedback && fbConfig && (
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium ${fbConfig.bg} ${fbConfig.text}`}>
                            {fbConfig.icon} {fbConfig.label}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[11px] text-stone-400">
                          {tx.date ? formatDate(tx.date) : "—"}
                        </span>
                        <Badge variant="default">{tx.category}</Badge>
                        <span className="text-[11px] text-stone-400">
                          typical: {formatCurrency(tx.typical_amount)}
                        </span>
                      </div>
                      <p className="text-xs text-amber-600 mt-1.5 bg-amber-50/50 rounded px-2 py-1 inline-block">
                        {tx.reason}
                      </p>
                      {hasFeedback && tx.feedback!.user_note && (
                        <p className="text-xs text-stone-500 mt-1.5 flex items-start gap-1">
                          <MessageSquare size={11} className="mt-0.5 flex-shrink-0" />
                          {tx.feedback!.user_note}
                        </p>
                      )}
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-semibold text-red-600 tabular-nums">{formatCurrency(tx.amount)}</p>
                      <p className="text-[11px] text-stone-400">
                        {tx.excess_pct > 0 ? `+${tx.excess_pct.toFixed(0)}%` : ""}
                      </p>
                    </div>
                  </div>

                  {reviewMode && (
                    <div className="mt-3 flex items-center gap-2 flex-wrap">
                      {hasFeedback ? (
                        <button
                          onClick={() => handleUndo(tx)}
                          disabled={isActive}
                          className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-stone-500 bg-stone-100 rounded-lg hover:bg-stone-200 transition-colors disabled:opacity-50"
                        >
                          <RotateCcw size={12} /> Undo
                        </button>
                      ) : (
                        <>
                          {(Object.entries(CLASSIFICATION_CONFIG) as [OutlierClassification, typeof CLASSIFICATION_CONFIG[OutlierClassification]][]).map(
                            ([key, cfg]) => (
                              <button
                                key={key}
                                onClick={() => handleClassify(tx, key)}
                                disabled={isActive}
                                className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium rounded-lg border transition-colors disabled:opacity-50 ${cfg.bg} ${cfg.text} ${cfg.border} hover:opacity-80`}
                              >
                                {isActive ? <Loader2 size={12} className="animate-spin" /> : cfg.icon}
                                {cfg.label}
                              </button>
                            )
                          )}
                        </>
                      )}
                      {!hasFeedback && (
                        <button
                          onClick={() => {
                            setActiveNoteId(activeNoteId === tx.id ? null : tx.id);
                            setNoteText("");
                          }}
                          className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-stone-500 rounded-lg hover:bg-stone-100 transition-colors"
                        >
                          <MessageSquare size={12} />
                          {activeNoteId === tx.id ? "Cancel note" : "Add note"}
                        </button>
                      )}
                    </div>
                  )}

                  {reviewMode && activeNoteId === tx.id && !hasFeedback && (
                    <div className="mt-2 flex items-center gap-2">
                      <input
                        type="text"
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        placeholder="e.g. Annual school tuition, paid every July"
                        className="flex-1 text-xs border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
                        onKeyDown={(e) => {
                          if (e.key === "Escape") {
                            setActiveNoteId(null);
                            setNoteText("");
                          }
                        }}
                      />
                      <button
                        onClick={() => { setActiveNoteId(null); setNoteText(""); }}
                        className="p-1.5 text-stone-400 hover:text-stone-600"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {!reviewMode && expenseOutliers.length > 5 && (
            <button
              onClick={() => setExpandedOutliers(!expandedOutliers)}
              className="w-full py-2.5 text-xs text-[#16A34A] font-medium hover:bg-stone-50 flex items-center justify-center gap-1"
            >
              {expandedOutliers ? (
                <><ChevronUp size={14} /> Show less</>
              ) : (
                <><ChevronDown size={14} /> Show all {expenseOutliers.length} outliers</>
              )}
            </button>
          )}
          {reviewMode && filteredExpenseOutliers.length === 0 && (
            <div className="text-center py-8">
              <Check className="mx-auto text-green-300 mb-2" size={28} />
              <p className="text-stone-400 text-sm">
                {reviewFilter === "pending"
                  ? "All outliers have been reviewed!"
                  : `No outliers with "${reviewFilter.replace("_", " ")}" classification.`}
              </p>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
