import type { Dashboard, MonthlyReport, FinancialPeriod } from "@/types/api";
import { request } from "./api-client";

export function getDashboard(year?: number, month?: number): Promise<Dashboard> {
  const params = new URLSearchParams();
  if (year != null) params.set("year", String(year));
  if (month != null) params.set("month", String(month));
  const qs = params.toString();
  return request(`/reports/dashboard${qs ? `?${qs}` : ""}`);
}

export function getMonthlyReport(year: number, month: number, includeAiInsights = false): Promise<MonthlyReport> {
  return request(`/reports/monthly?year=${year}&month=${month}&include_ai_insights=${includeAiInsights}`);
}

export function getPeriods(year?: number, segment = "all"): Promise<FinancialPeriod[]> {
  const params = new URLSearchParams({ segment });
  if (year) params.set("year", String(year));
  return request(`/reports/periods?${params}`);
}

export function recomputePeriods(year: number): Promise<{ recomputed: number; year: number }> {
  return request(`/reports/recompute?year=${year}`, { method: "POST" });
}
