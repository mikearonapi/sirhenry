"use client";
import { Shield, GraduationCap, Home, Landmark, AlertTriangle, Briefcase, PiggyBank } from "lucide-react";
import type { ReactNode } from "react";

export interface GoalTemplate {
  name: string;
  goal_type: string;
  target_amount: number;
  monthly_contribution: number;
  description: string;
  icon: ReactNode;
  color: string;
}

/** Pre-built goal templates designed for HENRYs (High Earners, Not Rich Yet) */
export const HENRY_GOAL_TEMPLATES: GoalTemplate[] = [
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
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
      {HENRY_GOAL_TEMPLATES.map((t, i) => (
        <button
          key={i}
          onClick={() => onSelect(t)}
          className="flex items-start gap-3 text-left p-4 rounded-xl border border-stone-100 bg-white hover:border-[#16A34A]/30 hover:bg-green-50/30 transition-all group"
        >
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-stone-50 group-hover:bg-green-50 flex items-center justify-center transition-colors">
            {t.icon}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-stone-700 group-hover:text-[#16A34A] transition-colors">
              {t.name}
            </p>
            <p className="text-xs text-stone-400 mt-0.5 line-clamp-2">{t.description}</p>
          </div>
        </button>
      ))}
    </div>
  );
}
