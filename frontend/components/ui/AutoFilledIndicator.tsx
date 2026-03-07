"use client";

import { useState } from "react";
import { Sparkles, Info } from "lucide-react";

interface AutoFilledIndicatorProps {
  source: string;
  className?: string;
}

/**
 * Small inline indicator showing a field was auto-filled from another data source.
 * Green dot + hover tooltip showing the data origin.
 */
export function AutoFilledIndicator({ source, className = "" }: AutoFilledIndicatorProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span
      className={`relative inline-flex items-center gap-1 ${className}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-accent-light text-accent">
        <Sparkles size={10} />
        <span className="text-xs font-medium leading-none">Auto-filled</span>
      </span>

      {showTooltip && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2.5 py-1.5 rounded-lg bg-stone-800 text-white text-xs whitespace-nowrap shadow-lg z-50">
          From {source}
          <span className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[5px] border-t-stone-800" />
        </span>
      )}
    </span>
  );
}

interface MissingDataHintProps {
  message: string;
  className?: string;
}

/**
 * Small hint shown when a field could be auto-filled but the source data is missing.
 * e.g. "Add a W-2 to auto-fill this"
 */
export function MissingDataHint({ message, className = "" }: MissingDataHintProps) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs text-text-muted italic ${className}`}>
      <Info size={11} />
      {message}
    </span>
  );
}
