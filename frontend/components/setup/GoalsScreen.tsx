"use client";
import { useState } from "react";
import {
  TrendingDown, PiggyBank, Wallet, Shield, Building2, Sparkles,
  ArrowRight, Check,
} from "lucide-react";
import { OB_CTA, OB_HEADING, OB_SUBTITLE } from "./styles";
import { ONBOARDING_GOALS_KEY } from "@/lib/storage-keys";

// TODO: Persist selected goals to backend when user accounts are implemented.
// Currently stored in localStorage only, which won't survive browser clears.

const GOALS = [
  {
    key: "tax",
    label: "Tax Optimization",
    desc: "Reduce your effective tax rate with smart strategies",
    icon: TrendingDown,
  },
  {
    key: "retirement",
    label: "Retirement Planning",
    desc: "Project and maximize your retirement savings",
    icon: PiggyBank,
  },
  {
    key: "cashflow",
    label: "Cash Flow & Budget",
    desc: "Track spending and build reserves",
    icon: Wallet,
  },
  {
    key: "insurance",
    label: "Insurance Review",
    desc: "Find coverage gaps and save on premiums",
    icon: Shield,
  },
  {
    key: "business",
    label: "Business & Side Income",
    desc: "Optimize entity structure and deductions",
    icon: Building2,
  },
  {
    key: "everything",
    label: "Full Financial Picture",
    desc: "All of the above — give me the full overview",
    icon: Sparkles,
  },
];

interface Props {
  onContinue: (goals: string[]) => void;
}

export default function GoalsScreen({ onContinue }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleContinue() {
    const goals = Array.from(selected);
    localStorage.setItem(ONBOARDING_GOALS_KEY, JSON.stringify(goals));
    onContinue(goals);
  }

  return (
    <div className="fixed inset-0 z-50 bg-background flex items-center justify-center overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-12 w-full">
        <h1 className={`${OB_HEADING} text-center`}>
          What are you looking to optimize?
        </h1>
        <p className={`${OB_SUBTITLE} text-center max-w-md mx-auto`}>
          Select all that apply. This helps us prioritize what matters most to you.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-10">
          {GOALS.map((goal) => {
            const Icon = goal.icon;
            const isSelected = selected.has(goal.key);
            return (
              <button
                key={goal.key}
                onClick={() => toggle(goal.key)}
                className={`relative p-5 rounded-xl text-left transition-all ${
                  isSelected
                    ? "border-2 border-accent bg-green-50 ring-1 ring-accent/20"
                    : "border-2 border-border bg-card hover:border-text-muted"
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      isSelected ? "bg-accent/10" : "bg-surface"
                    }`}
                  >
                    <Icon
                      size={20}
                      className={isSelected ? "text-accent" : "text-text-secondary"}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm font-semibold ${
                        isSelected ? "text-text-primary" : "text-text-primary"
                      }`}
                    >
                      {goal.label}
                    </p>
                    <p className="text-xs text-text-secondary mt-0.5">{goal.desc}</p>
                  </div>
                </div>
                {isSelected && (
                  <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-accent flex items-center justify-center">
                    <Check size={12} className="text-white" />
                  </div>
                )}
              </button>
            );
          })}
        </div>

        <div className="mt-10 flex flex-col items-center gap-3">
          <button
            onClick={handleContinue}
            className={`${OB_CTA} w-full max-w-sm`}
          >
            Continue
            <ArrowRight size={18} />
          </button>
          <button
            onClick={() => {
              localStorage.setItem(ONBOARDING_GOALS_KEY, "[]");
              onContinue([]);
            }}
            className="text-sm text-text-muted hover:text-text-secondary transition-colors"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  );
}
