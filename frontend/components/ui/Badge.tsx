import { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info" | "accent";
  className?: string;
  dot?: boolean;
}

const VARIANT_STYLES: Record<string, string> = {
  default: "bg-stone-100 text-stone-700",
  success: "bg-green-50 text-green-700",
  warning: "bg-amber-50 text-amber-700",
  danger: "bg-red-50 text-red-700",
  info: "bg-blue-50 text-blue-700",
  accent: "bg-[#DCFCE7] text-[#16A34A]",
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
            : variant === "accent" ? "bg-[#16A34A]"
            : "bg-stone-400"
          }`}
        />
      )}
      {children}
    </span>
  );
}
