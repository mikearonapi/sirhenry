"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import Link from "next/link";
import type { SetupItem } from "./accounts-types";
import ConnectEmployer from "./ConnectEmployer";

interface SetupBannerProps {
  items: SetupItem[];
  hasEmployerConnection: boolean;
  loading: boolean;
  onConnectionComplete: () => void;
}

const STATUS_COLORS = {
  complete: { bg: "bg-green-50 border-green-100", dot: "bg-green-500", text: "text-green-700", sub: "text-green-600" },
  partial: { bg: "bg-amber-50 border-amber-100", dot: "bg-amber-400", text: "text-amber-700", sub: "text-amber-600" },
  empty: { bg: "bg-surface border-border", dot: "bg-stone-300", text: "text-text-secondary", sub: "text-text-muted" },
} as const;

function ProgressRing({ percentage }: { percentage: number }) {
  const r = 12;
  const c = 2 * Math.PI * r;
  const offset = c - (percentage / 100) * c;
  return (
    <svg width={28} height={28} className="shrink-0">
      <circle cx={14} cy={14} r={r} fill="none" stroke="#e7e5e4" strokeWidth={2.5} />
      <circle
        cx={14} cy={14} r={r} fill="none"
        stroke="#16A34A" strokeWidth={2.5}
        strokeDasharray={c} strokeDashoffset={offset}
        strokeLinecap="round" transform="rotate(-90 14 14)"
        className="transition-all duration-500"
      />
      <text x={14} y={15} textAnchor="middle" dominantBaseline="central"
        className="fill-text-secondary text-[8px] font-mono font-bold">
        {percentage}
      </text>
    </svg>
  );
}

function ItemBadge({ item }: { item: SetupItem }) {
  const c = STATUS_COLORS[item.status];
  const inner = (
    <div className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs transition-colors hover:opacity-80 ${c.bg}`}>
      <div className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-[9px] font-bold shrink-0 ${c.dot}`}>
        {item.status === "complete" ? "✓" : item.status === "partial" ? "~" : "!"}
      </div>
      <div>
        <p className={`font-semibold ${c.text}`}>{item.label}</p>
        <p className={`text-xs ${c.sub}`}>
          {item.count > 0 ? `${item.count} item${item.count !== 1 ? "s" : ""}` : item.action}
        </p>
      </div>
    </div>
  );
  return <Link href={item.href}>{inner}</Link>;
}

export default function SetupBanner({
  items, hasEmployerConnection, loading, onConnectionComplete,
}: SetupBannerProps) {
  const [expanded, setExpanded] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (loading || dismissed) return null;

  const completedCount = items.filter((i) => i.status === "complete").length + (hasEmployerConnection ? 1 : 0);
  const totalCount = items.length + 1; // +1 for employer
  const percentage = Math.round((completedCount / totalCount) * 100);
  const isAllComplete = completedCount === totalCount;
  const incompleteItems = items.filter((i) => i.status !== "complete");

  // Split items into admin (first 4 from adminHealth) and financial (from completeness)
  const adminItems = items.filter((i) =>
    ["Household", "Life Events", "Policies", "Business"].includes(i.label),
  );
  const financialItems = items.filter((i) =>
    ["Accounts", "Bank Accounts", "Investments", "Real Estate", "Liabilities"].includes(i.label),
  );

  const statusText = isAllComplete
    ? "Setup complete"
    : percentage >= 75
      ? "Setup nearly complete"
      : "Setup in progress";

  const remainingText = incompleteItems.length > 0
    ? incompleteItems.map((i) => i.label).join(" · ")
    : null;

  return (
    <div className="bg-card border border-card-border rounded-xl shadow-sm overflow-hidden">
      {/* Collapsed row — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface transition-colors"
        aria-expanded={expanded}
        aria-controls="setup-details"
      >
        <ProgressRing percentage={percentage} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-text-primary">{statusText}</p>
          {remainingText && !hasEmployerConnection ? (
            <p className="text-xs text-text-secondary truncate">
              {incompleteItems.length + 1} remaining: {remainingText} · Employer
            </p>
          ) : remainingText ? (
            <p className="text-xs text-text-secondary truncate">
              {incompleteItems.length} remaining: {remainingText}
            </p>
          ) : !hasEmployerConnection ? (
            <p className="text-xs text-text-secondary">Connect employer for auto-fill</p>
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          {isAllComplete && (
            <button
              onClick={(e) => { e.stopPropagation(); setDismissed(true); }}
              className="p-1 text-text-muted hover:text-text-secondary rounded"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          )}
          {expanded ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
        </div>
      </button>

      {/* Expanded section */}
      {expanded && (
        <div id="setup-details" className="border-t border-card-border px-4 py-4 space-y-4">
          {/* Progress bar */}
          <div className="w-full bg-surface rounded-full h-1.5">
            <div className="bg-accent h-1.5 rounded-full transition-all" style={{ width: `${percentage}%` }} />
          </div>

          {/* Admin items */}
          {adminItems.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Profile Setup</p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                {adminItems.map((item) => <ItemBadge key={item.label} item={item} />)}
              </div>
            </div>
          )}

          {/* Financial items */}
          {financialItems.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Financial Picture</p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                {financialItems.map((item) => <ItemBadge key={item.label} item={item} />)}
              </div>
            </div>
          )}

          {/* Employer connection */}
          <div>
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Employer &amp; Payroll</p>
            <ConnectEmployer onConnectionComplete={onConnectionComplete} />
          </div>
        </div>
      )}
    </div>
  );
}
