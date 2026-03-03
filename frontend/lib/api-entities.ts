import type { BusinessEntity, BusinessEntityCreateIn } from "@/types/api";
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
