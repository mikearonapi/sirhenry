import { request } from "./api-client";

export interface SetupStatus {
  household: boolean;
  income: boolean;
  accounts: boolean;
  complete: boolean;
}

export function getSetupStatus(): Promise<SetupStatus> {
  return request("/setup/status");
}
