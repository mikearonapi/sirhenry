import { request } from "./api-client";
import type {
  VehicleDecodeResult,
  PropertyValuationResult,
  RefreshValuationResult,
} from "@/types/valuations";

export function decodeVehicleVin(vin: string): Promise<VehicleDecodeResult> {
  return request(`/valuations/vehicle/${encodeURIComponent(vin)}`);
}

export function getPropertyValuation(
  address: string,
): Promise<PropertyValuationResult> {
  return request(`/valuations/property?address=${encodeURIComponent(address)}`);
}

export function refreshAssetValuation(
  assetId: number,
  body?: { vin?: string; address?: string },
): Promise<RefreshValuationResult> {
  return request(`/valuations/assets/${assetId}/refresh`, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}
