import type {
  InsuranceGapAnalysis,
  InsurancePolicy,
  InsurancePolicyIn,
} from "@/types/api";
import { request } from "./api-client";

export function getInsurancePolicies(params?: { household_id?: number; policy_type?: string; is_active?: boolean }): Promise<InsurancePolicy[]> {
  const qs = params ? "?" + new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [k, String(v)])
  ).toString() : "";
  return request(`/insurance/${qs}`);
}

export function createInsurancePolicy(body: InsurancePolicyIn): Promise<InsurancePolicy> {
  return request("/insurance/", { method: "POST", body: JSON.stringify(body) });
}

export function updateInsurancePolicy(id: number, body: InsurancePolicyIn): Promise<InsurancePolicy> {
  return request(`/insurance/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteInsurancePolicy(id: number): Promise<void> {
  return request(`/insurance/${id}`, { method: "DELETE" });
}

export function getInsuranceGapAnalysis(body: {
  household_id?: number;
  spouse_a_income?: number;
  spouse_b_income?: number;
  total_debt?: number;
  dependents?: number;
  net_worth?: number;
}): Promise<InsuranceGapAnalysis> {
  return request("/insurance/gap-analysis", { method: "POST", body: JSON.stringify(body) });
}
