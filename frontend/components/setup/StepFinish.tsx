"use client";
import { useState, useMemo, useEffect, useRef } from "react";
import {
  Brain, Sparkles, Loader2, CheckCircle2, Zap, ChevronDown, ChevronUp,
  Lightbulb, MessageCircle, ArrowRight, ChevronRight, Target,
} from "lucide-react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import SirHenryName from "@/components/ui/SirHenryName";
import { generateRules, applyGeneratedRules } from "@/lib/api-rules";
import { getProactiveInsights } from "@/lib/api-smart-defaults";
import { getGoals, createGoal, getGoalSuggestions } from "@/lib/api-goals";
import type { GenerateRulesResponse } from "@/types/rules";
import type { ProactiveInsight } from "@/types/smart-defaults";
import type { SetupData, SetupStep } from "./SetupWizard";
import { OB_CTA, OB_HEADING, OB_SUBTITLE } from "./styles";
import { ONBOARDING_GOALS_KEY } from "@/lib/storage-keys";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

type Phase = "intro" | "analyzing" | "review" | "applying" | "done";

interface Props {
  data: SetupData;
  hasTransactions: boolean;
  onGoTo: (step: SetupStep) => void;
}

export default function StepFinish({ data, hasTransactions, onGoTo }: Props) {
  // ── Rules state ──
  const [phase, setPhase] = useState<Phase>(hasTransactions ? "analyzing" : "intro");
  const [rulesResponse, setRulesResponse] = useState<GenerateRulesResponse | null>(null);
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [showDetails, setShowDetails] = useState(false);
  const [result, setResult] = useState<{ rules_created: number; transactions_categorized: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [goalsCreated, setGoalsCreated] = useState(0);
  const goalsCreatedRef = useRef(false);
  const autoAnalyzeRef = useRef(false);

  const selectedRules = useMemo(() => {
    if (!rulesResponse) return [];
    return rulesResponse.rules.filter((r) => !excluded.has(r.merchant));
  }, [rulesResponse, excluded]);

  const categoryBreakdown = useMemo(() => {
    const counts: Record<string, { count: number; txns: number }> = {};
    for (const r of selectedRules) {
      const cat = r.category || "Unknown";
      if (!counts[cat]) counts[cat] = { count: 0, txns: 0 };
      counts[cat].count += 1;
      counts[cat].txns += r.transaction_count;
    }
    return Object.entries(counts).sort((a, b) => b[1].txns - a[1].txns).slice(0, 10);
  }, [selectedRules]);

  // Auto-create goals from GoalsScreen selections (one-time)
  useEffect(() => {
    if (goalsCreatedRef.current) return;
    goalsCreatedRef.current = true;

    const raw = localStorage.getItem(ONBOARDING_GOALS_KEY);
    if (!raw) return;
    let selectedGoals: string[];
    try { selectedGoals = JSON.parse(raw); } catch { return; }
    if (!selectedGoals.length) return;

    (async () => {
      try {
        const [suggestions, existingGoals] = await Promise.all([
          getGoalSuggestions().catch(() => ({ suggestions: [], annual_income: 0 })),
          getGoals().catch(() => []),
        ]);
        const existingTypes = new Set<string>(existingGoals.map((g) => g.goal_type));
        type GoalType = "savings" | "debt_payoff" | "investment" | "emergency_fund" | "purchase" | "tax" | "other";
        const goalsToCreate: Array<{ name: string; goal_type: GoalType; target_amount: number; monthly_contribution: number; description: string; color: string }> = [];

        const isEverything = selectedGoals.includes("everything");

        // Map onboarding keys to goal suggestions
        if (isEverything) {
          // Create top 3 suggestions that don't already exist
          for (const s of suggestions.suggestions.slice(0, 3)) {
            if (!existingTypes.has(s.goal_type)) {
              goalsToCreate.push({ name: s.name, goal_type: s.goal_type as GoalType, target_amount: s.target_amount, monthly_contribution: s.monthly_contribution, description: s.description, color: s.color });
            }
          }
        } else {
          for (const key of selectedGoals) {
            if (key === "tax") {
              const match = suggestions.suggestions.find((s) => s.goal_type === "tax");
              if (match && !existingTypes.has("tax")) {
                goalsToCreate.push({ name: match.name, goal_type: match.goal_type as GoalType, target_amount: match.target_amount, monthly_contribution: match.monthly_contribution, description: match.description, color: match.color });
              }
            } else if (key === "retirement") {
              if (!existingTypes.has("savings")) {
                const income = suggestions.annual_income || (data.household?.combined_income ?? 0);
                goalsToCreate.push({
                  name: "Retirement Savings", goal_type: "savings",
                  target_amount: Math.round(income * 0.15 * 10),
                  monthly_contribution: Math.round(income * 0.15 / 12),
                  description: "Build long-term retirement wealth", color: "#16A34A",
                });
              }
            } else if (key === "cashflow") {
              const match = suggestions.suggestions.find((s) => s.goal_type === "emergency_fund");
              if (match && !existingTypes.has("emergency_fund")) {
                goalsToCreate.push({ name: match.name, goal_type: match.goal_type as GoalType, target_amount: match.target_amount, monthly_contribution: match.monthly_contribution, description: match.description, color: match.color });
              }
            }
            // insurance + business don't map to goal types — skip
          }
        }

        let created = 0;
        for (const goal of goalsToCreate) {
          try {
            await createGoal({ ...goal, current_amount: 0, target_date: null, status: "active" });
            created++;
          } catch { /* skip duplicate */ }
        }
        if (created > 0) setGoalsCreated(created);
        localStorage.removeItem(ONBOARDING_GOALS_KEY);
      } catch { /* non-critical */ }
    })();
  }, [data.household?.combined_income]);

  // Auto-start analysis when component mounts with transactions
  useEffect(() => {
    if (autoAnalyzeRef.current || phase !== "analyzing") return;
    autoAnalyzeRef.current = true;
    handleAnalyzeInternal();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  async function handleAnalyzeInternal() {
    setPhase("analyzing");
    setError(null);
    try {
      const [rulesData, insightsData] = await Promise.all([
        generateRules(true).catch(() => null),
        getProactiveInsights().catch(() => ({ insights: [], count: 0 })),
      ]);
      setRulesResponse(rulesData);
      setInsights(insightsData.insights);
      setPhase("review");
    } catch {
      setError("Analysis failed. You can try again or skip this step.");
      setPhase("intro");
    }
  }

  async function handleApply() {
    if (!selectedRules.length) return;
    setPhase("applying");
    try {
      const res = await applyGeneratedRules(selectedRules);
      setResult(res);
      setPhase("done");
    } catch {
      setError("Failed to create rules. Please try again.");
      setPhase("review");
    }
  }

  function toggleRule(merchant: string) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(merchant)) next.delete(merchant);
      else next.add(merchant);
      return next;
    });
  }

  // ── Completion data ──
  const activeAccounts = data.accounts.filter((a) => a.is_active).length;
  const activePolicies = data.policies.filter((p) => p.is_active).length;

  const items = [
    { label: "About You", done: !!data.household, detail: data.household ? `${data.household.filing_status?.toUpperCase()} · $${(data.household.combined_income || 0).toLocaleString()}` : "Not set up", step: "about-you" as SetupStep },
    { label: "Accounts", done: activeAccounts > 0, detail: `${activeAccounts} accounts`, step: "connect" as SetupStep },
    { label: "Benefits & Coverage", done: !!data.household, detail: `${activePolicies} policies`, step: "benefits-coverage" as SetupStep },
    { label: "Life & Business", done: true, detail: data.entities.length > 0 ? `${data.entities.length} entities` : data.lifeEvents.length > 0 ? `${data.lifeEvents.length} events` : "Optional", step: "life-business" as SetupStep },
  ];

  const nudges: string[] = [];
  if (!data.household) nudges.push("Complete your profile to unlock tax strategy");
  else if (!data.household.spouse_a_income && !data.household.spouse_b_income) nudges.push("Add income details for accurate tax analysis");
  if (activeAccounts === 0) nudges.push("Connect bank accounts for spending insights");
  if (activePolicies === 0 && data.household) nudges.push("Add insurance policies for coverage gap analysis");

  return (
    <div className="space-y-8">
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-green-50 flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 size={36} className="text-accent" />
        </div>
        <h2 className={OB_HEADING}>You&apos;re almost there!</h2>
        <p className={OB_SUBTITLE + " text-center max-w-md mx-auto"}>
          Review your setup and let <SirHenryName /> learn your spending patterns.
        </p>
      </div>

      {/* ── AI Analysis Section ── */}
      {phase === "intro" && hasTransactions && (
        <Card padding="md" className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center flex-shrink-0">
              <Sparkles size={20} className="text-accent" />
            </div>
            <div>
              <p className="text-sm font-semibold text-text-primary">Learn your spending patterns</p>
              <p className="text-xs text-text-secondary mt-0.5">
                <SirHenryName /> will analyze transactions and create categorization rules.
              </p>
            </div>
          </div>
          <button onClick={handleAnalyzeInternal}
            className="w-full bg-text-primary text-white dark:text-black py-3 rounded-xl text-sm font-semibold hover:bg-text-primary/90 transition-colors flex items-center justify-center gap-2">
            <Brain size={16} /> Analyze My Data
          </button>
          {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}
        </Card>
      )}

      {phase === "intro" && !hasTransactions && (
        <Card padding="md" className="text-center py-6">
          <Brain size={28} className="mx-auto text-text-muted mb-2" />
          <p className="text-sm text-text-secondary">No transactions to analyze yet</p>
          <p className="text-xs text-text-muted mt-1">
            Once accounts sync, <SirHenryName /> will learn your patterns automatically.
          </p>
        </Card>
      )}

      {phase === "analyzing" && (
        <Card padding="md">
          <div className="flex flex-col items-center py-8 gap-4">
            <Loader2 className="animate-spin text-accent" size={32} />
            <div className="text-center">
              <p className="font-medium text-text-secondary"><SirHenryName /> is analyzing...</p>
              <p className="text-sm text-text-muted mt-1">Finding patterns and generating rules</p>
            </div>
          </div>
        </Card>
      )}

      {phase === "review" && (
        <div className="space-y-4">
          {rulesResponse && rulesResponse.rules.length > 0 ? (
            <Card padding="none">
              <div className="px-5 py-4 border-b border-card-border">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-text-primary flex items-center gap-2">
                      <Sparkles size={16} className="text-accent" />
                      {selectedRules.length} rules found
                    </h3>
                    <p className="text-sm text-text-muted mt-0.5">
                      Covering {selectedRules.reduce((s, r) => s + r.transaction_count, 0).toLocaleString()} transactions
                    </p>
                  </div>
                  <button onClick={() => setShowDetails(!showDetails)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs text-text-secondary hover:text-text-secondary border border-border rounded-lg hover:bg-surface transition-colors">
                    {showDetails ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    {showDetails ? "Summary" : "Details"}
                  </button>
                </div>
              </div>
              {!showDetails && (
                <div className="px-5 py-4 grid grid-cols-2 md:grid-cols-3 gap-2">
                  {categoryBreakdown.map(([cat, { count, txns }]) => (
                    <div key={cat} className="p-2.5 rounded-lg bg-surface">
                      <p className="text-xs font-medium text-text-secondary truncate">{cat}</p>
                      <p className="text-xs text-text-muted">{count} rules, {txns} txns</p>
                    </div>
                  ))}
                </div>
              )}
              {showDetails && (
                <div className="max-h-[300px] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-surface z-10">
                      <tr className="border-b border-card-border text-left">
                        <th className="px-4 py-2 w-8">
                          <input type="checkbox" checked={excluded.size === 0}
                            onChange={() => {
                              if (excluded.size === 0 && rulesResponse) setExcluded(new Set(rulesResponse.rules.map((r) => r.merchant)));
                              else setExcluded(new Set());
                            }}
                            className="rounded border-border" />
                        </th>
                        <th className="px-3 py-2 text-xs font-medium text-text-secondary uppercase tracking-wider">Merchant</th>
                        <th className="px-3 py-2 text-xs font-medium text-text-secondary uppercase tracking-wider">Category</th>
                        <th className="px-3 py-2 text-xs font-medium text-text-secondary uppercase tracking-wider text-right">Txns</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rulesResponse.rules.map((rule) => {
                        const isExcluded = excluded.has(rule.merchant);
                        return (
                          <tr key={rule.merchant} className={`border-b border-border-light hover:bg-surface/50 ${isExcluded ? "opacity-40" : ""}`}>
                            <td className="px-4 py-2">
                              <input type="checkbox" checked={!isExcluded} onChange={() => toggleRule(rule.merchant)} className="rounded border-border" />
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">{rule.merchant}</td>
                            <td className="px-3 py-2">
                              <span className="inline-block bg-surface text-text-secondary text-xs px-2 py-0.5 rounded-full truncate max-w-[180px]">{rule.category}</span>
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs">{rule.transaction_count}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="px-5 py-3 border-t border-card-border">
                <button onClick={handleApply} disabled={selectedRules.length === 0}
                  className="w-full flex items-center justify-center gap-1.5 bg-accent text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-accent-hover disabled:opacity-50 shadow-sm transition-colors">
                  <Zap size={14} /> Apply {selectedRules.length} Rules
                </button>
              </div>
              {error && <div className="px-5 py-3 text-sm text-red-600 bg-red-50 border-t border-red-100">{error}</div>}
            </Card>
          ) : (
            <Card padding="md" className="text-center">
              <CheckCircle2 size={24} className="mx-auto text-accent mb-2" />
              <p className="text-sm text-text-secondary">No new rules to create</p>
            </Card>
          )}

          {insights.length > 0 && (
            <Card padding="md">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <Lightbulb size={13} /> Initial Insights
              </p>
              <div className="space-y-2">
                {insights.slice(0, 5).map((insight, i) => (
                  <div key={i} className={`p-3 rounded-xl border ${
                    insight.severity === "action" ? "bg-amber-50/50 border-amber-100"
                      : insight.severity === "warning" ? "bg-orange-50/50 border-orange-100"
                      : "bg-surface border-card-border"
                  }`}>
                    <p className="text-sm font-medium text-text-primary">{insight.title}</p>
                    <p className="text-xs text-text-secondary mt-0.5">{insight.message}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {phase === "applying" && (
        <Card padding="md">
          <div className="flex flex-col items-center py-8 gap-4">
            <Loader2 className="animate-spin text-accent" size={32} />
            <p className="font-medium text-text-secondary">Creating rules...</p>
          </div>
        </Card>
      )}

      {phase === "done" && (
        <Card padding="md">
          <div className="flex flex-col items-center py-4 gap-2">
            <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center">
              <CheckCircle2 className="text-accent" size={28} />
            </div>
            <p className="font-semibold text-text-primary"><SirHenryName /> is ready</p>
            {result && (
              <p className="text-sm text-text-secondary">
                Created <span className="font-medium text-text-secondary">{result.rules_created}</span> rules
                and categorized <span className="font-medium text-text-secondary">{result.transactions_categorized}</span> transactions
              </p>
            )}
          </div>
        </Card>
      )}

      {/* ── Setup Summary ── */}
      <Card padding="md">
        <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-3">Setup Summary</p>
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.label} className="py-2 border-b border-border-light last:border-0">
              <div className="flex items-center gap-3">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                  item.done ? "bg-accent" : "bg-border"
                }`}>
                  {item.done && <CheckCircle2 size={14} className="text-white" />}
                </div>
                <div className="flex-1 min-w-0">
                  <span className={`text-sm ${item.done ? "text-text-secondary" : "text-text-muted"}`}>{item.label}</span>
                  <p className="text-xs text-text-muted">{item.detail}</p>
                </div>
                {!item.done && (
                  <button onClick={() => onGoTo(item.step)}
                    className="text-xs text-accent hover:underline flex items-center gap-0.5">
                    Set up <ChevronRight size={12} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Goals created banner */}
      {goalsCreated > 0 && (
        <Card padding="sm" className="bg-green-50/50 border-green-100">
          <div className="flex items-center gap-2">
            <Target size={14} className="text-accent flex-shrink-0" />
            <p className="text-sm text-green-800">
              <span className="font-medium">{goalsCreated} goal{goalsCreated > 1 ? "s" : ""} created</span>
              <span className="text-green-600"> based on your priorities</span>
            </p>
          </div>
        </Card>
      )}

      {/* Nudges */}
      {nudges.length > 0 && (
        <Card padding="sm" className="bg-amber-50/50 border-amber-100">
          <p className="text-xs font-medium text-amber-700 mb-1.5">Tips to get more from <SirHenryName /></p>
          {nudges.map((nudge, i) => (
            <p key={i} className="text-xs text-amber-600/80">&bull; {nudge}</p>
          ))}
        </Card>
      )}

      {/* Ask Henry */}
      <button type="button"
        onClick={() => askHenry("Now that my setup is complete, what should I focus on first?")}
        className="flex items-center justify-center gap-1.5 w-full py-3 rounded-xl border-2 border-accent/20 text-sm text-accent hover:bg-green-50 transition-colors">
        <MessageCircle size={14} />
        Ask <SirHenryName /> what to focus on first
      </button>

      {/* CTA is handled by the wizard's bottom nav bar (handleFinish) */}
    </div>
  );
}
