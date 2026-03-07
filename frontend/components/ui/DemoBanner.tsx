"use client";
import { ArrowRight, FlaskConical } from "lucide-react";

interface DemoBannerProps {
  onExitDemo: () => void;
}

/**
 * Persistent banner shown at the top of the app when demo mode is active.
 * Informs the user they're viewing synthetic data and offers CTA to start with their own data.
 */
export default function DemoBanner({ onExitDemo }: DemoBannerProps) {
  return (
    <div className="bg-amber-50 dark:bg-amber-950/50 border-b border-amber-200/60 dark:border-amber-800/40 px-4 py-2.5 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 min-w-0">
        <FlaskConical size={14} className="text-amber-600 dark:text-amber-400 flex-shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-300 truncate">
          You&apos;re exploring <span className="font-semibold">Sir HENRY</span> with demo data
        </p>
      </div>
      <button
        onClick={onExitDemo}
        className="flex-shrink-0 inline-flex items-center gap-1 bg-accent text-white text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-accent-hover transition-colors"
      >
        Start With Your Own Data
        <ArrowRight size={12} />
      </button>
    </div>
  );
}
