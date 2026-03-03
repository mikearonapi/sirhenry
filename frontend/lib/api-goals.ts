import type { Goal } from "@/types/api";
import { request } from "./api-client";

export function getGoals(): Promise<Goal[]> {
  return request("/goals");
}

export function createGoal(body: Omit<Goal, "id" | "progress_pct" | "months_remaining" | "on_track">): Promise<Goal> {
  return request("/goals", { method: "POST", body: JSON.stringify(body) });
}

export function updateGoal(id: number, body: Partial<Goal>): Promise<Goal> {
  return request(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteGoal(id: number): Promise<void> {
  return request(`/goals/${id}`, { method: "DELETE" });
}
