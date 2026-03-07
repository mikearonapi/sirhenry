"use client";
import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { CapturedError } from "@/types/errors";
import ErrorToast from "./ErrorToast";

interface ErrorContextValue {
  captureError: (
    error: unknown,
    errorType: CapturedError["error_type"],
    context?: Record<string, unknown>,
  ) => void;
}

const ErrorContext = createContext<ErrorContextValue>({
  captureError: () => {},
});

export function useErrorCapture() {
  return useContext(ErrorContext);
}

const MAX_QUEUE = 5;

export default function ErrorProvider({ children }: { children: ReactNode }) {
  const [errors, setErrors] = useState<CapturedError[]>([]);
  const seenIds = useRef(new Set<string>());

  const captureError = useCallback(
    (
      error: unknown,
      errorType: CapturedError["error_type"],
      context?: Record<string, unknown>,
    ) => {
      const message =
        error instanceof Error ? error.message : String(error ?? "Unknown error");
      const stack = error instanceof Error ? error.stack : undefined;

      // Dedup: skip if same message seen in last 5 seconds
      const dedup = `${errorType}:${message}`;
      if (seenIds.current.has(dedup)) return;
      seenIds.current.add(dedup);
      setTimeout(() => seenIds.current.delete(dedup), 5000);

      const entry: CapturedError = {
        id: crypto.randomUUID(),
        error_type: errorType,
        message,
        stack,
        source_url:
          typeof window !== "undefined" ? window.location.pathname : "",
        context,
        timestamp: Date.now(),
      };
      setErrors((prev) => [entry, ...prev].slice(0, MAX_QUEUE));
    },
    [],
  );

  // Global handlers for uncaught errors
  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      captureError(event.error || event.message, "window_error", {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      });
    };
    const handleRejection = (event: PromiseRejectionEvent) => {
      captureError(event.reason, "unhandled_rejection");
    };

    // Listen for custom events from api-client and ErrorBoundary
    const handleApiError = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      captureError(new Error(detail.message), "api_error", {
        path: detail.path,
        status: detail.status,
      });
    };
    const handleRenderError = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      const err = new Error(detail.message);
      err.stack = detail.stack;
      captureError(err, "render_error", {
        componentStack: detail.componentStack?.slice(0, 500),
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleRejection);
    window.addEventListener("sirhenry:api-error", handleApiError);
    window.addEventListener("sirhenry:render-error", handleRenderError);
    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleRejection);
      window.removeEventListener("sirhenry:api-error", handleApiError);
      window.removeEventListener("sirhenry:render-error", handleRenderError);
    };
  }, [captureError]);

  const dismiss = useCallback((id: string) => {
    setErrors((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const current = errors[0] ?? null;

  return (
    <ErrorContext.Provider value={{ captureError }}>
      {children}
      {current && <ErrorToast error={current} onDismiss={dismiss} />}
    </ErrorContext.Provider>
  );
}
