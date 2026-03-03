import type {
  BenchmarkComparison,
  CryptoHoldingType,
  InvestmentHolding,
  InvestmentHoldingIn,
  MarketQuote,
  NetWorthTrend,
  PortfolioConcentration,
  PortfolioPerformance,
  PortfolioSummary,
  RebalanceRecommendation,
  TaxLossHarvestResult,
} from "@/types/api";
import { request } from "./api-client";

export function getHoldings(activeOnly = true): Promise<InvestmentHolding[]> {
  return request(`/portfolio/holdings?active_only=${activeOnly}`);
}

export function createHolding(body: InvestmentHoldingIn): Promise<InvestmentHolding> {
  return request("/portfolio/holdings", { method: "POST", body: JSON.stringify(body) });
}

export function updateHolding(id: number, body: Partial<InvestmentHolding>): Promise<InvestmentHolding> {
  return request(`/portfolio/holdings/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteHolding(id: number): Promise<void> {
  return request(`/portfolio/holdings/${id}`, { method: "DELETE" });
}

export function getCryptoHoldings(): Promise<CryptoHoldingType[]> {
  return request("/portfolio/crypto");
}

export function createCryptoHolding(body: {
  coin_id: string; symbol: string; name?: string; quantity: number;
  cost_basis_per_unit?: number; purchase_date?: string; wallet_or_exchange?: string;
}): Promise<CryptoHoldingType> {
  return request("/portfolio/crypto", { method: "POST", body: JSON.stringify(body) });
}

export function deleteCryptoHolding(id: number): Promise<void> {
  return request(`/portfolio/crypto/${id}`, { method: "DELETE" });
}

export function refreshPrices(): Promise<{ stocks_updated: number; crypto_updated: number }> {
  return request("/portfolio/refresh-prices", { method: "POST" });
}

export function getPortfolioSummary(): Promise<PortfolioSummary> {
  return request("/portfolio/summary");
}

export function getQuote(ticker: string): Promise<MarketQuote> {
  return request(`/portfolio/quote/${ticker}`);
}

export function getTickerHistory(ticker: string, period = "1y"): Promise<{ ticker: string; data: Array<{ date: string; close: number }> }> {
  return request(`/portfolio/history/${ticker}?period=${period}`);
}

export function getTickerStats(ticker: string): Promise<Record<string, unknown>> {
  return request(`/portfolio/stats/${ticker}`);
}

export function getTaxLossHarvest(marginalRate = 0.37): Promise<TaxLossHarvestResult> {
  return request(`/portfolio/tax-loss-harvest?marginal_rate=${marginalRate}`);
}

// Portfolio Analytics

export function getRebalanceRecommendations(): Promise<RebalanceRecommendation[]> {
  return request("/portfolio/rebalance");
}

export function getBenchmarkComparison(): Promise<BenchmarkComparison> {
  return request("/portfolio/benchmark");
}

export function getPortfolioPerformance(): Promise<PortfolioPerformance> {
  return request("/portfolio/performance");
}

export function getNetWorthTrend(): Promise<NetWorthTrend> {
  return request("/portfolio/net-worth-trend");
}

export function getPortfolioConcentration(): Promise<PortfolioConcentration> {
  return request("/portfolio/concentration");
}
