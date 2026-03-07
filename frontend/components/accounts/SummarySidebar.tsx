"use client";

import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import type { UnifiedGroup } from "./accounts-types";

interface SummarySidebarProps {
  totalAssets: number;
  totalLiabilities: number;
  groups: UnifiedGroup[];
}

export default function SummarySidebar({ totalAssets, totalLiabilities, groups }: SummarySidebarProps) {
  return (
    <Card padding="lg">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">Summary</h3>
      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-text-secondary">Assets</span>
            <span className="font-semibold text-text-primary tabular-nums">{formatCurrency(totalAssets)}</span>
          </div>
          <div className="w-full bg-green-100 rounded-full h-2">
            <div
              className="bg-green-500 h-2 rounded-full"
              style={{ width: `${totalLiabilities > 0 ? Math.min(100, (totalAssets / Math.max(totalAssets, totalLiabilities)) * 100) : 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-text-secondary">Liabilities</span>
            <span className="font-semibold text-red-600 tabular-nums">{formatCurrency(totalLiabilities)}</span>
          </div>
          <div className="w-full bg-red-100 rounded-full h-2">
            <div
              className="bg-red-500 h-2 rounded-full"
              style={{ width: `${totalAssets > 0 ? Math.min(100, (totalLiabilities / totalAssets) * 100) : 0}%` }}
            />
          </div>
        </div>
        <div className="border-t border-card-border pt-3 space-y-2">
          {groups.map((g) => (
            <div key={g.key} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${g.isLiability ? "bg-red-500" : "bg-green-500"}`} />
                <span className="text-text-secondary">{g.label}</span>
              </div>
              <span className={`tabular-nums font-medium ${g.isLiability ? "text-red-600" : "text-text-secondary"}`}>
                {g.isLiability ? "-" : ""}{formatCurrency(g.total)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
