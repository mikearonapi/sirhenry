"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  X,
  Loader2,
  Sparkles,
  RefreshCw,
  Maximize2,
  Minimize2,
  ArrowRight,
} from "lucide-react";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage as ChatMessageType } from "@/types/api";
import ChatMessage, { SirHenryAvatar, type DisplayMessage } from "./ChatMessage";
import ChatToolCall from "./ChatToolCall";
import ChatSuggestions from "./ChatSuggestions";

// ---------------------------------------------------------------------------
// Main chat component
// ---------------------------------------------------------------------------

export default function ChatWindow() {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + "px";
    }
  }, [input]);

  async function handleSend(text?: string) {
    const messageText = text || input.trim();
    if (!messageText || loading) return;

    setInput("");
    setError(null);

    const userMsg: DisplayMessage = {
      role: "user",
      content: messageText,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const apiMessages: ChatMessageType[] = [
        ...messages.map((m) => ({ role: m.role, content: m.content })),
        { role: "user" as const, content: messageText },
      ];

      const result = await sendChatMessage(apiMessages);

      const assistantMsg: DisplayMessage = {
        role: "assistant",
        content: result.response,
        actions: result.actions,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "Something went wrong. Please try again.";
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleClear() {
    setMessages([]);
    setError(null);
  }

  const hasMessages = messages.length > 0;

  // Panel sizing
  const panelClasses = expanded
    ? "fixed inset-4 rounded-2xl"
    : "fixed bottom-6 right-6 w-[460px] h-[640px] rounded-2xl";

  return (
    <>
      {/* Floating trigger button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 group z-50"
        >
          <div className="relative">
            <div className="absolute inset-0 bg-[#EAB308] rounded-full blur-lg opacity-20 group-hover:opacity-40 transition-opacity" />
            <div className="relative w-14 h-14 bg-[#0a0a0b] border border-[#EAB308]/50 text-white rounded-full shadow-xl hover:shadow-2xl transition-all hover:scale-105 flex items-center justify-center">
              <span className="text-[#EAB308] text-xl font-bold leading-none" style={{ fontFamily: "var(--font-display, sans-serif)" }}>H</span>
            </div>
            {messages.length > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-green-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center shadow-sm ring-2 ring-white">
                {messages.filter((m) => m.role === "assistant").length}
              </span>
            )}
          </div>
          <div className="absolute bottom-full right-0 mb-2 px-3 py-1.5 bg-[#0a0a0b] text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none shadow-lg border border-zinc-800">
            Ask Sir Henry
            <div className="absolute top-full right-5 w-2 h-2 bg-[#0a0a0b] rotate-45 -mt-1 border-r border-b border-zinc-800" />
          </div>
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <>
          {/* Backdrop for expanded mode */}
          {expanded && (
            <div
              className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
              onClick={() => setExpanded(false)}
            />
          )}

          <div className={`${panelClasses} bg-[#0a0a0b] shadow-2xl border border-zinc-800 flex flex-col z-50 overflow-hidden transition-all duration-300`}>

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#0a0a0b] border-b border-zinc-800 text-white">
              <div className="flex items-center gap-3">
                <SirHenryAvatar size={9} />
                <div>
                  <p className="font-semibold text-[14px] leading-tight" style={{ fontFamily: "var(--font-display, sans-serif)" }}>Sir Henry</p>
                  <p className="text-[11px] text-zinc-500">Your AI financial advisor</p>
                </div>
              </div>
              <div className="flex items-center gap-0.5">
                {hasMessages && (
                  <button
                    onClick={handleClear}
                    className="p-2 hover:bg-white/10 rounded-lg transition-colors text-stone-400 hover:text-white"
                    title="New conversation"
                  >
                    <RefreshCw size={15} />
                  </button>
                )}
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors text-stone-400 hover:text-white"
                  title={expanded ? "Collapse" : "Expand"}
                >
                  {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                </button>
                <button
                  onClick={() => { setOpen(false); setExpanded(false); }}
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors text-stone-400 hover:text-white"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Messages area */}
            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto bg-[#0a0a0b]"
              style={{ scrollBehavior: "smooth" }}
            >
              {!hasMessages && !loading ? (
                <ChatSuggestions onSend={handleSend} />
              ) : (
                <div className="px-5 py-4 space-y-5">
                  {messages.map((msg, i) => (
                    <ChatMessage key={i} message={msg} />
                  ))}

                  {/* Loading / thinking state */}
                  {loading && <ChatToolCall />}

                  {/* Error display */}
                  {error && (
                    <div className="flex gap-3 items-start">
                      <div className="w-8 h-8 rounded-full bg-red-900/30 flex items-center justify-center flex-shrink-0">
                        <X size={15} className="text-red-400" />
                      </div>
                      <div className="bg-red-900/20 text-red-400 text-[13px] rounded-xl px-4 py-2.5 border border-red-900/50">
                        {error}
                        <button
                          onClick={() => setError(null)}
                          className="ml-2 text-red-500 hover:text-red-300 underline text-xs"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Quick follow-up suggestions */}
            {hasMessages && !loading && (
              <div className="px-4 pt-2 pb-0 flex gap-1.5 overflow-x-auto scrollbar-hide bg-[#0a0a0b] border-t border-zinc-800">
                {[
                  "Tell me more",
                  "Can you fix that?",
                  "Show the details",
                  "What else should I know?",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="flex-shrink-0 text-[11px] px-3 py-1.5 rounded-full bg-zinc-900 text-zinc-500 border border-zinc-800 hover:bg-green-900/20 hover:text-green-400 hover:border-green-800/50 transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            {/* Input area */}
            <div className="border-t border-zinc-800 px-4 py-3 bg-[#0a0a0b]">
              <div className="flex items-end gap-2.5 bg-[#141416] rounded-xl border border-zinc-700 focus-within:border-[#16A34A] focus-within:ring-2 focus-within:ring-green-900/30 transition-all px-3 py-2">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Henry anything about your finances..."
                  rows={1}
                  className="flex-1 resize-none text-[13.5px] bg-transparent focus:outline-none placeholder:text-zinc-600 text-zinc-200 max-h-[120px] leading-relaxed"
                  style={{ minHeight: "24px" }}
                  disabled={loading}
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading}
                  className="w-8 h-8 bg-[#16A34A] text-white rounded-lg flex items-center justify-center hover:bg-[#15803D] disabled:opacity-30 disabled:hover:bg-[#16A34A] transition-all flex-shrink-0"
                >
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
                </button>
              </div>
              <div className="flex items-center justify-between mt-1.5 px-1">
                <p className="text-[10px] text-zinc-700">
                  Shift + Enter for new line
                </p>
                <p className="text-[10px] text-zinc-700 flex items-center gap-1">
                  <Sparkles size={9} />
                  Sir Henry · Powered by Claude
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
