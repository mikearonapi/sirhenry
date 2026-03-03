import type { DocumentFilters, DocumentListOut } from "@/types/api";
import { request } from "./api-client";

export function getDocuments(filters: DocumentFilters = {}): Promise<DocumentListOut> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  return request(`/documents?${params}`);
}

export function deleteDocument(id: number): Promise<void> {
  return request(`/documents/${id}`, { method: "DELETE" });
}
