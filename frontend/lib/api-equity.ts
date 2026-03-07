import type {
  AMTCrossoverResult,
  ConcentrationRiskResult,
  EquityDashboard,
  EquityGrant,
  EquityGrantIn,
  SellStrategyResult,
  WithholdingGapResult,
} from "@/types/api";
import { request } from "./api-client";

export function getEquityGrants(activeOnly = true): Promise<EquityGrant[]> {
  return request(`/equity-comp/grants?active_only=${activeOnly}`);
}

export function createEquityGrant(body: EquityGrantIn): Promise<EquityGrant> {
  return request("/equity-comp/grants", { method: "POST", body: JSON.stringify(body) });
}

export function updateEquityGrant(id: number, body: Partial<EquityGrantIn>): Promise<EquityGrant> {
  return request(`/equity-comp/grants/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteEquityGrant(id: number): Promise<void> {
  return request(`/equity-comp/grants/${id}`, { method: "DELETE" });
}

export function getEquityDashboard(): Promise<EquityDashboard> {
  return request("/equity-comp/dashboard");
}

export function calcWithholdingGap(body: { vest_income: number; other_income: number; filing_status?: string; state?: string }): Promise<WithholdingGapResult> {
  return request("/equity-comp/withholding-gap", { method: "POST", body: JSON.stringify(body) });
}

export function calcAMTCrossover(body: { iso_shares_available: number; strike_price: number; current_fmv: number; other_income: number; filing_status?: string }): Promise<AMTCrossoverResult> {
  return request("/equity-comp/amt-crossover", { method: "POST", body: JSON.stringify(body) });
}

export function calcSellStrategy(body: { shares: number; cost_basis_per_share: number; current_price: number; other_income: number; filing_status?: string; holding_period_months?: number }): Promise<SellStrategyResult> {
  return request("/equity-comp/sell-strategy", { method: "POST", body: JSON.stringify(body) });
}

export function calcConcentrationRisk(body: { employer_stock_value: number; total_net_worth: number }): Promise<ConcentrationRiskResult> {
  return request("/equity-comp/concentration-risk", { method: "POST", body: JSON.stringify(body) });
}

export function refreshEquityPrices(): Promise<void> {
  return request("/equity-comp/refresh-prices", { method: "POST" });
}
