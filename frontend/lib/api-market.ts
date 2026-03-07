import type { CompanyResearch, EconomicIndicator, MortgageContext } from "@/types/api";
import { request } from "./api-client";

export function getEconomicIndicators(): Promise<{ indicators: EconomicIndicator[] }> {
  return request("/market/indicators");
}

export function getEconomicIndicator(seriesId: string): Promise<EconomicIndicator & { data: Array<{ date: string; value: number }> }> {
  return request(`/market/indicators/${seriesId}`);
}

export function getMortgageContext(): Promise<MortgageContext> {
  return request("/market/mortgage-context");
}

export function researchCompany(ticker: string): Promise<CompanyResearch> {
  return request(`/market/research/${ticker}`);
}

export function searchCrypto(query: string): Promise<{ results: Array<{ id: string; symbol: string; name: string }> }> {
  return request(`/market/crypto/search?query=${query}`);
}

export function getTrendingCrypto(): Promise<{ coins: Array<{ id: string; symbol: string; name: string }> }> {
  return request("/market/crypto/trending");
}
