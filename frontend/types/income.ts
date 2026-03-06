export interface IncomeConnection {
  id: number;
  employer_name: string | null;
  status: "pending" | "syncing" | "active" | "error";
  income_source_type: "payroll" | "bank";
  last_synced_at: string | null;
}

export interface IncomeCascadeSummary {
  connection_id: number;
  status: string;
  employer: string | null;
  annual_income: number | null;
  pay_stubs_imported: number;
  benefits_detected: string[];
  last_synced_at: string | null;
}
