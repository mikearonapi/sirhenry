import { DEMO_BUDGET } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function BudgetShowcase() {
  const b = DEMO_BUDGET;
  const remaining = b.totalBudgeted - b.totalSpent;
  const spentPct = Math.round((b.totalSpent / b.totalBudgeted) * 100);

  return (
    <MockupFrame title={`SirHENRY \u2014 Budget \u00b7 ${b.month} ${b.year}`}>
      {/* Summary row */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Budgeted</p>
          <p className="text-[#F9FAFB] text-base font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(b.totalBudgeted)}
          </p>
        </div>
        <div className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Spent</p>
          <p className="text-[#F9FAFB] text-base font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(b.totalSpent)}
          </p>
          <p className="text-[#22C55E] text-[10px] font-medium mt-0.5">{spentPct}% of budget</p>
        </div>
        <div className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A]">
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Remaining</p>
          <p className="text-[#22C55E] text-base font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(remaining)}
          </p>
        </div>
      </div>

      {/* Category rows */}
      <div className="space-y-2 mb-5">
        {b.groups.map((g) => {
          const pct = Math.min(Math.round((g.spent / g.budget) * 100), 100);
          const over = g.spent > g.budget;
          return (
            <div key={g.group} className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A]">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{g.icon}</span>
                  <span className="text-[#D1D5DB] text-xs font-medium">{g.group}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[#9CA3AF] text-[10px]" style={{ fontFamily: "var(--font-mono)" }}>
                    ${fmt(g.spent)}
                  </span>
                  <span className="text-[#6B7280] text-[10px]">/</span>
                  <span className="text-[#6B7280] text-[10px]" style={{ fontFamily: "var(--font-mono)" }}>
                    ${fmt(g.budget)}
                  </span>
                </div>
              </div>
              <div className="w-full h-1.5 bg-[#27272A] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${over ? "bg-[#EF4444]" : pct > 80 ? "bg-[#F59E0B]" : "bg-[#22C55E]"}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Forecast callout */}
      <div className="bg-[#22C55E]/10 rounded-lg p-3 border border-[#22C55E]/20 flex items-center justify-between">
        <div>
          <p className="text-[#22C55E] text-[10px] font-semibold uppercase tracking-wider">Month-End Forecast</p>
          <p className="text-[#9CA3AF] text-[10px] mt-0.5">
            Based on spend velocity &middot; {b.forecast.confidence}% confidence
          </p>
        </div>
        <p className="text-[#F9FAFB] text-sm font-bold" style={{ fontFamily: "var(--font-mono)" }}>
          ${fmt(b.forecast.predictedTotal)}
        </p>
      </div>
    </MockupFrame>
  );
}
