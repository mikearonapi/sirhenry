"use client";
import { useCallback, useEffect, useState } from "react";
import { Calendar, Plus, AlertCircle, Loader2, X } from "lucide-react";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import {
  getLifeEvents, createLifeEvent, updateLifeEvent, deleteLifeEvent, toggleLifeEventActionItem,
} from "@/lib/api";
import type { LifeEvent, LifeEventIn } from "@/types/api";
import { EVENT_TYPES } from "@/components/life-events/constants";
import LifeEventForm from "@/components/life-events/LifeEventForm";
import LifeEventTimeline from "@/components/life-events/LifeEventTimeline";

const CURRENT_YEAR = new Date().getFullYear();

export default function LifeEventsPage() {
  const [events, setEvents] = useState<LifeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filterType, setFilterType] = useState<string>("");
  const [filterYear, setFilterYear] = useState<string>("");
  const [editingEvent, setEditingEvent] = useState<LifeEvent | null>(null);

  const loadEvents = useCallback(async () => {
    try {
      const params: Record<string, string | number> = {};
      if (filterType) params.event_type = filterType;
      if (filterYear) params.tax_year = Number(filterYear);
      const data = await getLifeEvents(Object.keys(params).length ? params : undefined);
      setEvents(Array.isArray(data) ? data : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [filterType, filterYear]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  function resetForm() {
    setEditingEvent(null);
    setShowForm(false);
  }

  function openEditForm(event: LifeEvent) {
    setEditingEvent(event);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSave(body: LifeEventIn) {
    setError(null);
    if (editingEvent) {
      await updateLifeEvent(editingEvent.id, body);
    } else {
      await createLifeEvent(body);
    }
    await loadEvents();
    resetForm();
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this life event?")) return;
    try {
      await deleteLifeEvent(id);
      await loadEvents();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleToggleAction(event: LifeEvent, idx: number, completed: boolean) {
    try {
      const result = await toggleLifeEventActionItem(event.id, idx, completed);
      setEvents((prev) =>
        prev.map((e) =>
          e.id === event.id
            ? { ...e, action_items_json: JSON.stringify((result as { items: unknown[] }).items) }
            : e
        )
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Life Events"
        subtitle="Track major financial life events that affect your taxes and planning"
        actions={
          <button
            onClick={() => { if (showForm) resetForm(); else setShowForm(true); }}
            className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
          >
            {showForm ? <X size={14} /> : <Plus size={14} />}
            {showForm ? "Cancel" : "Add Event"}
          </button>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {showForm && (
        <LifeEventForm
          editingEvent={editingEvent}
          onSave={handleSave}
          onCancel={resetForm}
        />
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="text-sm border border-stone-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
        >
          <option value="">All Categories</option>
          {EVENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.icon} {t.label}</option>
          ))}
        </select>
        <input
          type="number"
          value={filterYear}
          onChange={(e) => setFilterYear(e.target.value)}
          placeholder="Filter by year"
          className="w-36 text-sm border border-stone-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
        />
        {(filterType || filterYear) && (
          <button onClick={() => { setFilterType(""); setFilterYear(""); }} className="text-xs text-stone-500 hover:text-stone-700 underline">
            Clear filters
          </button>
        )}
        <span className="ml-auto text-xs text-stone-400">{events.length} events</span>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-stone-500 text-sm py-8">
          <Loader2 size={16} className="animate-spin" />
          Loading events...
        </div>
      ) : events.length === 0 ? (
        <Card padding="lg">
          <div className="text-center py-8">
            <Calendar size={32} className="mx-auto text-stone-300 mb-3" />
            <p className="text-sm text-stone-500">No life events recorded yet.</p>
            <p className="text-xs text-stone-400 mt-1">
              Track major events like home purchases, job changes, or new dependents to get personalized tax and planning guidance.
            </p>
          </div>
        </Card>
      ) : (
        <LifeEventTimeline
          events={events}
          expandedId={expandedId}
          onToggleExpand={setExpandedId}
          onEdit={openEditForm}
          onDelete={handleDelete}
          onToggleAction={handleToggleAction}
        />
      )}
    </div>
  );
}
