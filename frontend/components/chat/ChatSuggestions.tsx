"use client";
import { useState } from "react";
import {
  Search,
  FileEdit,
  BarChart3,
  PiggyBank,
  Lightbulb,
  ChevronRight,
} from "lucide-react";
import {
  SUGGESTION_CATEGORIES,
  SUGGESTION_CATEGORIES_DARK,
} from "./constants";

// ---------------------------------------------------------------------------
// WelcomeScreen — shown when there are no messages yet
// ---------------------------------------------------------------------------

export interface ChatSuggestionsProps {
  onSend: (text: string) => void;
}

export default function ChatSuggestions({ onSend }: ChatSuggestionsProps) {
  const [activeCategory, setActiveCategory] = useState(0);

  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-8 bg-[#0a0a0b]">
      {/* Hero */}
      <div className="w-16 h-16 rounded-2xl bg-[#141416] border border-[#EAB308]/30 flex items-center justify-center mb-4 shadow-lg shadow-yellow-900/20">
        <span className="text-[#EAB308] text-3xl font-bold leading-none" style={{ fontFamily: "var(--font-display, sans-serif)" }}>H</span>
      </div>
      <h2 className="text-lg font-bold text-zinc-100 mb-1" style={{ fontFamily: "var(--font-display, sans-serif)" }}>Sir Henry</h2>
      <p className="text-sm text-zinc-500 text-center max-w-sm mb-6">
        Your AI financial advisor. Ask anything about your finances — I know your full picture.
      </p>

      {/* Quick actions grid */}
      <div className="w-full max-w-md grid grid-cols-4 gap-2 mb-5">
        {SUGGESTION_CATEGORIES_DARK.map((cat, i) => {
          const Icon = cat.icon;
          return (
            <button
              key={cat.label}
              onClick={() => setActiveCategory(i)}
              className={`flex flex-col items-center gap-1.5 px-2 py-2.5 rounded-xl text-[11px] font-medium transition-all border ${
                activeCategory === i
                  ? `${cat.bgColor} ${cat.color} shadow-sm`
                  : "bg-[#141416] text-zinc-500 border-zinc-800 hover:bg-zinc-800"
              }`}
            >
              <Icon size={18} />
              {cat.label}
            </button>
          );
        })}
      </div>

      {/* Suggestions for active category */}
      <div className="w-full max-w-md space-y-1.5">
        {SUGGESTION_CATEGORIES[activeCategory].suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onSend(s)}
            className="w-full flex items-center gap-3 text-left text-[13px] px-4 py-2.5 rounded-xl bg-[#141416] border border-zinc-800 text-zinc-300 hover:border-green-700/50 hover:bg-green-900/20 hover:text-green-300 transition-all group"
          >
            <Lightbulb size={14} className="text-zinc-600 group-hover:text-green-400 flex-shrink-0 transition-colors" />
            <span className="flex-1">{s}</span>
            <ChevronRight size={14} className="text-zinc-700 group-hover:text-green-400 transition-colors" />
          </button>
        ))}
      </div>

      {/* Capabilities footer */}
      <div className="mt-6 flex items-center gap-4 text-[10px] text-zinc-700">
        <span className="flex items-center gap-1"><Search size={10} /> Search</span>
        <span className="flex items-center gap-1"><FileEdit size={10} /> Recategorize</span>
        <span className="flex items-center gap-1"><BarChart3 size={10} /> Analyze</span>
        <span className="flex items-center gap-1"><PiggyBank size={10} /> Advise</span>
      </div>
    </div>
  );
}
