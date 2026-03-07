import type {
  CompositeScenarioResult,
  LifeScenarioType,
  MonteCarloResult,
  MultiYearProjection,
  RetirementImpact,
  ScenarioCalcInput,
  ScenarioCalcResult,
  ScenarioComparison,
  ScenarioCreateInput,
  ScenarioTemplate,
} from "@/types/api";
import { request } from "./api-client";

export function getScenarioTemplates(): Promise<{ templates: Record<string, ScenarioTemplate> }> {
  return request("/scenarios/templates");
}

export function getScenarios(): Promise<LifeScenarioType[]> {
  return request("/scenarios");
}

export function createScenario(body: ScenarioCreateInput): Promise<LifeScenarioType> {
  return request("/scenarios", { method: "POST", body: JSON.stringify(body) });
}

export function calculateScenario(body: ScenarioCalcInput): Promise<ScenarioCalcResult> {
  return request("/scenarios/calculate", { method: "POST", body: JSON.stringify(body) });
}

export function updateScenario(id: number, body: Partial<LifeScenarioType>): Promise<LifeScenarioType> {
  return request(`/scenarios/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteScenario(id: number): Promise<void> {
  return request(`/scenarios/${id}`, { method: "DELETE" });
}

// Life Planner Extensions

export function composeScenarios(body: { scenario_ids: number[] }): Promise<CompositeScenarioResult> {
  return request("/scenarios/compose", { method: "POST", body: JSON.stringify(body) });
}

export function multiYearProjection(id: number, body: { years: number }): Promise<MultiYearProjection> {
  return request(`/scenarios/${id}/multi-year`, { method: "POST", body: JSON.stringify(body) });
}

export function retirementImpact(id: number): Promise<RetirementImpact> {
  return request(`/scenarios/${id}/retirement-impact`, { method: "POST" });
}

export function monteCarloSimulation(id: number, body: { runs?: number }): Promise<MonteCarloResult> {
  return request(`/scenarios/${id}/monte-carlo`, { method: "POST", body: JSON.stringify(body) });
}

export function compareScenarios(body: { scenario_a_id: number; scenario_b_id: number }): Promise<ScenarioComparison> {
  return request("/scenarios/compare", { method: "POST", body: JSON.stringify(body) });
}
