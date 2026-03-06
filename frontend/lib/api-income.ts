import { request } from "./api-client";
import type { IncomeConnection, IncomeCascadeSummary } from "@/types/income";

export function getIncomeLinkToken(
  incomeSourceType: "payroll" | "bank" = "payroll",
): Promise<{ link_token: string; connection_id: number }> {
  return request("/income/link-token", {
    method: "POST",
    body: JSON.stringify({ income_source_type: incomeSourceType }),
  });
}

export function notifyIncomeConnected(
  connectionId: number,
): Promise<{ status: string; connection_id: number }> {
  return request(`/income/connected/${connectionId}`, { method: "POST" });
}

export function getIncomeConnections(): Promise<IncomeConnection[]> {
  return request("/income/connections");
}

export function getIncomeCascadeSummary(
  connectionId: number,
): Promise<IncomeCascadeSummary> {
  return request(`/income/cascade-summary/${connectionId}`);
}
