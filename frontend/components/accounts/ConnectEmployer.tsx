"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Briefcase, Loader2, CheckCircle, AlertCircle, RefreshCw,
  ArrowRight, X,
} from "lucide-react";
import { usePlaidLink } from "react-plaid-link";
import type { PlaidLinkError } from "react-plaid-link";
import {
  getIncomeLinkToken, notifyIncomeConnected,
  getIncomeConnections, getIncomeCascadeSummary,
} from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import type { IncomeConnection, IncomeCascadeSummary } from "@/types/api";

interface ConnectEmployerProps {
  onConnectionComplete?: () => void;
}

type ConnectionState = "idle" | "connecting" | "syncing" | "done" | "error";

const DATA_FLOW_BADGES = [
  { label: "Household", href: "/household" },
  { label: "Benefits", href: "/insurance" },
  { label: "Tax Docs", href: "/tax-documents" },
  { label: "Retirement", href: "/retirement" },
] as const;

const STATUS_BADGES: Record<IncomeConnection["status"], { label: string; className: string }> = {
  pending: { label: "Pending", className: "bg-amber-50 text-amber-700 border-amber-200" },
  syncing: { label: "Syncing", className: "bg-blue-50 text-blue-700 border-blue-200" },
  active: { label: "Active", className: "bg-green-50 text-green-700 border-green-200" },
  error: { label: "Error", className: "bg-red-50 text-red-700 border-red-200" },
};

export default function ConnectEmployer({ onConnectionComplete }: ConnectEmployerProps) {
  const [connections, setConnections] = useState<IncomeConnection[]>([]);
  const [cascadeSummaries, setCascadeSummaries] = useState<Map<number, IncomeCascadeSummary>>(new Map());
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [pendingConnectionId, setPendingConnectionId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingConnections, setLoadingConnections] = useState(true);

  // Load existing connections on mount
  useEffect(() => {
    loadConnections();
  }, []);

  async function loadConnections() {
    setLoadingConnections(true);
    try {
      const conns = await getIncomeConnections();
      setConnections(conns);

      // Fetch cascade summaries for active connections
      const summaries = new Map<number, IncomeCascadeSummary>();
      const activeConns = conns.filter((c) => c.status === "active");
      const results = await Promise.allSettled(
        activeConns.map((c) => getIncomeCascadeSummary(c.id)),
      );
      results.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          summaries.set(activeConns[idx].id, result.value);
        }
      });
      setCascadeSummaries(summaries);
    } catch (e: unknown) {
      // Non-critical — connections list just stays empty
      console.error("Failed to load income connections:", getErrorMessage(e));
    } finally {
      setLoadingConnections(false);
    }
  }

  // Plaid Link success handler
  const onPlaidSuccess = useCallback(async () => {
    setLinkToken(null);
    if (pendingConnectionId === null) return;

    setConnectionState("syncing");
    try {
      await notifyIncomeConnected(pendingConnectionId);
      // Poll for status until active or error
      await pollConnectionStatus(pendingConnectionId);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
      setConnectionState("error");
    }
  }, [pendingConnectionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const onPlaidExit = useCallback((err: PlaidLinkError | null) => {
    setLinkToken(null);
    if (err) {
      setError(err.display_message || err.error_message || "Payroll connection was cancelled.");
      setConnectionState("error");
    } else {
      setConnectionState("idle");
    }
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: onPlaidSuccess,
    onExit: onPlaidExit,
  });

  useEffect(() => {
    if (linkToken && ready) open();
  }, [linkToken, ready, open]);

  async function pollConnectionStatus(connectionId: number) {
    const maxAttempts = 20;
    const intervalMs = 3000;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
      try {
        const conns = await getIncomeConnections();
        const conn = conns.find((c) => c.id === connectionId);
        if (!conn) continue;

        if (conn.status === "active") {
          setConnections(conns);
          // Fetch cascade summary for the new connection
          try {
            const summary = await getIncomeCascadeSummary(connectionId);
            setCascadeSummaries((prev) => {
              const next = new Map(prev);
              next.set(connectionId, summary);
              return next;
            });
          } catch {
            // Summary fetch is non-critical
          }
          setConnectionState("done");
          setPendingConnectionId(null);
          onConnectionComplete?.();
          return;
        }

        if (conn.status === "error") {
          setError("Payroll sync failed. Please try again.");
          setConnectionState("error");
          setPendingConnectionId(null);
          return;
        }
        // Still syncing — continue polling
      } catch {
        // Transient network error — keep polling
      }
    }

    // Timed out
    setError("Payroll sync is taking longer than expected. Check back shortly.");
    setConnectionState("done");
    setPendingConnectionId(null);
    await loadConnections();
  }

  async function handleConnect() {
    setError(null);
    setConnectionState("connecting");
    try {
      const data = await getIncomeLinkToken("payroll");
      setPendingConnectionId(data.connection_id);
      setLinkToken(data.link_token);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
      setConnectionState("error");
    }
  }

  function handleRetry() {
    setError(null);
    setConnectionState("idle");
    handleConnect();
  }

  function dismissError() {
    setError(null);
    if (connectionState === "error") setConnectionState("idle");
  }

  const activeConnections = connections.filter((c) => c.status === "active");
  const hasConnections = activeConnections.length > 0;

  return (
    <div className="bg-card border border-card-border rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-5 pb-4 flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center shrink-0">
          <Briefcase size={18} className="text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-text-primary">Connect Your Employer</h3>
          <p className="text-xs text-text-secondary mt-0.5">
            Link your payroll provider to auto-import income, benefits, and tax withholdings
          </p>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-5 mb-3 bg-red-50 text-red-700 rounded-lg p-3 flex items-center gap-2 border border-red-100">
          <AlertCircle size={15} className="shrink-0" />
          <p className="text-xs flex-1">{error}</p>
          <button onClick={dismissError} className="text-red-400 hover:text-red-600">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Loading state */}
      {loadingConnections ? (
        <div className="px-5 pb-5 flex items-center gap-2 text-text-muted">
          <Loader2 size={14} className="animate-spin" />
          <span className="text-xs">Loading connections...</span>
        </div>
      ) : (
        <>
          {/* Existing active connections */}
          {hasConnections && (
            <div className="px-5 pb-3 space-y-3">
              {activeConnections.map((conn) => {
                const summary = cascadeSummaries.get(conn.id);
                const badge = STATUS_BADGES[conn.status];
                return (
                  <div key={conn.id} className="border border-card-border rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-accent" />
                        <span className="text-sm font-medium text-text-primary">
                          {conn.employer_name ?? "Employer"}
                        </span>
                      </div>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${badge.className}`}>
                        {badge.label}
                      </span>
                    </div>

                    {conn.last_synced_at && (
                      <p className="text-xs text-text-muted mb-2">
                        Last synced {new Date(conn.last_synced_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric", year: "numeric",
                        })}
                      </p>
                    )}

                    {/* Cascade summary */}
                    {summary && (
                      <div className="bg-surface rounded-lg p-3 mb-2">
                        <p className="text-xs font-medium text-text-secondary mb-1.5">
                          Imported from {summary.employer ?? "employer"}:
                        </p>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
                          {summary.annual_income != null && summary.annual_income > 0 && (
                            <span>
                              <span className="font-mono font-medium text-text-primary">
                                {formatCurrency(summary.annual_income, true)}
                              </span>
                              {" "}salary
                            </span>
                          )}
                          {summary.pay_stubs_imported > 0 && (
                            <span>{summary.pay_stubs_imported} pay stubs</span>
                          )}
                          {summary.benefits_detected.length > 0 && (
                            <span>{summary.benefits_detected.join(", ")}</span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Data flow badges */}
                    <div className="flex flex-wrap gap-1.5">
                      <span className="text-xs text-text-muted leading-5">Data flowing to:</span>
                      {DATA_FLOW_BADGES.map((b) => (
                        <a
                          key={b.href}
                          href={b.href}
                          className="inline-flex items-center gap-1 text-xs font-medium text-accent bg-green-50 hover:bg-green-100 px-2 py-0.5 rounded-full transition-colors"
                        >
                          {b.label}
                          <ArrowRight size={9} />
                        </a>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Non-active connections (pending/syncing/error) */}
          {connections.filter((c) => c.status !== "active").length > 0 && (
            <div className="px-5 pb-3 space-y-2">
              {connections.filter((c) => c.status !== "active").map((conn) => {
                const badge = STATUS_BADGES[conn.status];
                return (
                  <div key={conn.id} className="flex items-center gap-2 border border-card-border rounded-lg p-3">
                    {conn.status === "syncing" && <Loader2 size={14} className="animate-spin text-blue-500" />}
                    {conn.status === "error" && <AlertCircle size={14} className="text-red-500" />}
                    {conn.status === "pending" && <Loader2 size={14} className="animate-spin text-amber-500" />}
                    <span className="text-sm text-text-secondary flex-1">
                      {conn.employer_name ?? "Employer"}
                    </span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${badge.className}`}>
                      {badge.label}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Syncing state */}
          {connectionState === "syncing" && (
            <div className="mx-5 mb-3 bg-blue-50 rounded-lg p-3 flex items-center gap-2 border border-blue-100">
              <Loader2 size={14} className="animate-spin text-blue-600" />
              <span className="text-xs text-blue-700 font-medium">Syncing payroll data...</span>
            </div>
          )}

          {/* Connect CTA */}
          <div className="px-5 pb-5">
            {connectionState === "error" ? (
              <button
                onClick={handleRetry}
                className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm transition-colors"
              >
                <RefreshCw size={14} />
                Retry connection
              </button>
            ) : connectionState === "connecting" ? (
              <button
                disabled
                className="flex items-center gap-2 bg-surface text-text-secondary px-4 py-2 rounded-lg text-sm font-medium cursor-not-allowed"
              >
                <Loader2 size={14} className="animate-spin" />
                Opening Plaid...
              </button>
            ) : connectionState === "syncing" ? (
              <button
                disabled
                className="flex items-center gap-2 bg-surface text-text-secondary px-4 py-2 rounded-lg text-sm font-medium cursor-not-allowed"
              >
                <Loader2 size={14} className="animate-spin" />
                Syncing...
              </button>
            ) : (
              <button
                onClick={handleConnect}
                className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm transition-colors"
              >
                <Briefcase size={14} />
                {hasConnections ? "Connect another employer" : "Connect your employer"}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
