import { DEMO_HOUSEHOLD } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function HouseholdShowcase() {
  const h = DEMO_HOUSEHOLD;

  return (
    <MockupFrame title="SirHENRY \u2014 Household Optimization">
      {/* Dual income cards */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <div className="bg-[#1C1C1F] rounded-lg p-4 border border-[#27272A]">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-full bg-[#22C55E]/20 flex items-center justify-center">
              <span className="text-xs font-bold text-[#22C55E]">{h.primary.name[0]}</span>
            </div>
            <div>
              <p className="text-[#F9FAFB] text-sm font-medium">{h.primary.name}</p>
              <p className="text-[#6B7280] text-[10px]">{h.primary.employer}</p>
            </div>
          </div>
          <p className="text-[#F9FAFB] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(h.primary.income)}
          </p>
          <p className="text-[#6B7280] text-[10px] mt-0.5">annual income</p>
        </div>
        <div className="bg-[#1C1C1F] rounded-lg p-4 border border-[#27272A]">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-full bg-[#3B82F6]/20 flex items-center justify-center">
              <span className="text-xs font-bold text-[#3B82F6]">{h.spouse.name[0]}</span>
            </div>
            <div>
              <p className="text-[#F9FAFB] text-sm font-medium">{h.spouse.name}</p>
              <p className="text-[#6B7280] text-[10px]">{h.spouse.employer}</p>
            </div>
          </div>
          <p className="text-[#F9FAFB] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(h.spouse.income)}
          </p>
          <p className="text-[#6B7280] text-[10px] mt-0.5">annual income</p>
        </div>
      </div>

      {/* Filing status */}
      <div className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A] mb-4 flex items-center justify-between">
        <span className="text-[#9CA3AF] text-xs">Filing Status</span>
        <span className="text-[#22C55E] text-xs font-semibold">{h.filingStatus}</span>
      </div>

      {/* Recommendations */}
      <div className="mb-4">
        <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-3">
          Optimization Opportunities
        </p>
        <div className="space-y-2">
          {h.recommendations.map((r) => (
            <div key={r.area} className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A] flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#22C55E]/10 flex items-center justify-center shrink-0">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[#D1D5DB] text-xs font-medium">{r.area}</p>
                <p className="text-[#6B7280] text-[10px] truncate">{r.action}</p>
              </div>
              <span className="text-[#22C55E] text-xs font-semibold shrink-0" style={{ fontFamily: "var(--font-mono)" }}>
                +${fmt(r.savings)}/yr
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Total savings callout */}
      <div className="bg-[#22C55E]/10 rounded-lg p-4 border border-[#22C55E]/20 text-center">
        <p className="text-[#22C55E] text-[10px] font-semibold uppercase tracking-wider mb-1">
          Total Annual Savings Identified
        </p>
        <p className="text-[#F9FAFB] text-2xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
          ${fmt(h.totalAnnualSavings)}/yr
        </p>
      </div>
    </MockupFrame>
  );
}
