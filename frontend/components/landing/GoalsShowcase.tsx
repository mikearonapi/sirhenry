import { DEMO_GOALS } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function GoalsShowcase() {
  const goals = DEMO_GOALS;
  const totalMonthly = goals.reduce((s, g) => s + g.monthly, 0);
  const onTrackCount = goals.filter((g) => g.onTrack).length;

  return (
    <MockupFrame title="SirHENRY \u2014 Goals" dark={false} fadeBottom={false}>
      {/* Summary strip */}
      <div className="flex flex-wrap items-center gap-4 mb-5 pb-4 border-b border-[#E5E7EB]">
        <div>
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider">Active Goals</p>
          <p className="text-[#111827] text-lg font-bold">{goals.length}</p>
        </div>
        <div className="w-px h-8 bg-[#E5E7EB]" />
        <div>
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider">On Track</p>
          <p className="text-[#16A34A] text-lg font-bold">{onTrackCount}/{goals.length}</p>
        </div>
        <div className="w-px h-8 bg-[#E5E7EB]" />
        <div>
          <p className="text-[#9CA3AF] text-[10px] font-semibold uppercase tracking-wider">Monthly Commitment</p>
          <p className="text-[#111827] text-lg font-bold" style={{ fontFamily: "var(--font-mono)" }}>
            ${fmt(totalMonthly)}
          </p>
        </div>
      </div>

      {/* Goal cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {goals.map((g) => (
          <div key={g.name} className="rounded-xl overflow-hidden border border-[#E5E7EB]">
            {/* Gradient header */}
            <div className={`bg-gradient-to-br ${g.gradient} px-4 py-3`}>
              <p className="text-white/70 text-[10px] font-semibold uppercase tracking-wider">{g.name}</p>
              <p className="text-white text-xl font-bold mt-1" style={{ fontFamily: "var(--font-mono)" }}>
                ${fmt(g.current)}
              </p>
              <p className="text-white/60 text-[10px] mt-0.5">
                of ${fmt(g.target)} goal
              </p>
            </div>
            {/* Progress section */}
            <div className="p-4 bg-white">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                  g.onTrack
                    ? "bg-[#F0FDF4] text-[#16A34A] border border-[#DCFCE7]"
                    : "bg-[#FEF2F2] text-[#EF4444] border border-[#FECACA]"
                }`}>
                  {g.onTrack ? "On track" : "Behind"}
                </span>
                <span className="text-[#6B7280] text-[10px]" style={{ fontFamily: "var(--font-mono)" }}>
                  {g.pct}%
                </span>
              </div>
              <div className="w-full h-2 bg-[#F3F4F6] rounded-full overflow-hidden mb-2">
                <div
                  className={`h-full rounded-full ${g.onTrack ? "bg-[#16A34A]" : "bg-[#EF4444]"}`}
                  style={{ width: `${g.pct}%` }}
                />
              </div>
              <p className="text-[#9CA3AF] text-[10px]">
                ${fmt(g.monthly)}/mo contribution
              </p>
            </div>
          </div>
        ))}
      </div>
    </MockupFrame>
  );
}
