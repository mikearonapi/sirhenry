import type { ManualAsset, ManualAssetCreateIn, ManualAssetUpdateIn } from "@/types/api";
import { request } from "./api-client";

export function getManualAssets(): Promise<ManualAsset[]> {
  return request("/assets");
}

export function createManualAsset(body: ManualAssetCreateIn): Promise<ManualAsset> {
  return request("/assets", { method: "POST", body: JSON.stringify(body) });
}

export function updateManualAsset(id: number, body: ManualAssetUpdateIn): Promise<ManualAsset> {
  return request(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteManualAsset(id: number): Promise<void> {
  return request(`/assets/${id}`, { method: "DELETE" });
}
