"use client";
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { BudgetItem } from "@/types/api";

type BudgetSection = "income" | "expense" | "goal";

interface Props {
  item: BudgetItem;
  section: BudgetSection;
  onEdit: (id: number, newAmount: number) => Promise<void>;
  onDelete: (id: number) => void;
}

function varianceColor(variance: number, section: BudgetSection): string {
  if (section === "expense") return variance >= 0 ? "text-green-600" : "text-red-600";
  return variance <= 0 ? "text-green-600" : "text-text-secondary";
}

export default function BudgetCategoryRow({ item, section, onEdit, onDelete }: Props) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  function handleStartEdit() {
    setEditing(true);
    setEditValue(String(item.budget_amount));
  }

  async function handleSave() {
    const newAmount = parseFloat(editValue);
    if (isNaN(newAmount) || newAmount < 0) {
      setEditing(false);
      return;
    }
    try {
      await onEdit(item.id, newAmount);
    } finally {
      setEditing(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") setEditing(false);
  }

  const color = varianceColor(item.variance, section);

  return (
    <div className="flex items-center px-4 py-2.5 hover:bg-surface/50 group">
      <div className="flex-1 min-w-0 pl-7">
        <p className="text-sm text-text-secondary">{item.category}</p>
        {item.segment === "business" && (
          <span className="text-xs text-blue-600 font-medium">BUSINESS</span>
        )}
      </div>
      <div className="w-24 text-right">
        {editing ? (
          <div className="flex items-center gap-1 justify-end">
            <span className="text-xs text-text-muted">$</span>
            <input
              ref={inputRef}
              type="number"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={handleSave}
              min="0"
              step="10"
              className="w-16 text-sm text-right border border-accent rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        ) : (
          <button
            onClick={handleStartEdit}
            className="text-sm tabular-nums text-text-secondary hover:text-accent hover:underline cursor-text"
          >
            {formatCurrency(item.budget_amount)}
          </button>
        )}
      </div>
      <div className="w-24 text-right">
        <span className="text-sm tabular-nums text-text-secondary">{formatCurrency(item.actual_amount)}</span>
      </div>
      <div className="w-28 text-right pl-2">
        <span className={`text-sm font-semibold tabular-nums ${color}`}>
          {item.variance >= 0 ? "" : "-"}{formatCurrency(Math.abs(item.variance))}
        </span>
      </div>
      <div className="w-12 text-right">
        <button
          onClick={() => onDelete(item.id)}
          aria-label="Delete budget line"
          className="text-xs text-text-muted hover:text-red-500 opacity-0 group-hover:opacity-100"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
