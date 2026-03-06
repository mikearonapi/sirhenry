import { DEMO_RETIREMENT } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmtM(n: number) {
  return `$${(n / 1_000_000).toFixed(1)}M`;
}

function fmtK(n: number) {
  return `$${(n / 1_000).toFixed(0)}K`;
}

export default function RetirementShowcase() {
  const r = DEMO_RETIREMENT;

  return (
    <MockupFrame title="SirHENRY \u2014 Retirement Planning" dark={false} fadeBottom={false}>
      {/* Key metrics row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="bg-[#F0FDF4] rounded-lg p-3 border border-[#DCFCE7]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Retirement Target</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            {fmtM(r.fireNumber)}
          </p>
        </div>
        <div className="bg-[#F0FDF4] rounded-lg p-3 border border-[#DCFCE7]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Projected</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            {fmtM(r.projectedNestEgg)}
          </p>
        </div>
        <div className="bg-[#F0FDF4] rounded-lg p-3 border border-[#DCFCE7]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Earliest</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            Age {r.earliestRetirementAge}
          </p>
        </div>
        <div className="bg-[#F0FDF4] rounded-lg p-3 border border-[#DCFCE7]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Readiness</p>
          <p className="text-[#16A34A] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            {r.retirementReadinessPct}%
          </p>
        </div>
      </div>

      {/* Monte Carlo chart */}
      <div className="rounded-lg p-4 border border-[#E5E7EB] mb-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[#374151] text-xs font-semibold uppercase tracking-wider">
            Monte Carlo Simulation
          </p>
          <span className="text-[10px] px-2 py-0.5 rounded bg-[#F0FDF4] text-[#16A34A] font-medium border border-[#DCFCE7]">
            {r.monteCarlo.runs.toLocaleString()} runs
          </span>
        </div>
        <div className="relative h-32 sm:h-44">
          <svg viewBox="0 0 400 140" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full" preserveAspectRatio="none">
            {/* Grid lines */}
            <line x1="0" y1="35" x2="400" y2="35" stroke="#E5E7EB" strokeWidth="0.5" />
            <line x1="0" y1="70" x2="400" y2="70" stroke="#E5E7EB" strokeWidth="0.5" />
            <line x1="0" y1="105" x2="400" y2="105" stroke="#E5E7EB" strokeWidth="0.5" />

            {/* P90 band (widest) */}
            <path d="M0,125 Q60,120 120,105 Q200,75 280,40 Q340,15 400,5 L400,55 Q340,72 280,85 Q200,100 120,115 Q60,123 0,128 Z" fill="#22C55E" opacity="0.06" />
            {/* P50 band (middle) */}
            <path d="M0,124 Q60,118 120,100 Q200,68 280,35 Q340,12 400,3 L400,45 Q340,60 280,75 Q200,92 120,110 Q60,121 0,126 Z" fill="#22C55E" opacity="0.1" />
            {/* P10 band (tightest) */}
            <path d="M0,123 Q60,116 120,96 Q200,62 280,30 Q340,10 400,2 L400,35 Q340,50 280,65 Q200,85 120,106 Q60,118 0,125 Z" fill="#22C55E" opacity="0.15" />
            {/* Median line */}
            <path d="M0,124 Q60,117 120,98 Q200,65 280,32 Q340,11 400,3" stroke="#16A34A" strokeWidth="2.5" strokeLinecap="round" />

            {/* Retirement target line */}
            <line x1="0" y1="30" x2="400" y2="30" stroke="#F59E0B" strokeWidth="1" strokeDasharray="6 4" />
            <text x="4" y="26" fill="#F59E0B" fontSize="8" fontWeight="600">Target</text>

            {/* Y-axis labels */}
            <text x="4" y="42" fill="#9CA3AF" fontSize="7">{fmtM(r.monteCarlo.p90)}</text>
            <text x="4" y="77" fill="#9CA3AF" fontSize="7">{fmtM(r.monteCarlo.p50)}</text>
            <text x="4" y="112" fill="#9CA3AF" fontSize="7">{fmtM(r.monteCarlo.p10)}</text>

            {/* Age labels */}
            <text x="0" y="138" fill="#9CA3AF" fontSize="7">34</text>
            <text x="130" y="138" fill="#9CA3AF" fontSize="7">44</text>
            <text x="260" y="138" fill="#9CA3AF" fontSize="7">54</text>
            <text x="385" y="138" fill="#9CA3AF" fontSize="7">64</text>
          </svg>
        </div>
      </div>

      {/* Scenario outcomes */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg p-3 border border-[#E5E7EB] text-center">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Pessimistic (P10)</p>
          <p className="text-[#111827] text-sm font-bold" style={{ fontFamily: "var(--font-mono)" }}>{fmtM(r.monteCarlo.p10)}</p>
        </div>
        <div className="rounded-lg p-3 border border-[#16A34A]/30 bg-[#F0FDF4] text-center">
          <p className="text-[#16A34A] text-[10px] font-semibold uppercase tracking-wider mb-1">Base Case (P50)</p>
          <p className="text-[#111827] text-sm font-bold" style={{ fontFamily: "var(--font-mono)" }}>{fmtM(r.monteCarlo.p50)}</p>
        </div>
        <div className="rounded-lg p-3 border border-[#E5E7EB] text-center">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Optimistic (P90)</p>
          <p className="text-[#111827] text-sm font-bold" style={{ fontFamily: "var(--font-mono)" }}>{fmtM(r.monteCarlo.p90)}</p>
        </div>
      </div>
    </MockupFrame>
  );
}
