"use client";
import { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="bg-white rounded-xl border border-dashed border-stone-200 p-12 text-center">
      <div className="text-stone-200 mb-4 flex justify-center">{icon}</div>
      <h3 className="font-semibold text-stone-700 mb-2">{title}</h3>
      {description && <p className="text-stone-400 text-sm mb-6 max-w-md mx-auto">{description}</p>}
      {action}
    </div>
  );
}
