export type Segment = "personal" | "business" | "investment" | "reimbursable";

export interface Transaction {
  id: number;
  account_id: number;
  source_document_id: number | null;
  date: string;
  description: string;
  amount: number;
  currency: string;
  segment: Segment;
  business_entity_id: number | null;
  business_entity_override: number | null;
  effective_business_entity_id: number | null;
  reimbursement_status: string | null;
  reimbursement_match_id: number | null;
  category: string | null;
  tax_category: string | null;
  ai_confidence: number | null;
  category_override: string | null;
  tax_category_override: string | null;
  segment_override: string | null;
  is_manually_reviewed: boolean;
  effective_category: string | null;
  effective_tax_category: string | null;
  effective_segment: Segment | null;
  period_month: number | null;
  period_year: number | null;
  notes: string | null;
  data_source: "plaid" | "csv" | "manual" | "monarch" | "amazon";
  is_excluded: boolean;
  merchant_name: string | null;
  merchant_logo_url: string | null;
  parent_transaction_id: number | null;
  children?: Transaction[];
  created_at: string;
}

export interface TransactionCreateIn {
  account_id: number;
  date: string;
  description: string;
  amount: number;
  currency?: string;
  segment?: string;
  category?: string | null;
  tax_category?: string | null;
  notes?: string | null;
}

export interface TransactionListOut {
  total: number;
  items: Transaction[];
}

export interface TransactionUpdateIn {
  category_override?: string | null;
  tax_category_override?: string | null;
  segment_override?: string | null;
  business_entity_override?: number | null;
  notes?: string | null;
  is_excluded?: boolean;
}

export interface TransactionFilters {
  segment?: string;
  category?: string;
  business_entity_id?: number;
  year?: number;
  month?: number;
  account_id?: number;
  is_excluded?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}
