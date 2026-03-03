"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Bell, Plus, Check, Clock, AlertCircle, Loader2, Calendar, X, Pencil,
  User, ToggleLeft, ToggleRight, Link2, Database, Download, Trash2,
  RefreshCw, Building2, Settings,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { getReminders, createReminder, updateReminder, seedTaxDeadlines, getPlaidItems, syncPlaid } from "@/lib/api";
import type { Reminder, PlaidItem } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";

const TYPE_COLORS: Record<string, string> = {
  tax: "bg-red-50 text-red-700 border-red-100",
  bill: "bg-orange-50 text-orange-700 border-orange-100",
  subscription: "bg-blue-50 text-blue-700 border-blue-100",
  goal: "bg-purple-50 text-purple-700 border-purple-100",
  custom: "bg-stone-50 text-stone-700 border-stone-100",
};

const TYPE_ICONS: Record<string, React.ReactNode> = {
  tax: <span className="text-base">📋</span>,
  bill: <span className="text-base">💳</span>,
  subscription: <span className="text-base">🔄</span>,
  goal: <span className="text-base">🎯</span>,
  custom: <span className="text-base">📌</span>,
};

const SETTINGS_TABS = [
  { id: "reminders", label: "Reminders", icon: Bell },
  { id: "profile", label: "Profile", icon: User },
  { id: "notifications", label: "Notifications", icon: ToggleLeft },
  { id: "integrations", label: "Integrations", icon: Link2 },
  { id: "display", label: "Display", icon: Settings },
  { id: "data", label: "Data", icon: Database },
];

function loadPref<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try { const v = localStorage.getItem(`settings.${key}`); return v !== null ? JSON.parse(v) : fallback; }
  catch { return fallback; }
}

function savePref(key: string, value: unknown) {
  try { localStorage.setItem(`settings.${key}`, JSON.stringify(value)); } catch {}
}

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState("reminders");

  // Reminders state
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [filterType, setFilterType] = useState("");

  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [reminderType, setReminderType] = useState<"bill" | "tax" | "subscription" | "goal" | "custom">("bill");
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);

  // Profile preferences (localStorage)
  const [prefName, setPrefName] = useState(() => loadPref("name", ""));
  const [prefTaxYear, setPrefTaxYear] = useState(() => loadPref("taxYear", new Date().getFullYear()));
  const [prefCurrency, setPrefCurrency] = useState(() => loadPref("currency", "USD"));
  const [prefSaved, setPrefSaved] = useState(false);

  // Notification preferences (localStorage)
  const [notifBudgetAlert, setNotifBudgetAlert] = useState(() => loadPref("notif.budget", true));
  const [notifGoalMilestone, setNotifGoalMilestone] = useState(() => loadPref("notif.goal", true));
  const [notifUnusualSpend, setNotifUnusualSpend] = useState(() => loadPref("notif.unusual", true));
  const [notifPlaidFailure, setNotifPlaidFailure] = useState(() => loadPref("notif.plaid", true));
  const [notifBudgetThreshold, setNotifBudgetThreshold] = useState(() => loadPref("notif.budgetPct", 110));
  const [notifSaved, setNotifSaved] = useState(false);

  // Display preferences (localStorage)
  const [dispDateFormat, setDispDateFormat] = useState(() => loadPref("display.dateFormat", "MM/DD/YYYY"));
  const [dispShowCents, setDispShowCents] = useState(() => loadPref("display.showCents", true));
  const [dispSaved, setDispSaved] = useState(false);

  // Integrations (Plaid)
  const [plaidItems, setPlaidItems] = useState<PlaidItem[]>([]);
  const [plaidLoading, setPlaidLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // Data management
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getReminders(filterType || undefined);
      setReminders(Array.isArray(data) ? data : []);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setLoading(false);
  }, [filterType]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (activeTab === "integrations" && plaidItems.length === 0) {
      setPlaidLoading(true);
      getPlaidItems().then((d) => setPlaidItems(Array.isArray(d) ? d : [])).catch(() => {}).finally(() => setPlaidLoading(false));
    }
  }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSyncAll() {
    setSyncing(true);
    try {
      await syncPlaid();
      const d = await getPlaidItems();
      setPlaidItems(Array.isArray(d) ? d : []);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setSyncing(false);
  }

  function saveProfile() {
    savePref("name", prefName);
    savePref("taxYear", prefTaxYear);
    savePref("currency", prefCurrency);
    setPrefSaved(true);
    setTimeout(() => setPrefSaved(false), 2000);
  }

  function saveNotifications() {
    savePref("notif.budget", notifBudgetAlert);
    savePref("notif.goal", notifGoalMilestone);
    savePref("notif.unusual", notifUnusualSpend);
    savePref("notif.plaid", notifPlaidFailure);
    savePref("notif.budgetPct", notifBudgetThreshold);
    setNotifSaved(true);
    setTimeout(() => setNotifSaved(false), 2000);
  }

  function saveDisplay() {
    savePref("display.dateFormat", dispDateFormat);
    savePref("display.showCents", dispShowCents);
    setDispSaved(true);
    setTimeout(() => setDispSaved(false), 2000);
  }

  async function handleExportData() {
    setExporting(true);
    try {
      const [rem, pItems] = await Promise.all([getReminders(), getPlaidItems()]);
      const blob = new Blob([JSON.stringify({ reminders: rem, plaid_items: pItems, exported_at: new Date().toISOString() }, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `financials-export-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setExporting(false);
  }

  async function handleSeedAll() {
    setSeeding(true);
    setError(null);
    try {
      await seedTaxDeadlines();
      await load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setSeeding(false);
  }

  async function handleComplete(id: number) {
    try {
      await updateReminder(id, { status: "completed" });
      load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  async function handleDismiss(id: number) {
    if (!window.confirm("Are you sure you want to dismiss this reminder?")) return;
    try {
      await updateReminder(id, { status: "dismissed" });
      load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  function openEditReminder(r: Reminder) {
    setEditingReminder(r);
    setTitle(r.title);
    setDueDate(r.due_date.split("T")[0]);
    setReminderType(r.reminder_type);
    setAmount(r.amount != null ? String(r.amount) : "");
    setShowAdd(true);
  }

  function resetReminderForm() {
    setEditingReminder(null);
    setTitle(""); setDueDate(""); setAmount("");
    setReminderType("bill");
    setShowAdd(false);
  }

  async function handleAdd() {
    if (!title || !dueDate) return;
    setSaving(true);
    setError(null);
    try {
      if (editingReminder) {
        await updateReminder(editingReminder.id, {
          title, due_date: dueDate, reminder_type: reminderType,
          amount: amount ? parseFloat(amount) : null,
        });
      } else {
        await createReminder({
          title, due_date: dueDate, reminder_type: reminderType,
          amount: amount ? parseFloat(amount) : null,
        });
      }
      resetReminderForm();
      load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setSaving(false);
  }

  const overdue = reminders.filter((r) => r.is_overdue);
  const upcoming = reminders.filter((r) => !r.is_overdue && r.days_until_due <= 30);
  const later = reminders.filter((r) => !r.is_overdue && r.days_until_due > 30);

  function ReminderCard({ r }: { r: Reminder }) {
    const colorClass = TYPE_COLORS[r.reminder_type] ?? TYPE_COLORS.custom;
    return (
      <div className={`rounded-xl border p-4 ${colorClass} ${r.is_overdue ? "ring-2 ring-red-300" : ""}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            {TYPE_ICONS[r.reminder_type] ?? TYPE_ICONS.custom}
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm">{r.title}</p>
              {r.description && <p className="text-xs mt-0.5 opacity-80">{r.description}</p>}
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                <div className="flex items-center gap-1 text-xs opacity-70">
                  <Calendar size={11} />
                  {new Date(r.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </div>
                {r.is_overdue ? (
                  <span className="text-xs font-semibold text-red-700 bg-red-100 px-1.5 py-0.5 rounded">OVERDUE</span>
                ) : r.days_until_due <= 7 ? (
                  <span className="text-xs font-semibold text-orange-700 bg-orange-100 px-1.5 py-0.5 rounded">{r.days_until_due}d left</span>
                ) : (
                  <span className="text-xs opacity-60">{r.days_until_due}d away</span>
                )}
                {r.is_recurring && r.recurrence_rule && (
                  <span className="text-xs text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">{r.recurrence_rule}</span>
                )}
                {r.amount && <span className="text-xs font-semibold">{formatCurrency(r.amount)}</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={() => openEditReminder(r)} title="Edit reminder" aria-label="Edit reminder"
              className="p-1.5 rounded-lg hover:bg-white/50 transition-colors">
              <Pencil size={13} />
            </button>
            <button onClick={() => handleComplete(r.id)} title="Mark complete" aria-label="Mark complete"
              className="p-1.5 rounded-lg hover:bg-white/50 transition-colors">
              <Check size={13} />
            </button>
            <button onClick={() => handleDismiss(r.id)} title="Dismiss" aria-label="Dismiss reminder"
              className="p-1.5 rounded-lg hover:bg-white/50 transition-colors">
              <X size={13} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900">Settings</h1>
          <p className="text-stone-500 text-sm mt-0.5">App configuration, reminders, integrations, and preferences</p>
        </div>
        {activeTab === "reminders" && (
          <div className="flex items-center gap-3">
            <button onClick={handleSeedAll} disabled={seeding}
              className="flex items-center gap-2 text-sm text-stone-600 border border-stone-200 rounded-lg px-4 py-2 hover:bg-stone-50 disabled:opacity-60">
              {seeding ? <Loader2 size={13} className="animate-spin" /> : <Calendar size={13} />}
              Seed All Reminders
            </button>
            <button onClick={() => { if (showAdd) resetReminderForm(); else setShowAdd(true); }}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D]">
              {showAdd ? <X size={14} /> : <Plus size={14} />} {showAdd ? "Cancel" : "Add Reminder"}
            </button>
          </div>
        )}
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-stone-200 overflow-x-auto">
        {SETTINGS_TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === id
                ? "border-[#16A34A] text-[#16A34A]"
                : "border-transparent text-stone-500 hover:text-stone-700 hover:border-stone-300"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} /><p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {/* ── REMINDERS TAB ── */}
      {activeTab === "reminders" && (
        <div className="space-y-6">

      {/* Add form */}
      {showAdd && (
        <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-5">
          <h2 className="font-semibold text-stone-800 mb-4">
            {editingReminder ? "Edit Reminder" : "New Reminder"}
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-stone-500 mb-1">Title</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Pay credit card bill"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">Due Date</label>
              <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">Type</label>
              <select value={reminderType} onChange={(e) => setReminderType(e.target.value as typeof reminderType)}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]">
                <option value="bill">Bill</option>
                <option value="tax">Tax</option>
                <option value="subscription">Subscription</option>
                <option value="goal">Goal</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">Amount (optional)</label>
              <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00"
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button onClick={handleAdd} disabled={saving || !title || !dueDate}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60">
              {saving ? <Loader2 size={13} className="animate-spin" /> : null}
              {editingReminder ? "Update Reminder" : "Add Reminder"}
            </button>
            <button onClick={resetReminderForm} className="text-sm text-stone-500 hover:text-stone-700 px-3">Cancel</button>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2">
        {["", "tax", "bill", "subscription", "goal", "custom"].map((t) => (
          <button key={t} onClick={() => setFilterType(t)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${filterType === t ? "border-[#16A34A] bg-[#DCFCE7] text-[#16A34A]" : "border-stone-200 text-stone-500 hover:border-stone-300"}`}>
            {t === "" ? "All" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      ) : (
        <>
          {/* Overdue */}
          {overdue.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-red-500 mb-3 flex items-center gap-1">
                <AlertCircle size={13} /> Overdue ({overdue.length})
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {overdue.map((r) => <ReminderCard key={r.id} r={r} />)}
              </div>
            </div>
          )}

          {/* Upcoming (30 days) */}
          {upcoming.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-orange-500 mb-3 flex items-center gap-1">
                <Clock size={13} /> Due Within 30 Days ({upcoming.length})
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {upcoming.map((r) => <ReminderCard key={r.id} r={r} />)}
              </div>
            </div>
          )}

          {/* Later */}
          {later.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-3">
                Upcoming ({later.length})
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {later.map((r) => <ReminderCard key={r.id} r={r} />)}
              </div>
            </div>
          )}

          {reminders.length === 0 && (
            <div className="bg-white rounded-xl border border-dashed border-stone-200 p-12 text-center">
              <Bell className="mx-auto text-stone-200 mb-4" size={40} />
              <h3 className="font-semibold text-stone-700 mb-2">No reminders yet</h3>
              <p className="text-stone-400 text-sm mb-4">Add reminders for bills, tax deadlines, and financial events.</p>
              <button onClick={handleSeedAll}
                className="bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D]">
                Seed All Reminders
              </button>
            </div>
          )}
        </>
      )}
        </div>
      )}

      {/* ── PROFILE TAB ── */}
      {activeTab === "profile" && (
        <div className="max-w-lg space-y-4">
          <p className="text-xs text-stone-500">These preferences are stored locally on this device.</p>
          <div>
            <label className="text-xs text-stone-500">Your Name</label>
            <input type="text" value={prefName} onChange={(e) => setPrefName(e.target.value)}
              placeholder="e.g. Mike" className="mt-1 w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
          </div>
          <div>
            <label className="text-xs text-stone-500">Active Tax Year</label>
            <input type="number" value={prefTaxYear} onChange={(e) => setPrefTaxYear(Number(e.target.value))}
              className="mt-1 w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
          </div>
          <div>
            <label className="text-xs text-stone-500">Base Currency</label>
            <select value={prefCurrency} onChange={(e) => setPrefCurrency(e.target.value)}
              className="mt-1 w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20">
              <option value="USD">USD — US Dollar</option>
              <option value="EUR">EUR — Euro</option>
              <option value="GBP">GBP — British Pound</option>
              <option value="CAD">CAD — Canadian Dollar</option>
            </select>
          </div>
          <button onClick={saveProfile} className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D]">
            {prefSaved ? <Check size={14} /> : null} {prefSaved ? "Saved!" : "Save Profile"}
          </button>
        </div>
      )}

      {/* ── NOTIFICATIONS TAB ── */}
      {activeTab === "notifications" && (
        <div className="max-w-lg space-y-5">
          <p className="text-xs text-stone-500">Notification preferences are stored locally. Actual alerts appear in the Reminders section.</p>
          {([
            { label: "Budget overage alerts", sub: "Notify when spending exceeds budget", val: notifBudgetAlert, set: setNotifBudgetAlert },
            { label: "Goal milestone alerts", sub: "Notify when you reach a goal milestone", val: notifGoalMilestone, set: setNotifGoalMilestone },
            { label: "Unusual spending alerts", sub: "Notify when a transaction looks abnormal", val: notifUnusualSpend, set: setNotifUnusualSpend },
            { label: "Plaid sync failure alerts", sub: "Notify when a bank connection breaks", val: notifPlaidFailure, set: setNotifPlaidFailure },
          ] as { label: string; sub: string; val: boolean; set: (v: boolean) => void }[]).map(({ label, sub, val, set }) => (
            <div key={label} className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-stone-800">{label}</p>
                <p className="text-xs text-stone-500">{sub}</p>
              </div>
              <button onClick={() => set(!val)} className={`transition-colors ${val ? "text-[#16A34A]" : "text-stone-300"}`}>
                {val ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
              </button>
            </div>
          ))}
          <div>
            <label className="text-xs text-stone-500">Budget alert threshold (%)</label>
            <div className="flex items-center gap-3 mt-1">
              <input type="number" value={notifBudgetThreshold} onChange={(e) => setNotifBudgetThreshold(Number(e.target.value))}
                className="w-24 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
              <span className="text-xs text-stone-500">Alert when budget is {notifBudgetThreshold}% spent</span>
            </div>
          </div>
          <button onClick={saveNotifications} className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D]">
            {notifSaved ? <Check size={14} /> : null} {notifSaved ? "Saved!" : "Save Notifications"}
          </button>
        </div>
      )}

      {/* ── INTEGRATIONS TAB ── */}
      {activeTab === "integrations" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-stone-900">Plaid Connections</h3>
              <p className="text-xs text-stone-500 mt-0.5">Bank and investment accounts linked via Plaid</p>
            </div>
            <button onClick={handleSyncAll} disabled={syncing}
              className="flex items-center gap-2 text-sm text-stone-600 border border-stone-200 rounded-lg px-3 py-2 hover:bg-stone-50 disabled:opacity-60">
              {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Sync All
            </button>
          </div>
          {plaidLoading ? (
            <div className="flex items-center gap-2 text-stone-400 text-sm py-4"><Loader2 size={16} className="animate-spin" /> Loading connections...</div>
          ) : plaidItems.length === 0 ? (
            <div className="bg-stone-50 border border-dashed border-stone-200 rounded-xl p-8 text-center">
              <Building2 size={28} className="mx-auto text-stone-300 mb-3" />
              <p className="text-sm text-stone-500">No Plaid connections yet.</p>
              <p className="text-xs text-stone-400 mt-1">Connect bank accounts from the <a href="/accounts" className="text-[#16A34A] hover:underline">Accounts</a> page.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {plaidItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between bg-white border border-stone-100 rounded-xl px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Building2 size={18} className="text-stone-400" />
                    <div>
                      <p className="text-sm font-medium text-stone-900">{item.institution_name || "Unknown Institution"}</p>
                      <p className="text-xs text-stone-400">
                        {item.account_count} account{item.account_count !== 1 ? "s" : ""}
                        {item.last_synced_at ? ` · Last synced ${new Date(item.last_synced_at).toLocaleDateString()}` : ""}
                      </p>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    item.status === "active" ? "bg-green-50 text-green-600" :
                    item.status === "reauth_needed" ? "bg-amber-50 text-amber-600" :
                    "bg-red-50 text-red-600"
                  }`}>
                    {item.status === "active" ? "Active" : item.status === "reauth_needed" ? "Re-auth needed" : "Error"}
                  </span>
                </div>
              ))}
              <p className="text-xs text-stone-400">To add or remove connections, go to <a href="/accounts" className="text-[#16A34A] hover:underline">Accounts</a>.</p>
            </div>
          )}
        </div>
      )}

      {/* ── DISPLAY TAB ── */}
      {activeTab === "display" && (
        <div className="max-w-lg space-y-4">
          <p className="text-xs text-stone-500">Display preferences are stored locally on this device.</p>
          <div>
            <label className="text-xs text-stone-500">Date Format</label>
            <select value={dispDateFormat} onChange={(e) => setDispDateFormat(e.target.value)}
              className="mt-1 w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20">
              <option value="MM/DD/YYYY">MM/DD/YYYY (US)</option>
              <option value="DD/MM/YYYY">DD/MM/YYYY (International)</option>
              <option value="YYYY-MM-DD">YYYY-MM-DD (ISO)</option>
            </select>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-stone-800">Show cents in currency</p>
              <p className="text-xs text-stone-500">Display $1,234.56 vs $1,235</p>
            </div>
            <button onClick={() => setDispShowCents(!dispShowCents)} className={`transition-colors ${dispShowCents ? "text-[#16A34A]" : "text-stone-300"}`}>
              {dispShowCents ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
            </button>
          </div>
          <button onClick={saveDisplay} className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D]">
            {dispSaved ? <Check size={14} /> : null} {dispSaved ? "Saved!" : "Save Preferences"}
          </button>
        </div>
      )}

      {/* ── DATA MANAGEMENT TAB ── */}
      {activeTab === "data" && (
        <div className="space-y-4 max-w-lg">
          <div className="bg-white border border-stone-100 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <Download size={18} className="text-stone-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-stone-900">Export Data</p>
                <p className="text-xs text-stone-500 mt-0.5">Download your reminders and connection metadata as JSON for backup or migration.</p>
                <button onClick={handleExportData} disabled={exporting}
                  className="mt-3 flex items-center gap-2 bg-stone-800 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-stone-700 disabled:opacity-60">
                  {exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                  {exporting ? "Exporting..." : "Export JSON"}
                </button>
              </div>
            </div>
          </div>
          <div className="bg-white border border-stone-100 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <Trash2 size={18} className="text-red-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-stone-900">Clear Local Preferences</p>
                <p className="text-xs text-stone-500 mt-0.5">Remove all locally stored settings (profile, display, notification preferences). Does not affect your financial data.</p>
                <button
                  onClick={() => {
                    if (!confirm("Clear all local preferences? This only affects display and notification settings.")) return;
                    ["name","taxYear","currency","notif.budget","notif.goal","notif.unusual","notif.plaid","notif.budgetPct","display.dateFormat","display.showCents"].forEach((k) => localStorage.removeItem(`settings.${k}`));
                    window.location.reload();
                  }}
                  className="mt-3 flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700">
                  <Trash2 size={13} /> Clear Local Preferences
                </button>
              </div>
            </div>
          </div>
          <div className="bg-amber-50 border border-amber-100 rounded-xl p-3">
            <p className="text-xs text-amber-700">
              <span className="font-semibold">Note: </span>
              Your financial data (transactions, accounts, tax items) is stored in the local SQLite database. To fully export or back up all data, use your system backup tools on the database file.
            </p>
          </div>
        </div>
      )}

    </div>
  );
}
