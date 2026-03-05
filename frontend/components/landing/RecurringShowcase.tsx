import { DEMO_RECURRING } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function RecurringShowcase() {
  const r = DEMO_RECURRING;
  const maxMonthly = Math.max(...r.byCategory.map((c) => c.monthly));

  return (
    <MockupFrame title="SirHENRY \u2014 Recurring & Subscriptions" dark={false} fadeBottom={false}>
      {/* Summary row */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="rounded-lg p-3 border border-[#E5E7EB]">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Monthly</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(r.totalMonthly)}
          </p>
        </div>
        <div className="rounded-lg p-3 border border-[#E5E7EB]">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Annual</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(r.totalAnnual)}
          </p>
        </div>
        <div className="rounded-lg p-3 border border-[#E5E7EB]">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Active</p>
          <p className="text-[#111827] text-lg font-bold">{r.count} subscriptions</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Left: Category breakdown */}
        <div>
          <p className="text-[#374151] text-xs font-semibold uppercase tracking-wider mb-3">By Category</p>
          <div className="space-y-3">
            {r.byCategory.map((c) => {
              const barWidth = Math.round((c.monthly / maxMonthly) * 100);
              return (
                <div key={c.category}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: c.color }} />
                      <span className="text-[#374151] text-xs">{c.category}</span>
                    </div>
                    <span className="text-[#111827] text-xs font-medium" style={{ fontFamily: "var(--font-mono)" }}>
                      ${fmt(c.monthly)}/mo
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-[#F3F4F6] rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${barWidth}%`, backgroundColor: c.color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Recent subscriptions list */}
        <div>
          <p className="text-[#374151] text-xs font-semibold uppercase tracking-wider mb-3">Recent</p>
          <div className="space-y-2">
            {r.items.map((item) => (
              <div key={item.name} className="flex items-center gap-3 rounded-lg p-2.5 border border-[#E5E7EB]">
                <div className="w-8 h-8 rounded-lg bg-[#F3F4F6] flex items-center justify-center shrink-0">
                  <span className="text-[10px] font-bold text-[#6B7280]">{item.name.slice(0, 2).toUpperCase()}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[#111827] text-xs font-medium truncate">{item.name}</p>
                  <p className="text-[#9CA3AF] text-[10px] capitalize">{item.frequency}</p>
                </div>
                <span className="text-[#111827] text-xs font-medium shrink-0" style={{ fontFamily: "var(--font-mono)" }}>
                  ${item.amount < 100 ? item.amount.toFixed(2) : fmt(item.amount)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </MockupFrame>
  );
}
