import { request } from "./api-client";
import type {
  RulesSummary,
  CategoryRuleWithEntity,
  VendorRuleWithEntity,
  UserContextEntry,
  ProposedRule,
  GenerateRulesResponse,
  ApplyGeneratedRulesResponse,
  RuleCategoriesResponse,
} from "@/types/rules";

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

export function getRulesSummary() {
  return request<RulesSummary>("/rules/summary");
}

// ---------------------------------------------------------------------------
// Category Rules
// ---------------------------------------------------------------------------

export function getCategoryRulesWithEntities() {
  return request<{ rules: CategoryRuleWithEntity[] }>("/rules/category");
}

export function updateCategoryRule(
  ruleId: number,
  data: Partial<Pick<CategoryRuleWithEntity, "category" | "tax_category" | "segment" | "business_entity_id" | "is_active" | "effective_from" | "effective_to">>,
) {
  return request(`/rules/category/${ruleId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteCategoryRule(ruleId: number) {
  return request(`/rules/category/${ruleId}`, { method: "DELETE" });
}

export function applyCategoryRuleRetro(ruleId: number) {
  return request<{ applied: number; rule_id: number; merchant: string }>(
    `/rules/category/${ruleId}/apply`,
    { method: "POST" },
  );
}

// ---------------------------------------------------------------------------
// Vendor Rules
// ---------------------------------------------------------------------------

export function getVendorRulesWithEntities() {
  return request<{ rules: VendorRuleWithEntity[] }>("/rules/vendor");
}

// ---------------------------------------------------------------------------
// Categories (for edit dropdowns)
// ---------------------------------------------------------------------------

export function getRuleCategories() {
  return request<RuleCategoriesResponse>("/rules/categories");
}

// ---------------------------------------------------------------------------
// Rule Generation
// ---------------------------------------------------------------------------

export function generateRules(includeAi = false) {
  return request<GenerateRulesResponse>(
    `/rules/generate${includeAi ? "?include_ai=true" : ""}`,
    { method: "POST" },
  );
}

export function applyGeneratedRules(rules: ProposedRule[]) {
  return request<ApplyGeneratedRulesResponse>("/rules/generate/apply", {
    method: "POST",
    body: JSON.stringify({ rules }),
  });
}

// ---------------------------------------------------------------------------
// User Context
// ---------------------------------------------------------------------------

export function getUserContext(category?: string) {
  const params = category ? `?category=${category}` : "";
  return request<{ count: number; facts: UserContextEntry[] }>(
    `/user-context${params}`,
  );
}

export function upsertUserContext(data: {
  category: string;
  key: string;
  value: string;
  source?: string;
}) {
  return request<UserContextEntry>("/user-context", {
    method: "POST",
    body: JSON.stringify({ source: "manual", ...data }),
  });
}

export function deleteUserContext(contextId: number) {
  return request(`/user-context/${contextId}`, { method: "DELETE" });
}
