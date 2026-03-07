"use client";
import { Loader2 } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { PortfolioSummary, RebalanceRecommendation } from "@/types/api";
import { getRebalanceRecommendations } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import TargetAllocationEditor from "./TargetAllocationEditor";
import { SECTOR_COLORS } from "./constants";
import {
  PieChart as RePie, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from "recharts";

interface AllocationTabProps {
  summary: PortfolioSummary | null;
  rebalance: RebalanceRecommendation[];
  rebalanceLoading: boolean;
  onRebalanceRefresh: () => void;
  onError: (msg: string) => void;
}

export default function AllocationTab({
  summary, rebalance, rebalanceLoading, onRebalanceRefresh, onError,
}: AllocationTabProps) {
  const sectorData = summary
    ? Object.entries(summary.sector_allocation).map(([name, value]) => ({
        name: name.length > 18 ? name.slice(0, 16) + "..." : name, value: Math.round(value),
      }))
    : [];

  const classData = summary
    ? Object.entries(summary.asset_class_allocation).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1), value: Math.round(value),
      }))
    : [];

  return (
    <div className="space-y-6">
      {summary && (sectorData.length > 0 || classData.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {sectorData.length > 0 && (
            <Card padding="lg">
              <h3 className="text-sm font-semibold text-text-primary mb-4">Sector Allocation</h3>
              <ResponsiveContainer width="100%" height={220}>
                <RePie>
                  <Pie data={sectorData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false} fontSize={10}>
                    {sectorData.map((_, i) => <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v) => formatCurrency(Number(v))} />
                </RePie>
              </ResponsiveContainer>
            </Card>
          )}
          {classData.length > 0 && (
            <Card padding="lg">
              <h3 className="text-sm font-semibold text-text-primary mb-4">Asset Class Breakdown</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={classData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f1f0" />
                  <XAxis type="number" tickFormatter={(v) => formatCurrency(v, true)} fontSize={11} />
                  <YAxis type="category" dataKey="name" width={80} fontSize={11} />
                  <Tooltip formatter={(v) => formatCurrency(Number(v))} />
                  <Bar dataKey="value" fill="#16A34A" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>
      )}

      <Card padding="lg">
        <h3 className="text-sm font-semibold text-text-primary mb-4">Rebalance Recommendations</h3>
        {rebalanceLoading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-text-muted" size={24} /></div>
        ) : rebalance.length === 0 ? (
          <p className="text-sm text-text-secondary py-4">No rebalance recommendations.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-text-secondary">
                  <th className="text-left py-2">Ticker</th>
                  <th className="text-right py-2">Current %</th>
                  <th className="text-right py-2">Target %</th>
                  <th className="text-left py-2">Action</th>
                  <th className="text-right py-2">Amount</th>
                </tr>
              </thead>
              <tbody>
                {rebalance.map((r, i) => (
                  <tr key={i} className="border-b border-card-border">
                    <td className="py-2 font-medium">{r.ticker}</td>
                    <td className="text-right py-2 tabular-nums">{formatPercent(r.current_pct)}</td>
                    <td className="text-right py-2 tabular-nums">{formatPercent(r.target_pct)}</td>
                    <td className="py-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        r.action === "buy" ? "bg-green-100 text-green-700" :
                        r.action === "sell" ? "bg-red-100 text-red-700" : "bg-surface text-text-secondary"
                      }`}>
                        {r.action}
                      </span>
                    </td>
                    <td className="text-right py-2 tabular-nums">{formatCurrency(r.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <TargetAllocationEditor onSaved={onRebalanceRefresh} />
    </div>
  );
}
