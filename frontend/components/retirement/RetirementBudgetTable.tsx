"use client";

import { useCallback, useEffect, useState } from "react";
import { Pencil, Check, X, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { getRetirementBudget, saveRetirementBudgetOverride } from "@/lib/api";
import type { RetirementBudget, RetirementBudgetLine } from "@/types/api";
import { EXPENSE_GROUPS, GROUP_ICONS, getExpenseGroup } from "@/components/ui/budget-groups";

interface Props {
  retirementAge: number;
  onTotalChange?: (annualTotal: number) => void;
}

interface GroupedLines {
  group: string;
  lines: RetirementBudgetLine[];
  currentTotal: number;
  retirementTotal: number;
}

function formatCurrency(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`.replace(".0K", "K");
  return `$${Math.round(n).toLocaleString()}`;
}

function groupLines(lines: RetirementBudgetLine[]): GroupedLines[] {
  const map = new Map<string, RetirementBudgetLine[]>();
  for (const line of lines) {
    const g = getExpenseGroup(line.category);
    const list = map.get(g) ?? [];
    list.push(line);
    map.set(g, list);
  }
  const groups: GroupedLines[] = [];
  for (const [group, items] of map) {
    groups.push({
      group,
      lines: items.sort((a, b) => b.current_monthly - a.current_monthly),
      currentTotal: items.reduce((s, l) => s + l.current_monthly, 0),
      retirementTotal: items.reduce((s, l) => s + l.retirement_monthly, 0),
    });
  }
  const order = [...Object.keys(EXPENSE_GROUPS), "Other"];
  groups.sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group));
  return groups;
}

function ChangeIndicator({ multiplier }: { multiplier: number }) {
  if (multiplier === 0) return <span className="text-red-500 text-xs font-medium">-100%</span>;
  if (multiplier === 1) return <span className="text-stone-400 text-xs">—</span>;
  const pct = Math.round((multiplier - 1) * 100);
  if (pct < 0) return <span className="text-green-600 text-xs font-medium flex items-center gap-0.5"><TrendingDown size={10} />{pct}%</span>;
  return <span className="text-amber-600 text-xs font-medium flex items-center gap-0.5"><TrendingUp size={10} />+{pct}%</span>;
}

function BudgetRow({
  line,
  onSaveOverride,
}: {
  line: RetirementBudgetLine;
  onSaveOverride: (category: string, multiplier: number, reason: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [editMult, setEditMult] = useState(line.multiplier);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    const reason = editMult === 0 ? "Eliminated" : editMult < 1 ? "Reduced" : editMult > 1 ? "Increased" : "Same as current";
    await onSaveOverride(line.category, editMult, reason);
    setSaving(false);
    setEditing(false);
  }

  return (
    <tr className="border-b border-stone-100 hover:bg-stone-50/50">
      <td className="py-1.5 pl-6 pr-2 text-xs text-stone-600">
        {line.category}
        {line.source === "spending_history" && (
          <span className="ml-1 text-[10px] text-stone-400">(est.)</span>
        )}
      </td>
      <td className="py-1.5 px-2 text-xs text-stone-700 text-right font-mono">
        ${Math.round(line.current_monthly).toLocaleString()}
      </td>
      <td className="py-1.5 px-2 text-right">
        {editing ? (
          <div className="flex items-center justify-end gap-1">
            <input
              type="range"
              min={0}
              max={200}
              step={5}
              value={editMult * 100}
              onChange={(e) => setEditMult(Number(e.target.value) / 100)}
              className="w-16 h-3 accent-[#16A34A]"
            />
            <span className="text-[10px] text-stone-500 w-8 text-right font-mono">
              {Math.round(editMult * 100)}%
            </span>
            <button
              onClick={handleSave}
              disabled={saving}
              className="p-0.5 text-green-600 hover:text-green-700"
            >
              <Check size={12} />
            </button>
            <button
              onClick={() => { setEditing(false); setEditMult(line.multiplier); }}
              className="p-0.5 text-stone-400 hover:text-stone-600"
            >
              <X size={12} />
            </button>
          </div>
        ) : (
          <span className={`text-xs font-mono ${line.retirement_monthly === 0 ? "text-stone-300 line-through" : "text-stone-700"}`}>
            ${Math.round(line.retirement_monthly).toLocaleString()}
          </span>
        )}
      </td>
      <td className="py-1.5 px-2 text-right">
        <ChangeIndicator multiplier={line.multiplier} />
      </td>
      <td className="py-1.5 px-2 text-xs text-stone-400 max-w-[120px] truncate">
        {line.reason !== "Same as current" && line.reason}
      </td>
      <td className="py-1.5 pr-3 pl-1 w-6">
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="p-0.5 text-stone-300 hover:text-stone-500"
          >
            <Pencil size={11} />
          </button>
        )}
      </td>
    </tr>
  );
}

export default function RetirementBudgetTable({ retirementAge, onTotalChange }: Props) {
  const [budget, setBudget] = useState<RetirementBudget | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadBudget = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getRetirementBudget(retirementAge);
      setBudget(data);
      onTotalChange?.(data.retirement_annual_total);
    } catch (e) {
      setError("Failed to load retirement budget");
    } finally {
      setLoading(false);
    }
  }, [retirementAge, onTotalChange]);

  useEffect(() => { loadBudget(); }, [loadBudget]);

  const handleSaveOverride = useCallback(async (category: string, multiplier: number, reason: string) => {
    await saveRetirementBudgetOverride({ category, multiplier, reason });
    await loadBudget();
  }, [loadBudget]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-stone-200 p-8 text-center text-stone-400 text-sm">
        Loading your retirement budget...
      </div>
    );
  }

  if (error || !budget) {
    return (
      <div className="bg-white rounded-xl border border-stone-200 p-8 text-center text-red-500 text-sm">
        {error || "No budget data available"}
      </div>
    );
  }

  const groups = groupLines(budget.lines);
  const savingsPct = budget.current_monthly_total > 0
    ? Math.round((1 - budget.retirement_monthly_total / budget.current_monthly_total) * 100)
    : 0;

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white rounded-xl border border-stone-200 p-4">
          <p className="text-xs text-stone-400 mb-1">Current Monthly</p>
          <p className="text-xl font-semibold font-mono text-stone-800">
            ${Math.round(budget.current_monthly_total).toLocaleString()}
          </p>
          <p className="text-[10px] text-stone-400">${Math.round(budget.current_annual_total).toLocaleString()}/yr</p>
        </div>
        <div className="bg-white rounded-xl border border-stone-200 p-4">
          <p className="text-xs text-stone-400 mb-1">Retirement Monthly</p>
          <p className="text-xl font-semibold font-mono text-[#16A34A]">
            ${Math.round(budget.retirement_monthly_total).toLocaleString()}
          </p>
          <p className="text-[10px] text-stone-400">${Math.round(budget.retirement_annual_total).toLocaleString()}/yr</p>
        </div>
        <div className="bg-white rounded-xl border border-stone-200 p-4">
          <p className="text-xs text-stone-400 mb-1">Monthly Savings</p>
          <p className="text-xl font-semibold font-mono text-green-600">
            {savingsPct > 0 ? `-${savingsPct}%` : savingsPct < 0 ? `+${Math.abs(savingsPct)}%` : "Same"}
          </p>
          <p className="text-[10px] text-stone-400">
            ${Math.round(budget.current_monthly_total - budget.retirement_monthly_total).toLocaleString()}/mo less
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-stone-400 px-1">
        Your current personal spending translated to retirement. Mortgage drops off, kids become independent,
        healthcare increases. Click the pencil icon to adjust any line.
      </p>

      {/* Budget table */}
      <div className="bg-white rounded-xl border border-stone-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-stone-200 bg-stone-50">
              <th className="py-2 pl-4 pr-2 text-left text-[10px] font-medium text-stone-400 uppercase tracking-wider">Category</th>
              <th className="py-2 px-2 text-right text-[10px] font-medium text-stone-400 uppercase tracking-wider">Now/mo</th>
              <th className="py-2 px-2 text-right text-[10px] font-medium text-stone-400 uppercase tracking-wider">Retire/mo</th>
              <th className="py-2 px-2 text-right text-[10px] font-medium text-stone-400 uppercase tracking-wider">Change</th>
              <th className="py-2 px-2 text-left text-[10px] font-medium text-stone-400 uppercase tracking-wider">Why</th>
              <th className="py-2 pr-3 pl-1 w-6"></th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <GroupSection key={g.group} group={g} onSaveOverride={handleSaveOverride} />
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-stone-300 bg-stone-50 font-semibold">
              <td className="py-2.5 pl-4 text-xs text-stone-700">Total</td>
              <td className="py-2.5 px-2 text-xs text-stone-700 text-right font-mono">
                ${Math.round(budget.current_monthly_total).toLocaleString()}
              </td>
              <td className="py-2.5 px-2 text-xs text-[#16A34A] text-right font-mono">
                ${Math.round(budget.retirement_monthly_total).toLocaleString()}
              </td>
              <td className="py-2.5 px-2 text-right">
                <span className="text-xs text-green-600 font-medium">
                  {savingsPct > 0 ? `-${savingsPct}%` : "—"}
                </span>
              </td>
              <td colSpan={2}></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

function GroupSection({
  group,
  onSaveOverride,
}: {
  group: GroupedLines;
  onSaveOverride: (category: string, multiplier: number, reason: string) => Promise<void>;
}) {
  const icon = GROUP_ICONS[group.group] || GROUP_ICONS["Other"];
  const changePct = group.currentTotal > 0
    ? Math.round((group.retirementTotal / group.currentTotal - 1) * 100)
    : 0;

  return (
    <>
      <tr className="bg-stone-50/50">
        <td colSpan={2} className="py-1.5 pl-4 text-xs font-medium text-stone-600">
          <span className="mr-1.5">{icon}</span>
          {group.group}
        </td>
        <td className="py-1.5 px-2 text-right text-[10px] text-stone-400 font-mono">
          ${Math.round(group.retirementTotal).toLocaleString()}
        </td>
        <td className="py-1.5 px-2 text-right">
          {changePct !== 0 && (
            <span className={`text-[10px] ${changePct < 0 ? "text-green-600" : "text-amber-600"}`}>
              {changePct > 0 ? `+${changePct}%` : `${changePct}%`}
            </span>
          )}
        </td>
        <td colSpan={2}></td>
      </tr>
      {group.lines.map((line) => (
        <BudgetRow key={line.category} line={line} onSaveOverride={onSaveOverride} />
      ))}
    </>
  );
}
