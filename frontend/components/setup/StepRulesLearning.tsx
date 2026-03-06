"use client";
import { useState, useMemo } from "react";
import {
  Brain, Sparkles, Loader2, CheckCircle2, Zap, ChevronDown, ChevronUp,
  Lightbulb, MessageCircle,
} from "lucide-react";
import Card from "@/components/ui/Card";
import SirHenryName from "@/components/ui/SirHenryName";
import { generateRules, applyGeneratedRules } from "@/lib/api-rules";
import { getProactiveInsights } from "@/lib/api-smart-defaults";
import type { GenerateRulesResponse } from "@/types/rules";
import type { ProactiveInsight } from "@/types/smart-defaults";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

type Phase = "intro" | "analyzing" | "review" | "applying" | "done";

export default function StepRulesLearning({ hasTransactions }: { hasTransactions: boolean }) {
  const [phase, setPhase] = useState<Phase>("intro");
  const [rulesResponse, setRulesResponse] = useState<GenerateRulesResponse | null>(null);
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [showDetails, setShowDetails] = useState(false);
  const [result, setResult] = useState<{ rules_created: number; transactions_categorized: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    return Object.entries(counts)
      .sort((a, b) => b[1].txns - a[1].txns)
      .slice(0, 10);
  }, [selectedRules]);

  async function handleAnalyze() {
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

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 font-display">
          Rules & AI Learning
        </h2>
        <p className="text-sm text-stone-500 mt-0.5">
          <SirHenryName /> analyzes your data to create categorization rules and surface initial insights.
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: Auto-Categorization &middot; Spending Insights &middot; Tax Optimization Tips
        </p>
      </div>

      {/* Intro — prompt to analyze */}
      {phase === "intro" && (
        <>
          {!hasTransactions ? (
            <Card padding="md" className="text-center">
              <Brain size={28} className="mx-auto text-stone-300 mb-2" />
              <p className="text-sm text-stone-600">No transactions to analyze yet</p>
              <p className="text-xs text-stone-400 mt-1">
                Once your accounts sync and transactions flow in, <SirHenryName /> will learn your spending
                patterns and create rules automatically. You can trigger this anytime from the Rules page.
              </p>
            </Card>
          ) : (
            <Card padding="md" className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#16A34A]/10 flex items-center justify-center flex-shrink-0">
                  <Sparkles size={20} className="text-[#16A34A]" />
                </div>
                <div>
                  <p className="text-sm font-medium text-stone-800">
                    Ready to analyze your transactions
                  </p>
                  <p className="text-xs text-stone-500 mt-0.5">
                    <SirHenryName /> will find spending patterns and create categorization rules, then surface
                    initial insights about your financial picture.
                  </p>
                </div>
              </div>
              <button
                onClick={handleAnalyze}
                className="w-full flex items-center justify-center gap-2 bg-[#16A34A] text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm transition-colors"
              >
                <Brain size={16} />
                Analyze My Data
              </button>
              {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
            </Card>
          )}
        </>
      )}

      {/* Analyzing */}
      {phase === "analyzing" && (
        <Card padding="md">
          <div className="flex flex-col items-center py-8 gap-4">
            <Loader2 className="animate-spin text-[#16A34A]" size={32} />
            <div className="text-center">
              <p className="font-medium text-stone-700">
                <SirHenryName /> is analyzing your data...
              </p>
              <p className="text-sm text-stone-400 mt-1">
                Finding patterns, generating rules, and surfacing insights
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Review */}
      {phase === "review" && (
        <div className="space-y-4">
          {/* Rules section */}
          {rulesResponse && rulesResponse.rules.length > 0 ? (
            <Card padding="none">
              <div className="px-5 py-4 border-b border-stone-100">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-stone-800 flex items-center gap-2">
                      <Sparkles size={16} className="text-[#16A34A]" />
                      {selectedRules.length} rules found
                    </h3>
                    <p className="text-sm text-stone-400 mt-0.5">
                      Covering {selectedRules.reduce((s, r) => s + r.transaction_count, 0).toLocaleString()} transactions
                      across {categoryBreakdown.length} categories
                    </p>
                  </div>
                  <button
                    onClick={() => setShowDetails(!showDetails)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs text-stone-500 hover:text-stone-700 border border-stone-200 rounded-md hover:bg-stone-50 transition-colors"
                  >
                    {showDetails ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    {showDetails ? "Summary" : "Details"}
                  </button>
                </div>
                {/* Source breakdown */}
                {rulesResponse.stats && (
                  <div className="flex gap-3 mt-3">
                    {rulesResponse.stats.from_patterns > 0 && (
                      <span className="text-xs text-stone-400">
                        <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1" />
                        {rulesResponse.stats.from_patterns} from patterns
                      </span>
                    )}
                    {rulesResponse.stats.from_ai > 0 && (
                      <span className="text-xs text-stone-400">
                        <span className="inline-block w-2 h-2 rounded-full bg-blue-400 mr-1" />
                        {rulesResponse.stats.from_ai} from AI
                      </span>
                    )}
                  </div>
                )}
              </div>
              {/* Summary view */}
              {!showDetails && (
                <div className="px-5 py-4">
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {categoryBreakdown.map(([cat, { count, txns }]) => (
                      <div key={cat} className="flex items-center gap-2 p-2.5 rounded-lg bg-stone-50">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-stone-700 truncate">{cat}</p>
                          <p className="text-[10px] text-stone-400">{count} rules, {txns} txns</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Detail view */}
              {showDetails && (
                <div className="max-h-[300px] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-stone-50 z-10">
                      <tr className="border-b border-stone-100 text-left">
                        <th className="px-4 py-2 w-8">
                          <input
                            type="checkbox"
                            checked={excluded.size === 0}
                            onChange={() => {
                              if (excluded.size === 0 && rulesResponse) {
                                setExcluded(new Set(rulesResponse.rules.map((r) => r.merchant)));
                              } else {
                                setExcluded(new Set());
                              }
                            }}
                            className="rounded border-stone-300"
                          />
                        </th>
                        <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider">Merchant</th>
                        <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider">Category</th>
                        <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider text-right">Txns</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rulesResponse.rules.map((rule) => {
                        const isExcluded = excluded.has(rule.merchant);
                        return (
                          <tr
                            key={rule.merchant}
                            className={`border-b border-stone-50 hover:bg-stone-50/50 ${isExcluded ? "opacity-40" : ""}`}
                          >
                            <td className="px-4 py-2">
                              <input
                                type="checkbox"
                                checked={!isExcluded}
                                onChange={() => toggleRule(rule.merchant)}
                                className="rounded border-stone-300"
                              />
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">{rule.merchant}</td>
                            <td className="px-3 py-2">
                              <span className="inline-block bg-stone-100 text-stone-700 text-xs px-2 py-0.5 rounded-full truncate max-w-[180px]">
                                {rule.category}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs">{rule.transaction_count}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              {/* Apply button */}
              <div className="px-5 py-3 border-t border-stone-100">
                <button
                  onClick={handleApply}
                  disabled={selectedRules.length === 0}
                  className="w-full flex items-center justify-center gap-1.5 bg-[#16A34A] text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803d] disabled:opacity-50 shadow-sm transition-colors"
                >
                  <Zap size={14} />
                  Apply {selectedRules.length} Rules
                </button>
              </div>
              {error && (
                <div className="px-5 py-3 text-sm text-red-600 bg-red-50 border-t border-red-100">
                  {error}
                </div>
              )}
            </Card>
          ) : (
            <Card padding="md" className="text-center">
              <CheckCircle2 size={24} className="mx-auto text-[#16A34A] mb-2" />
              <p className="text-sm text-stone-600">No new rules to create</p>
              <p className="text-xs text-stone-400 mt-1">
                As more transactions come in, <SirHenryName /> will learn your patterns.
              </p>
            </Card>
          )}

          {/* Insights section */}
          {insights.length > 0 && (
            <Card padding="md">
              <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <Lightbulb size={13} />
                Initial Insights
              </p>
              <div className="space-y-2">
                {insights.slice(0, 5).map((insight, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-lg border ${
                      insight.severity === "action"
                        ? "bg-amber-50/50 border-amber-100"
                        : insight.severity === "warning"
                        ? "bg-orange-50/50 border-orange-100"
                        : "bg-stone-50 border-stone-100"
                    }`}
                  >
                    <p className="text-sm font-medium text-stone-800">{insight.title}</p>
                    <p className="text-xs text-stone-500 mt-0.5">{insight.message}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Applying */}
      {phase === "applying" && (
        <Card padding="md">
          <div className="flex flex-col items-center py-8 gap-4">
            <Loader2 className="animate-spin text-[#16A34A]" size={32} />
            <div className="text-center">
              <p className="font-medium text-stone-700">Creating rules and categorizing transactions...</p>
              <p className="text-sm text-stone-400 mt-1">This may take a moment</p>
            </div>
            <div className="w-64 h-1.5 bg-stone-100 rounded-full overflow-hidden">
              <div className="h-full bg-[#16A34A] rounded-full animate-pulse" style={{ width: "70%" }} />
            </div>
          </div>
        </Card>
      )}

      {/* Done */}
      {phase === "done" && (
        <div className="space-y-4">
          <Card padding="md">
            <div className="flex flex-col items-center py-6 gap-3">
              <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center">
                <CheckCircle2 className="text-[#16A34A]" size={28} />
              </div>
              <div className="text-center">
                <p className="font-semibold text-stone-800"><SirHenryName /> is ready</p>
                {result && (
                  <p className="text-sm text-stone-500 mt-1">
                    Created <span className="font-medium text-stone-700">{result.rules_created}</span> rules
                    and categorized <span className="font-medium text-stone-700">{result.transactions_categorized}</span> transactions
                  </p>
                )}
              </div>
            </div>
          </Card>

          {insights.length > 0 && (
            <Card padding="md">
              <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <Lightbulb size={13} />
                Insights Discovered
              </p>
              <div className="space-y-2">
                {insights.slice(0, 5).map((insight, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-lg border ${
                      insight.severity === "action"
                        ? "bg-amber-50/50 border-amber-100"
                        : insight.severity === "warning"
                        ? "bg-orange-50/50 border-orange-100"
                        : "bg-stone-50 border-stone-100"
                    }`}
                  >
                    <p className="text-sm font-medium text-stone-800">{insight.title}</p>
                    <p className="text-xs text-stone-500 mt-0.5">{insight.message}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <button
            type="button"
            onClick={() => askHenry("Now that my setup is complete, what should I focus on first? What are the most impactful financial optimizations I should look into?")}
            className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg border border-[#16A34A]/20 text-sm text-[#16A34A] hover:bg-green-50 transition-colors"
          >
            <MessageCircle size={14} />
            Ask <SirHenryName /> what to focus on first
          </button>
        </div>
      )}
    </div>
  );
}
