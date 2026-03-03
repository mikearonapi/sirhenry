export interface MarketQuote {
  ticker: string;
  company_name: string | null;
  price: number | null;
  previous_close: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  dividend_yield: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  beta: number | null;
  sector: string | null;
  industry: string | null;
}

export interface EconomicIndicator {
  series_id: string;
  label: string;
  unit: string;
  category: string;
  latest_value: number | null;
  latest_date: string | null;
  trend: Array<{ date: string; value: number }>;
}
