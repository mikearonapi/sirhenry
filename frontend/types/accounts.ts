export interface Account {
  id: number;
  name: string;
  account_type: "personal" | "business" | "investment" | "income";
  subtype: string | null;
  institution: string | null;
  last_four: string | null;
  currency: string;
  is_active: boolean;
  data_source: "plaid" | "csv" | "manual" | "api" | "monarch";
  default_segment: string | null;
  default_business_entity_id: number | null;
  notes: string | null;
  created_at: string;
  balance: number;
  transaction_count: number;
  // Plaid metadata (only populated for plaid-sourced accounts)
  plaid_mask?: string | null;
  plaid_type?: string | null;
  plaid_subtype?: string | null;
  plaid_last_synced?: string | null;
  plaid_institution?: string | null;
  current_balance?: number | null;
  available_balance?: number | null;
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
  accounts_matched?: number;
}

export interface ImportResult {
  document_id: number;
  filename: string;
  status: string;
  transactions_imported: number;
  transactions_skipped: number;
  transactions_split?: number;
  message: string;
}

export interface DocumentFilters {
  document_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Account CRUD
// ---------------------------------------------------------------------------

export interface AccountCreateIn {
  name: string;
  account_type: string;
  subtype?: string | null;
  institution?: string | null;
  last_four?: string | null;
  currency?: string;
  notes?: string | null;
  data_source?: string;
  default_segment?: string | null;
  default_business_entity_id?: number | null;
}

export interface AccountUpdateIn {
  name?: string;
  account_type?: string;
  subtype?: string | null;
  institution?: string | null;
  last_four?: string | null;
  currency?: string;
  notes?: string | null;
  is_active?: boolean;
  default_segment?: string | null;
  default_business_entity_id?: number | null;
}

// ---------------------------------------------------------------------------
// Account Linking & Merge
// ---------------------------------------------------------------------------

export interface AccountLink {
  id: number;
  primary_account_id: number;
  secondary_account_id: number;
  link_type: string;
  created_at: string;
}

export interface LinkAccountIn {
  target_account_id: number;
  link_type?: string;
}

export interface MergeResult {
  primary_account_id: number;
  secondary_account_id: number;
  transactions_moved: number;
  documents_moved: number;
  secondary_deactivated: boolean;
}

export interface SuggestedLink {
  account_a_id: number;
  account_a_name: string;
  account_a_source: string;
  account_b_id: number;
  account_b_name: string;
  account_b_source: string;
  match_reason: string;
}

// ---------------------------------------------------------------------------
// Cross-Source Dedup
// ---------------------------------------------------------------------------

export interface DuplicateCandidate {
  plaid_tx_id: number;
  csv_tx_id: number;
  plaid_date: string;
  csv_date: string;
  amount: number;
  confidence: number;
  description_similarity: number;
  plaid_description: string;
  csv_description: string;
}

export interface DuplicateResult {
  account_id: number;
  candidates: DuplicateCandidate[];
  count: number;
}

export interface AutoDedupResult {
  resolved: number;
  skipped: number;
  total_candidates: number;
}
