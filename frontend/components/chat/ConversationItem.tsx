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
          ? "bg-[#16A34A]/10 text-stone-900 border border-[#16A34A]/20"
          : "text-stone-600 hover:bg-stone-100 hover:text-stone-900 border border-transparent"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[12.5px] font-medium leading-snug line-clamp-2 flex-1">{conv.title}</p>
        <button
          onClick={handleDelete}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:text-red-500 flex-shrink-0 mt-0.5 text-stone-400"
          title="Delete conversation"
        >
          <Trash2 size={12} />
        </button>
      </div>
      <div className="flex items-center gap-1.5 mt-1">
        {contextLabel && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-500 border border-stone-200">
            {contextLabel}
          </span>
        )}
        <span className="text-[10px] text-stone-400">{timeAgo(conv.updated_at)}</span>
        <span className="text-[10px] text-stone-300">· {conv.message_count} msgs</span>
      </div>
    </div>
  );
}
