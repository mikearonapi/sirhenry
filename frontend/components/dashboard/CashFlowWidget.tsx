"use client";
import { formatCurrency } from "@/lib/utils";
import type { Dashboard, BudgetSummary } from "@/types/api";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import Link from "next/link";

interface Props {
  data: Dashboard;
  budget: BudgetSummary | null;
  currentMonthName: string;
  savingsRate: number;
  targetSavingsRate: number;
}

export default function CashFlowWidget({ data, budget, currentMonthName, savingsRate, targetSavingsRate }: Props) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      {/* Income vs Expenses bars */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text-secondary">This Month</h3>
          <span className="text-xs text-text-muted">{currentMonthName} {data.current_year}</span>
        </div>
        <div className="space-y-3">
          {[
            { label: "In", value: data.current_month_income, color: "#16A34A", max: data.current_month_income },
            { label: "Est. Tax", value: data.current_month_tax_estimate, color: "#CA8A04", max: data.current_month_income },
            { label: "Expenses", value: data.current_month_expenses, color: "#6B7280", max: data.current_month_income },
            { label: "Savings", value: Math.max(0, data.current_month_net - data.current_month_tax_estimate), color: "#3B82F6", max: data.current_month_income },
          ].map((row) => (
            <div key={row.label}>
              <div className="flex items-center justify-between text-xs text-text-secondary mb-1">
                <span>{row.label}</span>
                <span className="font-medium money">{formatCurrency(row.value, true)}</span>
              </div>
              <ProgressBar value={row.value} max={row.max || 1} color={row.color} size="sm" />
            </div>
          ))}
          {data.current_month_net < 0 && (
            <p className="text-xs text-red-500 font-medium pt-1">
              Deficit: {formatCurrency(Math.abs(data.current_month_net), true)} this month
            </p>
          )}
        </div>
        <Link href="/cashflow" className="text-xs text-accent hover:underline font-medium mt-3 block">
          Full cash flow →
        </Link>
      </Card>

      {/* YTD Summary */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text-secondary">Year-to-Date</h3>
          <span className="text-xs text-text-muted">{data.current_year}</span>
        </div>
        <div className="space-y-3">
          {[
            { label: "Income", value: data.ytd_income, dot: "#16A34A" },
            { label: "Expenses", value: data.ytd_expenses, dot: "#6B7280" },
            { label: "Net Savings", value: data.ytd_net, dot: data.ytd_net >= 0 ? "#3B82F6" : "#DC2626", bold: true },
          ].map((row) => (
            <div key={row.label} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: row.dot }} />
                <span className="text-sm text-text-secondary">{row.label}</span>
              </div>
              <span className={`text-sm money ${row.bold ? (data.ytd_net >= 0 ? "font-bold text-green-600" : "font-bold text-red-600") : "font-semibold text-text-primary"}`}>
                {formatCurrency(row.value, true)}
              </span>
            </div>
          ))}
          <div className="border-t border-card-border pt-2 flex items-center justify-between">
            <span className="text-sm text-text-secondary">Est. Tax</span>
            <span className="text-sm font-semibold text-text-secondary money">{formatCurrency(data.ytd_tax_estimate, true)}</span>
          </div>
        </div>
      </Card>

      {/* Budget */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text-secondary">Budget</h3>
          <span className="text-xs text-text-muted">{currentMonthName}</span>
        </div>
        {budget && budget.total_budgeted > 0 ? (
          <>
            <div className="mb-3">
              <div className="flex justify-between text-xs text-text-secondary mb-1">
                <span>Spent</span>
                <span className="money">{formatCurrency(data.current_month_expenses, true)} / {formatCurrency(budget.total_budgeted, true)}</span>
              </div>
              <ProgressBar
                value={data.current_month_expenses}
                max={budget.total_budgeted}
                color={data.current_month_expenses > budget.total_budgeted ? "#DC2626" : "#16A34A"}
                size="md"
              />
              <p className="text-xs mt-1 text-text-secondary">
                {data.current_month_expenses <= budget.total_budgeted
                  ? `${formatCurrency(budget.total_budgeted - data.current_month_expenses)} remaining`
                  : `${formatCurrency(data.current_month_expenses - budget.total_budgeted)} over`}
              </p>
            </div>
            <div className="mt-3">
              <div className="flex justify-between text-xs text-text-secondary mb-1">
                <span>Savings Rate</span>
                <span className={`font-semibold money ${savingsRate >= targetSavingsRate ? "text-green-600" : savingsRate >= 0 ? "text-amber-600" : "text-red-600"}`}>
                  {savingsRate.toFixed(1)}%
                </span>
              </div>
              <ProgressBar value={Math.max(0, savingsRate)} max={100} color={savingsRate >= targetSavingsRate ? "#16a34a" : "#D97706"} size="sm" />
            </div>
          </>
        ) : (
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="text-center bg-surface rounded-lg p-3">
              <p className="text-lg font-bold text-text-primary money">{formatCurrency(data.current_month_income, true)}</p>
              <p className="text-xs text-text-muted uppercase">In</p>
            </div>
            <div className="text-center bg-surface rounded-lg p-3">
              <p className="text-lg font-bold text-text-primary money">{formatCurrency(data.current_month_expenses, true)}</p>
              <p className="text-xs text-text-muted uppercase">Out</p>
            </div>
          </div>
        )}
        <Link href="/budget" className="text-xs text-accent hover:underline font-medium mt-1 block">
          {budget && budget.total_budgeted > 0 ? "View budget details →" : "Set up budget →"}
        </Link>
      </Card>
    </div>
  );
}
