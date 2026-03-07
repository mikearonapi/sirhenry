export interface DemoStatus {
  active: boolean;
  profile_name: string | null;
}

export interface DemoSeedResult {
  status: string;
  households: number;
  accounts: number;
  transactions: number;
  [key: string]: string | number;
}
