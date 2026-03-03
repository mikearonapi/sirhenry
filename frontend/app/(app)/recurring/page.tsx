"use client";
import { useCallback, useEffect, useState } from "react";
import {
  RefreshCw, Loader2, RotateCcw, AlertCircle,
  ChevronLeft, ChevronRight, Calendar, List as ListIcon,
  DollarSign, CreditCard, TrendingUp,
} from "lucide-react";
import { formatCurrency, monthName } from "@/lib/utils";
import { getRecurring, getRecurringSummary, detectRecurring, updateRecurring } from "@/lib/api";
import type { RecurringItem, RecurringSummary } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";

const FREQ_BADGE: Record<string, { variant: "info" | "accent" | "warning" | "success"; label: string }> = {
  monthly: { variant: "info", label: "Every month" },
  quarterly: { variant: "accent", label: "Every quarter" },
  annual: { variant: "warning", label: "Every year" },
  weekly: { variant: "success", label: "Every week" },
};

export default function RecurringPage() {
  const now = new Date();
  const [items, setItems] = useState<RecurringItem[]>([]);
  const [summary, setSummary] = useState<RecurringSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMonth] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const [filterMode, setFilterMode] = useState<"all" | "monthly">("all");

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

  async function handleDetect() {
    setDetecting(true);
    try { await detectRecurring(); await load(); }
    finally { setDetecting(false); }
  }

  async function handleCancel(id: number) {
    if (!window.confirm("Are you sure you want to cancel this subscription?")) return;
    try {
      await updateRecurring(id, { status: "cancelled" });
      load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  const active = items.filter((i) => i.status === "active" && (filterMode === "all" || i.frequency === "monthly"));
  const cancelled = items.filter((i) => i.status === "cancelled");

  // Split into upcoming (future) and completed (past)
  const today = new Date().toISOString().split("T")[0];
  const upcoming = active.filter((i) => (i.next_expected_date ?? "") >= today).sort((a, b) =>
    (a.next_expected_date ?? "").localeCompare(b.next_expected_date ?? "")
  );
  const completedThisMonth = active.filter((i) => (i.last_seen_date ?? "") >= `${viewMonth.year}-${String(viewMonth.month).padStart(2, "0")}-01`);

  function daysUntil(dateStr: string | null): string {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    const diff = Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    if (diff === 0) return "Today";
    if (diff === 1) return "In 1 day";
    if (diff < 0) return `${Math.abs(diff)} days ago`;
    return `In ${diff} days`;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Recurring</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm text-stone-500">{monthName(viewMonth.month)} {viewMonth.year}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-stone-100 rounded-lg p-0.5">
            <button
              onClick={() => setFilterMode("monthly")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filterMode === "monthly" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}
            >Monthly</button>
            <button
              onClick={() => setFilterMode("all")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filterMode === "all" ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}
            >All recurring</button>
          </div>
          <button
            onClick={handleDetect}
            disabled={detecting}
            className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60 shadow-sm"
          >
            {detecting ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {detecting ? "Detecting..." : "Auto-Detect"}
          </button>
        </div>
      </div>

      {/* Summary metrics */}
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <Card padding="lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                <TrendingUp size={18} className="text-green-500" />
              </div>
              <div>
                <p className="text-xs text-stone-400 font-medium uppercase">Monthly Cost</p>
                <p className="text-xl font-bold text-stone-900 tabular-nums">{formatCurrency(summary.total_monthly_cost)}</p>
              </div>
            </div>
          </Card>
          <Card padding="lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                <DollarSign size={18} className="text-blue-500" />
              </div>
              <div>
                <p className="text-xs text-stone-400 font-medium uppercase">Annual Cost</p>
                <p className="text-xl font-bold text-stone-900 tabular-nums">{formatCurrency(summary.total_annual_cost)}</p>
              </div>
            </div>
          </Card>
          <Card padding="lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center">
                <RotateCcw size={18} className="text-purple-500" />
              </div>
              <div>
                <p className="text-xs text-stone-400 font-medium uppercase">Active</p>
                <p className="text-xl font-bold text-stone-900">{summary.subscription_count}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      ) : active.length === 0 ? (
        <EmptyState
          icon={<RotateCcw size={40} />}
          title="No recurring transactions detected yet"
          description="Import at least 3 months of transactions, then click Auto-Detect to find subscriptions and recurring expenses."
        />
      ) : (
        <Card padding="none">
          {/* Upcoming header */}
          <div className="px-5 py-3 border-b border-stone-100 flex items-center gap-2">
            <ChevronRight size={14} className="text-stone-400" />
            <span className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Upcoming</span>
          </div>

          <div className="divide-y divide-stone-50">
            {active.map((item) => {
              const fb = FREQ_BADGE[item.frequency];
              const daysStr = daysUntil(item.next_expected_date);
              return (
                <div key={item.id} className="flex items-center px-5 py-3.5 hover:bg-stone-50/50 group">
                  {/* Icon */}
                  <div className="w-9 h-9 rounded-full bg-stone-100 flex items-center justify-center text-sm font-bold text-stone-500 shrink-0 mr-3">
                    {item.name.charAt(0).toUpperCase()}
                  </div>

                  {/* Name + frequency */}
                  <div className="flex-1 min-w-0 mr-4">
                    <p className="text-sm font-medium text-stone-800 truncate">{item.name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge variant={fb?.variant ?? "default"} dot>{fb?.label ?? item.frequency}</Badge>
                      {item.is_auto_detected && <span className="text-[10px] text-stone-400">Auto-detected</span>}
                    </div>
                  </div>

                  {/* Next date */}
                  <div className="w-28 text-right mr-4">
                    <p className="text-xs text-stone-500">
                      {item.next_expected_date ? new Date(item.next_expected_date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "—"}
                    </p>
                    {daysStr && <p className="text-[11px] text-stone-400">{daysStr}</p>}
                  </div>

                  {/* Category */}
                  <div className="w-32 mr-4">
                    <span className="text-xs text-stone-500">{item.category ?? "—"}</span>
                  </div>

                  {/* Amount */}
                  <span className="text-sm font-semibold tabular-nums text-stone-900 w-24 text-right">
                    {formatCurrency(Math.abs(item.amount))}
                  </span>

                  {/* Cancel */}
                  <button
                    onClick={() => handleCancel(item.id)}
                    className="text-xs text-stone-300 hover:text-red-500 opacity-0 group-hover:opacity-100 ml-3"
                  >
                    Cancel
                  </button>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Cancelled */}
      {cancelled.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-stone-400 uppercase tracking-wider mb-2">
            Cancelled ({cancelled.length})
          </h3>
          <Card padding="none">
            <div className="divide-y divide-stone-50">
              {cancelled.map((item) => (
                <div key={item.id} className="flex items-center px-5 py-3 opacity-50">
                  <div className="w-9 h-9 rounded-full bg-stone-100 flex items-center justify-center text-sm font-bold text-stone-400 shrink-0 mr-3">
                    {item.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-stone-500 line-through truncate">{item.name}</p>
                  </div>
                  <span className="text-sm tabular-nums text-stone-400">{formatCurrency(Math.abs(item.amount))}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
