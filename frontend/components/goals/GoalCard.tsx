"use client";
import { useState } from "react";
import { Check, Pencil, Trash2, MoreVertical, X, Loader2 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { updateGoal, deleteGoal } from "@/lib/api";
import type { Goal } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import ProgressBar from "@/components/ui/ProgressBar";

const GOAL_TYPES = [
  { value: "savings", label: "Savings" },
  { value: "debt_payoff", label: "Debt Payoff" },
  { value: "investment", label: "Investment" },
  { value: "emergency_fund", label: "Emergency Fund" },
  { value: "purchase", label: "Major Purchase" },
  { value: "tax", label: "Tax Reserve" },
  { value: "other", label: "Other" },
];

const GRADIENTS = [
  "from-stone-600 to-stone-800",
  "from-blue-600 to-indigo-800",
  "from-emerald-600 to-teal-800",
  "from-amber-500 to-orange-700",
  "from-rose-500 to-pink-700",
  "from-purple-600 to-violet-800",
  "from-cyan-500 to-sky-700",
];

const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];

interface GoalCardProps {
  goal: Goal;
  index: number;
  onUpdate: () => void;
  onError: (msg: string) => void;
}

export default function GoalCard({ goal, index, onUpdate, onError }: GoalCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [editing, setEditing] = useState(false);
  const [contribMode, setContribMode] = useState(false);
  const [contribAmount, setContribAmount] = useState("");
  const [saving, setSaving] = useState(false);

  // Edit form state
  const [editName, setEditName] = useState(goal.name);
  const [editType, setEditType] = useState(goal.goal_type);
  const [editTarget, setEditTarget] = useState(String(goal.target_amount));
  const [editCurrent, setEditCurrent] = useState(String(goal.current_amount));
  const [editContrib, setEditContrib] = useState(goal.monthly_contribution ? String(goal.monthly_contribution) : "");
  const [editDate, setEditDate] = useState(goal.target_date ?? "");
  const [editColor, setEditColor] = useState(goal.color);

  const type = GOAL_TYPES.find((t) => t.value === goal.goal_type);
  const gradient = GRADIENTS[index % GRADIENTS.length];

  async function handleContribution(amount: number) {
    try {
      await updateGoal(goal.id, { current_amount: goal.current_amount + amount });
      onUpdate();
    } catch (e: unknown) {
      onError(getErrorMessage(e));
    }
  }

  async function handleComplete() {
    try {
      await updateGoal(goal.id, { status: "completed" });
      onUpdate();
    } catch (e: unknown) {
      onError(getErrorMessage(e));
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this goal? This cannot be undone.")) return;
    try {
      await deleteGoal(goal.id);
      onUpdate();
    } catch (e: unknown) {
      onError(getErrorMessage(e));
    }
    setShowMenu(false);
  }

  async function handleEdit() {
    setSaving(true);
    try {
      await updateGoal(goal.id, {
        name: editName,
        goal_type: editType,
        target_amount: parseFloat(editTarget),
        current_amount: parseFloat(editCurrent),
        monthly_contribution: editContrib ? parseFloat(editContrib) : undefined,
        target_date: editDate || undefined,
        color: editColor,
      });
      setEditing(false);
      onUpdate();
    } catch (e: unknown) {
      onError(getErrorMessage(e));
    }
    setSaving(false);
  }

  if (editing) {
    return (
      <div className="rounded-xl overflow-hidden border border-[#16A34A]/30 shadow-sm bg-white">
        <div className={`bg-gradient-to-br ${gradient} px-5 py-3`}>
          <p className="text-white font-semibold text-sm">Edit Goal</p>
        </div>
        <div className="p-5 space-y-3">
          <div>
            <label className="block text-xs text-stone-500 mb-1">Name</label>
            <input value={editName} onChange={(e) => setEditName(e.target.value)}
              className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-stone-500 mb-1">Type</label>
              <select value={editType} onChange={(e) => setEditType(e.target.value as Goal["goal_type"])}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] bg-white">
                {GOAL_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">Target Amount</label>
              <input type="number" value={editTarget} onChange={(e) => setEditTarget(e.target.value)} min="0"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">Current Amount</label>
              <input type="number" value={editCurrent} onChange={(e) => setEditCurrent(e.target.value)} min="0"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">Monthly Contribution</label>
              <input type="number" value={editContrib} onChange={(e) => setEditContrib(e.target.value)} placeholder="Optional"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-stone-500 mb-1">Target Date</label>
            <input type="date" value={editDate} onChange={(e) => setEditDate(e.target.value)}
              className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
          </div>
          <div>
            <label className="block text-xs text-stone-500 mb-1.5">Color</label>
            <div className="flex gap-2">
              {COLORS.map((c) => (
                <button key={c} onClick={() => setEditColor(c)}
                  className={`w-7 h-7 rounded-full transition-transform ${editColor === c ? "scale-110 ring-2 ring-offset-2 ring-stone-400" : "hover:scale-105"}`}
                  style={{ backgroundColor: c }} />
              ))}
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <button onClick={handleEdit} disabled={saving || !editName || !editTarget}
              className="flex items-center gap-1.5 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60">
              {saving ? <Loader2 size={12} className="animate-spin" /> : null} Save
            </button>
            <button onClick={() => setEditing(false)} className="text-sm text-stone-500 hover:text-stone-700 px-3">
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl overflow-hidden border border-stone-100 shadow-sm hover:shadow-md transition-shadow group relative">
      {/* Gradient header */}
      <div className={`bg-gradient-to-br ${gradient} px-5 pt-5 pb-8 relative`}>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-white/70 text-xs font-medium">{type?.label ?? goal.goal_type}</p>
            <p className="text-white font-bold text-lg mt-0.5">{goal.name}</p>
          </div>
          <div className="flex items-center gap-2">
            {goal.on_track === true && (
              <span className="text-xs bg-white/20 text-white px-2 py-0.5 rounded backdrop-blur-sm">On track</span>
            )}
            {goal.on_track === false && (
              <span className="text-xs bg-red-500/30 text-white px-2 py-0.5 rounded backdrop-blur-sm">Behind</span>
            )}
            {/* Action menu */}
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="text-white/60 hover:text-white p-1 rounded transition-colors"
              >
                <MoreVertical size={16} />
              </button>
              {showMenu && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                  <div className="absolute right-0 top-8 bg-white rounded-lg shadow-lg border border-stone-200 py-1 z-20 w-36">
                    <button
                      onClick={() => { setEditing(true); setShowMenu(false); }}
                      className="flex items-center gap-2 w-full px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
                    >
                      <Pencil size={13} /> Edit
                    </button>
                    <button
                      onClick={handleDelete}
                      className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                    >
                      <Trash2 size={13} /> Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
        <p className="text-white font-bold text-2xl mt-3 tracking-tight font-mono tabular-nums">
          {formatCurrency(goal.current_amount, true)}
        </p>
      </div>

      {/* Progress section */}
      <div className="bg-white px-5 py-4 -mt-3 rounded-t-xl relative">
        <ProgressBar value={goal.progress_pct} color={goal.color} size="md" />
        <div className="flex justify-between items-center mt-2">
          <span className="text-xs font-semibold" style={{ color: goal.color }}>
            {goal.progress_pct}%
          </span>
          <span className="text-xs text-stone-400 font-mono tabular-nums">
            of {formatCurrency(goal.target_amount, true)}
          </span>
        </div>

        {goal.monthly_contribution && (
          <p className="text-xs text-stone-500 mt-2">
            {formatCurrency(goal.monthly_contribution)}/mo
            {goal.months_remaining != null && ` · ${goal.months_remaining}mo remaining`}
          </p>
        )}

        <div className="flex gap-2 mt-3">
          {contribMode ? (
            <div className="flex items-center gap-1.5 flex-1">
              <input
                type="number"
                autoFocus
                min="0"
                step="0.01"
                value={contribAmount}
                onChange={(e) => setContribAmount(e.target.value)}
                placeholder="Amount"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    const amt = parseFloat(contribAmount);
                    if (amt > 0) { handleContribution(amt); setContribMode(false); setContribAmount(""); }
                  } else if (e.key === "Escape") { setContribMode(false); setContribAmount(""); }
                }}
                className="w-24 text-xs border border-stone-200 rounded-lg px-2 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
              />
              <button
                onClick={() => {
                  const amt = parseFloat(contribAmount);
                  if (amt > 0) { handleContribution(amt); setContribMode(false); setContribAmount(""); }
                }}
                className="text-xs bg-[#16A34A] text-white rounded-lg px-3 py-2 font-medium hover:bg-[#15803D]"
              >
                Add
              </button>
              <button
                onClick={() => { setContribMode(false); setContribAmount(""); }}
                className="text-xs text-stone-400 hover:text-stone-600 px-1"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setContribMode(true)}
              className="flex-1 text-xs border border-stone-200 rounded-lg py-2 hover:bg-stone-50 text-stone-600 font-medium"
            >
              + Add Funds
            </button>
          )}
          {goal.progress_pct >= 100 && (
            <button
              onClick={handleComplete}
              className="flex items-center gap-1 text-xs bg-green-50 text-green-700 border border-green-200 rounded-lg px-3 py-2 hover:bg-green-100 font-medium"
            >
              <Check size={11} /> Complete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
