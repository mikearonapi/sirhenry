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
  response: string | null;
  requires_consent?: boolean;
  actions: ChatAction[];
  tool_calls_made: number;
  conversation_id?: number;
}

export interface ChatConversation {
  id: number;
  title: string;
  page_context: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessageRecord {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  actions_json: string | null;
  created_at: string;
}

export interface ChatConversationDetail extends ChatConversation {
  messages: ChatMessageRecord[];
}

export interface PrivacyConsent {
  id: number;
  consent_type: string;
  consented: boolean;
  consent_version: string;
  consented_at: string | null;
}

export interface PrivacyDisclosure {
  data_handling: string[];
  ai_privacy: string[];
  encryption: string[];
  data_retention: string[];
}
