"use client";
import { ChevronDown, ChevronRight } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { BudgetItem } from "@/types/api";
import Card from "@/components/ui/Card";
import BudgetCategoryRow from "./BudgetCategoryRow";

type BudgetSection = "income" | "expense" | "goal";

interface GroupedBudgets {
  group: string;
  items: BudgetItem[];
  totalBudget: number;
  totalActual: number;
  totalVariance: number;
}

interface Props {
  groups: GroupedBudgets[];
  groupIcons: Record<string, string>;
  collapsedGroups: Set<string>;
  onToggleGroup: (group: string) => void;
  onEditItem: (id: number, newAmount: number) => Promise<void>;
  onDeleteItem: (id: number) => void;
}

function varianceColor(variance: number, section: BudgetSection): string {
  if (section === "expense") return variance >= 0 ? "text-green-600" : "text-red-600";
  return variance <= 0 ? "text-green-600" : "text-text-muted";
}

export default function BudgetGroupedSection({
  groups, groupIcons, collapsedGroups, onToggleGroup, onEditItem, onDeleteItem,
}: Props) {
  const totalExpenseBudget = groups.reduce((s, g) => s + g.totalBudget, 0);
  const totalExpenseActual = groups.reduce((s, g) => s + g.totalActual, 0);
  const totalExpenseVariance = totalExpenseBudget - totalExpenseActual;
  const totalColor = varianceColor(totalExpenseVariance, "expense");

  return (
    <div>
      <div className="flex items-center px-4 py-2 mb-1">
        <span className="flex-1 text-xs font-semibold text-text-muted uppercase tracking-wider">Expenses</span>
        <span className="w-24 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Budget</span>
        <span className="w-24 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Actual</span>
        <span className="w-28 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Remaining</span>
        <span className="w-12" />
      </div>

      <div className="space-y-2">
        {groups.map(({ group, items, totalBudget, totalActual, totalVariance }) => {
          const collapsed = collapsedGroups.has(group);
          const icon = groupIcons[group] ?? "📦";
          return (
            <Card key={group} padding="none">
              <button
                onClick={() => onToggleGroup(group)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface/50"
              >
                <div className="flex items-center gap-2">
                  {collapsed ? <ChevronRight size={14} className="text-text-muted" /> : <ChevronDown size={14} className="text-text-muted" />}
                  <span className="text-sm mr-1">{icon}</span>
                  <span className="text-sm font-semibold text-text-secondary">{group}</span>
                </div>
                <div className="flex items-center text-xs tabular-nums">
                  <span className="w-24 text-right text-text-muted">{formatCurrency(totalBudget)}</span>
                  <span className="w-24 text-right text-text-muted">{formatCurrency(totalActual)}</span>
                  <span className={`w-28 text-right font-semibold ${varianceColor(totalVariance, "expense")}`}>
                    {formatCurrency(totalVariance)}
                  </span>
                  <span className="w-12" />
                </div>
              </button>

              {!collapsed && (
                <div className="border-t border-card-border divide-y divide-border">
                  {items.map((b) => (
                    <BudgetCategoryRow
                      key={b.id}
                      item={b}
                      section="expense"
                      onEdit={onEditItem}
                      onDelete={onDeleteItem}
                    />
                  ))}
                </div>
              )}
            </Card>
          );
        })}

        {/* Expense total */}
        <Card padding="none">
          <div className="flex items-center px-4 py-3 border-t-2 border-border bg-surface/30">
            <span className="flex-1 text-sm font-bold text-text-primary">Total Expenses</span>
            <span className="w-24 text-right text-sm font-bold tabular-nums text-text-primary">{formatCurrency(totalExpenseBudget)}</span>
            <span className="w-24 text-right text-sm font-bold tabular-nums text-text-secondary">{formatCurrency(totalExpenseActual)}</span>
            <span className={`w-28 text-right text-sm font-bold tabular-nums ${totalColor}`}>
              {formatCurrency(totalExpenseVariance)}
            </span>
            <span className="w-12" />
          </div>
        </Card>
      </div>
    </div>
  );
}
