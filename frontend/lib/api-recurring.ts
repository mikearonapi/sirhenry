import type { RecurringItem, RecurringSummary } from "@/types/api";
import { request } from "./api-client";

export function getRecurring(): Promise<RecurringItem[]> {
  return request("/recurring");
}

export function getRecurringSummary(): Promise<RecurringSummary> {
  return request("/recurring/summary");
}

export function detectRecurring(): Promise<{ detected: number }> {
  return request("/recurring/detect", { method: "POST" });
}

export function updateRecurring(id: number, body: Partial<RecurringItem>): Promise<RecurringItem> {
  return request(`/recurring/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}
