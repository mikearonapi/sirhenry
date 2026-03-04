import type { PrivacyConsent, PrivacyDisclosure } from "@/types/api";
import { request } from "./api-client";

export function getPrivacyConsent(): Promise<PrivacyConsent[]> {
  return request("/privacy/consent");
}

export function setPrivacyConsent(
  consentType: string,
  consented: boolean,
): Promise<PrivacyConsent> {
  return request("/privacy/consent", {
    method: "POST",
    body: JSON.stringify({ consent_type: consentType, consented }),
  });
}

export function getPrivacyDisclosure(): Promise<PrivacyDisclosure> {
  return request("/privacy/disclosure");
}

export function getAuditLog(params?: {
  action_type?: string;
  limit?: number;
  offset?: number;
}): Promise<
  {
    id: number;
    timestamp: string;
    action_type: string;
    data_category: string | null;
    detail: string | null;
    duration_ms: number | null;
  }[]
> {
  const searchParams = new URLSearchParams();
  if (params?.action_type) searchParams.set("action_type", params.action_type);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return request(`/privacy/audit-log${qs ? `?${qs}` : ""}`);
}
