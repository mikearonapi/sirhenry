"use client";
import { Loader2 } from "lucide-react";
import { formatPercent } from "@/lib/utils";
import type { PortfolioConcentration } from "@/types/api";
import Card from "@/components/ui/Card";

interface RiskTabProps {
  concentration: PortfolioConcentration | null;
  loading: boolean;
}

export default function RiskTab({ concentration, loading }: RiskTabProps) {
  if (loading) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-text-muted" size={28} /></div>;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card padding="lg">
          <p className="text-xs text-text-secondary font-medium">Top Holding %</p>
          <p className="text-2xl font-bold text-text-primary mt-1 font-mono tabular-nums">
            {concentration?.top_holding_pct != null ? formatPercent(concentration.top_holding_pct) : "-"}
          </p>
        </Card>
        <Card padding="lg">
          <p className="text-xs text-text-secondary font-medium">Top 3 Holdings %</p>
          <p className="text-2xl font-bold text-text-primary mt-1 font-mono tabular-nums">
            {concentration?.top_3_pct != null ? formatPercent(concentration.top_3_pct) : "-"}
          </p>
        </Card>
        <Card padding="lg">
          <p className="text-xs text-text-secondary font-medium">Single Stock Risk</p>
          <p className="text-lg font-bold text-text-primary mt-1 capitalize">
            {concentration?.single_stock_risk_level ?? "-"}
          </p>
        </Card>
      </div>
      {concentration?.sector_concentration && Object.keys(concentration.sector_concentration).length > 0 && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Sector Concentration</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-text-secondary">
                  <th className="text-left py-2">Sector</th>
                  <th className="text-right py-2">Allocation %</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(concentration.sector_concentration).map(([sector, pct]) => (
                  <tr key={sector} className="border-b border-card-border">
                    <td className="py-2">{sector}</td>
                    <td className="text-right py-2 tabular-nums">{formatPercent(pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
