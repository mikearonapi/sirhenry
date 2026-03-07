"use client";
import { useCallback, useEffect, useState } from "react";
import {
  RefreshCw, Loader2, RotateCcw, AlertCircle,
  ChevronRight, X, Edit2, Pause, Play,
  DollarSign, TrendingUp, Check,
} from "lucide-react";
import { formatCurrency, monthName } from "@/lib/utils";
import { getRecurring, getRecurringSummary, detectRecurring, updateRecurring } from "@/lib/api";
import type { RecurringItem, RecurringSummary } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import ConfirmDialog from "@/components/ui/ConfirmDialog";

const FREQ_BADGE: Record<string, { variant: "info" | "accent" | "warning" | "success"; label: string }> = {
  monthly: { variant: "info", label: "Every month" },
  quarterly: { variant: "accent", label: "Every quarter" },
  annual: { variant: "warning", label: "Every year" },
  weekly: { variant: "success", label: "Every week" },
  "bi-weekly": { variant: "info", label: "Every 2 weeks" },
};

const CATEGORY_COLORS: Record<string, string> = {
  "TV, Streaming & Entertainment": "bg-purple-500",
  "Internet": "bg-blue-500",
  "Phone": "bg-cyan-500",
  "Insurance": "bg-amber-500",
  "Fitness": "bg-green-500",
  "Gen AI": "bg-violet-500",
  "Business — Software & Subscriptions": "bg-indigo-500",
  "Electric": "bg-yellow-500",
  "Gas Utility": "bg-orange-500",
  "Water": "bg-sky-500",
  "Mortgage": "bg-red-500",
  "HOA Dues": "bg-rose-500",
};

export default function RecurringPage() {
  const now = new Date();
  const [items, setItems] = useState<RecurringItem[]>([]);
  const [summary, setSummary] = useState<RecurringSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const viewMonth = { year: now.getFullYear(), month: now.getMonth() + 1 };
  const [filterMode, setFilterMode] = useState<"all" | "monthly">("all");

  const [confirmCancel, setConfirmCancel] = useState<{ open: boolean; itemId: number | null }>({ open: false, itemId: null });

  // Edit modal state
  const [editItem, setEditItem] = useState<RecurringItem | null>(null);
  const [editCategory, setEditCategory] = useState("");
  const [editCustomCategory, setEditCustomCategory] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const categoryKeys = Object.keys(CATEGORY_COLORS);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, s] = await Promise.all([getRecurring(), getRecurringSummary()]);
      setItems(Array.isArray(r) ? r : []);
      setSummary(s);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  async function handleDetect() {
    setDetecting(true);
    try {
      const result = await detectRecurring();
      await load();
      const count = result?.detected ?? 0;
      setToast(count > 0 ? `Detected ${count} new recurring transaction${count > 1 ? "s" : ""}` : "No new recurring transactions found");
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setDetecting(false);
    }
  }

  async function handleStatusChange(id: number, newStatus: "cancelled" | "paused" | "active") {
    if (newStatus === "cancelled") {
      setConfirmCancel({ open: true, itemId: id });
      return;
    }
    const labels: Record<string, string> = { cancelled: "cancel", paused: "pause", active: "reactivate" };
    try {
      await updateRecurring(id, { status: newStatus });
      await load();
      setToast(`Subscription ${labels[newStatus]}${newStatus === "active" ? "d" : "led"}`);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  async function confirmCancelSubscription() {
    if (confirmCancel.itemId == null) return;
    try {
      await updateRecurring(confirmCancel.itemId, { status: "cancelled" });
      setConfirmCancel({ open: false, itemId: null });
      await load();
      setToast("Subscription cancelled");
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  function openEdit(item: RecurringItem) {
    setEditItem(item);
    const cat = item.category ?? "";
    if (cat && !categoryKeys.includes(cat)) {
      setEditCategory("__other__");
      setEditCustomCategory(cat);
    } else {
      setEditCategory(cat);
      setEditCustomCategory("");
    }
    setEditNotes(item.notes ?? "");
  }

  async function handleEditSave() {
    if (!editItem) return;
    setEditSaving(true);
    const resolvedCategory = editCategory === "__other__" ? editCustomCategory : editCategory;
    try {
      await updateRecurring(editItem.id, {
        category: resolvedCategory || undefined,
        notes: editNotes || undefined,
      });
      await load();
      setEditItem(null);
      setToast("Subscription updated");
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setEditSaving(false);
    }
  }

  const active = items.filter((i) => (i.status === "active" || i.status === "paused") && (filterMode === "all" || i.frequency === "monthly"));
  const cancelled = items.filter((i) => i.status === "cancelled");
  const paused = active.filter((i) => i.status === "paused");
  const activeOnly = active.filter((i) => i.status === "active");

  function daysUntil(dateStr: string | null): string {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    const diff = Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    if (diff === 0) return "Today";
    if (diff === 1) return "In 1 day";
    if (diff < 0) return `${Math.abs(diff)} days ago`;
    return `In ${diff} days`;
  }

  // Cost breakdown by category
  const categoryBreakdown = summary?.by_category
    ? Object.entries(summary.by_category).sort((a, b) => b[1] - a[1])
    : [];
  const maxCategoryAmount = categoryBreakdown.length > 0 ? categoryBreakdown[0][1] : 0;

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-text-primary text-white px-4 py-2.5 rounded-lg shadow-lg flex items-center gap-2 text-sm animate-in slide-in-from-top-2">
          <Check size={14} className="text-green-400" />
          {toast}
          <button onClick={() => setToast(null)} className="ml-2 text-text-muted hover:text-white">
            <X size={12} />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">Recurring</h1>
          <span className="text-sm text-text-secondary">{monthName(viewMonth.month)} {viewMonth.year}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-surface rounded-lg p-0.5">
            <button
              onClick={() => setFilterMode("monthly")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filterMode === "monthly" ? "bg-card text-text-primary shadow-sm" : "text-text-secondary hover:text-text-primary"}`}
            >Monthly</button>
            <button
              onClick={() => setFilterMode("all")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filterMode === "all" ? "bg-card text-text-primary shadow-sm" : "text-text-secondary hover:text-text-primary"}`}
            >All recurring</button>
          </div>
          <button
            onClick={handleDetect}
            disabled={detecting}
            className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60 shadow-sm"
          >
            {detecting ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {detecting ? "Detecting..." : "Auto-Detect"}
          </button>
        </div>
      </div>

      {/* Summary metrics */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card padding="lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                <TrendingUp size={18} className="text-green-500" />
              </div>
              <div>
                <p className="text-xs text-text-muted font-medium uppercase">Monthly Cost</p>
                <p className="text-xl font-bold text-text-primary tabular-nums">{formatCurrency(summary.total_monthly_cost)}</p>
              </div>
            </div>
          </Card>
          <Card padding="lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                <DollarSign size={18} className="text-blue-500" />
              </div>
              <div>
                <p className="text-xs text-text-muted font-medium uppercase">Annual Cost</p>
                <p className="text-xl font-bold text-text-primary tabular-nums">{formatCurrency(summary.total_annual_cost)}</p>
              </div>
            </div>
          </Card>
          <Card padding="lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center">
                <RotateCcw size={18} className="text-purple-500" />
              </div>
              <div>
                <p className="text-xs text-text-muted font-medium uppercase">Active</p>
                <p className="text-xl font-bold text-text-primary">{summary.subscription_count}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700"><X size={14} /></button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-text-muted" size={24} /></div>
      ) : active.length === 0 ? (
        <EmptyState
          icon={<RotateCcw size={40} />}
          title="No recurring transactions detected yet"
          description="Import at least 3 months of transactions, then click Auto-Detect to find subscriptions and recurring expenses."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main list — 2/3 width */}
          <div className="lg:col-span-2 space-y-4">
            {/* Active subscriptions */}
            <Card padding="none">
              <div className="px-5 py-3 border-b border-card-border flex items-center gap-2">
                <ChevronRight size={14} className="text-text-muted" />
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Active ({activeOnly.length})</span>
              </div>
              <div className="divide-y divide-border-light">
                {activeOnly.map((item) => {
                  const fb = FREQ_BADGE[item.frequency];
                  const daysStr = daysUntil(item.next_expected_date);
                  return (
                    <div key={item.id} className="flex items-center px-4 sm:px-5 py-3.5 hover:bg-surface/50 group">
                      <div className="w-9 h-9 rounded-full bg-surface flex items-center justify-center text-sm font-bold text-text-secondary shrink-0 mr-3">
                        {item.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0 mr-2 sm:mr-4">
                        <p className="text-sm font-medium text-text-primary truncate">{item.name}</p>
                        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                          <Badge variant={fb?.variant ?? "default"} dot>{fb?.label ?? item.frequency}</Badge>
                          {item.category && <span className="text-xs text-text-muted">{item.category}</span>}
                        </div>
                      </div>
                      <div className="hidden sm:block w-28 text-right mr-4">
                        <p className="text-xs text-text-secondary">
                          {item.next_expected_date ? new Date(item.next_expected_date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "—"}
                        </p>
                        {daysStr && <p className="text-xs text-text-muted">{daysStr}</p>}
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-text-primary min-w-[70px] text-right">
                        {formatCurrency(Math.abs(item.amount))}
                      </span>
                      {/* Actions */}
                      <div className="flex items-center gap-1 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => openEdit(item)} className="p-1 rounded hover:bg-surface text-text-muted hover:text-text-secondary" aria-label="Edit">
                          <Edit2 size={12} />
                        </button>
                        <button onClick={() => handleStatusChange(item.id, "paused")} className="p-1 rounded hover:bg-amber-50 text-text-muted hover:text-amber-600" aria-label="Pause">
                          <Pause size={12} />
                        </button>
                        <button onClick={() => handleStatusChange(item.id, "cancelled")} className="p-1 rounded hover:bg-red-50 text-text-muted hover:text-red-500" aria-label="Cancel">
                          <X size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Paused subscriptions */}
            {paused.length > 0 && (
              <Card padding="none">
                <div className="px-5 py-3 border-b border-card-border flex items-center gap-2">
                  <Pause size={14} className="text-amber-400" />
                  <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Paused ({paused.length})</span>
                </div>
                <div className="divide-y divide-border-light">
                  {paused.map((item) => (
                    <div key={item.id} className="flex items-center px-5 py-3 opacity-70 group">
                      <div className="w-9 h-9 rounded-full bg-amber-50 flex items-center justify-center text-sm font-bold text-amber-500 shrink-0 mr-3">
                        {item.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-text-secondary truncate">{item.name}</p>
                        <span className="text-xs text-amber-500">Paused</span>
                      </div>
                      <span className="text-sm tabular-nums text-text-secondary mr-2">{formatCurrency(Math.abs(item.amount))}</span>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                        <button onClick={() => handleStatusChange(item.id, "active")} className="p-1 rounded hover:bg-green-50 text-text-muted hover:text-green-600" aria-label="Resume">
                          <Play size={12} />
                        </button>
                        <button onClick={() => handleStatusChange(item.id, "cancelled")} className="p-1 rounded hover:bg-red-50 text-text-muted hover:text-red-500" aria-label="Cancel">
                          <X size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Cancelled */}
            {cancelled.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                  Cancelled ({cancelled.length})
                </h3>
                <Card padding="none">
                  <div className="divide-y divide-border-light">
                    {cancelled.map((item) => (
                      <div key={item.id} className="flex items-center px-5 py-3 opacity-50 group">
                        <div className="w-9 h-9 rounded-full bg-surface flex items-center justify-center text-sm font-bold text-text-muted shrink-0 mr-3">
                          {item.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-text-secondary line-through truncate">{item.name}</p>
                        </div>
                        <span className="text-sm tabular-nums text-text-muted mr-2">{formatCurrency(Math.abs(item.amount))}</span>
                        <button
                          onClick={() => handleStatusChange(item.id, "active")}
                          className="text-xs text-text-muted hover:text-green-600 opacity-0 group-hover:opacity-100"
                        >
                          Reactivate
                        </button>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            )}
          </div>

          {/* Sidebar — cost breakdown */}
          <div className="space-y-4">
            {categoryBreakdown.length > 0 && (
              <Card>
                <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">Cost Breakdown</h3>
                <div className="space-y-2.5">
                  {categoryBreakdown.map(([cat, amount]) => {
                    const pct = maxCategoryAmount > 0 ? (amount / maxCategoryAmount) * 100 : 0;
                    const color = CATEGORY_COLORS[cat] ?? "bg-stone-400 dark:bg-stone-500";
                    return (
                      <div key={cat}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-text-secondary truncate mr-2">{cat}</span>
                          <span className="text-text-primary font-medium tabular-nums shrink-0">{formatCurrency(amount)}/mo</span>
                        </div>
                        <div className="h-2 bg-surface rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                {summary && (
                  <div className="mt-4 pt-3 border-t border-card-border">
                    <div className="flex justify-between text-sm">
                      <span className="text-text-secondary">Total monthly</span>
                      <span className="font-semibold text-text-primary tabular-nums">{formatCurrency(summary.total_monthly_cost)}</span>
                    </div>
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setEditItem(null)} />
          <div className="relative bg-card rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-text-primary">Edit Subscription</h3>
              <button onClick={() => setEditItem(null)} className="p-1 rounded-lg hover:bg-surface text-text-muted">
                <X size={16} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-text-primary">{editItem.name}</p>
                <p className="text-xs text-text-muted">{formatCurrency(Math.abs(editItem.amount))} / {editItem.frequency}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1">Category</label>
                <select
                  value={editCategory}
                  onChange={(e) => {
                    setEditCategory(e.target.value);
                    if (e.target.value !== "__other__") setEditCustomCategory("");
                  }}
                  className="w-full text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-card"
                >
                  <option value="">Select a category</option>
                  {categoryKeys.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                  <option value="__other__">Other</option>
                </select>
                {editCategory === "__other__" && (
                  <input
                    type="text"
                    value={editCustomCategory}
                    onChange={(e) => setEditCustomCategory(e.target.value)}
                    className="w-full text-sm border border-border rounded-lg px-3 py-2 mt-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
                    placeholder="Enter custom category"
                  />
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1">Notes</label>
                <textarea
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  rows={2}
                  className="w-full text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent resize-none"
                  placeholder="Add notes..."
                />
              </div>
              <button
                onClick={handleEditSave}
                disabled={editSaving}
                className="w-full flex items-center justify-center gap-2 bg-accent text-white text-sm font-medium py-2 rounded-lg hover:bg-accent-hover disabled:opacity-40"
              >
                {editSaving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmCancel.open}
        title="Cancel Subscription"
        message="Are you sure you want to cancel this subscription? You can reactivate it later."
        confirmLabel="Cancel Subscription"
        variant="danger"
        onConfirm={confirmCancelSubscription}
        onCancel={() => setConfirmCancel({ open: false, itemId: null })}
      />
    </div>
  );
}
