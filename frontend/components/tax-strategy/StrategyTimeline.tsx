"use client";
import { useState } from "react";
import { ChevronDown, ChevronUp, Zap, Calendar, Rocket, Clock } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { TaxStrategy } from "@/types/api";
import StrategyCard from "./StrategyCard";

const CATEGORY_CONFIG = {
  quick_win: { label: "Quick Wins", sublabel: "Do this week", icon: Zap, color: "text-green-600", bg: "bg-green-50" },
  this_year: { label: "This Tax Year", sublabel: "Act before Dec 31", icon: Calendar, color: "text-blue-600", bg: "bg-blue-50" },
  big_move: { label: "Big Moves", sublabel: "Structural changes", icon: Rocket, color: "text-amber-600", bg: "bg-amber-50" },
  long_term: { label: "Long-Term Plays", sublabel: "Multi-year strategies", icon: Clock, color: "text-purple-600", bg: "bg-purple-50" },
} as const;

const CATEGORY_ORDER: (keyof typeof CATEGORY_CONFIG)[] = ["quick_win", "this_year", "big_move", "long_term"];

export default function StrategyTimeline({ strategies, onDismiss, onOpenSimulator }: {
  strategies: TaxStrategy[];
  onDismiss: (id: number) => void;
  onOpenSimulator?: (key: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const grouped = CATEGORY_ORDER.map((cat) => {
    const items = strategies.filter((s) => (s.category ?? "this_year") === cat);
    const savings = items.reduce((sum, s) => sum + (s.estimated_savings_high ?? s.estimated_savings_low ?? 0), 0);
    return { cat, items, savings };
  }).filter((g) => g.items.length > 0);

  if (grouped.length === 0) return null;

  return (
    <div className="space-y-4">
      {grouped.map(({ cat, items, savings }) => {
        const config = CATEGORY_CONFIG[cat];
        const Icon = config.icon;
        const isCollapsed = collapsed[cat] ?? false;

        return (
          <div key={cat}>
            <button
              type="button"
              onClick={() => setCollapsed((prev) => ({ ...prev, [cat]: !prev[cat] }))}
              className="flex items-center gap-3 w-full text-left mb-2 group"
            >
              <div className={`w-8 h-8 rounded-lg ${config.bg} flex items-center justify-center flex-shrink-0`}>
                <Icon size={16} className={config.color} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-text-primary">{config.label}</h3>
                  <span className="text-xs text-text-muted">{config.sublabel}</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-text-muted">{items.length} {items.length === 1 ? "strategy" : "strategies"}</span>
                {savings > 0 && <span className="text-xs font-medium text-green-600 font-mono tabular-nums">{formatCurrency(savings, true)}</span>}
                {isCollapsed ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronUp size={14} className="text-text-muted" />}
              </div>
            </button>
            {!isCollapsed && (
              <div className="space-y-2 ml-11">
                {items.map((s) => (
                  <StrategyCard key={s.id} strategy={s} onDismiss={onDismiss} onOpenSimulator={onOpenSimulator} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
