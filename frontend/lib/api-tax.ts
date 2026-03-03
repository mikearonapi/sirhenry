import type {
  MultiYearTaxProjection,
  RothConversionResult,
  SCorpAnalysisResult,
  StudentLoanResult,
  TaxChecklist,
  TaxDeductionInsights,
  TaxEstimate,
  TaxItem,
  TaxStrategy,
  TaxSummary,
} from "@/types/api";
import { request } from "./api-client";

export function getTaxItems(taxYear?: number, formType?: string): Promise<TaxItem[]> {
  const params = new URLSearchParams();
  if (taxYear) params.set("tax_year", String(taxYear));
  if (formType) params.set("form_type", formType);
  return request(`/tax/items?${params}`);
}

export function getTaxSummary(taxYear: number): Promise<TaxSummary> {
  return request(`/tax/summary?tax_year=${taxYear}`);
}

export function getTaxStrategies(taxYear?: number, includeDismissed = false): Promise<TaxStrategy[]> {
  const params = new URLSearchParams({ include_dismissed: String(includeDismissed) });
  if (taxYear) params.set("tax_year", String(taxYear));
  return request(`/tax/strategies?${params}`);
}

export function runTaxAnalysis(taxYear?: number): Promise<{ generated: number; tax_year: number }> {
  const params = taxYear ? `?tax_year=${taxYear}` : "";
  return request(`/tax/strategies/analyze${params}`, { method: "POST" });
}

export function dismissStrategy(id: number): Promise<{ dismissed: number }> {
  return request(`/tax/strategies/${id}/dismiss`, { method: "PATCH" });
}

export function getTaxEstimate(taxYear: number): Promise<TaxEstimate> {
  return request(`/tax/estimate?tax_year=${taxYear}`);
}

export function getTaxChecklist(taxYear: number): Promise<TaxChecklist> {
  return request(`/tax/checklist?tax_year=${taxYear}`);
}

export function getTaxDeductionOpportunities(taxYear: number): Promise<TaxDeductionInsights> {
  return request(`/tax/deduction-opportunities?tax_year=${taxYear}`);
}

// Tax Modeling (Strategy Lab)

export function modelRothConversion(body: Record<string, unknown>): Promise<RothConversionResult> {
  return request("/tax/model/roth-conversion", { method: "POST", body: JSON.stringify(body) });
}

export function modelSCorp(body: Record<string, unknown>): Promise<SCorpAnalysisResult> {
  return request("/tax/model/scorp", { method: "POST", body: JSON.stringify(body) });
}

export function modelMultiYearTax(body: Record<string, unknown>): Promise<MultiYearTaxProjection> {
  return request("/tax/model/multi-year", { method: "POST", body: JSON.stringify(body) });
}

export function modelEstimatedPayments(body: Record<string, unknown>): Promise<{ quarterly_payments: Array<{ quarter: number; due_date: string; amount: number }> }> {
  return request("/tax/model/estimated-payments", { method: "POST", body: JSON.stringify(body) });
}

export function modelStudentLoan(body: Record<string, unknown>): Promise<StudentLoanResult> {
  return request("/tax/model/student-loan", { method: "POST", body: JSON.stringify(body) });
}

export function modelBackdoorRoth(body: Record<string, unknown>): Promise<{ eligible: boolean; steps: string[]; pro_rata_warning: boolean }> {
  return request("/tax/model/backdoor-roth", { method: "POST", body: JSON.stringify(body) });
}

export function modelDAFBunching(body: Record<string, unknown>): Promise<{ annual_tax: number; bunched_tax: number; savings: number }> {
  return request("/tax/model/daf-bunching", { method: "POST", body: JSON.stringify(body) });
}
