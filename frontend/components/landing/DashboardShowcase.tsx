import { DEMO_DASHBOARD, DEMO_ACTION_PLAN } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function DashboardShowcase() {
  const d = DEMO_DASHBOARD;
  const actions = DEMO_ACTION_PLAN;

  return (
    <MockupFrame title="SirHENRY Dashboard">
      {/* Top metrics row */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4 mb-5 sm:mb-6">
        <div className="bg-[#1C1C1F] rounded-lg p-3 sm:p-4 border border-[#27272A]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">
            Net Worth
          </p>
          <p className="text-[#F9FAFB] text-base sm:text-xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(d.netWorth)}
          </p>
          <p className="text-[#22C55E] text-[10px] sm:text-xs font-medium mt-1">
            +${(d.netWorthDelta90d / 1000).toFixed(0)}K (90d)
          </p>
        </div>
        <div className="bg-[#1C1C1F] rounded-lg p-3 sm:p-4 border border-[#27272A]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">
            Savings Rate
          </p>
          <p className="text-[#F9FAFB] text-base sm:text-xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            {d.savingsRate}%
          </p>
          <p className="text-[#22C55E] text-[10px] sm:text-xs font-medium mt-1">On track</p>
        </div>
        <div className="bg-[#1C1C1F] rounded-lg p-3 sm:p-4 border border-[#27272A]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">
            Retire By
          </p>
          <p className="text-[#F9FAFB] text-base sm:text-xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            Age {d.retireByAge}
          </p>
          <p className="text-[#22C55E] text-[10px] sm:text-xs font-medium mt-1">
            {d.retireConfidence}% confidence
          </p>
        </div>
      </div>

      {/* Trajectory chart */}
      <div className="bg-[#1C1C1F] rounded-lg p-4 sm:p-5 border border-[#27272A] mb-5 sm:mb-6">
        <div className="flex items-center justify-between mb-4">
          <p className="text-[#9CA3AF] text-[10px] sm:text-xs font-semibold uppercase tracking-wider">
            30-Year Trajectory
          </p>
          <div className="flex gap-1.5 sm:gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-[#22C55E]/10 text-[#22C55E] font-medium">10Y</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-[#27272A] text-[#6B7280] font-medium">20Y</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-[#27272A] text-[#6B7280] font-medium">30Y</span>
          </div>
        </div>
        <div className="relative h-28 sm:h-40">
          <svg viewBox="0 0 400 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full" preserveAspectRatio="none">
            <line x1="0" y1="30" x2="400" y2="30" stroke="#27272A" strokeWidth="0.5" />
            <line x1="0" y1="60" x2="400" y2="60" stroke="#27272A" strokeWidth="0.5" />
            <line x1="0" y1="90" x2="400" y2="90" stroke="#27272A" strokeWidth="0.5" />
            <path d="M0,105 Q80,95 160,75 Q240,50 320,30 Q360,20 400,8 L400,45 Q360,52 320,60 Q240,75 160,88 Q80,100 0,108 Z" fill="#22C55E" opacity="0.06" />
            <path d="M0,103 Q80,92 160,70 Q240,45 320,25 Q360,16 400,5 L400,40 Q360,47 320,55 Q240,68 160,82 Q80,97 0,106 Z" fill="#22C55E" opacity="0.1" />
            <path d="M0,104 Q80,93 160,72 Q240,47 320,27 Q360,18 400,7" stroke="#22C55E" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>
      </div>

      {/* Action plan */}
      <div className="bg-[#1C1C1F] rounded-lg p-4 sm:p-5 border border-[#27272A]">
        <p className="text-[#9CA3AF] text-[10px] sm:text-xs font-semibold uppercase tracking-wider mb-3">
          Your Action Plan
        </p>
        <div className="space-y-2.5">
          {actions.map((a) => (
            <div key={a.name} className="flex items-center gap-3">
              {a.status === "done" ? (
                <div className="w-5 h-5 rounded bg-[#22C55E]/20 flex items-center justify-center shrink-0">
                  <div className="w-2 h-2 rounded-sm bg-[#22C55E]" />
                </div>
              ) : (
                <div className="w-5 h-5 rounded border border-[#3F3F46] shrink-0" />
              )}
              <span className="text-[#D1D5DB] text-xs flex-1 truncate">{a.name}</span>
              <span
                className={`text-xs font-medium shrink-0 ${a.status === "pending" && a.value === "Reduce risk" ? "text-[#9CA3AF]" : "text-[#22C55E]"}`}
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {a.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </MockupFrame>
  );
}
