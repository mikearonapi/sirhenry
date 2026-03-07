"use client";
import type { TabDef } from "@/components/ui/TabBar";
import Card from "@/components/ui/Card";
import {
  LayoutDashboard, TrendingUp, Snowflake, GitCompareArrows,
} from "lucide-react";

/* ── Color palettes ─────────────────────────────────────── */

export const EXPENSE_COLORS = [
  "#16A34A", "#f59e0b", "#3b82f6", "#8b5cf6", "#ec4899",
  "#06b6d4", "#16a34a", "#64748b", "#ef4444", "#a855f7",
];

export const INCOME_COLORS = [
  "#16a34a", "#22c55e", "#4ade80", "#86efac", "#bbf7d0",
];

/* ── Tab definitions ────────────────────────────────────── */

export const TABS: TabDef[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "trends", label: "Trends", icon: TrendingUp },
  { id: "seasonal", label: "Seasonal", icon: Snowflake },
  { id: "yoy", label: "Year-over-Year", icon: GitCompareArrows },
];

/* ── Skeleton loaders ───────────────────────────────────── */

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <Card padding="lg">
      <div className="animate-pulse space-y-3">
        <div className="h-4 bg-surface rounded w-1/3" />
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="h-3 bg-surface rounded" style={{ width: `${80 - i * 10}%` }} />
        ))}
      </div>
    </Card>
  );
}

export function SkeletonChart() {
  return (
    <Card padding="lg">
      <div className="animate-pulse">
        <div className="h-4 bg-surface rounded w-2/5 mb-4" />
        <div className="h-[300px] bg-surface rounded-lg flex items-end justify-around px-6 pb-4 gap-3">
          {[60, 80, 45, 90, 55, 70, 40, 65, 50, 75, 60, 85].map((h, i) => (
            <div key={i} className="bg-surface rounded-t w-full" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    </Card>
  );
}
