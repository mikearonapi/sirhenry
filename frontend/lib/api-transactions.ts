import type {
  Transaction,
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
