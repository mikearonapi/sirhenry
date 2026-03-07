"use client";
import { Component, type ReactNode, type ErrorInfo } from "react";
import { RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("sirhenry:render-error", {
          detail: {
            message: error.message,
            stack: error.stack,
            componentStack: errorInfo.componentStack,
          },
        }),
      );
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex items-center justify-center min-h-[50vh]">
          <div className="text-center max-w-md px-6">
            <h2 className="text-lg font-semibold text-text-primary mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-text-secondary mb-4">
              {this.state.error?.message || "An unexpected error occurred."}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover transition-colors"
            >
              <RefreshCw size={14} />
              Reload
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
