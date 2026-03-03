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

export function exchangePlaidPublicToken(publicToken: string, institution: string): Promise<{ item_id: string; status: string }> {
  return request("/plaid/exchange-token", {
    method: "POST",
    body: JSON.stringify({ public_token: publicToken, institution_name: institution }),
  });
}
