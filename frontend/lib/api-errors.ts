import { request } from "./api-client";
import type { ErrorReportPayload, ErrorReportOut } from "@/types/errors";

export async function submitErrorReport(
  payload: ErrorReportPayload,
): Promise<{ id: number; status: string }> {
  return request("/errors/report", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getErrorReports(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: ErrorReportOut[]; total: number }> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return request(`/errors/reports${query ? `?${query}` : ""}`);
}

export async function updateErrorReportStatus(
  errorId: number,
  status: string,
): Promise<{ id: number; status: string }> {
  return request(`/errors/reports/${errorId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
