export type ManualAssetType = "real_estate" | "vehicle" | "investment" | "other_asset" | "mortgage" | "loan" | "other_liability";

export type InvestmentSubtype =
  | "401k_traditional" | "401k_roth" | "rollover_ira" | "roth_ira" | "traditional_ira"
  | "brokerage" | "trust" | "espp" | "rsu" | "hsa" | "529" | "other";

export type TaxTreatment = "tax_deferred" | "tax_free" | "taxable";
export type ContributionType = "pre_tax" | "roth" | "after_tax" | "mixed";

export interface ManualAsset {
  id: number;
  name: string;
  asset_type: ManualAssetType;
  is_liability: boolean;
  current_value: number;
  purchase_price: number | null;
  purchase_date: string | null;
  institution: string | null;
  address: string | null;
  description: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  owner: string | null;
  account_subtype: InvestmentSubtype | null;
  custodian: string | null;
  employer: string | null;
  tax_treatment: TaxTreatment | null;
  is_retirement_account: boolean | null;
  as_of_date: string | null;
  vested_balance: number | null;
  contribution_type: ContributionType | null;
  contribution_rate_pct: number | null;
  employee_contribution_ytd: number | null;
  employer_contribution_ytd: number | null;
  employer_match_pct: number | null;
  employer_match_limit_pct: number | null;
  annual_return_pct: number | null;
  allocation_json: string | null;
  beneficiary: string | null;
  linked_account_id: number | null;
}

export interface ManualAssetCreateIn {
  name: string;
  asset_type: ManualAssetType;
  current_value: number;
  purchase_price?: number | null;
  purchase_date?: string | null;
  institution?: string | null;
  address?: string | null;
  description?: string | null;
  notes?: string | null;
  owner?: string | null;
  account_subtype?: InvestmentSubtype | null;
  custodian?: string | null;
  employer?: string | null;
  tax_treatment?: TaxTreatment | null;
  is_retirement_account?: boolean | null;
  as_of_date?: string | null;
  vested_balance?: number | null;
  contribution_type?: ContributionType | null;
  contribution_rate_pct?: number | null;
  employee_contribution_ytd?: number | null;
  employer_contribution_ytd?: number | null;
  employer_match_pct?: number | null;
  employer_match_limit_pct?: number | null;
  annual_return_pct?: number | null;
  allocation_json?: string | null;
  beneficiary?: string | null;
}

export interface ManualAssetUpdateIn {
  name?: string;
  current_value?: number;
  purchase_price?: number | null;
  purchase_date?: string | null;
  institution?: string | null;
  address?: string | null;
  description?: string | null;
  is_active?: boolean;
  notes?: string | null;
  owner?: string | null;
  account_subtype?: InvestmentSubtype | null;
  custodian?: string | null;
  employer?: string | null;
  tax_treatment?: TaxTreatment | null;
  is_retirement_account?: boolean | null;
  as_of_date?: string | null;
  vested_balance?: number | null;
  contribution_type?: ContributionType | null;
  contribution_rate_pct?: number | null;
  employee_contribution_ytd?: number | null;
  employer_contribution_ytd?: number | null;
  employer_match_pct?: number | null;
  employer_match_limit_pct?: number | null;
  annual_return_pct?: number | null;
  allocation_json?: string | null;
  beneficiary?: string | null;
}

export interface InvestmentHolding {
  id: number;
  account_id: number | null;
  ticker: string;
  name: string | null;
  asset_class: string;
  shares: number;
  cost_basis_per_share: number | null;
  total_cost_basis: number | null;
  purchase_date: string | null;
  current_price: number | null;
  current_value: number | null;
  unrealized_gain_loss: number | null;
  unrealized_gain_loss_pct: number | null;
  term: string | null;
  sector: string | null;
  dividend_yield: number | null;
  last_price_update: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface InvestmentHoldingIn {
  ticker: string;
  name?: string | null;
  asset_class?: string;
  shares: number;
  cost_basis_per_share?: number | null;
  purchase_date?: string | null;
  account_id?: number | null;
  tax_lot_id?: string | null;
  notes?: string | null;
}

export interface CryptoHoldingType {
  id: number;
  coin_id: string;
  symbol: string;
  name: string | null;
  quantity: number;
  cost_basis_per_unit: number | null;
  total_cost_basis: number | null;
  current_price: number | null;
  current_value: number | null;
  unrealized_gain_loss: number | null;
  price_change_24h_pct: number | null;
  wallet_or_exchange: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface PortfolioSummary {
  total_value: number;
  total_cost_basis: number;
  total_gain_loss: number;
  total_gain_loss_pct: number;
  has_cost_basis: boolean;
  weighted_avg_return: number | null;
  stock_value: number;
  etf_value: number;
  crypto_value: number;
  other_value: number;
  manual_investment_value?: number;
  holdings_count: number;
  accounts_count?: number;
  top_holdings: Array<{ ticker: string; name: string | null; value: number; gain_loss_pct: number; is_annual_return?: boolean }>;
  sector_allocation: Record<string, number>;
  asset_class_allocation: Record<string, number>;
}

export interface TaxLossHarvestResult {
  total_unrealized_losses: number;
  total_unrealized_gains: number;
  net_unrealized: number;
  harvestable_losses: number;
  estimated_tax_savings: number;
  capital_loss_carryover: number;
  candidates: Array<{
    holding_id: number;
    ticker: string;
    name: string;
    shares: number;
    cost_basis: number;
    current_value: number;
    unrealized_loss: number;
    loss_pct: number;
    term: string;
    estimated_tax_savings: number;
    wash_sale_risk: boolean;
  }>;
}

export interface RebalanceRecommendation {
  ticker: string;
  name: string | null;
  current_pct: number;
  target_pct: number;
  action: "buy" | "sell" | "hold";
  shares: number;
  amount: number;
}

export interface BenchmarkComparison {
  portfolio_return: number;
  benchmark_return: number;
  alpha: number;
  benchmark_ticker: string;
  period_months: number;
}

export interface PortfolioPerformance {
  time_weighted_return: number;
  sharpe_ratio: number | null;
  max_drawdown: number;
  volatility: number | null;
  period_months: number;
}

export interface NetWorthTrend {
  monthly_series: Array<{ date: string; net_worth: number }>;
  growth_rate: number;
  current_net_worth: number;
}

export interface PortfolioConcentration {
  top_holding_pct?: number;
  top_3_pct?: number;
  single_stock_risk_level?: string;
  sector_concentration?: Record<string, number>;
}
