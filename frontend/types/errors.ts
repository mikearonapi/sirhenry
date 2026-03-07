export interface CapturedError {
  id: string;
  error_type: "render_error" | "unhandled_rejection" | "api_error" | "window_error";
  message: string;
  stack?: string;
  source_url: string;
  context?: Record<string, unknown>;
  timestamp: number;
}

export interface ErrorReportPayload {
  error_type: string;
  message: string;
  stack_trace?: string;
  source_url: string;
  user_note?: string;
  context?: Record<string, unknown>;
}

export interface ErrorReportOut {
  id: number;
  timestamp: string;
  error_type: string;
  message: string | null;
  stack_trace: string | null;
  source_url: string | null;
  user_agent: string | null;
  user_note: string | null;
  status: string;
  context_json: string | null;
}
