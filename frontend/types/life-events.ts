export interface ActionItem {
  text: string;
  completed: boolean;
  link?: string;
}

export interface LifeEvent {
  id: number;
  household_id: number | null;
  event_type: string;
  event_subtype: string | null;
  title: string;
  event_date: string | null;
  tax_year: number | null;
  amounts_json: string | null;
  status: "upcoming" | "completed" | "needs_documentation";
  action_items_json: string | null;
  document_ids_json: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LifeEventIn {
  household_id?: number | null;
  event_type: string;
  event_subtype?: string | null;
  title: string;
  event_date?: string | null;
  tax_year?: number | null;
  amounts_json?: string | null;
  status?: string;
  action_items_json?: string | null;
  notes?: string | null;
}
