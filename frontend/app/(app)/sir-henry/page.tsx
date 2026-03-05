"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { Plus, ArrowRight, Loader2, Sparkles, X, RefreshCw, Shield } from "lucide-react";
import {
  streamChatMessage,
  getConversations,
  getConversation,
  deleteConversation,
} from "@/lib/api";
import type { ChatMessage as ChatMessageType, ChatConversation } from "@/types/api";
import ChatMessage, { SirHenryAvatar, renderStreamingMarkdown, type DisplayMessage } from "@/components/chat/ChatMessage";
import ChatSuggestions from "@/components/chat/ChatSuggestions";
import ConsentModal from "@/components/chat/ConsentModal";
import DataPrivacyModal from "@/components/chat/DataPrivacyModal";
import ConversationList from "@/components/chat/ConversationList";
import { TOOL_ICONS } from "@/components/chat/constants";
import { getErrorMessage } from "@/lib/errors";

export default function SirHenryPage() {
  // Conversation history sidebar
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [convFilter, setConvFilter] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Active chat
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [activeTools, setActiveTools] = useState<{ tool: string; label: string; done: boolean }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showConsent, setShowConsent] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [showPrivacy, setShowPrivacy] = useState(false);

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

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 160) + "px";
    }
  }, [input]);

  // Focus input on mount
  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  // Load conversation history on mount
  useEffect(() => {
    loadConversations();
  }, []);

  async function loadConversations() {
    setHistoryLoading(true);
    try {
      const convs = await getConversations();
      setConversations(convs);
    } catch {
      // Silently ignore — backend may not be running
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadConversation(id: number) {
    setActiveConvId(id);
    setError(null);
    try {
      const detail = await getConversation(id);
      setMessages(
        detail.messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
          actions: m.actions_json ? JSON.parse(m.actions_json) : undefined,
          timestamp: new Date(m.created_at),
        }))
      );
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
  }

  async function handleDeleteConversation(id: number) {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConvId === id) {
        startNewConversation();
      }
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
  }

  function startNewConversation() {
    abortRef.current?.abort();
    setActiveConvId(null);
    setMessages([]);
    setStreamingText("");
    setActiveTools([]);
    setError(null);
    setTimeout(() => inputRef.current?.focus(), 50);
  }

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

    try {
      await streamChatMessage(
        apiMessages,
        { conversationId: activeConvId ?? undefined, pageContext: null },
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
          if (event.type === "done" && event.conversation_id != null) {
            setActiveConvId(event.conversation_id);
            loadConversations();
          }
          if (event.type === "error") {
            setError(event.message ?? "Something went wrong.");
          }
        },
        abort.signal,
      );

      if (accumulatedText) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: accumulatedText, timestamp: new Date() },
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

  const hasMessages = messages.length > 0;
  const isStreaming = loading && (streamingText.length > 0 || activeTools.length > 0);

  return (
    <div className="flex h-screen overflow-hidden bg-[#faf9f7]">

      {/* ── Left sidebar: conversation history ── */}
      <aside className="w-60 flex-shrink-0 border-r border-stone-200 flex flex-col bg-white">

        {/* Header */}
        <div className="px-4 py-4 border-b border-stone-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SirHenryAvatar size={8} />
            <span
              className="text-stone-900 font-semibold text-[13px]"
              style={{ fontFamily: "var(--font-display, sans-serif)" }}
            >
              Sir Henry
            </span>
          </div>
          <button
            onClick={startNewConversation}
            title="New conversation"
            className="p-1.5 rounded-lg hover:bg-stone-100 text-stone-400 hover:text-stone-700 transition-colors"
          >
            <Plus size={15} />
          </button>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-hidden">
          {historyLoading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 size={16} className="animate-spin text-stone-300" />
            </div>
          ) : (
            <ConversationList
              conversations={conversations}
              activeId={activeConvId}
              filter={convFilter}
              onFilterChange={setConvFilter}
              onSelect={loadConversation}
              onDelete={handleDeleteConversation}
            />
          )}
        </div>
      </aside>

      {/* ── Right: active chat ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Chat toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-stone-200 bg-white">
          <div className="text-[13px] text-stone-500">
            {activeConvId
              ? conversations.find((c) => c.id === activeConvId)?.title ?? "Conversation"
              : "New Conversation"}
          </div>
          {hasMessages && (
            <button
              onClick={startNewConversation}
              className="flex items-center gap-1.5 text-[12px] text-stone-400 hover:text-stone-700 transition-colors"
            >
              <RefreshCw size={13} />
              New chat
            </button>
          )}
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto bg-[#faf9f7]"
          style={{ scrollBehavior: "smooth" }}
        >
          {!hasMessages && !loading ? (
            <ChatSuggestions onSend={handleSend} dark={false} onPrivacy={() => setShowPrivacy(true)} />
          ) : (
            <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
              {messages.map((msg, i) => (
                <ChatMessage key={i} message={msg} dark={false} />
              ))}

              {/* Streaming: tool indicators */}
              {activeTools.length > 0 && (
                <div className="flex gap-3 items-start">
                  <SirHenryAvatar size={8} />
                  <div className="space-y-1.5">
                    {activeTools.map((t, i) => {
                      const Icon = TOOL_ICONS[t.tool as keyof typeof TOOL_ICONS];
                      return (
                        <div
                          key={i}
                          className={`flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-lg ${
                            t.done
                              ? "bg-green-50 text-green-700 border border-green-100"
                              : "bg-stone-100 text-stone-500"
                          }`}
                        >
                          {t.done
                            ? <span className="w-3.5 h-3.5 rounded-full bg-green-100 flex items-center justify-center"><span className="w-1.5 h-1.5 rounded-full bg-green-500" /></span>
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

              {/* Streaming: live text */}
              {streamingText && (
                <div className="flex gap-3 items-start">
                  <SirHenryAvatar size={8} />
                  <div className="flex-1 min-w-0 max-w-[90%]">
                    <div
                      className="prose-chat text-[14px] leading-relaxed text-stone-700"
                      dangerouslySetInnerHTML={{ __html: renderStreamingMarkdown(streamingText, false) }}
                    />
                    <span className="inline-block w-0.5 h-3.5 bg-[#16A34A] animate-pulse" />
                  </div>
                </div>
              )}

              {/* Thinking state (before any text or tools) */}
              {loading && !isStreaming && (
                <div className="flex gap-3 items-start">
                  <SirHenryAvatar size={8} />
                  <div className="flex gap-1 pt-2">
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="w-1.5 h-1.5 bg-stone-300 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <div className="flex gap-3 items-start">
                  <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                    <X size={15} className="text-red-500" />
                  </div>
                  <div className="bg-red-50 text-red-600 text-[13px] rounded-xl px-4 py-2.5 border border-red-200">
                    {error}
                    <button
                      onClick={() => setError(null)}
                      className="ml-2 text-red-400 hover:text-red-600 underline text-xs"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Quick follow-ups */}
        {hasMessages && !loading && (
          <div className="px-6 pt-2 pb-0 flex gap-2 overflow-x-auto scrollbar-hide border-t border-stone-200 bg-white">
            {["Tell me more", "Can you fix that?", "Show the details", "What else should I know?"].map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="flex-shrink-0 text-[11px] px-3 py-1.5 rounded-full bg-stone-100 text-stone-500 border border-stone-200 hover:bg-green-50 hover:text-green-700 hover:border-green-200 transition-all"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="px-6 py-4 border-t border-stone-200 bg-white">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-3 bg-white rounded-xl border border-stone-300 focus-within:border-[#16A34A] focus-within:ring-2 focus-within:ring-green-100 transition-all px-4 py-3 shadow-sm">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask Sir Henry anything about your finances..."
                rows={1}
                className="flex-1 resize-none text-[14px] bg-transparent focus:outline-none placeholder:text-stone-400 text-stone-800 max-h-[160px] leading-relaxed"
                style={{ minHeight: "24px" }}
                disabled={loading}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || loading}
                className="w-9 h-9 bg-[#16A34A] text-white rounded-lg flex items-center justify-center hover:bg-[#15803D] disabled:opacity-30 disabled:hover:bg-[#16A34A] transition-all flex-shrink-0"
              >
                {loading ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
              </button>
            </div>
            <div className="flex items-center justify-between mt-1.5 px-1">
              <p className="text-[10px] text-stone-400">Shift + Enter for new line</p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowPrivacy(true)}
                  className="text-[10px] text-stone-400 hover:text-[#16A34A] flex items-center gap-1 transition-colors"
                >
                  <Shield size={9} />
                  Your privacy
                </button>
                <p className="text-[10px] text-stone-400 flex items-center gap-1">
                  <Sparkles size={9} />
                  Sir Henry · Powered by Claude
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Privacy modal */}
      {showPrivacy && <DataPrivacyModal onClose={() => setShowPrivacy(false)} />}

      {/* Consent modal */}
      {showConsent && (
        <ConsentModal
          onAccept={() => {
            setShowConsent(false);
            if (pendingMessage) {
              const msg = pendingMessage;
              setPendingMessage(null);
              handleSend(msg);
            }
          }}
          onDecline={() => {
            setShowConsent(false);
            setPendingMessage(null);
          }}
        />
      )}
    </div>
  );
}
