"use client";
import { ExternalLink } from "lucide-react";
import { getCascadeSuggestions, SECTION_COLORS, SECTION_LABELS } from "./constants";

interface Props {
  eventType: string;
  eventSubtype: string;
}

export default function LifeEventImpactChart({ eventType, eventSubtype }: Props) {
  const suggestions = getCascadeSuggestions(eventType, eventSubtype);
  if (!suggestions.length) return null;

  return (
    <div className="mt-3 pt-3 border-t border-card-border">
      <p className="text-xs font-semibold text-text-secondary mb-2">What this means for your finances</p>
      <div className="space-y-2">
        {suggestions.map((s, i) => (
          <a
            key={i}
            href={s.href}
            className={`flex items-start gap-3 p-2.5 rounded-lg border text-xs hover:opacity-80 transition-opacity ${SECTION_COLORS[s.section]}`}
          >
            <span className="shrink-0 mt-0.5 font-semibold text-xs uppercase tracking-wide opacity-70 w-14">
              {SECTION_LABELS[s.section]}
            </span>
            <span className="flex-1 min-w-0">
              <span className="font-semibold block">{s.label}</span>
              <span className="opacity-80">{s.detail}</span>
            </span>
            <ExternalLink size={11} className="shrink-0 mt-0.5 opacity-50" />
          </a>
        ))}
      </div>
    </div>
  );
}
