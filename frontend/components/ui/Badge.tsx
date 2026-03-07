import { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info" | "accent";
  className?: string;
  dot?: boolean;
}

const VARIANT_STYLES: Record<string, string> = {
  default: "bg-surface text-text-secondary",
  success: "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-400",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400",
  danger: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400",
  info: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
  accent: "bg-accent-light text-accent",
};

export default function Badge({ children, variant = "default", className = "", dot }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium ${VARIANT_STYLES[variant] ?? VARIANT_STYLES.default} ${className}`}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            variant === "success" ? "bg-green-500"
            : variant === "warning" ? "bg-amber-500"
            : variant === "danger" ? "bg-red-500"
            : variant === "info" ? "bg-blue-500"
            : variant === "accent" ? "bg-accent"
            : "bg-text-muted"
          }`}
        />
      )}
      {children}
    </span>
  );
}
