"use client";
import { useCallback, useEffect, useState } from "react";
import { Plus, Target, Loader2, Check, AlertCircle, MessageCircle, ArrowRight, Landmark, PieChart, Compass, Briefcase } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { getGoals, createGoal } from "@/lib/api";
import type { Goal } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import GoalCard from "@/components/goals/GoalCard";
import GoalTemplates, { type GoalTemplate } from "@/components/goals/GoalTemplates";

const GOAL_TYPES = [
  { value: "savings", label: "Savings" },
  { value: "debt_payoff", label: "Debt Payoff" },
  { value: "investment", label: "Investment" },
  { value: "emergency_fund", label: "Emergency Fund" },
  { value: "purchase", label: "Major Purchase" },
  { value: "tax", label: "Tax Reserve" },
  { value: "other", label: "Other" },
];

const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  // Create form state
  const [name, setName] = useState("");
  const [goalType, setGoalType] = useState<Goal["goal_type"]>("savings");
  const [targetAmount, setTargetAmount] = useState("");
  const [currentAmount, setCurrentAmount] = useState("0");
  const [targetDate, setTargetDate] = useState("");
  const [monthlyContrib, setMonthlyContrib] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getGoals();
      setGoals(Array.isArray(data) ? data : []);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  function prefillFromTemplate(template: GoalTemplate) {
    setName(template.name);
    setGoalType(template.goal_type as Goal["goal_type"]);
    setTargetAmount(String(template.target_amount));
    setMonthlyContrib(String(template.monthly_contribution));
    setColor(template.color);
    setCurrentAmount("0");
    setTargetDate("");
    setShowAdd(true);
  }

  function resetForm() {
    setName(""); setGoalType("savings"); setTargetAmount(""); setCurrentAmount("0");
    setTargetDate(""); setMonthlyContrib(""); setColor(COLORS[0]);
  }

  async function handleAdd() {
    if (!name || !targetAmount) return;
    setSaving(true);
    setError(null);
    try {
      await createGoal({
        name,
        goal_type: goalType,
        target_amount: parseFloat(targetAmount),
        current_amount: parseFloat(currentAmount) || 0,
        target_date: targetDate || null,
        monthly_contribution: monthlyContrib ? parseFloat(monthlyContrib) : null,
        color,
        status: "active",
        description: null,
      });
      setShowAdd(false);
      resetForm();
      load();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setSaving(false);
  }

  const active = goals.filter((g) => g.status === "active");
  const completed = goals.filter((g) => g.status === "completed");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Goals"
        subtitle="Financial goals and progress tracking"
        actions={
          <div className="flex items-center gap-3">
            <button
              onClick={() => askHenry("Review my financial goals and suggest what I should prioritize given my income and situation.")}
              className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:text-[#15803D] transition-colors"
            >
              <MessageCircle size={14} />
              Ask Sir Henry
            </button>
            <button
              onClick={() => { resetForm(); setShowAdd(true); }}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
            >
              <Plus size={15} /> Add goal
            </button>
          </div>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
            <Plus size={14} className="rotate-45" />
          </button>
        </div>
      )}

      {/* Add goal form */}
      {showAdd && (
        <Card padding="lg">
          <h2 className="font-semibold text-stone-800 mb-4">New Goal</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-stone-500 mb-1.5">Goal Name</label>
              <input
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Emergency Fund, Down Payment, Pay off loans"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
              />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1.5">Goal Type</label>
              <select value={goalType} onChange={(e) => setGoalType(e.target.value as Goal["goal_type"])}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] bg-white">
                {GOAL_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
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
            <button onClick={() => { setShowAdd(false); resetForm(); }} className="text-sm text-stone-500 hover:text-stone-700 px-3">Cancel</button>
          </div>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      ) : (
        <>
          {active.length === 0 && !showAdd ? (
            <div className="space-y-6">
              <EmptyState
                icon={<Target size={40} />}
                title="Set your first financial goal"
                description="HENRYs who track specific goals save 2-3x more than those who don't. Start with what matters most to you."
                henryTip="Most high earners I work with start with an emergency fund and maxing tax-advantaged accounts. Those two moves alone can save you thousands in taxes."
                askHenryPrompt="What financial goals should I prioritize given my income and situation?"
                action={
                  <button onClick={() => { resetForm(); setShowAdd(true); }}
                    className="bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm">
                    Create Custom Goal
                  </button>
                }
              />
              {/* HENRY goal template gallery */}
              <div>
                <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">
                  Recommended for high earners
                </h2>
                <GoalTemplates onSelect={prefillFromTemplate} />
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {active.map((goal, i) => (
                <GoalCard
                  key={goal.id}
                  goal={goal}
                  index={i}
                  onUpdate={load}
                  onError={(msg) => setError(msg)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Cross-page links based on goal types */}
      {active.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {active.some((g) => g.goal_type === "investment" || g.goal_type === "savings") && (
            <a href="/portfolio" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 hover:border-[#16A34A]/30 hover:bg-green-50/30 transition-colors text-xs text-stone-600 hover:text-stone-800">
              <PieChart size={14} className="text-[#16A34A]" /> Track investments in Portfolio <ArrowRight size={12} />
            </a>
          )}
          {active.some((g) => g.goal_type === "tax") && (
            <a href="/equity-comp" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 hover:border-[#16A34A]/30 hover:bg-green-50/30 transition-colors text-xs text-stone-600 hover:text-stone-800">
              <Briefcase size={14} className="text-[#16A34A]" /> Manage equity comp taxes <ArrowRight size={12} />
            </a>
          )}
          {active.some((g) => g.goal_type === "purchase") && (
            <a href="/life-planner" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 hover:border-[#16A34A]/30 hover:bg-green-50/30 transition-colors text-xs text-stone-600 hover:text-stone-800">
              <Compass size={14} className="text-[#16A34A]" /> Model purchase in Life Planner <ArrowRight size={12} />
            </a>
          )}
          <a href="/retirement" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 hover:border-[#16A34A]/30 hover:bg-green-50/30 transition-colors text-xs text-stone-600 hover:text-stone-800">
            <Landmark size={14} className="text-[#16A34A]" /> Retirement planner <ArrowRight size={12} />
          </a>
        </div>
      )}

      {/* Completed goals */}
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
                  <span className="text-sm font-semibold text-green-600 font-mono tabular-nums">{formatCurrency(goal.target_amount)}</span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Show templates below active goals for adding more */}
      {active.length > 0 && !showAdd && (
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">
            Add another goal
          </h2>
          <GoalTemplates onSelect={prefillFromTemplate} />
        </div>
      )}
    </div>
  );
}
