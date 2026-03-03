import type {
  BudgetForecastResponse,
  BudgetItem,
  BudgetSummary,
  SpendVelocity,
} from "@/types/api";
import { request } from "./api-client";

export function getBudgets(year: number, month: number): Promise<BudgetItem[]> {
  return request(`/budget?year=${year}&month=${month}`);
}

export function getBudgetSummary(year: number, month: number): Promise<BudgetSummary> {
  return request(`/budget/summary?year=${year}&month=${month}`);
}

export function createBudget(body: { year: number; month: number; category: string; segment: string; budget_amount: number }): Promise<BudgetItem> {
  return request("/budget", { method: "POST", body: JSON.stringify(body) });
}

export function updateBudget(id: number, body: { budget_amount?: number; notes?: string }): Promise<BudgetItem> {
  return request(`/budget/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteBudget(id: number): Promise<void> {
  return request(`/budget/${id}`, { method: "DELETE" });
}

export interface BudgetCategoryMeta {
  category: string;
  category_type: "income" | "goal" | "expense";
}

export function getBudgetCategories(year?: number, month?: number): Promise<BudgetCategoryMeta[]> {
  const params = new URLSearchParams();
  if (year) params.set("year", String(year));
  if (month) params.set("month", String(month));
  const qs = params.toString();
  return request(`/budget/categories${qs ? `?${qs}` : ""}`);
}

export function getUnbudgetedCategories(year: number, month: number): Promise<Array<{ category: string; actual_amount: number }>> {
  return request(`/budget/unbudgeted?year=${year}&month=${month}`);
}

export function copyBudgetMonth(
  fromYear: number, fromMonth: number,
  toYear: number, toMonth: number,
): Promise<{ copied: number }> {
  return request(
    `/budget/copy?from_year=${fromYear}&from_month=${fromMonth}&to_year=${toYear}&to_month=${toMonth}`,
    { method: "POST" },
  );
}

export function getBudgetForecast(year?: number, month?: number): Promise<BudgetForecastResponse> {
  const params = new URLSearchParams();
  if (year != null) params.set("year", String(year));
  if (month != null) params.set("month", String(month));
  const qs = params.toString();
  return request(`/budget/forecast${qs ? `?${qs}` : ""}`);
}

export function getSpendVelocity(year?: number, month?: number): Promise<SpendVelocity[]> {
  const params = new URLSearchParams();
  if (year != null) params.set("year", String(year));
  if (month != null) params.set("month", String(month));
  const qs = params.toString();
  return request(`/budget/velocity${qs ? `?${qs}` : ""}`);
}
