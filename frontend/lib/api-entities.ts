import type {
  BusinessEntity,
  BusinessEntityCreateIn,
  EntityReassignIn,
  VendorEntityRule,
  VendorEntityRuleCreateIn,
} from "@/types/api";
import { request } from "./api-client";

export function getBusinessEntities(includeInactive = false): Promise<BusinessEntity[]> {
  return request(`/entities?include_inactive=${includeInactive}`);
}

export function createBusinessEntity(body: BusinessEntityCreateIn): Promise<BusinessEntity> {
  return request("/entities", { method: "POST", body: JSON.stringify(body) });
}

export function updateBusinessEntity(id: number, body: Partial<BusinessEntityCreateIn>): Promise<BusinessEntity> {
  return request(`/entities/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteBusinessEntity(id: number): Promise<void> {
  return request(`/entities/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Vendor Entity Rules
// ---------------------------------------------------------------------------

export function getVendorRules(entityId?: number): Promise<VendorEntityRule[]> {
  const qs = entityId !== undefined ? `?entity_id=${entityId}` : "";
  return request(`/entities/rules/vendor${qs}`);
}

export function createVendorRule(body: VendorEntityRuleCreateIn): Promise<VendorEntityRule> {
  return request("/entities/rules/vendor", { method: "POST", body: JSON.stringify(body) });
}

export function deleteVendorRule(ruleId: number): Promise<void> {
  return request(`/entities/rules/vendor/${ruleId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Entity Assignment
// ---------------------------------------------------------------------------

export function applyEntityRules(params?: {
  year?: number;
  month?: number;
  document_id?: number;
}): Promise<{ updated: number }> {
  const qs = params
    ? "?" + new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  return request(`/entities/apply-rules${qs}`, { method: "POST" });
}

export function reassignEntity(body: EntityReassignIn): Promise<{ reassigned: number }> {
  return request("/entities/reassign", { method: "POST", body: JSON.stringify(body) });
}
