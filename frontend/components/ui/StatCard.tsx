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
      className={`bg-white rounded-xl border border-stone-100 shadow-sm ${sizeClasses[size]} ${
        accent ? "ring-1 ring-[#16A34A]/10" : ""
      } ${className}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-stone-500 uppercase tracking-wider">{label}</span>
        {icon && <span className="text-stone-300">{icon}</span>}
      </div>
      <div className={`${valueClasses[size]} font-bold text-stone-900 tracking-tight`}>{value}</div>
      {(sub || trendValue) && (
        <div className="flex items-center gap-1.5 mt-1.5">
          {trend === "up" && <TrendingUp size={13} className="text-green-500" />}
          {trend === "down" && <TrendingDown size={13} className="text-red-500" />}
          {trendValue && (
            <span
              className={`text-xs font-medium ${
                trend === "up" ? "text-green-600" : trend === "down" ? "text-red-600" : "text-stone-500"
              }`}
            >
              {trendValue}
            </span>
          )}
          {sub && <span className="text-xs text-stone-400">{sub}</span>}
        </div>
      )}
    </div>
  );
}
