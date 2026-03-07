import { ReactNode } from "react";
import { Info } from "lucide-react";

export default function SimulatorCard({ title, purpose, bestFor, children }: {
  title: string;
  purpose: string;
  bestFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="bg-card rounded-xl border border-card-border shadow-sm p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text-secondary">{title}</h3>
        <p className="text-xs text-text-muted mt-1 leading-relaxed">{purpose}</p>
        {bestFor && (
          <div className="flex items-center gap-1.5 mt-2">
            <Info size={12} className="text-blue-400 flex-shrink-0" />
            <p className="text-xs text-blue-600">{bestFor}</p>
          </div>
        )}
      </div>
      {children}
    </div>
  );
}
