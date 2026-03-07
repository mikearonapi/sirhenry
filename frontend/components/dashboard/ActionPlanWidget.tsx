"use client";
import { ArrowRight, CheckCircle } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { FOOStep } from "@/types/api";
import Card from "@/components/ui/Card";
import Link from "next/link";

interface Props {
  fooSteps: FOOStep[];
}

export default function ActionPlanWidget({ fooSteps }: Props) {
  const totalOpportunity = fooSteps
    .filter((s) => s.status !== "done" && s.target_value != null)
    .reduce((sum, s) => sum + (s.target_value ?? 0), 0);

  if (fooSteps.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted">Your Action Plan</h2>
        {totalOpportunity > 0 && (
          <span className="text-xs font-semibold text-accent bg-accent-light px-2.5 py-1 rounded-full money">
            {formatCurrency(totalOpportunity, true)}/yr in opportunities
          </span>
        )}
      </div>
      <Card padding="none">
        <div className="divide-y divide-border-light">
          {fooSteps.map((step) => {
            const isDone = step.status === "done";
            const isInProgress = step.status === "in_progress";
            const isNext = step.status === "next";
            const circleClass = isDone
              ? "bg-green-500 text-white"
              : isInProgress
                ? "bg-[#D97706] text-white"
                : isNext
                  ? "bg-accent text-white ring-2 ring-accent/30"
                  : "bg-surface text-text-muted";
            return (
              <div key={step.step} className={`flex gap-4 px-5 py-3.5 ${isNext ? "bg-accent-light/40" : ""}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm font-semibold ${circleClass}`}>
                  {isDone ? <CheckCircle size={18} strokeWidth={2.5} /> : step.step}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {step.link ? (
                      <Link href={step.link} className={`font-medium ${isNext ? "text-accent" : "text-text-primary"} hover:underline`}>
                        {step.name}
                      </Link>
                    ) : (
                      <span className={`font-medium ${isNext ? "text-accent" : isDone ? "text-text-secondary line-through" : "text-text-primary"}`}>
                        {step.name}
                      </span>
                    )}
                    {isNext && <ArrowRight size={14} className="text-accent shrink-0" />}
                  </div>
                  {step.description && (
                    <p className="text-xs text-text-secondary mt-0.5">{step.description}</p>
                  )}
                  {(step.current_value != null || step.target_value != null) && (
                    <div className="flex items-center gap-2 mt-1 text-xs">
                      <span className="text-text-secondary money">{step.current_value != null ? formatCurrency(step.current_value) : "—"}</span>
                      <span className="text-text-muted">/</span>
                      <span className="text-text-muted money">{step.target_value != null ? formatCurrency(step.target_value) : "—"}</span>
                    </div>
                  )}
                </div>
                {!isDone && (
                  <div className="flex-shrink-0 flex items-center">
                    <span className="text-xs text-text-muted hover:text-accent cursor-pointer whitespace-nowrap">
                      Ask Henry →
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
