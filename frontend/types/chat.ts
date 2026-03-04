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
