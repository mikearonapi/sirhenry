"use client";
import { Loader2 } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { NetWorthTrend } from "@/types/api";
import Card from "@/components/ui/Card";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

interface NetWorthTabProps {
  netWorth: NetWorthTrend | null;
  loading: boolean;
}

export default function NetWorthTab({ netWorth, loading }: NetWorthTabProps) {
  if (loading) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-text-muted" size={28} /></div>;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <Card padding="lg">
          <p className="text-xs text-text-secondary font-medium">Current Net Worth</p>
          <p className="text-2xl font-bold text-text-primary mt-1 font-mono tabular-nums">
            {netWorth ? formatCurrency(netWorth.current_net_worth, true) : "-"}
          </p>
        </Card>
        <Card padding="lg">
          <p className="text-xs text-text-secondary font-medium">Growth Rate</p>
          <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${(netWorth?.growth_rate ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
            {netWorth ? `${netWorth.growth_rate >= 0 ? "+" : ""}${formatPercent(netWorth.growth_rate)}` : "-"}
          </p>
        </Card>
      </div>
      {netWorth && netWorth.monthly_series.length > 0 && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Monthly Net Worth</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={netWorth.monthly_series.map((d) => ({ ...d, value: d.net_worth }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f1f0" />
              <XAxis dataKey="date" tickFormatter={(v) => new Date(v).toLocaleDateString("en-US", { month: "short", year: "2-digit" })} fontSize={11} />
              <YAxis tickFormatter={(v) => formatCurrency(v, true)} fontSize={11} />
              <Tooltip formatter={(v) => formatCurrency(Number(v))} labelFormatter={(v) => new Date(v).toLocaleDateString("en-US")} />
              <Line type="monotone" dataKey="value" stroke="#16A34A" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
