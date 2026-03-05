import { DEMO_TAX } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function TaxStrategyShowcase() {
  const t = DEMO_TAX;
  const checklistPct = Math.round((t.checklist.completed / t.checklist.total) * 100);

  return (
    <MockupFrame title="SirHENRY \u2014 Tax Strategy" dark={false} fadeBottom={false}>
      {/* Tax summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="rounded-lg p-3 border border-[#E5E7EB]">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Est. AGI</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(t.estimatedAGI)}
          </p>
        </div>
        <div className="rounded-lg p-3 border border-[#E5E7EB]">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Effective Rate</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            {t.effectiveRate}%
          </p>
        </div>
        <div className="rounded-lg p-3 border border-[#E5E7EB]">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Marginal Rate</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            {t.marginalRate}%
          </p>
        </div>
        <div className="rounded-lg p-3 border border-[#E5E7EB]">
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider mb-1">Est. Total Tax</p>
          <p className="text-[#EF4444] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(t.estimatedTotalTax)}
          </p>
        </div>
      </div>

      {/* Strategies */}
      <div className="mb-5">
        <p className="text-[#374151] text-xs font-semibold uppercase tracking-wider mb-3">
          Identified Strategies
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {t.strategies.map((s) => (
            <div key={s.title} className="rounded-lg p-3 border border-[#E5E7EB] hover:border-[#16A34A]/30 transition-colors">
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="text-[#111827] text-sm font-medium">{s.title}</p>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0 ${
                  s.complexity === "low"
                    ? "bg-[#F0FDF4] text-[#16A34A] border border-[#DCFCE7]"
                    : "bg-[#FFFBEB] text-[#D97706] border border-[#FEF3C7]"
                }`}>
                  {s.complexity}
                </span>
              </div>
              <p className="text-[#16A34A] text-sm font-semibold" style={{ fontFamily: "var(--font-mono)" }}>
                {s.savings}
              </p>
              <p className="text-[#9CA3AF] text-[10px] mt-1">estimated annual savings</p>
            </div>
          ))}
        </div>
      </div>

      {/* Filing checklist */}
      <div className="rounded-lg p-3 border border-[#E5E7EB]">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[#374151] text-xs font-semibold">Tax Filing Checklist</p>
          <span className="text-[#16A34A] text-xs font-medium" style={{ fontFamily: "var(--font-mono)" }}>
            {t.checklist.completed}/{t.checklist.total}
          </span>
        </div>
        <div className="w-full h-2 bg-[#F3F4F6] rounded-full overflow-hidden">
          <div className="h-full bg-[#16A34A] rounded-full" style={{ width: `${checklistPct}%` }} />
        </div>
      </div>
    </MockupFrame>
  );
}
