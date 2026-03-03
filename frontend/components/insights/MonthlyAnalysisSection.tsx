"use client";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import type { MonthlyAnalysis } from "@/types/api";
import Card from "@/components/ui/Card";
import { CLASSIFICATION_STYLES } from "@/components/insights/constants";

interface MonthlyChartDatum {
  name: string;
  "Total Expenses": number;
  "Normalized Expenses": number;
  "Outlier Amount": number;
  Income: number;
  classification: string;
}

interface Props {
  monthlyAnalysis: MonthlyAnalysis[];
}

function buildChartData(monthlyAnalysis: MonthlyAnalysis[]): MonthlyChartDatum[] {
  return monthlyAnalysis.map((m) => ({
    name: m.month_name.slice(0, 3),
    "Total Expenses": Math.round(m.total_expenses),
    "Normalized Expenses": Math.round(m.expenses_excl_outliers),
    "Outlier Amount": Math.round(m.outlier_expense_total),
    Income: Math.round(m.total_income),
    classification: m.classification,
  }));
}

export default function MonthlyAnalysisSection({ monthlyAnalysis }: Props) {
  const monthlyChartData = buildChartData(monthlyAnalysis);

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-sm font-semibold text-stone-700">Monthly Spending: Actual vs Normalized</h2>
          <p className="text-xs text-stone-400 mt-0.5">
            Orange bars show outlier spending that inflates your monthly totals
          </p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={monthlyChartData} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" />
          <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12, fill: "#78716c" }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #e7e5e4", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
            formatter={(v, name) => [typeof v === "number" ? formatCurrency(v) : String(v ?? ""), String(name)]}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "#78716c" }} />
          <Bar dataKey="Normalized Expenses" stackId="expenses" fill="#86efac" radius={[0, 0, 0, 0]} />
          <Bar dataKey="Outlier Amount" stackId="expenses" fill="#fdba74" radius={[4, 4, 0, 0]} />
          <Line type="monotone" dataKey="Income" stroke="#16a34a" strokeWidth={2} dot={false} strokeDasharray="5 5" />
        </ComposedChart>
      </ResponsiveContainer>
      {/* Month classification badges */}
      <div className="flex flex-wrap gap-2 mt-4">
        {monthlyAnalysis.map((m) => {
          const style = CLASSIFICATION_STYLES[m.classification] || CLASSIFICATION_STYLES.normal;
          return (
            <div key={m.month} className={`${style.bg} rounded-lg px-3 py-1.5`}>
              <span className={`text-xs font-medium ${style.text}`}>
                {m.month_name.slice(0, 3)}: {style.label}
              </span>
              {m.outlier_count > 0 && (
                <span className="text-xs text-stone-400 ml-1">
                  ({m.outlier_count} outlier{m.outlier_count > 1 ? "s" : ""})
                </span>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
