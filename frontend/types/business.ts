export interface BusinessEntity {
  id: number;
  name: string;
  owner: string | null;
  entity_type: string;
  tax_treatment: string;
  ein: string | null;
  is_active: boolean;
  is_provisional: boolean;
  active_from: string | null;
  active_to: string | null;
  notes: string | null;
  created_at: string;
}

export interface BusinessEntityCreateIn {
  name: string;
  owner?: string | null;
  entity_type?: string;
  tax_treatment?: string;
  ein?: string | null;
  is_provisional?: boolean;
  active_from?: string | null;
  active_to?: string | null;
  notes?: string | null;
}

export interface VendorEntityRule {
  id: number;
  vendor_pattern: string;
  business_entity_id: number;
  segment_override: string | null;
  effective_from: string | null;
  effective_to: string | null;
  priority: number;
  is_active: boolean;
  created_at: string;
}

export interface EntityReassignIn {
  from_entity_id: number;
  to_entity_id: number;
  date_from?: string | null;
  date_to?: string | null;
}

export interface VendorEntityRuleCreateIn {
  vendor_pattern: string;
  business_entity_id: number;
  segment_override?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  priority?: number;
}
