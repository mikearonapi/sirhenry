import { DEMO_PORTFOLIO } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function PortfolioShowcase() {
  const p = DEMO_PORTFOLIO;

  // Build SVG donut segments
  const total = p.allocation.reduce((sum, a) => sum + a.pct, 0);
  const segments: { offset: number; length: number; color: string }[] = [];
  let cumulative = 0;
  for (const slice of p.allocation) {
    const length = (slice.pct / total) * 283; // circumference = 2*PI*45 ~ 283
    segments.push({ offset: cumulative, length, color: slice.color });
    cumulative += length;
  }

  return (
    <MockupFrame title="SirHENRY \u2014 Portfolio">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Left: Donut + allocation */}
        <div>
          {/* Portfolio value */}
          <div className="mb-5">
            <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Total Portfolio</p>
            <p className="text-[#F9FAFB] text-2xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
              ${fmt(p.totalValue)}
            </p>
            <p className="text-[#22C55E] text-xs font-medium mt-1">
              +${fmt(p.totalGainLoss)} ({p.totalGainLossPct}%)
            </p>
          </div>

          {/* Donut chart */}
          <div className="flex items-center gap-6">
            <div className="relative w-28 h-28 shrink-0">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                {segments.map((seg, i) => (
                  <circle
                    key={i}
                    cx="50" cy="50" r="45"
                    fill="none"
                    stroke={seg.color}
                    strokeWidth="8"
                    strokeDasharray={`${seg.length} ${283 - seg.length}`}
                    strokeDashoffset={-seg.offset}
                    strokeLinecap="round"
                  />
                ))}
              </svg>
            </div>
            <div className="space-y-1.5">
              {p.allocation.map((a) => (
                <div key={a.name} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: a.color }} />
                  <span className="text-[#9CA3AF] text-[11px]">{a.name}</span>
                  <span className="text-[#D1D5DB] text-[11px] font-medium ml-auto" style={{ fontFamily: "var(--font-mono)" }}>
                    {a.pct}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Holdings + Tax harvest */}
        <div>
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-3">Top Holdings</p>
          <div className="space-y-2 mb-5">
            {p.topHoldings.map((h) => (
              <div key={h.ticker} className="flex items-center gap-3 bg-[#1C1C1F] rounded-lg p-2.5 border border-[#27272A]">
                <div className="w-8 h-8 rounded bg-[#27272A] flex items-center justify-center shrink-0">
                  <span className="text-[10px] font-bold text-[#D1D5DB]">{h.ticker.slice(0, 3)}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[#D1D5DB] text-xs font-medium truncate">{h.name}</p>
                  <p className="text-[#6B7280] text-[10px]">{h.ticker}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[#F9FAFB] text-xs font-medium" style={{ fontFamily: "var(--font-mono)" }}>
                    ${fmt(h.value)}
                  </p>
                  <p className="text-[#22C55E] text-[10px] font-medium">+{h.gainPct}%</p>
                </div>
              </div>
            ))}
          </div>

          {/* Tax loss harvesting callout */}
          <div className="bg-[#22C55E]/10 rounded-lg p-3 border border-[#22C55E]/20">
            <p className="text-[#22C55E] text-[10px] font-semibold uppercase tracking-wider mb-1">
              Tax-Loss Harvest Opportunity
            </p>
            <p className="text-[#F9FAFB] text-sm font-bold" style={{ fontFamily: "var(--font-mono)" }}>
              ${fmt(p.taxLossHarvesting.harvestableAmount)} harvestable
            </p>
            <p className="text-[#9CA3AF] text-[10px] mt-1">
              Est. tax savings: ${fmt(p.taxLossHarvesting.estimatedTaxSavings)} &middot; {p.taxLossHarvesting.candidates} candidates
            </p>
          </div>
        </div>
      </div>
    </MockupFrame>
  );
}
