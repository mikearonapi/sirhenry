"use client";
import type { ChatConversation } from "@/types/api";
import ConversationItem from "./ConversationItem";

const FILTER_TABS = [
  { key: null, label: "All" },
  { key: "goals", label: "Goals" },
  { key: "budget", label: "Budget" },
  { key: "cashflow", label: "Cash Flow" },
  { key: "transactions", label: "Transactions" },
  { key: "portfolio", label: "Portfolio" },
  { key: "retirement", label: "Retirement" },
  { key: "tax-strategy", label: "Tax Strategy" },
  { key: "tax-documents", label: "Tax Docs" },
  { key: "dashboard", label: "Dashboard" },
] as const;

interface Props {
  conversations: ChatConversation[];
  activeId: number | null;
  filter: string | null;
  onFilterChange: (f: string | null) => void;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}

export default function ConversationList({
  conversations,
  activeId,
  filter,
  onFilterChange,
  onSelect,
  onDelete,
}: Props) {
  const presentContexts = new Set(conversations.map((c) => c.page_context));
  const visibleTabs = FILTER_TABS.filter(
    (t) => t.key === null || presentContexts.has(t.key)
  );

  const filtered =
    filter === null
      ? conversations
      : conversations.filter((c) => c.page_context === filter);

  return (
    <div className="flex flex-col h-full">
      {/* Filter tabs */}
      {visibleTabs.length > 1 && (
        <div className="flex gap-1 px-2 py-2 overflow-x-auto scrollbar-hide flex-shrink-0 border-b border-card-border">
          {visibleTabs.map((tab) => (
            <button
              key={String(tab.key)}
              onClick={() => onFilterChange(tab.key)}
              className={`flex-shrink-0 text-xs px-2.5 py-1 rounded-full transition-colors ${
                filter === tab.key
                  ? "bg-accent/15 text-accent border border-accent/30"
                  : "bg-surface text-text-secondary hover:text-text-secondary hover:bg-surface"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 pt-1 space-y-0.5">
        {filtered.length === 0 ? (
          <p className="text-[12px] text-text-muted text-center py-6 px-3">
            No conversations yet
          </p>
        ) : (
          filtered.map((conv) => (
            <ConversationItem
              key={conv.id}
              conv={conv}
              isActive={conv.id === activeId}
              onClick={() => onSelect(conv.id)}
              onDelete={() => onDelete(conv.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
