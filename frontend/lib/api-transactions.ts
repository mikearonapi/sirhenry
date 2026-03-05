import type {
  Transaction,
  TransactionCreateIn,
  TransactionFilters,
  TransactionListOut,
  TransactionUpdateIn,
} from "@/types/api";
import { request } from "./api-client";

export function getTransactions(filters: TransactionFilters = {}): Promise<TransactionListOut> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  return request(`/transactions?${params}`);
}

export function getTransaction(id: number): Promise<Transaction> {
  return request(`/transactions/${id}`);
}

export function updateTransaction(id: number, body: TransactionUpdateIn): Promise<Transaction> {
  return request(`/transactions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function createTransaction(body: TransactionCreateIn): Promise<Transaction> {
  return request("/transactions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface TransactionAudit {
  total_transactions: number;
  categorized: number;
  uncategorized: number;
  manually_reviewed: number;
  categorization_rate: number;
  quality: "good" | "needs_attention" | "poor";
}

export function getTransactionAudit(year?: number): Promise<TransactionAudit> {
  const params = new URLSearchParams();
  if (year) params.set("year", String(year));
  return request(`/transactions/audit?${params}`);
}
