import type { Account } from "@/types/api";
import { request } from "./api-client";

export const getAccounts = (): Promise<Account[]> =>
  request("/accounts");
