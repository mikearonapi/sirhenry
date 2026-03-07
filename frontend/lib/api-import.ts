import type { ImportResult } from "@/types/api";
import { getBase, getAuthHeaders, request } from "./api-client";

export async function uploadFile(
  file: File,
  documentType: string,
  options: {
    accountName?: string;
    institution?: string;
    segment?: string;
    taxYear?: number;
    runCategorize?: boolean;
  } = {}
): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("document_type", documentType);
  form.append("account_name", options.accountName ?? "");
  form.append("institution", options.institution ?? "");
  form.append("segment", options.segment ?? "personal");
  if (options.taxYear) form.append("tax_year", String(options.taxYear));
  form.append("run_categorize", String(options.runCategorize ?? true));

  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${getBase()}/import/upload`, { method: "POST", headers: authHeaders, body: form });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Import failed (${res.status}): ${body}`);
  }
  return res.json();
}

export function runCategorization(year?: number, month?: number): Promise<{ categorized: number; skipped: number; errors: number }> {
  const params = new URLSearchParams();
  if (year) params.set("year", String(year));
  if (month) params.set("month", String(month));
  return request(`/import/categorize?${params}`, { method: "POST" });
}
