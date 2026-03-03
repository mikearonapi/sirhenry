import type {
  BenefitPackageType,
  FamilyMember,
  FamilyMemberIn,
  FamilyMilestone,
  HouseholdOptimizationResult,
  HouseholdProfile,
  HouseholdProfileIn,
  TaxThresholdResult,
  W4OptimizationResult,
} from "@/types/api";
import { request } from "./api-client";

// Family Members

export function getFamilyMembers(householdId?: number): Promise<FamilyMember[]> {
  const qs = householdId !== undefined ? `?household_id=${householdId}` : "";
  return request(`/family-members/${qs}`);
}

export function createFamilyMember(body: FamilyMemberIn): Promise<FamilyMember> {
  return request("/family-members/", { method: "POST", body: JSON.stringify(body) });
}

export function updateFamilyMember(id: number, body: Partial<FamilyMemberIn>): Promise<FamilyMember> {
  return request(`/family-members/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteFamilyMember(id: number): Promise<void> {
  return request(`/family-members/${id}`, { method: "DELETE" });
}

export function getFamilyMilestones(householdId: number): Promise<FamilyMilestone[]> {
  return request(`/family-members/milestones/by-household?household_id=${householdId}`);
}

// Household Optimization

export function getHouseholdProfiles(): Promise<HouseholdProfile[]> {
  return request("/household/profiles");
}

export function createHouseholdProfile(body: HouseholdProfileIn): Promise<HouseholdProfile> {
  return request("/household/profiles", { method: "POST", body: JSON.stringify(body) });
}

export function updateHouseholdProfile(id: number, body: HouseholdProfileIn): Promise<HouseholdProfile> {
  return request(`/household/profiles/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteHouseholdProfile(id: number): Promise<void> {
  return request(`/household/profiles/${id}`, { method: "DELETE" });
}

export function optimizeHousehold(body: { household_id: number; tax_year?: number }): Promise<HouseholdOptimizationResult> {
  return request("/household/optimize", { method: "POST", body: JSON.stringify(body) });
}

export function getHouseholdOptimization(id: number): Promise<HouseholdOptimizationResult> {
  return request(`/household/profiles/${id}/optimization`);
}

export function compareFilingStatus(body: { spouse_a_income: number; spouse_b_income: number; state?: string; dependents?: number }): Promise<{ mfj_tax: number; mfs_tax: number; savings: number; recommendation: string }> {
  return request("/household/filing-comparison", { method: "POST", body: JSON.stringify(body) });
}

export function getHouseholdBenefits(profileId: number): Promise<BenefitPackageType[]> {
  return request(`/household/profiles/${profileId}/benefits`);
}

export function upsertHouseholdBenefits(profileId: number, body: Partial<BenefitPackageType> & { spouse: string }): Promise<{ status: string }> {
  return request(`/household/profiles/${profileId}/benefits`, { method: "POST", body: JSON.stringify(body) });
}

export function w4Optimization(body: {
  spouse_a_income: number;
  spouse_b_income: number;
  spouse_a_pay_periods?: number;
  spouse_b_pay_periods?: number;
  other_income?: number;
  pre_tax_deductions_a?: number;
  pre_tax_deductions_b?: number;
  filing_status?: string;
}): Promise<W4OptimizationResult> {
  return request("/household/w4-optimization", { method: "POST", body: JSON.stringify(body) });
}

export function getTaxThresholds(body: {
  spouse_a_income: number;
  spouse_b_income: number;
  capital_gains?: number;
  qualified_dividends?: number;
  pre_tax_deductions?: number;
  filing_status?: string;
  dependents?: number;
}): Promise<TaxThresholdResult> {
  return request("/household/tax-thresholds", { method: "POST", body: JSON.stringify(body) });
}
