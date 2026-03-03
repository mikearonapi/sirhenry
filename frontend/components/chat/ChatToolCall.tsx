"use client";
import { Loader2, CheckCircle2, Search } from "lucide-react";
import { SirHenryAvatar } from "./ChatMessage";
import { TOOL_ICONS, TOOL_LABELS, TOOL_DONE_LABELS } from "./constants";

// ---------------------------------------------------------------------------
// ThinkingIndicator — shows tool invocations while the assistant is working
// ---------------------------------------------------------------------------

export interface ChatToolCallProps {
  actions?: { tool: string; status: "running" | "done" }[];
}

export default function ChatToolCall({ actions }: ChatToolCallProps) {
  return (
    <div className="flex gap-3 items-start">
      <SirHenryAvatar size={8} />
      <div className="flex-1 min-w-0">
        {actions && actions.length > 0 ? (
          <div className="space-y-1.5">
            {actions.map((a, i) => {
              const Icon = TOOL_ICONS[a.tool] || Search;
              const label = a.status === "running"
                ? TOOL_LABELS[a.tool] || a.tool
                : TOOL_DONE_LABELS[a.tool] || a.tool;
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  {a.status === "running" ? (
                    <div className="w-5 h-5 rounded-full bg-green-900/30 flex items-center justify-center">
                      <Loader2 size={11} className="animate-spin text-green-400" />
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full bg-green-900/30 flex items-center justify-center">
                      <CheckCircle2 size={11} className="text-green-400" />
                    </div>
                  )}
                  <Icon size={12} className={a.status === "running" ? "text-green-400" : "text-zinc-500"} />
                  <span className={a.status === "running" ? "text-zinc-400" : "text-zinc-600"}>
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex items-center gap-2.5">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            <span className="text-xs text-zinc-500">Henry is thinking...</span>
          </div>
        )}
      </div>
    </div>
  );
}
