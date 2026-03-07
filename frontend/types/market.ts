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

/** Current mortgage-relevant economic context for life scenario calculations. */
export interface MortgageContext {
  fed_funds_rate: number | null;
  ten_year_treasury: number | null;
  inflation_rate: number | null;
  estimated_30yr_mortgage: number | null;
  rate_environment: "low" | "moderate" | "elevated" | "high" | "unknown";
}

/** Company fundamental overview from Alpha Vantage. */
export interface CompanyResearch {
  ticker: string | null;
  name: string | null;
  description: string | null;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  pe_ratio: number | null;
  peg_ratio: number | null;
  book_value: number | null;
  dividend_yield: number | null;
  eps: number | null;
  revenue_per_share: number | null;
  profit_margin: number | null;
  operating_margin: number | null;
  roe: number | null;
  target_price: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  beta: number | null;
}
