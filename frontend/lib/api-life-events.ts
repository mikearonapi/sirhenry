import type { LifeEvent, LifeEventIn } from "@/types/api";
import { request } from "./api-client";

export function getLifeEvents(params?: { household_id?: number; event_type?: string; tax_year?: number }): Promise<LifeEvent[]> {
  const qs = params ? "?" + new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [k, String(v)])
  ).toString() : "";
  return request(`/life-events/${qs}`);
}

export function createLifeEvent(body: LifeEventIn): Promise<LifeEvent> {
  return request("/life-events/", { method: "POST", body: JSON.stringify(body) });
}

export function updateLifeEvent(id: number, body: LifeEventIn): Promise<LifeEvent> {
  return request(`/life-events/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteLifeEvent(id: number): Promise<void> {
  return request(`/life-events/${id}`, { method: "DELETE" });
}

export function toggleLifeEventActionItem(eventId: number, itemIndex: number, completed: boolean): Promise<{ status: string; items: unknown[] }> {
  return request(`/life-events/${eventId}/action-items/${itemIndex}`, {
    method: "PATCH",
    body: JSON.stringify({ index: itemIndex, completed }),
  });
}
