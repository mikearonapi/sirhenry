import type { ChatMessage, ChatResponse, ChatConversation, ChatConversationDetail } from "@/types/api";
import { request, BASE } from "./api-client";

export interface SendChatOptions {
  conversationId?: number;
  pageContext?: string | null;
}

export function sendChatMessage(
  messages: ChatMessage[],
  options: SendChatOptions = {},
): Promise<ChatResponse> {
  return request("/chat/message", {
    method: "POST",
    body: JSON.stringify({
      messages,
      conversation_id: options.conversationId ?? null,
      page_context: options.pageContext ?? null,
    }),
  });
}

// ---------------------------------------------------------------------------
// Streaming chat — yields SSE events
// ---------------------------------------------------------------------------

export interface StreamEvent {
  type: "text_delta" | "tool_start" | "tool_done" | "done" | "error" | "requires_consent" | "learning";
  text?: string;
  tool?: string;
  label?: string;
  preview?: string;
  conversation_id?: number;
  actions?: unknown[];
  message?: string;
}

export async function streamChatMessage(
  messages: ChatMessage[],
  options: SendChatOptions,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages,
      conversation_id: options.conversationId ?? null,
      page_context: options.pageContext ?? null,
    }),
    signal,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    // Keep incomplete last line in buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6).trim();
      if (data === "[DONE]") return;
      try {
        const event = JSON.parse(data) as StreamEvent;
        onEvent(event);
      } catch {
        // Ignore malformed lines
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Conversation history CRUD
// ---------------------------------------------------------------------------

export function getConversations(): Promise<ChatConversation[]> {
  return request("/chat/conversations");
}

export function getConversation(id: number): Promise<ChatConversationDetail> {
  return request(`/chat/conversations/${id}`);
}

export function deleteConversation(id: number): Promise<void> {
  return request(`/chat/conversations/${id}`, { method: "DELETE" });
}
