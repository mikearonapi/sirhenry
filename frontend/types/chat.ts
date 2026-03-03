export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatAction {
  tool: string;
  input: Record<string, unknown>;
  result_preview: string;
}

export interface ChatResponse {
  response: string;
  actions: ChatAction[];
  tool_calls_made: number;
}
