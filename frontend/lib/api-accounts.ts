import type {
  Account,
  AccountCreateIn,
  AccountLink,
  AccountUpdateIn,
  AutoDedupResult,
  DuplicateResult,
  LinkAccountIn,
  MergeResult,
  SuggestedLink,
} from "@/types/api";
import { request } from "./api-client";

export const getAccounts = (): Promise<Account[]> =>
  request("/accounts");

export function createAccount(body: AccountCreateIn): Promise<Account> {
  return request("/accounts", { method: "POST", body: JSON.stringify(body) });
}

export function updateAccount(id: number, body: AccountUpdateIn): Promise<Account> {
  return request(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deactivateAccount(id: number): Promise<Account> {
  return request(`/accounts/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Account Linking & Merge
// ---------------------------------------------------------------------------

export function linkAccounts(accountId: number, body: LinkAccountIn): Promise<AccountLink> {
  return request(`/accounts/${accountId}/link`, { method: "POST", body: JSON.stringify(body) });
}

export function getAccountLinks(accountId: number): Promise<AccountLink[]> {
  return request(`/accounts/${accountId}/links`);
}

export function removeAccountLink(accountId: number, linkId: number): Promise<{ status: string }> {
  return request(`/accounts/${accountId}/link/${linkId}`, { method: "DELETE" });
}

export function mergeAccounts(primaryId: number, body: LinkAccountIn): Promise<MergeResult> {
  return request(`/accounts/${primaryId}/merge`, { method: "POST", body: JSON.stringify(body) });
}

export function suggestLinks(): Promise<SuggestedLink[]> {
  return request("/accounts/suggest-links");
}

// ---------------------------------------------------------------------------
// Cross-Source Dedup
// ---------------------------------------------------------------------------

export function findDuplicates(accountId: number): Promise<DuplicateResult> {
  return request(`/accounts/${accountId}/duplicates`);
}

export function autoDedup(accountId: number, minConfidence?: number): Promise<AutoDedupResult> {
  const qs = minConfidence !== undefined ? `?min_confidence=${minConfidence}` : "";
  return request(`/accounts/${accountId}/auto-dedup${qs}`, { method: "POST" });
}

export function resolveDuplicate(
  keepId: number,
  excludeId: number,
): Promise<{ status: string; excluded_id: number; kept_id: number }> {
  return request("/accounts/resolve-duplicate", {
    method: "POST",
    body: JSON.stringify({ keep_id: keepId, exclude_id: excludeId }),
  });
}
