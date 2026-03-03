export interface EquityGrant {
  id: number;
  employer_name: string;
  grant_type: "rsu" | "iso" | "nso" | "espp";
  grant_date: string;
  total_shares: number;
  vested_shares: number;
  unvested_shares: number;
  vesting_schedule_json: string | null;
  strike_price: number | null;
  current_fmv: number | null;
  exercise_price: number | null;
  expiration_date: string | null;
  ticker: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EquityGrantIn {
  employer_name: string;
  grant_type: "rsu" | "iso" | "nso" | "espp";
  grant_date: string;
  total_shares: number;
  vested_shares?: number;
  unvested_shares?: number;
  vesting_schedule_json?: string | null;
  strike_price?: number | null;
  current_fmv?: number | null;
  exercise_price?: number | null;
  expiration_date?: string | null;
  ticker?: string | null;
  notes?: string | null;
}

export interface VestingEventType {
  id: number;
  grant_id: number;
  vest_date: string;
  shares: number;
  price_at_vest: number | null;
  withheld_shares: number | null;
  federal_withholding_pct: number | null;
  state_withholding_pct: number | null;
  is_sold: boolean;
  sale_price: number | null;
  sale_date: string | null;
  net_proceeds: number | null;
  tax_impact_json: string | null;
  status: "upcoming" | "vested" | "sold" | "expired";
}

export interface EquityDashboard {
  total_equity_value: number;
  upcoming_vest_value_12mo: number;
  total_withholding_gap: number;
  grants_count: number;
  grants: Array<{
    id: number;
    employer: string;
    grant_type: string;
    total_shares: number;
    vested_shares: number;
    unvested_shares: number;
    current_fmv: number;
    total_value: number;
  }>;
}

export interface WithholdingGapResult {
  total_vest_income: number;
  total_withholding_at_supplemental: number;
  actual_marginal_rate: number;
  total_tax_at_marginal: number;
  withholding_gap: number;
  quarterly_payments: Array<{ quarter: number; due_date: string; amount: number }>;
  state_rate: number;
  state_tax: number;
}

export interface AMTCrossoverResult {
  safe_exercise_shares: number;
  amt_trigger_point: number;
  iso_bargain_element: number;
  amt_exemption: number;
  amt_tax_without_exercise: number;
  amt_tax_with_exercise: number;
  regular_tax: number;
  recommendation: string;
}

export interface SellStrategyResult {
  immediate_sell: { gross_proceeds: number; gain: number; tax_rate: number; tax: number; net_proceeds: number };
  hold_one_year: { projected_price: number; gross_proceeds: number; gain: number; tax_rate: number; tax: number; net_proceeds: number };
  staged_sell: { sell_now_shares: number; sell_later_shares: number; total_gross: number; total_tax: number; net_proceeds: number };
  recommendation: string;
}

export interface ConcentrationRiskResult {
  employer_stock_value: number;
  total_net_worth: number;
  concentration_pct: number;
  risk_level: "low" | "moderate" | "elevated" | "high" | "critical";
  recommendation: string;
}
