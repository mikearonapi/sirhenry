import type { Reminder } from "@/types/api";
import { request } from "./api-client";

export function getReminders(type?: string, status?: string): Promise<Reminder[]> {
  const params = new URLSearchParams();
  if (type) params.set("reminder_type", type);
  if (status) params.set("status", status);
  const qs = params.toString();
  return request(`/reminders${qs ? `?${qs}` : ""}`);
}

export function createReminder(body: Partial<Reminder>): Promise<Reminder> {
  return request("/reminders", { method: "POST", body: JSON.stringify(body) });
}

export function updateReminder(id: number, body: Partial<Reminder>): Promise<Reminder> {
  return request(`/reminders/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteReminder(id: number): Promise<void> {
  return request(`/reminders/${id}`, { method: "DELETE" });
}

export function seedTaxDeadlines(): Promise<{ seeded: number }> {
  return request("/reminders/seed-all", { method: "POST" });
}
