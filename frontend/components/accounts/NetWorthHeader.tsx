"use client";

import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";

interface NetWorthHeaderProps {
  netWorth: number;
}

export default function NetWorthHeader({ netWorth }: NetWorthHeaderProps) {
  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-stone-500 uppercase tracking-wider">Net Worth</span>
      </div>
      <div className="flex items-baseline gap-3">
        <span className={`text-3xl font-bold tracking-tight ${netWorth >= 0 ? "text-stone-900" : "text-red-600"}`}>
          {formatCurrency(netWorth)}
        </span>
      </div>
    </Card>
  );
}
