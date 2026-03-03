import React from "react";
import {
  TrendingUp, TrendingDown, Minus, Calendar, Ban, CheckCircle2,
} from "lucide-react";
import type { OutlierClassification } from "@/types/api";

export const CLASSIFICATION_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  normal: { bg: "bg-green-50", text: "text-green-700", label: "Normal" },
  elevated: { bg: "bg-amber-50", text: "text-amber-700", label: "Elevated" },
  very_high: { bg: "bg-red-50", text: "text-red-700", label: "Very High" },
  low: { bg: "bg-blue-50", text: "text-blue-700", label: "Low" },
};

export const TREND_ICONS: Record<string, React.ReactNode> = {
  increasing: React.createElement(TrendingUp, { size: 14, className: "text-red-500" }),
  decreasing: React.createElement(TrendingDown, { size: 14, className: "text-green-500" }),
  stable: React.createElement(Minus, { size: 14, className: "text-stone-400" }),
  insufficient_data: React.createElement(Minus, { size: 14, className: "text-stone-300" }),
};

export const SEASONAL_COLORS: Record<string, string> = {
  peak: "#ef4444",
  above_average: "#f59e0b",
  typical: "#22c55e",
  below_average: "#3b82f6",
  low: "#6366f1",
};

export const CLASSIFICATION_CONFIG: Record<
  OutlierClassification,
  { label: string; description: string; icon: React.ReactNode; bg: string; text: string; border: string }
> = {
  recurring: {
    label: "Recurring / Expected",
    description: "Annual or periodic expense — include in budget",
    icon: React.createElement(Calendar, { size: 14 }),
    bg: "bg-blue-50",
    text: "text-blue-700",
    border: "border-blue-200",
  },
  one_time: {
    label: "One-Time Purchase",
    description: "True outlier — exclude from normalized budget",
    icon: React.createElement(Ban, { size: 14 }),
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200",
  },
  not_outlier: {
    label: "Not an Outlier",
    description: "Regular expense, wrongly flagged — suppress in future",
    icon: React.createElement(CheckCircle2, { size: 14 }),
    bg: "bg-green-50",
    text: "text-green-700",
    border: "border-green-200",
  },
};
