export interface Account {
  id: number;
  name: string;
  account_type: "personal" | "business" | "investment" | "income";
  subtype: string | null;
  institution: string | null;
  last_four: string | null;
  currency: string;
  is_active: boolean;
  default_segment: string | null;
  default_business_entity_id: number | null;
  notes: string | null;
  created_at: string;
  balance: number;
  transaction_count: number;
}

export interface Document {
  id: number;
  filename: string;
  file_type: string;
  document_type: string;
  status: "pending" | "processing" | "completed" | "failed" | "duplicate";
  tax_year: number | null;
  account_id: number | null;
  error_message: string | null;
  imported_at: string;
  processed_at: string | null;
}

export interface DocumentListOut {
  total: number;
  items: Document[];
}

export interface PlaidItem {
  id: number;
  institution_name: string | null;
  status: "active" | "error" | "reauth_needed";
  last_synced_at: string | null;
  account_count: number;
}

export interface PlaidAccount {
  id: number;
  name: string;
  official_name: string | null;
  type: string;
  subtype: string | null;
  current_balance: number | null;
  available_balance: number | null;
  limit_balance: number | null;
  mask: string | null;
  last_updated: string | null;
}

export interface PlaidExchangeResult {
  item_id: string;
  status: string;
}

export interface ImportResult {
  document_id: number;
  filename: string;
  status: string;
  transactions_imported: number;
  transactions_skipped: number;
  message: string;
}

export interface DocumentFilters {
  document_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}
