import React from "react";
import {
  TrendingUp, TrendingDown, Minus, Calendar, Ban, CheckCircle2,
} from "lucide-react";
import type { OutlierClassification } from "@/types/api";

export const CLASSIFICATION_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  normal: { bg: "bg-green-50 dark:bg-green-950/40", text: "text-green-700 dark:text-green-400", label: "Normal" },
  elevated: { bg: "bg-amber-50 dark:bg-amber-950/40", text: "text-amber-700 dark:text-amber-400", label: "Elevated" },
  very_high: { bg: "bg-red-50 dark:bg-red-950/40", text: "text-red-700 dark:text-red-400", label: "Very High" },
  low: { bg: "bg-blue-50 dark:bg-blue-950/40", text: "text-blue-700 dark:text-blue-400", label: "Low" },
};

export const TREND_ICONS: Record<string, React.ReactNode> = {
  increasing: React.createElement(TrendingUp, { size: 14, className: "text-red-500" }),
  decreasing: React.createElement(TrendingDown, { size: 14, className: "text-green-500" }),
  stable: React.createElement(Minus, { size: 14, className: "text-text-muted" }),
  insufficient_data: React.createElement(Minus, { size: 14, className: "text-text-muted" }),
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
    bg: "bg-blue-50 dark:bg-blue-950/40",
    text: "text-blue-700 dark:text-blue-400",
    border: "border-blue-200 dark:border-blue-900",
  },
  one_time: {
    label: "One-Time Purchase",
    description: "True outlier — exclude from normalized budget",
    icon: React.createElement(Ban, { size: 14 }),
    bg: "bg-amber-50 dark:bg-amber-950/40",
    text: "text-amber-700 dark:text-amber-400",
    border: "border-amber-200 dark:border-amber-900",
  },
  not_outlier: {
    label: "Not an Outlier",
    description: "Regular expense, wrongly flagged — suppress in future",
    icon: React.createElement(CheckCircle2, { size: 14 }),
    bg: "bg-green-50 dark:bg-green-950/40",
    text: "text-green-700 dark:text-green-400",
    border: "border-green-200 dark:border-green-900",
  },
};
