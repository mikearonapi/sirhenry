import { request } from "./api-client";
import type { DemoStatus, DemoSeedResult } from "@/types/demo";

export function getDemoStatus(): Promise<DemoStatus> {
  return request("/demo/status");
}

export function seedDemo(): Promise<DemoSeedResult> {
  return request("/demo/seed", { method: "POST" });
}

export function resetDemo(): Promise<{ status: string }> {
  return request("/demo/reset", { method: "POST" });
}

/** Switch the API to local or demo database mode. */
export function selectMode(mode: "local" | "demo"): Promise<{ status: string; mode: string }> {
  return request("/auth/select-mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

/** Get the current database mode from the API. */
export function getMode(): Promise<{ mode: string }> {
  return request("/auth/mode");
}
