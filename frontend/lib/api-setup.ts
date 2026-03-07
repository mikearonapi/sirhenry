import { request } from "./api-client";

export interface SetupStatus {
  household: boolean;
  income: boolean;
  accounts: boolean;
  complete: boolean;
  setup_completed_at: string | null;
}

export function getSetupStatus(): Promise<SetupStatus> {
  return request("/setup/status");
}
