export interface RulesSummary {
  category_rule_count: number;
  vendor_rule_count: number;
  context_count: number;
  total_matches: number;
  total_transactions: number;
}

export interface CategoryRuleWithEntity {
  id: number;
  merchant_pattern: string;
  category: string | null;
  tax_category: string | null;
  segment: string | null;
  business_entity_id: number | null;
  entity_name: string | null;
  match_count: number;
  is_active: boolean;
  source: string;
  effective_from: string | null;
  effective_to: string | null;
}

export interface RuleCategoriesResponse {
  categories: string[];
  tax_categories: string[];
}

export interface VendorRuleWithEntity {
  id: number;
  vendor_pattern: string;
  business_entity_id: number;
  entity_name: string | null;
  segment_override: string | null;
  effective_from: string | null;
  effective_to: string | null;
  priority: number;
  is_active: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Rule Generation
// ---------------------------------------------------------------------------

export interface ProposedRule {
  merchant: string;
  category: string | null;
  tax_category: string | null;
  segment: string | null;
  entity_id: number | null;
  entity_name: string | null;
  transaction_count: number;
  confidence: number;
  source: "pattern" | "ai";
}

export interface GenerateRulesResponse {
  rules: ProposedRule[];
  stats: {
    from_patterns: number;
    from_ai: number;
    total_transactions_covered: number;
    existing_rules_skipped: number;
  };
}

export interface ApplyGeneratedRulesResponse {
  rules_created: number;
  duplicates_skipped: number;
  transactions_categorized: number;
}

export interface UserContextEntry {
  id: number;
  category: string;
  key: string;
  value: string;
  source: string;
  confidence: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
