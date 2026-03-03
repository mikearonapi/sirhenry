import type { ChatMessage, ChatResponse } from "@/types/api";
import { request } from "./api-client";

export function sendChatMessage(messages: ChatMessage[]): Promise<ChatResponse> {
  return request("/chat/message", {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}
