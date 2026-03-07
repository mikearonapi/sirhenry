"use client";
import { Trash2 } from "lucide-react";
import type { ChatConversation } from "@/types/api";

export const CONTEXT_LABELS: Record<string, string> = {
  goals: "Goals",
  budget: "Budget",
  cashflow: "Cash Flow",
  transactions: "Transactions",
  recurring: "Recurring",
  portfolio: "Portfolio",
  retirement: "Retirement",
  market: "Market Pulse",
  "equity-comp": "Equity Comp",
  "life-planner": "Life Planner",
  "tax-strategy": "Tax Strategy",
  "tax-documents": "Tax Docs",
  setup: "Setup",
  accounts: "Accounts",
  household: "Household",
  "life-events": "Life Events",
  business: "Business",
  insurance: "Policies",
  dashboard: "Dashboard",
};

export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

interface Props {
  conv: ChatConversation;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}

export default function ConversationItem({ conv, isActive, onClick, onDelete }: Props) {
  const contextLabel = conv.page_context ? CONTEXT_LABELS[conv.page_context] ?? conv.page_context : null;

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (window.confirm(`Delete "${conv.title}"?`)) {
      onDelete();
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      className={`w-full text-left px-3 py-2.5 rounded-lg group transition-colors relative cursor-pointer ${
        isActive
          ? "bg-accent/10 text-text-primary border border-accent/20"
          : "text-text-secondary hover:bg-surface hover:text-text-primary border border-transparent"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[12.5px] font-medium leading-snug line-clamp-2 flex-1">{conv.title}</p>
        <button
          onClick={handleDelete}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:text-red-500 flex-shrink-0 mt-0.5 text-text-muted"
          title="Delete conversation"
        >
          <Trash2 size={12} />
        </button>
      </div>
      <div className="flex items-center gap-1.5 mt-1">
        {contextLabel && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-surface text-text-secondary border border-border">
            {contextLabel}
          </span>
        )}
        <span className="text-xs text-text-muted">{timeAgo(conv.updated_at)}</span>
        <span className="text-xs text-text-muted">· {conv.message_count} msgs</span>
      </div>
    </div>
  );
}
