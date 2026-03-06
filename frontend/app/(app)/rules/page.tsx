"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Brain, BookOpen, Link2, Sparkles, Trash2, ToggleLeft, ToggleRight,
  Loader2, RotateCcw, Wand2, CheckCircle2, ChevronDown, ChevronUp,
  Zap, Pencil,
} from "lucide-react";
import Card from "@/components/ui/Card";
import StatCard from "@/components/ui/StatCard";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import EditRuleModal from "@/components/rules/EditRuleModal";
import {
  getRulesSummary,
  getCategoryRulesWithEntities,
  updateCategoryRule,
  deleteCategoryRule,
  applyCategoryRuleRetro,
  getVendorRulesWithEntities,
  getUserContext,
  deleteUserContext,
  generateRules,
  applyGeneratedRules,
} from "@/lib/api-rules";
import type {
  RulesSummary,
  CategoryRuleWithEntity,
  VendorRuleWithEntity,
  UserContextEntry,
  ProposedRule,
  GenerateRulesResponse,
} from "@/types/rules";

// ---------------------------------------------------------------------------
// Tab types
// ---------------------------------------------------------------------------
type Tab = "category" | "vendor" | "context";

const TABS: { key: Tab; label: string; icon: typeof BookOpen }[] = [
  { key: "category", label: "Category Rules", icon: BookOpen },
  { key: "vendor", label: "Vendor Rules", icon: Link2 },
  { key: "context", label: "User Context", icon: Brain },
];

const CONTEXT_CATEGORIES: Record<string, { label: string; color: string }> = {
  business: { label: "Business", color: "bg-blue-50 text-blue-700" },
  tax: { label: "Tax", color: "bg-amber-50 text-amber-700" },
  preference: { label: "Preference", color: "bg-purple-50 text-purple-700" },
  household: { label: "Household", color: "bg-green-50 text-green-700" },
  financial_goal: { label: "Goal", color: "bg-indigo-50 text-indigo-700" },
  investment: { label: "Investment", color: "bg-cyan-50 text-cyan-700" },
  career: { label: "Career", color: "bg-orange-50 text-orange-700" },
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function RulesPage() {
  const [tab, setTab] = useState<Tab>("category");
  const [summary, setSummary] = useState<RulesSummary | null>(null);
  const [categoryRules, setCategoryRules] = useState<CategoryRuleWithEntity[]>([]);
  const [vendorRules, setVendorRules] = useState<VendorRuleWithEntity[]>([]);
  const [contextFacts, setContextFacts] = useState<UserContextEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [editingRule, setEditingRule] = useState<CategoryRuleWithEntity | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, cat, vendor, ctx] = await Promise.all([
        getRulesSummary(),
        getCategoryRulesWithEntities(),
        getVendorRulesWithEntities(),
        getUserContext(),
      ]);
      setSummary(s);
      setCategoryRules(cat.rules);
      setVendorRules(vendor.rules);
      setContextFacts(ctx.facts);
    } catch (e) {
      console.error("Failed to load rules", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // --- Category rule actions ---
  const handleToggleCategoryRule = async (rule: CategoryRuleWithEntity) => {
    try {
      await updateCategoryRule(rule.id, { is_active: !rule.is_active });
      setCategoryRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, is_active: !r.is_active } : r)),
      );
      showToast(rule.is_active ? "Rule deactivated" : "Rule activated");
    } catch {
      showToast("Failed to update rule");
    }
  };

  const handleDeleteCategoryRule = async (ruleId: number) => {
    try {
      await deleteCategoryRule(ruleId);
      setCategoryRules((prev) => prev.filter((r) => r.id !== ruleId));
      setSummary((s) => s ? { ...s, category_rule_count: s.category_rule_count - 1 } : s);
      showToast("Rule deleted");
    } catch {
      showToast("Failed to delete rule");
    }
  };

  const handleApplyRetro = async (rule: CategoryRuleWithEntity) => {
    try {
      const result = await applyCategoryRuleRetro(rule.id);
      showToast(`Applied to ${result.applied} transactions`);
    } catch {
      showToast("Failed to apply rule");
    }
  };

  // --- Edit rule ---
  const handleSaveRule = async (ruleId: number, data: Record<string, unknown>) => {
    try {
      await updateCategoryRule(ruleId, data as Parameters<typeof updateCategoryRule>[1]);
      // Resolve entity name for local state update
      const entityId = data.business_entity_id as number | null;
      const entityName = entityId
        ? categoryRules.find((r) => r.business_entity_id === entityId)?.entity_name ?? null
        : null;
      setCategoryRules((prev) =>
        prev.map((r) => (r.id === ruleId ? { ...r, ...data, entity_name: entityName } : r)),
      );
      setEditingRule(null);
      showToast("Rule updated");
    } catch {
      showToast("Failed to update rule");
    }
  };

  // --- Context actions ---
  const handleDeleteContext = async (id: number) => {
    try {
      await deleteUserContext(id);
      setContextFacts((prev) => prev.filter((f) => f.id !== id));
      setSummary((s) => s ? { ...s, context_count: s.context_count - 1 } : s);
      showToast("Context removed");
    } catch {
      showToast("Failed to delete context");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-stone-300" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rules & Learning"
        subtitle="Everything Sir Henry has learned about your finances"
      />

      {/* Summary stats */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Category Rules"
            value={String(summary.category_rule_count)}
            icon={<BookOpen size={16} />}
            size="sm"
          />
          <StatCard
            label="Vendor Rules"
            value={String(summary.vendor_rule_count)}
            icon={<Link2 size={16} />}
            size="sm"
          />
          <StatCard
            label="Context Facts"
            value={String(summary.context_count)}
            icon={<Brain size={16} />}
            size="sm"
          />
          <StatCard
            label="Rule Coverage"
            value={summary.total_transactions > 0
              ? `${Math.round((summary.total_matches / summary.total_transactions) * 100)}%`
              : "—"}
            sub={`${summary.total_matches.toLocaleString()} of ${summary.total_transactions.toLocaleString()} transactions`}
            icon={<Sparkles size={16} />}
            size="sm"
            accent
          />
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 bg-stone-100 rounded-lg p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              tab === t.key
                ? "bg-white text-stone-900 shadow-sm"
                : "text-stone-500 hover:text-stone-700"
            }`}
          >
            <t.icon size={15} />
            {t.label}
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
              tab === t.key ? "bg-stone-100 text-stone-600" : "bg-stone-200/50 text-stone-400"
            }`}>
              {t.key === "category" ? categoryRules.length :
               t.key === "vendor" ? vendorRules.length :
               contextFacts.length}
            </span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "category" && (
        <CategoryRulesTab
          rules={categoryRules}
          onToggle={handleToggleCategoryRule}
          onDelete={handleDeleteCategoryRule}
          onApplyRetro={handleApplyRetro}
          onEdit={setEditingRule}
          onRulesGenerated={load}
        />
      )}
      {tab === "vendor" && <VendorRulesTab rules={vendorRules} />}
      {tab === "context" && (
        <ContextTab facts={contextFacts} onDelete={handleDeleteContext} />
      )}

      {/* Edit Rule Modal */}
      {editingRule && (
        <EditRuleModal
          rule={editingRule}
          onSave={handleSaveRule}
          onClose={() => setEditingRule(null)}
        />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-stone-900 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg z-50 animate-in fade-in slide-in-from-bottom-2">
          {toast}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generate Rules Wizard
// ---------------------------------------------------------------------------
type WizardStep = "idle" | "analyzing" | "review" | "applying" | "done";

function GenerateRulesWizard({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<WizardStep>("idle");
  const [includeAi, setIncludeAi] = useState(false);
  const [response, setResponse] = useState<GenerateRulesResponse | null>(null);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [showDetails, setShowDetails] = useState(false);
  const [result, setResult] = useState<{ rules_created: number; transactions_categorized: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedRules = useMemo(() => {
    if (!response) return [];
    return response.rules.filter((r) => !excluded.has(r.merchant));
  }, [response, excluded]);

  // Category breakdown for summary view
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

  const handleGenerate = async () => {
    setStep("analyzing");
    setError(null);
    try {
      const data = await generateRules(includeAi);
      setResponse(data);
      setStep("review");
    } catch {
      setError("Failed to analyze transactions. Please try again.");
      setStep("idle");
    }
  };

  const handleApply = async () => {
    if (!selectedRules.length) return;
    setStep("applying");
    try {
      const res = await applyGeneratedRules(selectedRules);
      setResult(res);
      setStep("done");
    } catch {
      setError("Failed to create rules. Please try again.");
      setStep("review");
    }
  };

  const toggleRule = (merchant: string) => {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(merchant)) next.delete(merchant);
      else next.add(merchant);
      return next;
    });
  };

  const handleDone = () => {
    setStep("idle");
    setResponse(null);
    setResult(null);
    onComplete();
  };

  // --- Idle state: CTA ---
  if (step === "idle") {
    return (
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-1.5 text-xs text-stone-500 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={includeAi}
            onChange={(e) => setIncludeAi(e.target.checked)}
            className="rounded border-stone-300 text-[#16A34A] focus:ring-green-500"
          />
          Include AI suggestions
        </label>
        <button
          onClick={handleGenerate}
          className="flex items-center gap-2 px-4 py-2 bg-[#16A34A] text-white text-sm font-medium rounded-lg hover:bg-[#15803D] transition-colors"
        >
          <Wand2 size={15} />
          Generate Rules
        </button>
      </div>
    );
  }

  // --- Analyzing ---
  if (step === "analyzing") {
    return (
      <Card>
        <div className="flex flex-col items-center py-8 gap-4">
          <div className="relative">
            <Loader2 className="animate-spin text-[#16A34A]" size={32} />
          </div>
          <div className="text-center">
            <p className="font-medium text-stone-700">Analyzing your transactions...</p>
            <p className="text-sm text-stone-400 mt-1">
              {includeAi
                ? "Analyzing patterns and using AI for uncategorized merchants"
                : "Finding merchants with consistent categorization patterns"}
            </p>
          </div>
        </div>
      </Card>
    );
  }

  // --- Review ---
  if (step === "review" && response) {
    // No new rules found — show a friendly message
    if (response.rules.length === 0) {
      return (
        <Card>
          <div className="flex flex-col items-center py-8 gap-4">
            <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center">
              <CheckCircle2 className="text-[#16A34A]" size={28} />
            </div>
            <div className="text-center">
              <p className="font-semibold text-stone-800">All caught up</p>
              <p className="text-sm text-stone-500 mt-1">
                All {response.stats.existing_rules_skipped} merchant patterns already have rules.
                Correct individual transactions to teach new patterns.
              </p>
            </div>
            <button
              onClick={() => { setStep("idle"); setResponse(null); }}
              className="px-4 py-2 text-sm text-stone-600 hover:text-stone-800 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </Card>
      );
    }

    const totalTxns = selectedRules.reduce((s, r) => s + r.transaction_count, 0);

    return (
      <Card padding="none">
        {/* Header */}
        <div className="px-5 py-4 border-b border-stone-100">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-stone-800 flex items-center gap-2">
                <Sparkles size={16} className="text-[#16A34A]" />
                {selectedRules.length} rules found
              </h3>
              <p className="text-sm text-stone-400 mt-0.5">
                Covering {totalTxns.toLocaleString()} transactions across {categoryBreakdown.length} categories
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-stone-500 hover:text-stone-700 border border-stone-200 rounded-md hover:bg-stone-50 transition-colors"
              >
                {showDetails ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                {showDetails ? "Summary" : "Review Details"}
              </button>
              <button
                onClick={handleApply}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-[#16A34A] text-white text-sm font-medium rounded-md hover:bg-[#15803D] transition-colors"
              >
                <Zap size={14} />
                Create {selectedRules.length} Rules
              </button>
            </div>
          </div>

          {/* Source breakdown */}
          <div className="flex gap-3 mt-3">
            {response.stats.from_patterns > 0 && (
              <span className="text-xs text-stone-400">
                <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1" />
                {response.stats.from_patterns} from patterns
              </span>
            )}
            {response.stats.from_ai > 0 && (
              <span className="text-xs text-stone-400">
                <span className="inline-block w-2 h-2 rounded-full bg-blue-400 mr-1" />
                {response.stats.from_ai} from AI
              </span>
            )}
            {response.stats.existing_rules_skipped > 0 && (
              <span className="text-xs text-stone-400">
                {response.stats.existing_rules_skipped} existing rules kept
              </span>
            )}
          </div>
        </div>

        {/* Summary view: category breakdown */}
        {!showDetails && (
          <div className="px-5 py-4">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
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

        {/* Detail view: full table */}
        {showDetails && (
          <div className="max-h-[500px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-stone-50 z-10">
                <tr className="border-b border-stone-100 text-left">
                  <th className="px-4 py-2 w-8">
                    <input
                      type="checkbox"
                      checked={excluded.size === 0}
                      onChange={() => {
                        if (excluded.size === 0) {
                          setExcluded(new Set(response.rules.map((r) => r.merchant)));
                        } else {
                          setExcluded(new Set());
                        }
                      }}
                      className="rounded border-stone-300"
                    />
                  </th>
                  <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider">Merchant</th>
                  <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider">Category</th>
                  <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider">Segment</th>
                  <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider">Entity</th>
                  <th className="px-3 py-2 text-xs font-medium text-stone-500 uppercase tracking-wider text-right">Txns</th>
                </tr>
              </thead>
              <tbody>
                {response.rules.map((rule) => {
                  const isExcluded = excluded.has(rule.merchant);
                  return (
                    <tr
                      key={rule.merchant}
                      className={`border-b border-stone-50 hover:bg-stone-50/50 transition-colors ${
                        isExcluded ? "opacity-40" : ""
                      }`}
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
                        {rule.category && (
                          <span className="inline-block bg-stone-100 text-stone-700 text-xs px-2 py-0.5 rounded-full truncate max-w-[180px]">
                            {rule.category}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {rule.segment && (
                          <span className={`inline-block text-xs px-2 py-0.5 rounded-full ${
                            rule.segment === "business" ? "bg-blue-50 text-blue-700" :
                            rule.segment === "personal" ? "bg-green-50 text-green-700" :
                            "bg-stone-100 text-stone-700"
                          }`}>
                            {rule.segment}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-stone-500 truncate max-w-[120px]">
                        {rule.entity_name || "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">{rule.transaction_count}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {error && (
          <div className="px-5 py-3 text-sm text-red-600 bg-red-50 border-t border-red-100">
            {error}
          </div>
        )}
      </Card>
    );
  }

  // --- Applying ---
  if (step === "applying") {
    return (
      <Card>
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
    );
  }

  // --- Done ---
  if (step === "done" && result) {
    return (
      <Card>
        <div className="flex flex-col items-center py-8 gap-4">
          <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center">
            <CheckCircle2 className="text-[#16A34A]" size={28} />
          </div>
          <div className="text-center">
            <p className="font-semibold text-stone-800">Rules created successfully</p>
            <p className="text-sm text-stone-500 mt-1">
              Created <span className="font-medium text-stone-700">{result.rules_created}</span> rules and categorized{" "}
              <span className="font-medium text-stone-700">{result.transactions_categorized}</span> transactions
            </p>
            {result.rules_created === 0 && (
              <p className="text-xs text-stone-400 mt-2">
                All patterns already have rules. Try correcting individual transactions to teach new patterns.
              </p>
            )}
          </div>
          <button
            onClick={handleDone}
            className="px-4 py-2 bg-stone-900 text-white text-sm font-medium rounded-lg hover:bg-stone-800 transition-colors"
          >
            Done
          </button>
        </div>
      </Card>
    );
  }

  return null;
}

// ---------------------------------------------------------------------------
// Category Rules Tab
// ---------------------------------------------------------------------------
function CategoryRulesTab({
  rules,
  onToggle,
  onDelete,
  onApplyRetro,
  onEdit,
  onRulesGenerated,
}: {
  rules: CategoryRuleWithEntity[];
  onToggle: (r: CategoryRuleWithEntity) => void;
  onDelete: (id: number) => void;
  onApplyRetro: (r: CategoryRuleWithEntity) => void;
  onEdit: (r: CategoryRuleWithEntity) => void;
  onRulesGenerated: () => void;
}) {
  if (rules.length === 0) {
    return (
      <div className="space-y-6">
        {/* Empty state with generate CTA */}
        <div className="bg-white rounded-xl border border-dashed border-stone-200 p-12 text-center">
          <div className="text-stone-200 mb-4 flex justify-center">
            <Wand2 size={48} />
          </div>
          <h3 className="font-semibold text-stone-700 mb-2">No category rules yet</h3>
          <p className="text-stone-400 text-sm mb-6 max-w-md mx-auto">
            Generate rules automatically from your transaction history. Sir Henry will analyze your spending patterns and create rules to categorize future transactions instantly.
          </p>
          <GenerateRulesWizard onComplete={onRulesGenerated} />
        </div>
      </div>
    );
  }

  const active = rules.filter((r) => r.is_active);
  const inactive = rules.filter((r) => !r.is_active);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-stone-400">
          Rules are learned when you correct a transaction category. They are applied automatically before AI categorization.
        </p>
        <GenerateRulesWizard onComplete={onRulesGenerated} />
      </div>
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stone-100 text-left">
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Merchant Pattern</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Category</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Segment</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Entity</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider text-right">Matches</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {[...active, ...inactive].map((rule) => (
                <tr
                  key={rule.id}
                  onClick={() => onEdit(rule)}
                  className={`border-b border-stone-50 hover:bg-stone-50/50 transition-colors cursor-pointer ${
                    !rule.is_active ? "opacity-50" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs">{rule.merchant_pattern}</span>
                    {(rule.effective_from || rule.effective_to) && (
                      <span className="block text-[10px] text-stone-400 mt-0.5">
                        {rule.effective_from || "..."} — {rule.effective_to || "ongoing"}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {rule.category && (
                      <span className="inline-block bg-stone-100 text-stone-700 text-xs px-2 py-0.5 rounded-full">
                        {rule.category}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {rule.segment && (
                      <span className={`inline-block text-xs px-2 py-0.5 rounded-full ${
                        rule.segment === "business" ? "bg-blue-50 text-blue-700" :
                        rule.segment === "personal" ? "bg-green-50 text-green-700" :
                        "bg-stone-100 text-stone-700"
                      }`}>
                        {rule.segment}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-stone-600">{rule.entity_name || "—"}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs">{rule.match_count}</td>
                  <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => onEdit(rule)}
                        className="p-1.5 rounded-md hover:bg-stone-100 text-stone-400 hover:text-stone-600 transition-colors"
                        title="Edit rule"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => onApplyRetro(rule)}
                        className="p-1.5 rounded-md hover:bg-stone-100 text-stone-400 hover:text-stone-600 transition-colors"
                        title="Apply retroactively"
                      >
                        <RotateCcw size={14} />
                      </button>
                      <button
                        onClick={() => onToggle(rule)}
                        className="p-1.5 rounded-md hover:bg-stone-100 text-stone-400 hover:text-stone-600 transition-colors"
                        title={rule.is_active ? "Deactivate" : "Activate"}
                      >
                        {rule.is_active ? <ToggleRight size={14} className="text-green-600" /> : <ToggleLeft size={14} />}
                      </button>
                      <button
                        onClick={() => onDelete(rule.id)}
                        className="p-1.5 rounded-md hover:bg-red-50 text-stone-400 hover:text-red-600 transition-colors"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vendor Rules Tab
// ---------------------------------------------------------------------------
function VendorRulesTab({ rules }: { rules: VendorRuleWithEntity[] }) {
  if (rules.length === 0) {
    return (
      <EmptyState
        icon={<Link2 size={48} />}
        title="No vendor rules yet"
        description="Vendor rules map specific merchants to business entities. Create them on the Business page to auto-assign transactions."
      />
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-stone-400">
        Vendor rules assign transactions from specific merchants to business entities. Manage them on the Business page.
      </p>
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stone-100 text-left">
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Vendor Pattern</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Entity</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Segment</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider">Date Range</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider text-right">Priority</th>
                <th className="px-4 py-3 text-xs font-medium text-stone-500 uppercase tracking-wider text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr
                  key={rule.id}
                  className={`border-b border-stone-50 hover:bg-stone-50/50 transition-colors ${
                    !rule.is_active ? "opacity-50" : ""
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-xs">{rule.vendor_pattern}</td>
                  <td className="px-4 py-3 text-xs text-stone-700 font-medium">{rule.entity_name || "Unknown"}</td>
                  <td className="px-4 py-3">
                    {rule.segment_override ? (
                      <span className="inline-block bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full">
                        {rule.segment_override}
                      </span>
                    ) : (
                      <span className="text-stone-300 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-stone-500">
                    {rule.effective_from || rule.effective_to ? (
                      <span>{rule.effective_from || "..."} — {rule.effective_to || "ongoing"}</span>
                    ) : (
                      <span className="text-stone-300">Always</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs">{rule.priority}</td>
                  <td className="px-4 py-3 text-right">
                    <span className={`inline-block text-xs px-2 py-0.5 rounded-full ${
                      rule.is_active ? "bg-green-50 text-green-700" : "bg-stone-100 text-stone-500"
                    }`}>
                      {rule.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// User Context Tab
// ---------------------------------------------------------------------------
function ContextTab({
  facts,
  onDelete,
}: {
  facts: UserContextEntry[];
  onDelete: (id: number) => void;
}) {
  if (facts.length === 0) {
    return (
      <EmptyState
        icon={<Brain size={48} />}
        title="No context learned yet"
        description="As you chat with Sir Henry about your financial situation, preferences, and goals, he'll remember important details here."
        askHenryPrompt="Tell me about my financial situation and goals"
      />
    );
  }

  // Group by category
  const grouped = facts.reduce<Record<string, UserContextEntry[]>>((acc, f) => {
    const cat = f.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(f);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <p className="text-xs text-stone-400">
        Facts Sir Henry has learned through conversations. These are included in his context to personalize advice.
      </p>
      <div className="grid gap-4">
        {Object.entries(grouped).map(([category, items]) => {
          const config = CONTEXT_CATEGORIES[category] || { label: category, color: "bg-stone-50 text-stone-700" };
          return (
            <Card key={category} padding="sm">
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${config.color}`}>
                  {config.label}
                </span>
                <span className="text-xs text-stone-400">{items.length} {items.length === 1 ? "fact" : "facts"}</span>
              </div>
              <div className="space-y-2">
                {items.map((fact) => (
                  <div
                    key={fact.id}
                    className="flex items-start justify-between gap-3 p-3 rounded-lg bg-stone-50/80 group"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-stone-700">{fact.value}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] text-stone-400 font-mono">{fact.key}</span>
                        <span className="text-[10px] text-stone-300">via {fact.source}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => onDelete(fact.id)}
                      className="p-1 rounded hover:bg-red-50 text-stone-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
                      title="Remove"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
