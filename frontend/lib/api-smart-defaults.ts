import { request, getBase, getAuthHeaders } from "./api-client";
import type {
  SmartDefaults,
  HouseholdUpdateSuggestion,
  SmartBudgetLine,
  TaxCarryForwardItem,
  ProactiveInsight,
  CategoryRule,
  DocumentTypeDetection,
} from "@/types/smart-defaults";

// ── Smart Defaults (core) ──────────────────────────────────────────────
export function getSmartDefaults(): Promise<SmartDefaults> {
  return request<SmartDefaults>("/smart-defaults");
}

// ── Household Updates (W-2 → Household sync) ──────────────────────────
export function getHouseholdUpdates(): Promise<{
  suggestions: HouseholdUpdateSuggestion[];
  count: number;
}> {
  return request("/smart-defaults/household-updates");
}

export function applyHouseholdUpdates(
  updates: Array<{ field: string; suggested: number | string }>,
): Promise<{ applied: number }> {
  return request("/smart-defaults/apply-household-updates", {
    method: "POST",
    body: JSON.stringify({ updates }),
  });
}

// ── Smart Budget ───────────────────────────────────────────────────────
export function generateSmartBudget(
  year: number,
  month: number,
): Promise<{ lines: SmartBudgetLine[]; total: number; year: number; month: number }> {
  return request(`/budget/auto-generate?year=${year}&month=${month}`, {
    method: "POST",
  });
}

export function applySmartBudget(
  year: number,
  month: number,
): Promise<{ created: number; year: number; month: number }> {
  return request(`/budget/auto-generate/apply?year=${year}&month=${month}`, {
    method: "POST",
  });
}

// ── Tax Carry-Forward ──────────────────────────────────────────────────
export function getTaxCarryForward(
  fromYear: number,
  toYear: number,
): Promise<{ items: TaxCarryForwardItem[]; from_year: number; to_year: number }> {
  return request(`/smart-defaults/tax-carry-forward?from_year=${fromYear}&to_year=${toYear}`);
}

// ── Proactive Insights ─────────────────────────────────────────────────
export function getProactiveInsights(): Promise<{
  insights: ProactiveInsight[];
  count: number;
}> {
  return request("/smart-defaults/insights");
}

// ── Category Rules ─────────────────────────────────────────────────────
export function getCategoryRules(): Promise<{ rules: CategoryRule[] }> {
  return request("/smart-defaults/category-rules");
}

export function learnCategory(
  transactionId: number,
  category?: string,
  taxCategory?: string,
  segment?: string,
  businessEntityId?: number,
): Promise<{
  rule_created: boolean;
  similar_count: number;
  applied_count: number;
  merchant: string;
  rule_id: number | null;
}> {
  return request("/smart-defaults/learn-category", {
    method: "POST",
    body: JSON.stringify({
      transaction_id: transactionId,
      category,
      tax_category: taxCategory,
      segment,
      business_entity_id: businessEntityId,
    }),
  });
}

export function applyCategoryRule(
  ruleId: number,
): Promise<{ applied: number; rule_id: number; merchant: string }> {
  return request(`/smart-defaults/apply-category-rule/${ruleId}`, {
    method: "POST",
  });
}

// ── Document Type Detection ────────────────────────────────────────────
export async function detectDocumentType(file: File): Promise<DocumentTypeDetection> {
  const formData = new FormData();
  formData.append("file", file);

  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${getBase()}/import/detect-type`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}
