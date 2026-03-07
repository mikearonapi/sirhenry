"use client";
import { ChevronDown, ChevronUp, CheckCircle2, Circle, ExternalLink, Tag, Pencil, Trash2 } from "lucide-react";
import Card from "@/components/ui/Card";
import type { LifeEvent, ActionItem } from "@/types/api";
import {
  getEventConfig, getCascadeSuggestions, parseAmounts,
  STATUS_COLORS, STATUS_LABELS, SECTION_COLORS, SECTION_LABELS,
} from "./constants";
import LifeEventImpactChart from "./LifeEventImpactChart";

interface Props {
  events: LifeEvent[];
  expandedId: number | null;
  onToggleExpand: (id: number | null) => void;
  onEdit: (event: LifeEvent) => void;
  onDelete: (id: number) => void;
  onToggleAction: (event: LifeEvent, idx: number, completed: boolean) => void;
}

export default function LifeEventTimeline({
  events, expandedId, onToggleExpand, onEdit, onDelete, onToggleAction,
}: Props) {
  // Group events by year
  const eventsByYear = events.reduce<Record<string, LifeEvent[]>>((acc, e) => {
    const yr = String(e.tax_year || "No year");
    (acc[yr] = acc[yr] || []).push(e);
    return acc;
  }, {});

  const sortedYears = Object.keys(eventsByYear).sort((a, b) => Number(b) - Number(a));

  return (
    <div className="space-y-6">
      {sortedYears.map((year) => (
        <div key={year}>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">{year}</h3>
          <div className="space-y-3">
            {eventsByYear[year].map((event) => {
              const cfg = getEventConfig(event.event_type);
              const actionItems: ActionItem[] = JSON.parse(event.action_items_json || "[]");
              const completedItems = actionItems.filter((a) => a.completed).length;
              const isExpanded = expandedId === event.id;

              return (
                <Card key={event.id} padding="md">
                  <div className="flex items-start gap-3">
                    <div className="text-2xl mt-0.5">{cfg.icon}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h4 className="text-sm font-semibold text-text-primary">{event.title}</h4>
                          <div className="flex flex-wrap items-center gap-2 mt-1">
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg.color}`}>
                              {cfg.label}{event.event_subtype ? ` · ${event.event_subtype.replace(/_/g, " ")}` : ""}
                            </span>
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[event.status] || "bg-surface text-text-secondary"}`}>
                              {STATUS_LABELS[event.status] || event.status}
                            </span>
                            {event.event_date && (
                              <span className="text-xs text-text-muted">
                                {new Date(event.event_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {actionItems.length > 0 && (
                            <button
                              onClick={() => onToggleExpand(isExpanded ? null : event.id)}
                              className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-secondary px-2 py-1 rounded-lg hover:bg-surface"
                            >
                              <Tag size={12} />
                              {completedItems}/{actionItems.length} done
                              {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            </button>
                          )}
                          <button onClick={() => onEdit(event)} className="p-1.5 text-text-muted hover:text-accent rounded" title="Edit event"><Pencil size={13} /></button>
                          <button onClick={() => onDelete(event.id)} className="p-1.5 text-text-muted hover:text-red-500 rounded"><Trash2 size={13} /></button>
                        </div>
                      </div>

                      {event.notes && <p className="text-xs text-text-secondary mt-2">{event.notes}</p>}

                      {/* Financial amounts summary */}
                      {event.amounts_json && (() => {
                        const amounts = parseAmounts(event.amounts_json);
                        const entries = Object.entries(amounts).filter(([, v]) => v);
                        return entries.length > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-0.5">
                            {entries.map(([k, v]) => (
                              <span key={k} className="text-xs text-text-secondary">
                                <span className="capitalize">{k.replace(/_/g, " ")}: </span>
                                <span className="font-medium text-text-secondary">
                                  {k.includes("rate") ? `${v}%` : `$${Number(v).toLocaleString()}`}
                                </span>
                              </span>
                            ))}
                          </div>
                        ) : null;
                      })()}

                      {/* Action items (expanded) */}
                      {isExpanded && actionItems.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-card-border">
                          <p className="text-xs font-semibold text-text-secondary mb-2">Action Items</p>
                          <ul className="space-y-1.5">
                            {actionItems.map((item, idx) => (
                              <li key={idx} className="flex items-start gap-2">
                                <button
                                  onClick={() => onToggleAction(event, idx, !item.completed)}
                                  className={`mt-0.5 shrink-0 ${item.completed ? "text-green-500" : "text-text-muted hover:text-text-muted"}`}
                                >
                                  {item.completed ? <CheckCircle2 size={15} /> : <Circle size={15} />}
                                </button>
                                <span className={`text-xs ${item.completed ? "line-through text-text-muted" : "text-text-secondary"}`}>
                                  {item.text}
                                </span>
                                {item.link && !item.completed && (
                                  <a href={item.link} className="ml-auto shrink-0 text-accent hover:text-accent-hover" title={`Go to ${item.link}`}>
                                    <ExternalLink size={12} />
                                  </a>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Cascade suggestions (financial impact) */}
                      {isExpanded && (
                        <LifeEventImpactChart
                          eventType={event.event_type}
                          eventSubtype={event.event_subtype || ""}
                        />
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
