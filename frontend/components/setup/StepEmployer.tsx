"use client";

import { useState, useEffect } from "react";
import {
  Briefcase, CheckCircle, ArrowRight, SkipForward,
} from "lucide-react";
import ConnectEmployer from "@/components/accounts/ConnectEmployer";
import { getIncomeCascadeSummary, getIncomeConnections } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import type { IncomeCascadeSummary } from "@/types/income";

interface Props {
  onNext: () => void;
  onRefresh: () => void;
}

export default function StepEmployer({ onNext, onRefresh }: Props) {
  const [connected, setConnected] = useState(false);
  const [cascadeSummary, setCascadeSummary] = useState<IncomeCascadeSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // Check if there is already an active connection on mount
  useEffect(() => {
    getIncomeConnections()
      .then((conns) => {
        const active = conns.find((c) => c.status === "active");
        if (active) {
          setConnected(true);
          loadCascade(active.id);
        }
      })
      .catch(() => {
        // Non-critical -- user can still connect fresh
      });
  }, []);

  async function loadCascade(connectionId: number) {
    setLoadingSummary(true);
    try {
      const summary = await getIncomeCascadeSummary(connectionId);
      setCascadeSummary(summary);
    } catch (e: unknown) {
      // Non-critical -- the summary display is informational
      console.error("Failed to load cascade summary:", getErrorMessage(e));
    } finally {
      setLoadingSummary(false);
    }
  }

  function handleConnectionComplete() {
    setConnected(true);
    onRefresh();
    // Load cascade summary for the most recent connection
    getIncomeConnections()
      .then((conns) => {
        const active = conns.filter((c) => c.status === "active");
        if (active.length > 0) {
          const latest = active[active.length - 1];
          loadCascade(latest.id);
        }
      })
      .catch(() => {
        // Silent
      });
  }

  return (
    <div className="space-y-5">
      {/* Section header */}
      <div>
        <h2 className="text-lg font-semibold text-stone-900 font-display">
          Connect Your Employer
        </h2>
        <p className="text-sm text-stone-500 mt-0.5">
          Auto-fill your income, benefits, and tax information by connecting your payroll provider
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: Income Tracking &middot; Benefits Pre-fill &middot; Tax Withholding &middot; Retirement Match
        </p>
      </div>

      {/* Employer connection component */}
      <ConnectEmployer onConnectionComplete={handleConnectionComplete} />

      {/* Cascade summary after successful connection */}
      {connected && cascadeSummary && !loadingSummary && (
        <div className="bg-green-50/50 border border-[#16A34A]/20 rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <CheckCircle size={16} className="text-[#16A34A]" />
            <p className="text-sm font-medium text-stone-800">
              Successfully imported from {cascadeSummary.employer ?? "your employer"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {cascadeSummary.annual_income != null && cascadeSummary.annual_income > 0 && (
              <CascadeItem
                label="Annual Income"
                value={formatCurrency(cascadeSummary.annual_income, true)}
                destination="Household"
              />
            )}
            {cascadeSummary.pay_stubs_imported > 0 && (
              <CascadeItem
                label="Pay Stubs"
                value={`${cascadeSummary.pay_stubs_imported} imported`}
                destination="Tax Documents"
              />
            )}
            {cascadeSummary.benefits_detected.length > 0 && (
              <CascadeItem
                label="Benefits Detected"
                value={cascadeSummary.benefits_detected.join(", ")}
                destination="Benefits"
              />
            )}
          </div>

          <button
            onClick={onNext}
            className="w-full flex items-center justify-center gap-2 bg-[#16A34A] text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm transition-colors mt-2"
          >
            Continue
            <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* Connected but no cascade data yet (still loading or empty) */}
      {connected && !cascadeSummary && !loadingSummary && (
        <div className="bg-green-50/50 border border-[#16A34A]/20 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle size={16} className="text-[#16A34A]" />
            <p className="text-sm font-medium text-stone-800">
              Employer connected successfully
            </p>
          </div>
          <p className="text-xs text-stone-500 mb-3">
            Your payroll data is being synced. Benefits and income information will appear shortly.
          </p>
          <button
            onClick={onNext}
            className="w-full flex items-center justify-center gap-2 bg-[#16A34A] text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm transition-colors"
          >
            Continue
            <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* Skip option */}
      {!connected && (
        <button
          onClick={onNext}
          className="w-full flex items-center justify-center gap-2 py-2.5 text-sm text-stone-400 hover:text-stone-600 transition-colors"
        >
          <SkipForward size={14} />
          Skip — I&apos;ll enter manually
        </button>
      )}
    </div>
  );
}

/** Small card showing a single piece of cascade data and where it flows. */
function CascadeItem({
  label,
  value,
  destination,
}: {
  label: string;
  value: string;
  destination: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-stone-100 p-3">
      <p className="text-[10px] font-medium text-stone-400 uppercase tracking-wide">
        {label}
      </p>
      <p className="text-sm font-medium text-stone-800 mt-0.5 font-mono">
        {value}
      </p>
      <div className="flex items-center gap-1 mt-1.5">
        <ArrowRight size={9} className="text-[#16A34A]" />
        <span className="text-[10px] text-[#16A34A] font-medium">{destination}</span>
      </div>
    </div>
  );
}
