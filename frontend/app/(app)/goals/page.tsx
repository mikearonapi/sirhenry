"use client";
import { useCallback, useEffect, useState } from "react";
import { Plus, Target, Loader2, Check, AlertCircle, MessageCircle, ArrowRight, Landmark, PieChart, Compass, Briefcase, TrendingUp, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { formatCurrency } from "@/lib/utils";
import { getGoals, createGoal } from "@/lib/api";
import type { Goal } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import ProgressBar from "@/components/ui/ProgressBar";
import GoalCard from "@/components/goals/GoalCard";
import GoalTemplates, { type GoalTemplate } from "@/components/goals/GoalTemplates";
import { GOAL_TYPES, COLORS } from "@/components/goals/constants";
import SirHenryName from "@/components/ui/SirHenryName";

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
  const [color, setColor] = useState<string>(COLORS[0]);
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

  // Form validation
  const targetNum = parseFloat(targetAmount);
  const currentNum = parseFloat(currentAmount) || 0;
  const isTargetValid = !isNaN(targetNum) && targetNum > 0;
  const isCurrentOverTarget = isTargetValid && currentNum > targetNum;
  const today = new Date().toISOString().split("T")[0];
  const isDatePast = targetDate && targetDate < today;
  const canSubmit = name.trim() && isTargetValid && !saving;

  async function handleAdd() {
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      await createGoal({
        name: name.trim(),
        goal_type: goalType,
        target_amount: targetNum,
        current_amount: currentNum,
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

  // Summary stats
  const totalTarget = active.reduce((s, g) => s + g.target_amount, 0);
  const totalCurrent = active.reduce((s, g) => s + g.current_amount, 0);
  const overallProgress = totalTarget > 0 ? Math.round(totalCurrent / totalTarget * 100) : 0;
  const onTrackCount = active.filter((g) => g.on_track === true).length;
  const behindCount = active.filter((g) => g.on_track === false).length;
  const totalMonthly = active.reduce((s, g) => s + (g.monthly_contribution ?? 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Goals"
        subtitle="Financial goals and progress tracking"
        actions={
          <div className="flex items-center gap-3">
            <button
              onClick={() => askHenry("Review my financial goals and suggest what I should prioritize given my income and situation.")}
              className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
            >
              <MessageCircle size={14} />
              Ask <SirHenryName />
            </button>
            <button
              onClick={() => { resetForm(); setShowAdd(true); }}
              className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm"
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

      {/* Goals Summary Dashboard — only when there are active goals */}
      {!loading && active.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="!p-4">
            <p className="text-xs text-text-muted mb-1">Overall Progress</p>
            <p className="text-2xl font-bold text-text-primary font-mono tabular-nums">{overallProgress}%</p>
            <ProgressBar value={overallProgress} color="#16A34A" size="sm" />
            <p className="text-xs text-text-muted mt-1.5">
              {formatCurrency(totalCurrent, true)} of {formatCurrency(totalTarget, true)}
            </p>
          </Card>
          <Card className="!p-4">
            <p className="text-xs text-text-muted mb-1">Active Goals</p>
            <p className="text-2xl font-bold text-text-primary font-mono tabular-nums">{active.length}</p>
            <div className="flex items-center gap-2 mt-1.5">
              {onTrackCount > 0 && (
                <span className="text-xs text-green-600 flex items-center gap-0.5">
                  <CheckCircle2 size={10} /> {onTrackCount} on track
                </span>
              )}
              {behindCount > 0 && (
                <span className="text-xs text-red-500 flex items-center gap-0.5">
                  <AlertCircle size={10} /> {behindCount} behind
                </span>
              )}
            </div>
          </Card>
          <Card className="!p-4">
            <p className="text-xs text-text-muted mb-1">Monthly Commitment</p>
            <p className="text-2xl font-bold text-text-primary font-mono tabular-nums">{formatCurrency(totalMonthly, true)}</p>
            <p className="text-xs text-text-muted mt-1.5">across {active.filter((g) => g.monthly_contribution).length} goals</p>
          </Card>
          <Card className="!p-4">
            <p className="text-xs text-text-muted mb-1">Remaining</p>
            <p className="text-2xl font-bold text-text-primary font-mono tabular-nums">{formatCurrency(totalTarget - totalCurrent, true)}</p>
            <p className="text-xs text-text-muted mt-1.5">
              {completed.length > 0 && `${completed.length} goal${completed.length > 1 ? "s" : ""} completed`}
              {completed.length === 0 && "to reach all targets"}
            </p>
          </Card>
        </div>
      )}

      {/* Add goal form */}
      {showAdd && (
        <Card padding="lg">
          <h2 className="font-semibold text-text-primary mb-4">New Goal</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-text-secondary mb-1.5">Goal Name</label>
              <input
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Emergency Fund, Down Payment, Pay off loans"
                className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
              />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Goal Type</label>
              <select value={goalType} onChange={(e) => setGoalType(e.target.value as Goal["goal_type"])}
                className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-card">
                {GOAL_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Target Amount</label>
              <input type="number" value={targetAmount} onChange={(e) => setTargetAmount(e.target.value)} placeholder="0.00" min="1" step="0.01"
                className={`w-full text-sm border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent ${targetAmount && !isTargetValid ? "border-red-300" : "border-border"}`} />
              {targetAmount && !isTargetValid && (
                <p className="text-xs text-red-500 mt-1">Target amount must be greater than 0</p>
              )}
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Current Amount</label>
              <input type="number" value={currentAmount} onChange={(e) => setCurrentAmount(e.target.value)} placeholder="0.00" min="0" step="0.01"
                className={`w-full text-sm border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent ${isCurrentOverTarget ? "border-amber-300" : "border-border"}`} />
              {isCurrentOverTarget && (
                <p className="text-xs text-amber-600 mt-1">Current amount exceeds target — goal may already be complete</p>
              )}
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Monthly Contribution</label>
              <input type="number" value={monthlyContrib} onChange={(e) => setMonthlyContrib(e.target.value)} placeholder="Optional" min="0" step="0.01"
                className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Target Date</label>
              <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)}
                className={`w-full text-sm border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent ${isDatePast ? "border-amber-300" : "border-border"}`} />
              {isDatePast && (
                <p className="text-xs text-amber-600 mt-1">This date is in the past</p>
              )}
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-text-secondary mb-2">Color</label>
              <div className="flex gap-2">
                {COLORS.map((c) => (
                  <button key={c} onClick={() => setColor(c)}
                    aria-label={`Select color ${c}`}
                    className={`w-8 h-8 rounded-full transition-transform ${color === c ? "scale-110 ring-2 ring-offset-2 ring-border" : "hover:scale-105"}`}
                    style={{ backgroundColor: c }} />
                ))}
              </div>
            </div>
          </div>

          {/* Show projected timeline when monthly contribution and target are set */}
          {isTargetValid && monthlyContrib && parseFloat(monthlyContrib) > 0 && (
            <div className="mt-4 p-3 bg-surface rounded-lg border border-card-border">
              <div className="flex items-center gap-2 text-xs text-text-secondary">
                <TrendingUp size={12} className="text-accent" />
                <span>
                  At {formatCurrency(parseFloat(monthlyContrib))}/mo, you&apos;ll reach {formatCurrency(targetNum, true)} in{" "}
                  <strong className="text-text-secondary">
                    {Math.ceil((targetNum - currentNum) / parseFloat(monthlyContrib))} months
                  </strong>
                  {targetDate && !isDatePast && (
                    <>
                      {" "}(target: {new Date(targetDate + "T00:00:00").toLocaleDateString("en-US", { month: "short", year: "numeric" })})
                    </>
                  )}
                </span>
              </div>
            </div>
          )}

          <div className="flex gap-3 mt-5">
            <button onClick={handleAdd} disabled={!canSubmit}
              className="flex items-center gap-2 bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60 shadow-sm">
              {saving ? <Loader2 size={13} className="animate-spin" /> : null} Create Goal
            </button>
            <button onClick={() => { setShowAdd(false); resetForm(); }} className="text-sm text-text-secondary hover:text-text-secondary px-3">Cancel</button>
          </div>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-text-muted" size={24} /></div>
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
                    className="bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm">
                    Create Custom Goal
                  </button>
                }
              />
              {/* HENRY goal template gallery */}
              <div>
                <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
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
            <Link href="/portfolio" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface border border-border hover:border-accent/30 hover:bg-green-50/30 transition-colors text-xs text-text-secondary hover:text-text-primary">
              <PieChart size={14} className="text-accent" /> Track investments in Portfolio <ArrowRight size={12} />
            </Link>
          )}
          {active.some((g) => g.goal_type === "tax") && (
            <Link href="/equity-comp" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface border border-border hover:border-accent/30 hover:bg-green-50/30 transition-colors text-xs text-text-secondary hover:text-text-primary">
              <Briefcase size={14} className="text-accent" /> Manage equity comp taxes <ArrowRight size={12} />
            </Link>
          )}
          {active.some((g) => g.goal_type === "purchase") && (
            <Link href="/life-planner" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface border border-border hover:border-accent/30 hover:bg-green-50/30 transition-colors text-xs text-text-secondary hover:text-text-primary">
              <Compass size={14} className="text-accent" /> Model purchase in Life Planner <ArrowRight size={12} />
            </Link>
          )}
          <Link href="/retirement" className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface border border-border hover:border-accent/30 hover:bg-green-50/30 transition-colors text-xs text-text-secondary hover:text-text-primary">
            <Landmark size={14} className="text-accent" /> Retirement planner <ArrowRight size={12} />
          </Link>
        </div>
      )}

      {/* Completed goals */}
      {completed.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
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
                    <p className="font-medium text-text-secondary">{goal.name}</p>
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
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
            Add another goal
          </h2>
          <GoalTemplates onSelect={prefillFromTemplate} />
        </div>
      )}
    </div>
  );
}
