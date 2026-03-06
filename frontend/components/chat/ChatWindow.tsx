"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import {
  X,
  Loader2,
  Sparkles,
  RefreshCw,
  Maximize2,
  Minimize2,
  ArrowRight,
} from "lucide-react";
import { streamChatMessage, getConversations, getConversation } from "@/lib/api";
import type { ChatMessage as ChatMessageType } from "@/types/api";
import ChatMessage, { SirHenryAvatar, renderMarkdown, renderStreamingMarkdown, type DisplayMessage } from "./ChatMessage";
import ChatSuggestions from "./ChatSuggestions";
import ConsentModal from "./ConsentModal";
import { TOOL_ICONS, TOOL_LABELS, TOOL_DONE_LABELS } from "./constants";
import SirHenryName from "@/components/ui/SirHenryName";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function derivePageContext(pathname: string): string | null {
  const segment = pathname.split("/")[1];
  const KNOWN = new Set([
    "goals", "budget", "cashflow", "transactions", "recurring",
    "portfolio", "retirement", "market", "equity-comp", "life-planner",
    "tax-strategy", "tax-documents", "setup", "accounts", "household",
    "life-events", "business", "insurance", "dashboard", "rules",
  ]);
  return KNOWN.has(segment) ? segment : null;
}

// ---------------------------------------------------------------------------
// Main chat component
// ---------------------------------------------------------------------------

export default function ChatWindow() {
  const pathname = usePathname();
  const pageContext = derivePageContext(pathname);
  const isSirHenryPage = pathname === "/sir-henry";

  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [streamingText, setStreamingText] = useState<string>("");
  const [activeTools, setActiveTools] = useState<{ tool: string; label: string; done: boolean }[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConsent, setShowConsent] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [learningMsg, setLearningMsg] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, loading, scrollToBottom]);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  // Reset conversation when navigating to a different page
  useEffect(() => {
    abortRef.current?.abort();
    setConversationId(null);
    setMessages([]);
    setStreamingText("");
    setActiveTools([]);
    setError(null);
    setOpen(false);
  }, [pathname]);

  // Load last conversation for this page context when the widget opens
  useEffect(() => {
    if (!open) return;
    if (messages.length > 0) return;

    getConversations()
      .then((convs) => {
        const match = convs.find((c) => c.page_context === pageContext);
        if (!match) return;
        return getConversation(match.id).then((detail) => {
          setConversationId(detail.id);
          setMessages(
            detail.messages.map((m) => ({
              role: m.role as "user" | "assistant",
              content: m.content,
              actions: m.actions_json ? JSON.parse(m.actions_json) : undefined,
              timestamp: new Date(m.created_at),
            }))
          );
        });
      })
      .catch(() => {/* Silently ignore — backend may not be running */});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Listen for "ask-henry" events from other pages
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.message) {
        setOpen(true);
        setTimeout(() => handleSend(detail.message), 300);
      }
    };
    window.addEventListener("ask-henry", handler);
    return () => window.removeEventListener("ask-henry", handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, conversationId]);

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
    setStreamingText("");
    setActiveTools([]);

    const userMsg: DisplayMessage = {
      role: "user",
      content: messageText,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    const abort = new AbortController();
    abortRef.current = abort;

    const apiMessages: ChatMessageType[] = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user" as const, content: messageText },
    ];

    let accumulatedText = "";
    let finalConvId = conversationId;

    try {
      await streamChatMessage(
        apiMessages,
        { conversationId: conversationId ?? undefined, pageContext },
        (event) => {
          if (event.type === "requires_consent") {
            setPendingMessage(messageText);
            setShowConsent(true);
            setMessages((prev) => prev.slice(0, -1));
            setLoading(false);
            return;
          }
          if (event.type === "text_delta" && event.text) {
            accumulatedText += event.text;
            setStreamingText(accumulatedText);
            scrollToBottom();
          }
          if (event.type === "tool_start" && event.tool) {
            setActiveTools((prev) => [
              ...prev,
              { tool: event.tool!, label: event.label ?? event.tool!, done: false },
            ]);
          }
          if (event.type === "tool_done" && event.tool) {
            setActiveTools((prev) =>
              prev.map((t) => (t.tool === event.tool ? { ...t, done: true, label: event.label ?? t.label } : t))
            );
          }
          if (event.type === "done") {
            if (event.conversation_id != null) {
              finalConvId = event.conversation_id;
              setConversationId(event.conversation_id);
            }
          }
          if (event.type === "learning" && event.message) {
            setLearningMsg(event.message);
            setTimeout(() => setLearningMsg(null), 4000);
          }
          if (event.type === "error") {
            setError(event.message ?? "Something went wrong.");
          }
        },
        abort.signal,
      );

      // Commit the streamed response to messages state
      if (accumulatedText) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: accumulatedText,
            timestamp: new Date(),
          },
        ]);
      }
      setStreamingText("");
      setActiveTools([]);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") return;
      let errMsg = "Something went wrong. Please try again.";
      if (e instanceof TypeError && (e.message === "Failed to fetch" || e.message.includes("NetworkError"))) {
        errMsg = "Can't reach the API server. Make sure the backend is running (docker compose up api).";
      } else if (e instanceof Error) {
        errMsg = e.message;
      }
      setError(errMsg);
    } finally {
      setLoading(false);
      setStreamingText("");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleClear() {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    setStreamingText("");
    setActiveTools([]);
    setError(null);
  }

  // Hide on the Sir Henry full-page chat (after all hooks)
  if (isSirHenryPage) return null;

  const hasMessages = messages.length > 0;
  const isStreaming = loading && (streamingText.length > 0 || activeTools.length > 0);

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
            <div className="absolute inset-0 bg-[#16A34A] rounded-full blur-lg opacity-20 group-hover:opacity-40 transition-opacity" />
            <div className="relative w-14 h-14 bg-[#0a0a0b] border border-zinc-700 text-white rounded-full shadow-xl hover:shadow-2xl transition-all hover:scale-105 flex items-center justify-center">
              <span className="text-white text-xl font-extrabold leading-none" style={{ fontFamily: "var(--font-display, sans-serif)" }}>H</span>
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
          {expanded && (
            <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40" onClick={() => setExpanded(false)} />
          )}

          <div className={`${panelClasses} bg-[#0a0a0b] shadow-2xl border border-zinc-800 flex flex-col z-50 overflow-hidden transition-all duration-300`}>

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#0a0a0b] border-b border-zinc-800 text-white">
              <div className="flex items-center gap-3">
                <SirHenryAvatar size={9} />
                <div>
                  <p className="font-semibold text-[14px] leading-tight" style={{ fontFamily: "var(--font-display, sans-serif)" }}><SirHenryName /></p>
                  <p className="text-[11px] text-zinc-500">Your AI financial advisor</p>
                </div>
              </div>
              <div className="flex items-center gap-0.5">
                {hasMessages && (
                  <button onClick={handleClear} className="p-2 hover:bg-white/10 rounded-lg transition-colors text-stone-400 hover:text-white" title="New conversation">
                    <RefreshCw size={15} />
                  </button>
                )}
                <button onClick={() => setExpanded(!expanded)} className="p-2 hover:bg-white/10 rounded-lg transition-colors text-stone-400 hover:text-white" title={expanded ? "Collapse" : "Expand"}>
                  {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                </button>
                <button onClick={() => { setOpen(false); setExpanded(false); }} className="p-2 hover:bg-white/10 rounded-lg transition-colors text-stone-400 hover:text-white">
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Messages area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto bg-[#0a0a0b]" style={{ scrollBehavior: "smooth" }}>
              {!hasMessages && !loading ? (
                <ChatSuggestions onSend={handleSend} />
              ) : (
                <div className="px-5 py-4 space-y-5">
                  {messages.map((msg, i) => (
                    <ChatMessage key={i} message={msg} />
                  ))}

                  {/* Streaming: tool indicators */}
                  {activeTools.length > 0 && (
                    <div className="flex gap-3 items-start">
                      <SirHenryAvatar size={8} />
                      <div className="space-y-1.5">
                        {activeTools.map((t, i) => {
                          const Icon = TOOL_ICONS[t.tool as keyof typeof TOOL_ICONS];
                          return (
                            <div key={i} className={`flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-lg ${t.done ? "bg-green-900/20 text-green-400" : "bg-zinc-800 text-zinc-400"}`}>
                              {t.done
                                ? <span className="w-3.5 h-3.5 rounded-full bg-green-500/20 flex items-center justify-center"><span className="w-1.5 h-1.5 rounded-full bg-green-400" /></span>
                                : <Loader2 size={12} className="animate-spin" />
                              }
                              {Icon && <Icon size={12} />}
                              <span>{t.label}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Learning indicator */}
                  {learningMsg && (
                    <div className="flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-lg bg-purple-900/20 text-purple-300 animate-in fade-in slide-in-from-bottom-1 ml-11">
                      <Sparkles size={12} className="text-purple-400 flex-shrink-0" />
                      <span>{learningMsg}</span>
                    </div>
                  )}

                  {/* Streaming: live text */}
                  {streamingText && (
                    <div className="flex gap-3 items-start">
                      <SirHenryAvatar size={8} />
                      <div className="flex-1 min-w-0 max-w-[90%]">
                        <div
                          className="prose-chat text-[13.5px] leading-relaxed text-zinc-300"
                          dangerouslySetInnerHTML={{ __html: renderStreamingMarkdown(streamingText, true) }}
                        />
                        <span className="inline-block w-0.5 h-3.5 bg-green-400 animate-pulse" />
                      </div>
                    </div>
                  )}

                  {/* Thinking state (before any text) */}
                  {loading && !isStreaming && (
                    <div className="flex gap-3 items-start">
                      <SirHenryAvatar size={8} />
                      <div className="flex gap-1 pt-2">
                        {[0, 1, 2].map((i) => (
                          <span key={i} className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Error */}
                  {error && (
                    <div className="flex gap-3 items-start">
                      <div className="w-8 h-8 rounded-full bg-red-900/30 flex items-center justify-center flex-shrink-0">
                        <X size={15} className="text-red-400" />
                      </div>
                      <div className="bg-red-900/20 text-red-400 text-[13px] rounded-xl px-4 py-2.5 border border-red-900/50">
                        {error}
                        <button onClick={() => setError(null)} className="ml-2 text-red-500 hover:text-red-300 underline text-xs">Dismiss</button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Quick follow-up suggestions */}
            {hasMessages && !loading && (
              <div className="px-4 pt-2 pb-0 flex gap-1.5 overflow-x-auto scrollbar-hide bg-[#0a0a0b] border-t border-zinc-800">
                {["Tell me more", "Can you fix that?", "Show the details", "What else should I know?"].map((q) => (
                  <button key={q} onClick={() => handleSend(q)} className="flex-shrink-0 text-[11px] px-3 py-1.5 rounded-full bg-zinc-900 text-zinc-500 border border-zinc-800 hover:bg-green-900/20 hover:text-green-400 hover:border-green-800/50 transition-all">
                    {q}
                  </button>
                ))}
              </div>
            )}

            {/* Input area */}
            <div className="border-t border-zinc-800 px-4 py-3 bg-[#0a0a0b]">
              <div className="flex items-end gap-2.5 bg-[#141416] rounded-xl border border-zinc-700 focus-within:border-zinc-500 focus-within:shadow-[0_0_0_3px_rgba(255,255,255,0.04)] transition-all px-3 py-2">
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
                <p className="text-[10px] text-zinc-700">Shift + Enter for new line</p>
                <p className="text-[10px] text-zinc-700 flex items-center gap-1"><Sparkles size={9} /> <SirHenryName /> · Powered by Claude</p>
              </div>
            </div>
          </div>
        </>
      )}

      {showConsent && (
        <ConsentModal
          onAccept={() => {
            setShowConsent(false);
            if (pendingMessage) { const msg = pendingMessage; setPendingMessage(null); handleSend(msg); }
          }}
          onDecline={() => { setShowConsent(false); setPendingMessage(null); }}
        />
      )}
    </>
  );
}
