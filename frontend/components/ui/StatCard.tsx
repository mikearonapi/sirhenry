"use client";
import { ReactNode } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  icon?: ReactNode;
  className?: string;
  accent?: boolean;
  size?: "sm" | "md" | "lg";
}

export default function StatCard({
  label,
  value,
  sub,
  trend,
  trendValue,
  icon,
  className = "",
  accent = false,
  size = "md",
}: StatCardProps) {
  const sizeClasses = {
    sm: "p-4",
    md: "p-5",
    lg: "p-6",
  };

  const valueClasses = {
    sm: "text-lg",
    md: "text-2xl",
    lg: "text-3xl",
  };

  return (
    <div
      className={`bg-card rounded-xl border border-card-border shadow-sm ${sizeClasses[size]} ${
        accent ? "ring-1 ring-accent/10" : ""
      } ${className}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">{label}</span>
        {icon && <span className="text-text-muted">{icon}</span>}
      </div>
      <div className={`${valueClasses[size]} font-bold text-text-primary tracking-tight font-mono tabular-nums`}>{value}</div>
      {(sub || trendValue) && (
        <div className="flex items-center gap-1.5 mt-1.5">
          {trend === "up" && <TrendingUp size={13} className="text-green-600 dark:text-green-400" />}
          {trend === "down" && <TrendingDown size={13} className="text-red-600 dark:text-red-400" />}
          {trendValue && (
            <span
              className={`text-xs font-medium ${
                trend === "up" ? "text-green-600 dark:text-green-400" : trend === "down" ? "text-red-600 dark:text-red-400" : "text-text-secondary"
              }`}
            >
              {trendValue}
            </span>
          )}
          {sub && <span className="text-xs text-text-muted">{sub}</span>}
        </div>
      )}
    </div>
  );
}
