import { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
  hover?: boolean;
}

const PADDING = {
  none: "",
  sm: "p-4",
  md: "p-5",
  lg: "p-6",
};

export default function Card({ children, className = "", padding = "md", hover = false }: CardProps) {
  return (
    <div
      className={`bg-card rounded-xl border border-card-border shadow-sm ${PADDING[padding]} ${
        hover ? "hover:shadow-md hover:border-border transition-shadow cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}
