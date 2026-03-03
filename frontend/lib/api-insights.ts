import type { Insights, OutlierFeedback, OutlierFeedbackIn } from "@/types/api";
import { request } from "./api-client";

export function getInsights(year?: number): Promise<Insights> {
  const params = new URLSearchParams();
  if (year != null) params.set("year", String(year));
  const qs = params.toString();
  return request(`/insights/annual${qs ? `?${qs}` : ""}`);
}

export function submitOutlierFeedback(body: OutlierFeedbackIn): Promise<OutlierFeedback> {
  return request("/insights/outlier-feedback", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteOutlierFeedback(feedbackId: number): Promise<void> {
  return request(`/insights/outlier-feedback/${feedbackId}`, { method: "DELETE" });
}
