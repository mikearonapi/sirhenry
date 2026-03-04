"use client";
import { useCallback, useEffect, useState } from "react";
import { Loader2, Calendar } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import { request } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";

interface VestingEvent {
  id: number;
  grant_id: number;
  employer: string;
  grant_type: string;
  ticker: string | null;
  vest_date: string;
  shares: number;
  estimated_value: number;
  status: string;
}

const GRANT_TYPE_COLORS: Record<string, string> = {
  rsu: "#3b82f6",
  iso: "#8b5cf6",
  nso: "#f59e0b",
  espp: "#06b6d4",
};

const GRANT_TYPE_LABELS: Record<string, string> = {
  rsu: "RSU",
  iso: "ISO",
  nso: "NSO",
  espp: "ESPP",
};

export default function VestingCalendar() {
  const [events, setEvents] = useState<VestingEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await request<{ events: VestingEvent[]; months: number }>("/equity-comp/vesting-events?months=24");
      setEvents(data.events);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <Card padding="lg">
        <div className="flex justify-center py-8"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      </Card>
    );
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (events.length === 0) {
    return (
      <Card padding="lg">
        <div className="text-center py-8">
          <Calendar size={32} className="mx-auto mb-3 text-stone-200" />
          <p className="text-sm text-stone-500">No upcoming vesting events</p>
          <p className="text-xs text-stone-400 mt-1">Add vesting schedules to your grants to see upcoming vests here.</p>
        </div>
      </Card>
    );
  }

  // Group events by month
  const grouped: Record<string, VestingEvent[]> = {};
  for (const ev of events) {
    const d = new Date(ev.vest_date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(ev);
  }

  const totalValue = events.reduce((s, e) => s + e.estimated_value, 0);

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-stone-800">Vesting Timeline (24 months)</h3>
        <span className="text-xs text-stone-400">
          {events.length} events · {formatCurrency(totalValue)} estimated
        </span>
      </div>

      <div className="space-y-4">
        {Object.entries(grouped).map(([monthKey, monthEvents]) => {
          const d = new Date(monthKey + "-01");
          const label = d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
          const monthTotal = monthEvents.reduce((s, e) => s + e.estimated_value, 0);

          return (
            <div key={monthKey}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-stone-500 uppercase tracking-wider">{label}</span>
                <span className="text-xs font-semibold text-stone-600 font-mono tabular-nums">{formatCurrency(monthTotal)}</span>
              </div>
              <div className="space-y-2">
                {monthEvents.map((ev) => {
                  const vestDate = new Date(ev.vest_date);
                  const color = GRANT_TYPE_COLORS[ev.grant_type] ?? "#64748b";
                  return (
                    <div key={ev.id} className="flex items-center gap-3 py-2 px-3 rounded-lg bg-stone-50 hover:bg-stone-100 transition-colors">
                      <div className="w-2 h-8 rounded-full" style={{ backgroundColor: color }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-stone-800">{ev.employer}</span>
                          <span className="text-xs px-1.5 py-0.5 rounded text-white" style={{ backgroundColor: color }}>
                            {GRANT_TYPE_LABELS[ev.grant_type] ?? ev.grant_type.toUpperCase()}
                          </span>
                          {ev.ticker && <span className="text-xs text-stone-400">{ev.ticker}</span>}
                        </div>
                        <p className="text-xs text-stone-400">
                          {vestDate.toLocaleDateString("en-US", { month: "short", day: "numeric" })} · {ev.shares.toLocaleString()} shares
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold font-mono tabular-nums">{formatCurrency(ev.estimated_value)}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
