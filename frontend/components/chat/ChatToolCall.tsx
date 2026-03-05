"use client";
import { useState, useEffect } from "react";
import { Loader2, CheckCircle2, Search } from "lucide-react";
import { SirHenryAvatar } from "./ChatMessage";
import { TOOL_ICONS, TOOL_LABELS, TOOL_DONE_LABELS } from "./constants";

const THINKING_MESSAGES = [
  "Searching your financial data...",
  "Analyzing transactions...",
  "Reviewing your accounts...",
  "Calculating insights...",
  "Preparing your response...",
];

export interface ChatToolCallProps {
  actions?: { tool: string; status: "running" | "done" }[];
  dark?: boolean;
}

export default function ChatToolCall({ actions, dark = true }: ChatToolCallProps) {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    if (actions && actions.length > 0) return;
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % THINKING_MESSAGES.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [actions]);

  const ringBg = dark ? "bg-green-900/30" : "bg-green-100";
  const iconActive = dark ? "text-green-400" : "text-green-600";
  const iconDone = dark ? "text-zinc-500" : "text-stone-400";
  const labelActive = dark ? "text-zinc-400" : "text-stone-600";
  const labelDone = dark ? "text-zinc-600" : "text-stone-400";
  const thinkingText = dark ? "text-zinc-500" : "text-stone-500";

  return (
    <div className="flex gap-3 items-start">
      <SirHenryAvatar size={8} />
      <div className="flex-1 min-w-0">
        {actions && actions.length > 0 ? (
          <div className="space-y-1.5">
            {actions.map((a, i) => {
              const Icon = TOOL_ICONS[a.tool] || Search;
              const label =
                a.status === "running"
                  ? TOOL_LABELS[a.tool] || a.tool
                  : TOOL_DONE_LABELS[a.tool] || a.tool;
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <div className={`w-5 h-5 rounded-full ${ringBg} flex items-center justify-center`}>
                    {a.status === "running" ? (
                      <Loader2 size={11} className={`animate-spin ${iconActive}`} />
                    ) : (
                      <CheckCircle2 size={11} className={iconActive} />
                    )}
                  </div>
                  <Icon size={12} className={a.status === "running" ? iconActive : iconDone} />
                  <span className={a.status === "running" ? labelActive : labelDone}>{label}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex items-center gap-2.5 py-1">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            <span className={`text-xs transition-all duration-500 ${thinkingText}`}>
              {THINKING_MESSAGES[msgIndex]}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
