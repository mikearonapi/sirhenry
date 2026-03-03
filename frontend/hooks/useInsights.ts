"use client";
import { useCallback, useEffect, useState } from "react";
import { getInsights, submitOutlierFeedback, deleteOutlierFeedback } from "@/lib/api";
import type { Insights, OutlierTransaction, OutlierClassification } from "@/types/api";

export function useInsights(year: number) {
  const [data, setData] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadInsights = useCallback((signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    getInsights(year)
      .then((insights) => {
        if (signal?.aborted) return;
        setData(insights);
      })
      .catch((e: Error) => {
        if (!signal?.aborted) setError(e.message);
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false);
      });
  }, [year]);

  useEffect(() => {
    const controller = new AbortController();
    loadInsights(controller.signal);
    return () => controller.abort();
  }, [loadInsights]);

  const classify = async (
    tx: OutlierTransaction,
    classification: OutlierClassification,
    userNote?: string,
  ) => {
    await submitOutlierFeedback({
      transaction_id: tx.id,
      classification,
      user_note: userNote,
      apply_to_future: true,
      year,
    });
    loadInsights();
  };

  const undoClassification = async (tx: OutlierTransaction) => {
    if (!tx.feedback) return;
    await deleteOutlierFeedback(tx.feedback.id);
    loadInsights();
  };

  return { data, loading, error, setError, classify, undoClassification };
}
