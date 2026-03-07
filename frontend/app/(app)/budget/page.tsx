"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Plus, Loader2, Target, AlertCircle, Copy, ChevronDown, ChevronRight,
  Check, X, Eye, EyeOff, ChevronLeft,
  DollarSign, Bot, Sparkles,
} from "lucide-react";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import TabBar from "@/components/ui/TabBar";
import { useTabState } from "@/hooks/useTabState";
import { BUDGET_TABS } from "@/components/budget/constants";
import { formatCurrency, monthName } from "@/lib/utils";
import {
  getBudgets, getBudgetSummary, createBudget, updateBudget,
  deleteBudget, getBudgetCategories, getUnbudgetedCategories,
  copyBudgetMonth, getBudgetForecast, getSpendVelocity,
  generateSmartBudget, applySmartBudget,
} from "@/lib/api";
import type { BudgetCategoryMeta } from "@/lib/api-budget";
import type { BudgetItem, BudgetSummary, UnbudgetedCategory, BudgetForecastResponse, SpendVelocity, SmartBudgetLine } from "@/types/api";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import { useInsights } from "@/hooks/useInsights";
import { BudgetGroupedSection, BudgetCategoryRow, BudgetForecastPanel } from "@/components/budget";

const now = new Date();

// ── Category classification ──────────────────────────────────────────────────

const FALLBACK_INCOME_CATEGORIES = new Set([
  "Other Income", "Dividend Income", "Interest Income", "Capital Gain",
  "Board / Director Income", "W-2 Wages",
]);

const FALLBACK_GOAL_CATEGORIES = new Set([
  "Emergency Fund", "Vacation Fund",
]);

type BudgetSection = "income" | "expense" | "goal";

function makeClassifier(meta: BudgetCategoryMeta[]): (cat: string) => BudgetSection {
  const typeMap = new Map<string, BudgetSection>(meta.map((m) => [m.category, m.category_type]));
  return (category: string): BudgetSection => {
    if (typeMap.has(category)) return typeMap.get(category)!;
    if (FALLBACK_INCOME_CATEGORIES.has(category)) return "income";
    if (FALLBACK_GOAL_CATEGORIES.has(category)) return "goal";
    return "expense";
  };
}

// ── Expense sub-groups ───────────────────────────────────────────────────────

const DEFAULT_EXPENSE_GROUPS: Record<string, string[]> = {
  "Food & Dining": ["Groceries", "Restaurants & Bars", "Fast Food", "Coffee Shops"],
  "Home & Home Services": [
    "Mortgage", "HOA Dues", "Home Security", "House Cleaners",
    "Home Improvement", "Lawn Care", "Pest Control", "Water",
  ],
  "Bills & Utilities": ["Internet", "Phone", "Electric", "Gas Utility"],
  "Gifts & Donations": ["Charity", "Birthday Gifts", "Christmas Gifts", "Tithe"],
  "Family & Children": ["Kid's Clothing", "Child Activities", "Babysitting", "Pets", "Pet Insurance"],
  "Shopping": ["Amazon", "Shopping", "Postage & Shipping"],
  "Health & Wellness": ["Dentist", "Fitness", "Medical"],
  "Discretionary": ["Discretionary"],
  "Travel & Lifestyle": ["TV, Streaming & Entertainment", "Vacation", "Haircut"],
  "Education": ["Education", "Education - Other"],
  "Auto & Transport": ["Gas", "Parking & Tolls", "Auto Maintenance", "Vehicle Purchase"],
  "Financial": ["Financial Fees", "Financial & Legal Services", "Insurance", "Taxes", "Personal Property Tax"],
  "Business": ["Business Technology"],
};

function getExpenseGroup(category: string): string {
  for (const [group, cats] of Object.entries(DEFAULT_EXPENSE_GROUPS)) {
    if (cats.includes(category)) return group;
  }
  if (category.includes("Discretionary")) return "Discretionary";
  return "Other";
}

const GROUP_ICONS: Record<string, string> = {
  "Food & Dining": "🍽️", "Bills & Utilities": "💡", "Shopping": "🛍️",
  "Health & Wellness": "💊", "Home & Home Services": "🏠", "Travel & Lifestyle": "✈️",
  "Family & Children": "👨‍👩‍👧‍👦", "Education": "🎓", "Auto & Transport": "🚗",
  "Financial": "🏦", "Discretionary": "💳", "Gifts & Donations": "❤️",
  "Business": "💼", "Other": "📦",
};

interface GroupedBudgets {
  group: string;
  items: BudgetItem[];
  totalBudget: number;
  totalActual: number;
  totalVariance: number;
}

function groupExpenses(expenses: BudgetItem[]): GroupedBudgets[] {
  const map = new Map<string, BudgetItem[]>();
  for (const b of expenses) {
    const g = getExpenseGroup(b.category);
    const list = map.get(g) ?? [];
    list.push(b);
    map.set(g, list);
  }
  const groups: GroupedBudgets[] = [];
  for (const [group, items] of map) {
    groups.push({
      group, items,
      totalBudget: items.reduce((s, b) => s + b.budget_amount, 0),
      totalActual: items.reduce((s, b) => s + b.actual_amount, 0),
      totalVariance: items.reduce((s, b) => s + b.variance, 0),
    });
  }
  const groupOrder = [...Object.keys(DEFAULT_EXPENSE_GROUPS), "Other"];
  groups.sort((a, b) => groupOrder.indexOf(a.group) - groupOrder.indexOf(b.group));
  return groups;
}

function prevMonth(year: number, month: number) {
  return month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

function varianceColor(variance: number, section: BudgetSection): string {
  if (section === "expense") return variance >= 0 ? "text-green-600" : "text-red-600";
  return variance <= 0 ? "text-green-600" : "text-text-secondary";
}

// ── Main component ───────────────────────────────────────────────────────────

export default function BudgetPage() {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [activeView, setActiveView] = useTabState(BUDGET_TABS, "budget");
  const [confirmDelete, setConfirmDelete] = useState<{ open: boolean; budgetId: number | null }>({ open: false, budgetId: null });
  const [budgets, setBudgets] = useState<BudgetItem[]>([]);
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [unbudgeted, setUnbudgeted] = useState<UnbudgetedCategory[]>([]);
  const [categories, setCategories] = useState<BudgetCategoryMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forecastData, setForecastData] = useState<BudgetForecastResponse | null>(null);
  const [velocity, setVelocity] = useState<SpendVelocity[]>([]);
  const [forecastLoading, setForecastLoading] = useState(false);

  const insights = useInsights(year);

  const [showUnbudgeted, setShowUnbudgeted] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [showAddForm, setShowAddForm] = useState(false);

  const [addCategory, setAddCategory] = useState("");
  const [customCategory, setCustomCategory] = useState("");
  const [addAmount, setAddAmount] = useState("");
  const [saving, setSaving] = useState(false);

  const [copying, setCopying] = useState(false);
  const [segmentFilter, setSegmentFilter] = useState<"all" | "personal" | "business">("all");
  const [suggestingBudget, setSuggestingBudget] = useState(false);
  const [smartLines, setSmartLines] = useState<SmartBudgetLine[]>([]);
  const [smartPreview, setSmartPreview] = useState(false);
  const [generatingSmart, setGeneratingSmart] = useState(false);
  const [applyingSmart, setApplyingSmart] = useState(false);

  // ── Data fetching ────────────────────────────────────────────────────────

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [b, s, u, c] = await Promise.all([
        getBudgets(year, month),
        getBudgetSummary(year, month),
        getUnbudgetedCategories(year, month),
        getBudgetCategories(),
      ]);
      if (signal?.aborted) return;
      setBudgets(b);
      setSummary(s);
      setUnbudgeted(u);
      setCategories(c);
    } catch (e: unknown) {
      if (signal?.aborted) return;
      setError(e instanceof Error ? e.message : String(e));
    }
    if (!signal?.aborted) setLoading(false);
  }, [year, month]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const loadForecast = useCallback(async () => {
    setForecastLoading(true);
    setError(null);
    try {
      const [f, v] = await Promise.all([
        getBudgetForecast(year, month),
        getSpendVelocity(year, month),
      ]);
      setForecastData(f);
      setVelocity(v);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setForecastLoading(false);
  }, [year, month]);

  useEffect(() => {
    if (activeView === "forecast") loadForecast();
  }, [activeView, loadForecast]);

  // ── Event handlers ───────────────────────────────────────────────────────

  const effectiveCategory = customCategory.trim() || addCategory;

  async function handleAdd() {
    if (!effectiveCategory || !addAmount) return;
    setSaving(true);
    try {
      await createBudget({ year, month, category: effectiveCategory, segment: "personal", budget_amount: parseFloat(addAmount) });
      setAddCategory(""); setCustomCategory(""); setAddAmount(""); setShowAddForm(false);
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setSaving(false);
  }

  async function handleDelete(id: number) {
    setConfirmDelete({ open: true, budgetId: id });
  }

  async function confirmDeleteBudget() {
    if (confirmDelete.budgetId == null) return;
    await deleteBudget(confirmDelete.budgetId);
    setConfirmDelete({ open: false, budgetId: null });
    await load();
  }

  async function handleInlineEdit(id: number, newAmount: number) {
    try { await updateBudget(id, { budget_amount: newAmount }); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function handleCopyPrevious() {
    const prev = prevMonth(year, month);
    setCopying(true);
    try {
      const result = await copyBudgetMonth(prev.year, prev.month, year, month);
      if (result.copied === 0) setError(`No new budget lines to copy from ${monthName(prev.month)} ${prev.year}.`);
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setCopying(false);
  }

  async function handleQuickBudget(category: string, suggestedAmount: number) {
    setSaving(true);
    try {
      await createBudget({ year, month, category, segment: "personal", budget_amount: Math.round(suggestedAmount / 10) * 10 });
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setSaving(false);
  }

  async function handleSuggestBudget() {
    setSuggestingBudget(true);
    try {
      // Use unbudgeted categories to auto-create budget lines from historical spending
      const promises = unbudgeted.map((u) =>
        createBudget({
          year, month,
          category: u.category,
          segment: "personal",
          budget_amount: Math.round(u.actual_amount / 10) * 10 || 50,
        }).catch(() => {}) // Skip duplicates
      );
      await Promise.all(promises);
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setSuggestingBudget(false);
  }

  async function handleGenerateSmartBudget() {
    setGeneratingSmart(true);
    try {
      const result = await generateSmartBudget(year, month);
      setSmartLines(result.lines);
      setSmartPreview(true);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setGeneratingSmart(false);
  }

  async function handleApplySmartBudget() {
    setApplyingSmart(true);
    try {
      await applySmartBudget(year, month);
      setSmartPreview(false);
      setSmartLines([]);
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setApplyingSmart(false);
  }

  function toggleGroup(group: string) {
    setCollapsedGroups((prev) => { const next = new Set(prev); if (next.has(group)) next.delete(group); else next.add(group); return next; });
  }

  // ── Derived data ─────────────────────────────────────────────────────────

  const classifyCategory = makeClassifier(categories);
  const filteredBudgets = segmentFilter === "all" ? budgets : budgets.filter(b => b.segment === segmentFilter);
  const incomeItems = filteredBudgets.filter(b => classifyCategory(b.category) === "income");
  const expenseItems = filteredBudgets.filter(b => classifyCategory(b.category) === "expense");
  const goalItems = filteredBudgets.filter(b => classifyCategory(b.category) === "goal");
  const expenseGroups = groupExpenses(expenseItems);

  const totalIncomeBudget = incomeItems.reduce((s, b) => s + b.budget_amount, 0);
  const totalIncomeActual = incomeItems.reduce((s, b) => s + b.actual_amount, 0);
  const totalExpenseBudget = expenseItems.reduce((s, b) => s + b.budget_amount, 0);
  const totalExpenseActual = expenseItems.reduce((s, b) => s + b.actual_amount, 0);
  const totalGoalBudget = goalItems.reduce((s, b) => s + b.budget_amount, 0);
  const totalGoalActual = goalItems.reduce((s, b) => s + b.actual_amount, 0);
  const unallocated = totalIncomeBudget - totalExpenseBudget - totalGoalBudget;

  const prev = prevMonth(year, month);
  const isBalanced = Math.abs(unallocated) < 1;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">{monthName(month)} {year}</h1>
          <TabBar tabs={BUDGET_TABS} activeTab={activeView} onChange={setActiveView} variant="pill" />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => { if (month === 1) { setYear(year - 1); setMonth(12); } else setMonth(month - 1); }} aria-label="Previous month" className="p-2 hover:bg-surface rounded-lg border border-border"><ChevronLeft size={14} className="text-text-secondary" /></button>
          <button onClick={() => { if (month === 12) { setYear(year + 1); setMonth(1); } else setMonth(month + 1); }} aria-label="Next month" className="p-2 hover:bg-surface rounded-lg border border-border"><ChevronRight size={14} className="text-text-secondary" /></button>
          <button onClick={() => { setYear(now.getFullYear()); setMonth(now.getMonth() + 1); }} className="p-2 hover:bg-surface rounded-lg border border-border text-text-secondary text-xs font-medium px-3">Today</button>
          <button onClick={() => setShowAddForm(!showAddForm)} className="flex items-center gap-1.5 text-xs bg-accent text-white rounded-lg px-3 py-2 hover:bg-accent-hover shadow-sm"><Plus size={12} /> Add Line</button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-start gap-3 border border-red-100">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <p className="text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} aria-label="Dismiss error" className="text-red-400 hover:text-red-600"><X size={14} /></button>
        </div>
      )}

      {activeView === "budget" && (
      <>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 space-y-6">
          {/* Toolbar */}
          <div className="flex items-center gap-3 flex-wrap">
            <button onClick={handleCopyPrevious} disabled={copying} className="flex items-center gap-1.5 text-xs border border-border rounded-lg px-3 py-2 text-text-secondary hover:bg-surface disabled:opacity-50">
              {copying ? <Loader2 size={12} className="animate-spin" /> : <Copy size={12} />}
              Copy from {monthName(prev.month)}
            </button>
            {unbudgeted.length > 0 && (
              <button onClick={handleSuggestBudget} disabled={suggestingBudget} className="flex items-center gap-1.5 text-xs bg-violet-600 text-white rounded-lg px-3 py-2 hover:bg-violet-700 disabled:opacity-50 shadow-sm">
                {suggestingBudget ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                Auto-budget {unbudgeted.length} categories
              </button>
            )}
            <div className="flex bg-surface rounded-lg p-0.5 ml-auto">
              {(["all", "personal", "business"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setSegmentFilter(s)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${segmentFilter === s ? "bg-card text-text-primary shadow-sm" : "text-text-secondary hover:text-text-secondary"}`}
                >
                  {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Add form */}
          {showAddForm && (
            <Card padding="md">
              <div className="flex gap-2 flex-wrap items-end">
                <div className="flex-1 min-w-48">
                  <label className="block text-xs text-text-secondary mb-1">Category</label>
                  <select value={addCategory} onChange={(e) => { setAddCategory(e.target.value); setCustomCategory(""); }} className="w-full text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-card">
                    <option value="">Select category...</option>
                    {categories.length > 0 && (<optgroup label="From Your Transactions">{categories.map((m) => <option key={m.category} value={m.category}>{m.category}</option>)}</optgroup>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-text-secondary mb-1">Or custom</label>
                  <input type="text" value={customCategory} onChange={(e) => { setCustomCategory(e.target.value); setAddCategory(""); }} placeholder="Type custom..." className="w-36 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                </div>
                <div>
                  <label className="block text-xs text-text-secondary mb-1">Amount</label>
                  <input type="number" value={addAmount} onChange={(e) => setAddAmount(e.target.value)} placeholder="$0" min="0" step="10" className="w-24 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                </div>
                <button onClick={handleAdd} disabled={saving || !effectiveCategory || !addAmount} className="flex items-center gap-1 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60">
                  {saving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />} Add
                </button>
                <button onClick={() => setShowAddForm(false)} className="text-xs text-text-muted hover:text-text-secondary px-2 py-2">Cancel</button>
              </div>
            </Card>
          )}

          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="animate-spin text-text-muted" size={24} /></div>
          ) : budgets.length === 0 ? (
            <Card padding="lg" className="text-center">
              <Target className="mx-auto text-text-muted mb-3" size={36} />
              <p className="text-text-muted text-sm">No budget set for {monthName(month)} {year}.</p>
              <p className="text-text-muted text-xs mt-1 mb-4">Add budget lines above or copy from {monthName(prev.month)}.</p>
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={handleGenerateSmartBudget}
                  disabled={generatingSmart}
                  className="flex items-center gap-2 bg-accent text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50 shadow-sm"
                >
                  {generatingSmart ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  Generate Smart Budget
                </button>
                <button
                  onClick={handleCopyPrevious}
                  disabled={copying}
                  className="flex items-center gap-1.5 text-sm border border-border rounded-lg px-4 py-2.5 text-text-secondary hover:bg-surface disabled:opacity-50"
                >
                  {copying ? <Loader2 size={14} className="animate-spin" /> : <Copy size={14} />}
                  Copy from {monthName(prev.month)}
                </button>
              </div>
            </Card>
          ) : (
          <div className="space-y-6">
            {/* INCOME SECTION */}
            {incomeItems.length > 0 && (
            <div>
              <div className="flex items-center px-4 py-2 mb-1">
                <span className="flex-1 text-xs font-semibold text-green-700 uppercase tracking-wider">Income</span>
                <span className="w-24 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Budget</span>
                <span className="w-24 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Actual</span>
                <span className="w-28 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Remaining</span>
                <span className="w-12" />
              </div>
              <Card padding="none">
                <button onClick={() => toggleGroup("__income")} className="w-full flex items-center justify-between px-4 py-3 hover:bg-green-50/30">
                  <div className="flex items-center gap-2">
                    {collapsedGroups.has("__income") ? <ChevronRight size={14} className="text-green-500" /> : <ChevronDown size={14} className="text-green-500" />}
                    <span className="text-sm mr-1">💰</span>
                    <span className="text-sm font-semibold text-green-800">Income</span>
                  </div>
                  <div className="flex items-center text-xs tabular-nums">
                    <span className="w-24 text-right text-green-700 font-medium">{formatCurrency(totalIncomeBudget)}</span>
                    <span className="w-24 text-right text-green-600">{formatCurrency(totalIncomeActual)}</span>
                    <span className="w-28 text-right font-semibold text-green-600">{formatCurrency(totalIncomeBudget - totalIncomeActual)}</span>
                    <span className="w-12" />
                  </div>
                </button>
                {!collapsedGroups.has("__income") && (
                  <div className="border-t border-green-100 divide-y divide-green-50">
                    {incomeItems.map(b => <BudgetCategoryRow key={b.id} item={b} section="income" onEdit={handleInlineEdit} onDelete={handleDelete} />)}
                  </div>
                )}
                <div className="flex items-center px-4 py-3 border-t-2 border-green-200 bg-green-50/30">
                  <span className="flex-1 text-sm font-bold text-green-800">Total Income</span>
                  <span className="w-24 text-right text-sm font-bold tabular-nums text-text-primary">{formatCurrency(totalIncomeBudget)}</span>
                  <span className="w-24 text-right text-sm font-bold tabular-nums text-text-secondary">{formatCurrency(totalIncomeActual)}</span>
                  <span className={`w-28 text-right text-sm font-bold tabular-nums ${varianceColor(totalIncomeBudget - totalIncomeActual, "income")}`}>{formatCurrency(totalIncomeBudget - totalIncomeActual)}</span>
                  <span className="w-12" />
                </div>
              </Card>
            </div>
            )}

            {/* EXPENSES SECTION */}
            {expenseItems.length > 0 && (
              <BudgetGroupedSection
                groups={expenseGroups}
                groupIcons={GROUP_ICONS}
                collapsedGroups={collapsedGroups}
                onToggleGroup={toggleGroup}
                onEditItem={handleInlineEdit}
                onDeleteItem={handleDelete}
              />
            )}

            {/* Unbudgeted categories */}
            {unbudgeted.length > 0 && (
              <Card padding="none">
                <button onClick={() => setShowUnbudgeted(!showUnbudgeted)} className="w-full flex items-center justify-between px-4 py-3 bg-amber-50/50 hover:bg-amber-50">
                  <div className="flex items-center gap-2">
                    {showUnbudgeted ? <EyeOff size={14} className="text-amber-500" /> : <Eye size={14} className="text-amber-500" />}
                    <span className="text-sm font-medium text-amber-700">{unbudgeted.length} unbudgeted {unbudgeted.length === 1 ? "category" : "categories"}</span>
                  </div>
                  <span className="text-xs text-amber-600 tabular-nums font-medium">{formatCurrency(unbudgeted.reduce((s, u) => s + u.actual_amount, 0))} spent</span>
                </button>
                {showUnbudgeted && (
                  <div className="divide-y divide-border-light">
                    {unbudgeted.map((u) => (
                      <div key={u.category} className="flex items-center px-4 py-2.5 hover:bg-surface/50">
                        <div className="flex-1 pl-7"><p className="text-sm text-text-secondary">{u.category}</p></div>
                        <span className="text-sm tabular-nums text-text-secondary mr-4">{formatCurrency(u.actual_amount)}</span>
                        <button onClick={() => handleQuickBudget(u.category, u.actual_amount)} disabled={saving} className="text-xs text-accent hover:underline font-medium">+ Budget</button>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}

            {/* GOALS SECTION */}
            {goalItems.length > 0 && (
            <div>
              <div className="flex items-center px-4 py-2 mb-1">
                <span className="flex-1 text-xs font-semibold text-blue-700 uppercase tracking-wider">Contributions</span>
                <span className="w-24 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Budget</span>
                <span className="w-24 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Actual</span>
                <span className="w-28 text-right text-xs font-semibold text-text-muted uppercase tracking-wider">Remaining</span>
                <span className="w-12" />
              </div>
              <Card padding="none">
                <button onClick={() => toggleGroup("__goals")} className="w-full flex items-center justify-between px-4 py-3 hover:bg-blue-50/30">
                  <div className="flex items-center gap-2">
                    {collapsedGroups.has("__goals") ? <ChevronRight size={14} className="text-blue-500" /> : <ChevronDown size={14} className="text-blue-500" />}
                    <span className="text-sm mr-1">🎯</span>
                    <span className="text-sm font-semibold text-blue-800">Goals</span>
                  </div>
                  <div className="flex items-center text-xs tabular-nums">
                    <span className="w-24 text-right text-blue-700 font-medium">{formatCurrency(totalGoalBudget)}</span>
                    <span className="w-24 text-right text-blue-600">{formatCurrency(totalGoalActual)}</span>
                    <span className={`w-28 text-right font-semibold ${varianceColor(totalGoalBudget - totalGoalActual, "goal")}`}>{formatCurrency(totalGoalBudget - totalGoalActual)}</span>
                    <span className="w-12" />
                  </div>
                </button>
                {!collapsedGroups.has("__goals") && (
                  <div className="border-t border-blue-100 divide-y divide-blue-50">
                    {goalItems.map(b => <BudgetCategoryRow key={b.id} item={b} section="goal" onEdit={handleInlineEdit} onDelete={handleDelete} />)}
                  </div>
                )}
                <div className="flex items-center px-4 py-3 border-t-2 border-blue-200 bg-blue-50/30">
                  <span className="flex-1 text-sm font-bold text-blue-800">Total Contributions</span>
                  <span className="w-24 text-right text-sm font-bold tabular-nums text-text-primary">{formatCurrency(totalGoalBudget)}</span>
                  <span className="w-24 text-right text-sm font-bold tabular-nums text-text-secondary">{formatCurrency(totalGoalActual)}</span>
                  <span className={`w-28 text-right text-sm font-bold tabular-nums ${varianceColor(totalGoalBudget - totalGoalActual, "goal")}`}>{formatCurrency(totalGoalBudget - totalGoalActual)}</span>
                  <span className="w-12" />
                </div>
              </Card>
            </div>
            )}
          </div>
          )}
        </div>

        {/* Right Sidebar */}
        <div className="space-y-4">
          <Card padding="lg" className={isBalanced ? "ring-1 ring-green-200 bg-green-50/20" : unallocated > 0 ? "ring-1 ring-amber-200 bg-amber-50/20" : "ring-1 ring-red-200 bg-red-50/20"}>
            <div className="text-center">
              <p className={`text-3xl font-bold tracking-tight ${isBalanced ? "text-green-600" : unallocated > 0 ? "text-amber-600" : "text-red-600"}`}>{formatCurrency(Math.abs(unallocated))}</p>
              <p className="text-xs text-text-secondary mt-1">{isBalanced ? "Balanced budget" : unallocated > 0 ? "Left to budget" : "Over-allocated"}</p>
            </div>
          </Card>

          {budgets.length > 0 && (
            <Card padding="lg">
              <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">Summary</h3>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs text-text-secondary mb-1"><span>Income</span><span className="font-medium">{formatCurrency(totalIncomeBudget)} budget</span></div>
                  <ProgressBar value={totalIncomeActual} max={totalIncomeBudget || 1} color="#16a34a" size="sm" />
                  <div className="flex justify-between text-xs mt-1"><span className="text-text-secondary">{formatCurrency(totalIncomeActual)} earned</span><span className="text-text-muted">{formatCurrency(Math.max(0, totalIncomeBudget - totalIncomeActual))} remaining</span></div>
                </div>
                <div>
                  <div className="flex justify-between text-xs text-text-secondary mb-1"><span>Expenses</span><span className="font-medium">{formatCurrency(totalExpenseBudget)} budget</span></div>
                  <ProgressBar value={totalExpenseActual} max={totalExpenseBudget || 1} color="#16A34A" size="sm" />
                  <div className="flex justify-between text-xs mt-1"><span className="text-text-secondary">{formatCurrency(totalExpenseActual)} spent</span><span className="text-text-muted">{formatCurrency(Math.max(0, totalExpenseBudget - totalExpenseActual))} remaining</span></div>
                </div>
                <div>
                  <div className="flex justify-between text-xs text-text-secondary mb-1"><span>Goals</span><span className="font-medium">{formatCurrency(totalGoalBudget)} budget</span></div>
                  <ProgressBar value={totalGoalActual} max={totalGoalBudget || 1} color="#2563eb" size="sm" />
                  <div className="flex justify-between text-xs mt-1"><span className="text-text-secondary">{formatCurrency(totalGoalActual)} contributed</span><span className="text-text-muted">{formatCurrency(Math.max(0, totalGoalBudget - totalGoalActual))} remaining</span></div>
                </div>
                <div className="border-t border-card-border pt-3">
                  <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between"><span className="text-text-muted">Income</span><span className="tabular-nums text-text-secondary font-medium">{formatCurrency(totalIncomeBudget)}</span></div>
                    <div className="flex justify-between"><span className="text-text-muted">- Expenses</span><span className="tabular-nums text-text-secondary font-medium">-{formatCurrency(totalExpenseBudget)}</span></div>
                    <div className="flex justify-between"><span className="text-text-muted">- Goals</span><span className="tabular-nums text-text-secondary font-medium">-{formatCurrency(totalGoalBudget)}</span></div>
                    <div className="flex justify-between border-t border-border pt-1.5">
                      <span className={`font-semibold ${isBalanced ? "text-green-700" : unallocated > 0 ? "text-amber-700" : "text-red-700"}`}>{isBalanced ? "= Balanced" : unallocated > 0 ? "= Unallocated" : "= Over-allocated"}</span>
                      <span className={`tabular-nums font-bold ${isBalanced ? "text-green-700" : unallocated > 0 ? "text-amber-700" : "text-red-700"}`}>{formatCurrency(unallocated)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {summary && summary.over_budget_categories.length > 0 && (
            <Card padding="md" className="border-red-100 bg-red-50/30">
              <p className="text-xs font-semibold text-red-700 mb-2">Over Budget ({summary.over_budget_categories.length})</p>
              <div className="space-y-1.5">
                {summary.over_budget_categories.map((c) => (
                  <div key={c.category} className="text-xs text-red-600 flex justify-between">
                    <span className="truncate">{c.category}</span>
                    <span className="tabular-nums font-medium ml-2">{formatCurrency(c.actual)} / {formatCurrency(c.budgeted)}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {insights.data && (
            <Card padding="lg">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-lg bg-green-50 flex items-center justify-center"><DollarSign size={14} className="text-green-600" /></div>
                <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Normalized</span>
              </div>
              <p className="text-xl font-bold text-text-primary tabular-nums">{formatCurrency(insights.data.summary.normalized_monthly_budget, true)}</p>
              <p className="text-xs text-text-muted mt-1">per month (excl. outliers)</p>
            </Card>
          )}
        </div>
      </div>
      {/* Smart Budget Preview */}
      {smartPreview && smartLines.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-accent" />
              <h3 className="text-sm font-semibold text-text-primary">Smart Budget Preview</h3>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => { setSmartPreview(false); setSmartLines([]); }} className="text-xs text-text-muted hover:text-text-secondary px-2 py-1">Cancel</button>
              <button onClick={handleApplySmartBudget} disabled={applyingSmart} className="flex items-center gap-1.5 text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent-hover disabled:opacity-50">
                {applyingSmart ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                Apply All ({smartLines.length} lines)
              </button>
            </div>
          </div>
          <div className="divide-y divide-card-border">
            {smartLines.map((line, i) => (
              <div key={i} className="flex items-center py-2.5 text-sm">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-text-secondary">{line.category}</p>
                  <p className="text-xs text-text-muted">{line.source}</p>
                </div>
                <span className="text-sm font-mono tabular-nums text-text-primary">{formatCurrency(line.budget_amount)}</span>
              </div>
            ))}
            <div className="flex items-center pt-3 mt-1">
              <span className="flex-1 text-sm font-bold text-text-primary">Total</span>
              <span className="text-sm font-bold font-mono tabular-nums text-text-primary">
                {formatCurrency(smartLines.reduce((s, l) => s + l.budget_amount, 0))}
              </span>
            </div>
          </div>
        </Card>
      )}
      </>
      )}

      {activeView === "forecast" && (
        <BudgetForecastPanel
          forecastData={forecastData}
          velocity={velocity}
          loading={forecastLoading}
          year={year}
          month={month}
        />
      )}

      <ConfirmDialog
        open={confirmDelete.open}
        title="Delete Budget Line"
        message="Are you sure you want to delete this budget? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDeleteBudget}
        onCancel={() => setConfirmDelete({ open: false, budgetId: null })}
      />
    </div>
  );
}
