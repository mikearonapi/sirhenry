import type {
  BackdoorRothInput,
  BackdoorRothResult,
  DAFBunchingInput,
  DAFBunchingResult,
  DefinedBenefitInput,
  DefinedBenefitResult,
  EstimatedPaymentsInput,
  EstimatedPaymentsResult,
  FilingStatusCompareInput,
  FilingStatusCompareResult,
  MegaBackdoorInput,
  MegaBackdoorResult,
  MultiYearTaxInput,
  MultiYearTaxProjection,
  QBIDeductionInput,
  QBIDeductionResult,
  RealEstateSTRInput,
  RealEstateSTRResult,
  RothConversionInput,
  RothConversionResult,
  SCorpInput,
  SCorpAnalysisResult,
  Section179Input,
  Section179Result,
  StateComparisonInput,
  StateComparisonResult,
  StudentLoanInput,
  StudentLoanResult,
  TaxChecklist,
  TaxDeductionInsights,
  TaxEstimate,
  TaxItem,
  TaxStrategy,
  TaxStrategyProfile,
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

export function modelRothConversion(body: RothConversionInput): Promise<RothConversionResult> {
  return request("/tax/model/roth-conversion", { method: "POST", body: JSON.stringify(body) });
}

export function modelSCorp(body: SCorpInput): Promise<SCorpAnalysisResult> {
  return request("/tax/model/scorp", { method: "POST", body: JSON.stringify(body) });
}

export function modelMultiYearTax(body: MultiYearTaxInput): Promise<MultiYearTaxProjection> {
  return request("/tax/model/multi-year", { method: "POST", body: JSON.stringify(body) });
}

export function modelEstimatedPayments(body: EstimatedPaymentsInput): Promise<EstimatedPaymentsResult> {
  return request("/tax/model/estimated-payments", { method: "POST", body: JSON.stringify(body) });
}

export function modelStudentLoan(body: StudentLoanInput): Promise<StudentLoanResult> {
  return request("/tax/model/student-loan", { method: "POST", body: JSON.stringify(body) });
}

export function modelBackdoorRoth(body: BackdoorRothInput): Promise<BackdoorRothResult> {
  return request("/tax/model/backdoor-roth", { method: "POST", body: JSON.stringify(body) });
}

export function modelDAFBunching(body: DAFBunchingInput): Promise<DAFBunchingResult> {
  return request("/tax/model/daf-bunching", { method: "POST", body: JSON.stringify(body) });
}

// Tax Strategy Interview Profile

export function getTaxStrategyProfile(): Promise<{ profile: TaxStrategyProfile | null }> {
  return request("/household/tax-strategy-profile");
}

export function saveTaxStrategyProfile(profile: TaxStrategyProfile): Promise<{ status: string }> {
  return request("/household/tax-strategy-profile", { method: "PUT", body: JSON.stringify(profile) });
}

// New simulators

export function modelMegaBackdoor(body: MegaBackdoorInput): Promise<MegaBackdoorResult> {
  return request("/tax/model/mega-backdoor", { method: "POST", body: JSON.stringify(body) });
}

export function modelDefinedBenefit(body: DefinedBenefitInput): Promise<DefinedBenefitResult> {
  return request("/tax/model/defined-benefit", { method: "POST", body: JSON.stringify(body) });
}

export function modelRealEstateSTR(body: RealEstateSTRInput): Promise<RealEstateSTRResult> {
  return request("/tax/model/real-estate-str", { method: "POST", body: JSON.stringify(body) });
}

export function modelSection179(body: Section179Input): Promise<Section179Result> {
  return request("/tax/model/section-179", { method: "POST", body: JSON.stringify(body) });
}

export function modelFilingStatusCompare(body: FilingStatusCompareInput): Promise<FilingStatusCompareResult> {
  return request("/tax/model/filing-status-compare", { method: "POST", body: JSON.stringify(body) });
}

export function updateTaxItem(id: number, updates: Partial<TaxItem>): Promise<{ id: number; updated_fields: string[] }> {
  return request(`/tax/items/${id}`, { method: "PATCH", body: JSON.stringify(updates) });
}

export function modelQBIDeduction(body: QBIDeductionInput): Promise<QBIDeductionResult> {
  return request("/tax/model/qbi-deduction", { method: "POST", body: JSON.stringify(body) });
}

export function modelStateComparison(body: StateComparisonInput): Promise<StateComparisonResult> {
  return request("/tax/model/state-comparison", { method: "POST", body: JSON.stringify(body) });
}
