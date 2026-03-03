"use client";
import { useCallback, useEffect, useState } from "react";
import { Plus, Target, Loader2, Check, AlertCircle, ChevronRight } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { getGoals, createGoal, updateGoal } from "@/lib/api";
import type { Goal } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import ProgressBar from "@/components/ui/ProgressBar";

const GOAL_TYPES = [
  { value: "savings", label: "Savings", icon: "💰" },
  { value: "debt_payoff", label: "Debt Payoff", icon: "💳" },
  { value: "investment", label: "Investment", icon: "📈" },
  { value: "emergency_fund", label: "Emergency Fund", icon: "🛡️" },
  { value: "purchase", label: "Major Purchase", icon: "🏠" },
  { value: "tax", label: "Tax Reserve", icon: "📋" },
  { value: "other", label: "Other", icon: "⭐" },
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

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const [name, setName] = useState("");
  const [goalType, setGoalType] = useState<"savings" | "debt_payoff" | "investment" | "emergency_fund" | "purchase" | "tax" | "other">("savings");
  const [targetAmount, setTargetAmount] = useState("");
  const [currentAmount, setCurrentAmount] = useState("0");
  const [targetDate, setTargetDate] = useState("");
  const [monthlyContrib, setMonthlyContrib] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [saving, setSaving] = useState(false);
  const [contribGoalId, setContribGoalId] = useState<number | null>(null);
  const [contribAmount, setContribAmount] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getGoals();
      setGoals(Array.isArray(data) ? data : []);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleAdd() {
    if (!name || !targetAmount) return;
    setSaving(true);
    setError(null);
    try {
      await createGoal({
        name, goal_type: goalType,
        target_amount: parseFloat(targetAmount),
        current_amount: parseFloat(currentAmount) || 0,
        target_date: targetDate || null,
        monthly_contribution: monthlyContrib ? parseFloat(monthlyContrib) : null,
        color, status: "active", description: null,
      });
      setShowAdd(false);
      setName(""); setTargetAmount(""); setCurrentAmount("0"); setTargetDate(""); setMonthlyContrib("");
      load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setSaving(false);
  }

  async function handleContribution(goal: Goal, amount: number) {
    try {
      await updateGoal(goal.id, { current_amount: goal.current_amount + amount });
      load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  async function handleComplete(goalId: number) {
    try {
      await updateGoal(goalId, { status: "completed" });
      load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  const active = goals.filter((g) => g.status === "active");
  const completed = goals.filter((g) => g.status === "completed");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Goals"
        subtitle="Financial goals and progress tracking"
        actions={
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
          >
            <Plus size={15} /> Add goal
          </button>
        }
      />

      {/* Add goal form */}
      {showAdd && (
        <Card padding="lg">
          <h2 className="font-semibold text-stone-800 mb-4">New Goal</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-stone-500 mb-1.5">Goal Name</label>
              <input
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Emergency Fund, Vacation, Pay off car"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
              />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1.5">Goal Type</label>
              <select value={goalType} onChange={(e) => setGoalType(e.target.value as typeof goalType)}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] bg-white">
                {GOAL_TYPES.map((t) => <option key={t.value} value={t.value}>{t.icon} {t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1.5">Target Amount</label>
              <input type="number" value={targetAmount} onChange={(e) => setTargetAmount(e.target.value)} placeholder="0.00" min="0"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1.5">Current Amount</label>
              <input type="number" value={currentAmount} onChange={(e) => setCurrentAmount(e.target.value)} placeholder="0.00" min="0"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1.5">Monthly Contribution</label>
              <input type="number" value={monthlyContrib} onChange={(e) => setMonthlyContrib(e.target.value)} placeholder="Optional"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1.5">Target Date</label>
              <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-stone-500 mb-2">Color</label>
              <div className="flex gap-2">
                {COLORS.map((c) => (
                  <button key={c} onClick={() => setColor(c)}
                    className={`w-8 h-8 rounded-full transition-transform ${color === c ? "scale-110 ring-2 ring-offset-2 ring-stone-400" : "hover:scale-105"}`}
                    style={{ backgroundColor: c }} />
                ))}
              </div>
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button onClick={handleAdd} disabled={saving || !name || !targetAmount}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60 shadow-sm">
              {saving ? <Loader2 size={13} className="animate-spin" /> : null} Create Goal
            </button>
            <button onClick={() => setShowAdd(false)} className="text-sm text-stone-500 hover:text-stone-700 px-3">Cancel</button>
          </div>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      ) : (
        <>
          {error && (
            <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
              <AlertCircle size={18} />
              <p className="text-sm">{error}</p>
            </div>
          )}

          {active.length === 0 && !showAdd ? (
            <EmptyState
              icon={<Target size={40} />}
              title="No goals yet"
              description="Set financial goals to track your progress towards savings, debt payoff, and more."
              action={
                <button onClick={() => setShowAdd(true)} className="bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm">
                  Create First Goal
                </button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {active.map((goal, i) => {
                const type = GOAL_TYPES.find((t) => t.value === goal.goal_type);
                const gradient = GRADIENTS[i % GRADIENTS.length];

                return (
                  <div
                    key={goal.id}
                    className="rounded-xl overflow-hidden border border-stone-100 shadow-sm hover:shadow-md transition-shadow group"
                  >
                    {/* Gradient header */}
                    <div className={`bg-gradient-to-br ${gradient} px-5 pt-5 pb-8 relative`}>
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-white/70 text-xs font-medium">{type?.label ?? goal.goal_type}</p>
                          <p className="text-white font-bold text-lg mt-0.5">{goal.name}</p>
                        </div>
                        {goal.on_track === true && (
                          <span className="text-xs bg-white/20 text-white px-2 py-0.5 rounded backdrop-blur-sm">On track</span>
                        )}
                        {goal.on_track === false && (
                          <span className="text-xs bg-red-500/30 text-white px-2 py-0.5 rounded backdrop-blur-sm">Behind</span>
                        )}
                      </div>
                      <p className="text-white font-bold text-2xl mt-3 tracking-tight">
                        {formatCurrency(goal.current_amount, true)}
                      </p>
                    </div>

                    {/* Progress section */}
                    <div className="bg-white px-5 py-4 -mt-3 rounded-t-xl relative">
                      <ProgressBar
                        value={goal.progress_pct}
                        color={goal.color}
                        size="md"
                      />
                      <div className="flex justify-between items-center mt-2">
                        <span className="text-xs font-semibold" style={{ color: goal.color }}>
                          {goal.progress_pct}%
                        </span>
                        <span className="text-xs text-stone-400 tabular-nums">
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
                        {contribGoalId === goal.id ? (
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
                                  if (amt > 0) { handleContribution(goal, amt); setContribGoalId(null); setContribAmount(""); }
                                } else if (e.key === "Escape") { setContribGoalId(null); setContribAmount(""); }
                              }}
                              className="w-24 text-xs border border-stone-200 rounded-lg px-2 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
                            />
                            <button
                              onClick={() => {
                                const amt = parseFloat(contribAmount);
                                if (amt > 0) { handleContribution(goal, amt); setContribGoalId(null); setContribAmount(""); }
                              }}
                              className="text-xs bg-[#16A34A] text-white rounded-lg px-3 py-2 font-medium hover:bg-[#15803D]"
                            >
                              Add
                            </button>
                            <button
                              onClick={() => { setContribGoalId(null); setContribAmount(""); }}
                              className="text-xs text-stone-400 hover:text-stone-600 px-1"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => { setContribGoalId(goal.id); setContribAmount(""); }}
                            className="flex-1 text-xs border border-stone-200 rounded-lg py-2 hover:bg-stone-50 text-stone-600 font-medium"
                          >
                            + Add Funds
                          </button>
                        )}
                        {goal.progress_pct >= 100 && (
                          <button
                            onClick={() => handleComplete(goal.id)}
                            className="flex items-center gap-1 text-xs bg-green-50 text-green-700 border border-green-200 rounded-lg px-3 py-2 hover:bg-green-100 font-medium"
                          >
                            <Check size={11} /> Complete
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {completed.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">
            Completed Goals ({completed.length})
          </h2>
          <div className="space-y-2">
            {completed.map((goal) => (
              <Card key={goal.id} className="bg-green-50/50 border-green-100">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                      <Check size={14} className="text-green-600" />
                    </div>
                    <p className="font-medium text-stone-700">{goal.name}</p>
                  </div>
                  <span className="text-sm font-semibold text-green-600 tabular-nums">{formatCurrency(goal.target_amount)}</span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
