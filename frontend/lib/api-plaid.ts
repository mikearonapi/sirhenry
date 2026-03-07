import type { PlaidAccount, PlaidItem } from "@/types/api";
import { request } from "./api-client";

export function getPlaidItems(): Promise<PlaidItem[]> {
  return request("/plaid/items");
}

export function getPlaidAccounts(): Promise<PlaidAccount[]> {
  return request("/plaid/accounts");
}

export function syncPlaid(): Promise<{ items_synced: number; transactions_added: number; accounts_updated: number }> {
  return request("/plaid/sync", { method: "POST" });
}

export function getPlaidLinkToken(): Promise<{ link_token: string }> {
  return request("/plaid/link-token");
}

export function exchangePlaidPublicToken(publicToken: string, institution: string): Promise<{
  id: number;
  item_id: string;
  status: string;
  sync_status?: string;
  accounts_matched?: number;
  accounts_created?: number;
}> {
  return request("/plaid/exchange-token", {
    method: "POST",
    body: JSON.stringify({ public_token: publicToken, institution_name: institution }),
  });
}

export function getPlaidSyncStatus(itemId: number): Promise<{
  id: number;
  status: string;
  sync_phase: string | null;
  last_synced_at: string | null;
  error_code: string | null;
}> {
  return request(`/plaid/sync-status/${itemId}`);
}

export function deletePlaidItem(itemId: number): Promise<{ status: string; institution: string }> {
  return request(`/plaid/items/${itemId}`, { method: "DELETE" });
}

export function getUpdateLinkToken(itemId: number): Promise<{ link_token: string }> {
  return request(`/plaid/link-token/update/${itemId}`);
}

export function getPlaidHealth(): Promise<{
  items: Array<{
    id: number;
    institution: string;
    status: string;
    stale: boolean;
    account_count: number;
  }>;
  summary: {
    total_items: number;
    total_accounts: number;
    total_assets: number;
    total_liabilities: number;
    net_balance: number;
    any_stale: boolean;
  };
}> {
  return request("/plaid/health");
}
