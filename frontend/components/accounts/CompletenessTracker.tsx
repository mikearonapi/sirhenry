"use client";

import type { CompletenessStep } from "./accounts-types";

interface CompletenessTrackerProps {
  steps: CompletenessStep[];
}

export default function CompletenessTracker({ steps }: CompletenessTrackerProps) {
  const complete = steps.filter((s) => s.count > 0).length;
  const pct = Math.round((complete / steps.length) * 100);

  return (
    <div className="bg-white border border-stone-100 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-sm font-semibold text-stone-800">Financial Picture Completeness</p>
          <p className="text-xs text-stone-500">{complete} of {steps.length} categories connected — {pct}% complete</p>
        </div>
        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${pct === 100 ? "bg-green-50 text-green-700" : pct >= 50 ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-600"}`}>
          {pct}%
        </span>
      </div>
      <div className="w-full bg-stone-100 rounded-full h-1.5 mb-3">
        <div className="bg-[#16A34A] h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {steps.map((s) => (
          <div key={s.label} className={`flex items-center gap-2 p-2 rounded-lg text-xs ${s.count > 0 ? "bg-green-50" : "bg-stone-50"}`}>
            <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 text-white text-[9px] font-bold ${s.count > 0 ? "bg-green-500" : "bg-stone-300"}`}>
              {s.count > 0 ? "✓" : "!"}
            </div>
            <div>
              <p className={`font-medium ${s.count > 0 ? "text-green-700" : "text-stone-600"}`}>{s.label}</p>
              <p className={`text-[10px] ${s.count > 0 ? "text-green-600" : "text-stone-400"}`}>
                {s.count > 0 ? `${s.count} added` : s.action}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
