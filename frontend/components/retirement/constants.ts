"use client";
import { Wallet, Sliders, TrendingUp, Zap } from "lucide-react";
import type { TabDef } from "@/components/ui/TabBar";
import type { DebtPayoff } from "@/types/api";

export interface RetirementInputState {
  name: string;
  current_age: number;
  retirement_age: number;
  life_expectancy: number;
  current_annual_income: number;
  expected_income_growth_pct: number;
  expected_social_security_monthly: number;
  social_security_start_age: number;
  pension_monthly: number;
  other_retirement_income_monthly: number;
  current_retirement_savings: number;
  current_other_investments: number;
  monthly_retirement_contribution: number;
  employer_match_pct: number;
  employer_match_limit_pct: number;
  desired_annual_retirement_income: number;
  income_replacement_pct: number;
  healthcare_annual_estimate: number;
  additional_annual_expenses: number;
  inflation_rate_pct: number;
  pre_retirement_return_pct: number;
  post_retirement_return_pct: number;
  tax_rate_in_retirement_pct: number;
  current_annual_expenses: number;
  debt_payoffs: DebtPayoff[];
  is_primary: boolean;
  notes: string | null;
}

export const DEFAULT_INPUTS: RetirementInputState = {
  name: "My Retirement Plan",
  current_age: 35,
  retirement_age: 65,
  life_expectancy: 90,
  current_annual_income: 200000,
  expected_income_growth_pct: 3,
  expected_social_security_monthly: 2800,
  social_security_start_age: 67,
  pension_monthly: 0,
  other_retirement_income_monthly: 0,
  current_retirement_savings: 250000,
  current_other_investments: 100000,
  monthly_retirement_contribution: 3000,
  employer_match_pct: 50,
  employer_match_limit_pct: 6,
  desired_annual_retirement_income: 0,
  income_replacement_pct: 80,
  healthcare_annual_estimate: 15000,
  additional_annual_expenses: 10000,
  inflation_rate_pct: 3,
  pre_retirement_return_pct: 7,
  post_retirement_return_pct: 5,
  tax_rate_in_retirement_pct: 22,
  current_annual_expenses: 0,
  debt_payoffs: [],
  is_primary: true,
  notes: null,
};

export type InputKey = keyof RetirementInputState;

export const TABS: TabDef[] = [
  { id: "budget", label: "Budget", icon: Wallet },
  { id: "inputs", label: "Inputs", icon: Sliders },
  { id: "projections", label: "Projections", icon: TrendingUp },
  { id: "scenarios", label: "Scenarios", icon: Zap },
];
