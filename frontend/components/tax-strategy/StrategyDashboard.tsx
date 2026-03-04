"use client";
import { DollarSign, MessageCircle } from "lucide-react";
import type { TaxStrategy } from "@/types/api";
import StrategySummaryBar from "./StrategySummaryBar";
import StrategyTimeline from "./StrategyTimeline";
import StrategyCard from "./StrategyCard";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function StrategyDashboard({ strategies, onDismiss, onOpenSimulator }: {
  strategies: TaxStrategy[];
  onDismiss: (id: number) => void;
  onOpenSimulator?: (key: string) => void;
}) {
  const hasCategories = strategies.some((s) => s.category != null);

  return (
    <div className="space-y-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400">
        AI Tax Strategies ({strategies.length})
      </h2>
      {strategies.length === 0 ? (
        <div className="bg-white rounded-xl border border-stone-100 shadow-sm p-8 text-center">
          <DollarSign className="mx-auto text-stone-200 mb-3" size={36} />
          <p className="text-stone-500 text-sm">No strategies yet. Click &quot;Run AI Analysis&quot; to generate personalized tax strategies.</p>
          <button
            type="button"
            onClick={() => askHenry("What are my best tax optimization strategies for this year? Consider my income, business, and household situation.")}
            className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:underline mt-3 mx-auto"
          >
            <MessageCircle size={12} /> Or ask Sir Henry for advice
          </button>
        </div>
      ) : (
        <>
          <StrategySummaryBar strategies={strategies} />
          {hasCategories ? (
            <StrategyTimeline strategies={strategies} onDismiss={onDismiss} onOpenSimulator={onOpenSimulator} />
          ) : (
            <div className="space-y-3">
              {strategies.map((s) => (
                <StrategyCard key={s.id} strategy={s} onDismiss={onDismiss} onOpenSimulator={onOpenSimulator} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
