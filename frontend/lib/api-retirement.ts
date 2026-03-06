import type { BudgetSnapshot, RetirementProfile, RetirementResults, RetirementBudget } from "@/types/api";
import { request } from "./api-client";

export function getRetirementProfiles(): Promise<RetirementProfile[]> {
  return request("/retirement/profiles");
}

export function createRetirementProfile(body: Omit<RetirementProfile, "id" | "target_nest_egg" | "projected_nest_egg_at_retirement" | "monthly_savings_needed" | "retirement_readiness_pct" | "years_money_will_last" | "projected_monthly_retirement_income" | "savings_gap" | "fire_number" | "coast_fire_number" | "last_computed_at">): Promise<RetirementProfile> {
  return request("/retirement/profiles", { method: "POST", body: JSON.stringify(body) });
}

export function updateRetirementProfile(id: number, body: Record<string, unknown>): Promise<RetirementProfile> {
  return request(`/retirement/profiles/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteRetirementProfile(id: number): Promise<void> {
  return request(`/retirement/profiles/${id}`, { method: "DELETE" });
}

export function calculateRetirement(body: Record<string, unknown>): Promise<RetirementResults> {
  return request("/retirement/calculate", { method: "POST", body: JSON.stringify(body) });
}

export function getRetirementBudgetSnapshot(): Promise<BudgetSnapshot> {
  return request("/retirement/budget-snapshot");
}

export interface TrajectoryScenario {
  name: "Pessimistic" | "Base" | "Optimistic";
  data: Array<{ age: number; balance: number }>;
}

export interface TrajectoryProjection {
  scenarios: TrajectoryScenario[];
  target_nest_egg: number;
  retirement_age: number;
  readiness_pct: number;
  projected_nest_egg: number;
  on_track: boolean;
}

export function getTrajectoryProjection(profileId: number): Promise<TrajectoryProjection> {
  return request(`/retirement/trajectory/${profileId}`);
}

export function getRetirementBudget(retirementAge: number = 65): Promise<RetirementBudget> {
  return request(`/retirement/retirement-budget?retirement_age=${retirementAge}`);
}

export function saveRetirementBudgetOverride(body: {
  category: string;
  multiplier?: number | null;
  fixed_amount?: number | null;
  reason?: string | null;
}): Promise<{ status: string }> {
  return request("/retirement/retirement-budget/override", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}
