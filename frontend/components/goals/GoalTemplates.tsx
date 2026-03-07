"use client";
import { useEffect, useState } from "react";
import { Shield, GraduationCap, Home, Landmark, AlertTriangle, Briefcase, PiggyBank, Sparkles, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { getGoalSuggestions, type GoalSuggestion } from "@/lib/api-goals";
import { formatCurrency } from "@/lib/utils";

export interface GoalTemplate {
  name: string;
  goal_type: string;
  target_amount: number;
  monthly_contribution: number;
  description: string;
  icon: ReactNode;
  color: string;
}

const ICON_MAP: Record<string, (color: string) => ReactNode> = {
  emergency_fund: (c) => <Shield size={18} className={c} />,
  debt_payoff: (c) => <GraduationCap size={18} className={c} />,
  purchase: (c) => <Home size={18} className={c} />,
  tax: (c) => <Landmark size={18} className={c} />,
  investment: (c) => <PiggyBank size={18} className={c} />,
  savings: (c) => <PiggyBank size={18} className={c} />,
  other: (c) => <Briefcase size={18} className={c} />,
};

const COLOR_TO_TEXT: Record<string, string> = {
  "#22c55e": "text-emerald-600",
  "#6366f1": "text-indigo-600",
  "#3b82f6": "text-blue-600",
  "#f59e0b": "text-amber-600",
  "#ef4444": "text-red-500",
  "#8b5cf6": "text-purple-600",
  "#06b6d4": "text-cyan-600",
};

function suggestionToTemplate(s: GoalSuggestion): GoalTemplate {
  const textColor = COLOR_TO_TEXT[s.color] ?? "text-text-secondary";
  const iconFn = ICON_MAP[s.goal_type] ?? ICON_MAP.other;
  return {
    name: s.name,
    goal_type: s.goal_type,
    target_amount: s.target_amount,
    monthly_contribution: s.monthly_contribution,
    description: s.description,
    icon: iconFn(textColor),
    color: s.color,
  };
}

/** Static fallback templates for when the API is unavailable */
const FALLBACK_TEMPLATES: GoalTemplate[] = [
  {
    name: "Emergency Fund (6 months)",
    goal_type: "emergency_fund",
    target_amount: 50000,
    monthly_contribution: 2000,
    description: "6 months of living expenses as your financial safety net",
    icon: <Shield size={18} className="text-emerald-600" />,
    color: "#22c55e",
  },
  {
    name: "Pay Off Student Loans",
    goal_type: "debt_payoff",
    target_amount: 100000,
    monthly_contribution: 2500,
    description: "Accelerate student debt payoff to free up cash flow",
    icon: <GraduationCap size={18} className="text-indigo-600" />,
    color: "#6366f1",
  },
  {
    name: "House Down Payment",
    goal_type: "purchase",
    target_amount: 150000,
    monthly_contribution: 3000,
    description: "20% down payment fund for your first home",
    icon: <Home size={18} className="text-blue-600" />,
    color: "#3b82f6",
  },
  {
    name: "Max Tax-Advantaged Accounts",
    goal_type: "tax",
    target_amount: 30500,
    monthly_contribution: 2542,
    description: "Max out 401(k) and IRA contributions this year",
    icon: <Landmark size={18} className="text-amber-600" />,
    color: "#f59e0b",
  },
  {
    name: "RSU Tax Withholding Reserve",
    goal_type: "tax",
    target_amount: 25000,
    monthly_contribution: 2000,
    description: "Cover the underwithholding gap when RSUs vest",
    icon: <AlertTriangle size={18} className="text-red-500" />,
    color: "#ef4444",
  },
  {
    name: "Career Growth Fund",
    goal_type: "investment",
    target_amount: 20000,
    monthly_contribution: 1000,
    description: "Invest in certifications, courses, or a career pivot",
    icon: <Briefcase size={18} className="text-purple-600" />,
    color: "#8b5cf6",
  },
  {
    name: "Wealth Building (Taxable Brokerage)",
    goal_type: "investment",
    target_amount: 100000,
    monthly_contribution: 3000,
    description: "Build long-term wealth beyond retirement accounts",
    icon: <PiggyBank size={18} className="text-cyan-600" />,
    color: "#06b6d4",
  },
];

interface GoalTemplatesProps {
  onSelect: (template: GoalTemplate) => void;
}

export default function GoalTemplates({ onSelect }: GoalTemplatesProps) {
  const [templates, setTemplates] = useState<GoalTemplate[]>(FALLBACK_TEMPLATES);
  const [personalized, setPersonalized] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getGoalSuggestions();
        if (!cancelled && data.suggestions.length > 0) {
          setTemplates(data.suggestions.map(suggestionToTemplate));
          setPersonalized(true);
        }
      } catch {
        // Silently fall back to static templates
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div>
      {personalized && (
        <div className="flex items-center gap-1.5 mb-2">
          <Sparkles size={12} className="text-[#EAB308]" />
          <span className="text-xs text-text-muted">Personalized based on your income and situation</span>
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {(loading ? FALLBACK_TEMPLATES : templates).map((t, i) => (
          <button
            key={i}
            onClick={() => onSelect(t)}
            className="flex items-start gap-3 text-left p-4 rounded-xl border border-card-border bg-card hover:border-accent/30 hover:bg-green-50/30 transition-all group"
          >
            <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-surface group-hover:bg-green-50 flex items-center justify-center transition-colors">
              {t.icon}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-text-secondary group-hover:text-accent transition-colors">
                {t.name}
              </p>
              <p className="text-xs text-text-muted mt-0.5 line-clamp-2">{t.description}</p>
              <p className="text-xs text-text-secondary mt-1.5 font-mono tabular-nums">
                {formatCurrency(t.target_amount, true)} target · {formatCurrency(t.monthly_contribution)}/mo
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
