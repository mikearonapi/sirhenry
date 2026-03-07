import { CheckCircle, Minus } from "lucide-react";
import SirHenryBrand from "./SirHenryBrand";

const ROWS: [string, boolean, boolean, boolean][] = [
  ["Monte Carlo retirement simulation", false, false, true],
  ["AI advisor (your actual numbers)", false, false, true],
  ["Equity comp + RSU guidance", false, false, true],
  ["Personalized tax strategy", false, false, true],
  ["Household dual-income optimization", false, false, true],
  ["Budget forecasting & velocity", true, false, true],
  ["Goal tracking with templates", true, false, true],
  ["Subscription & recurring audit", true, false, true],
  ["Bank sync (Plaid)", true, true, true],
  ["Spending / cash flow view", true, false, true],
  ["Investment portfolio view", false, true, true],
  ["No minimums / No commissions", true, false, true],
];

export default function ComparisonTable() {
  return (
    <section id="compare" className="bg-card py-24 px-6">
      <div className="max-w-3xl mx-auto">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#9CA3AF] text-center mb-4">
          How we compare
        </p>
        <h2
          className="text-center font-bold text-[#111827] mb-4"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.75rem, 3.5vw, 2.25rem)",
          }}
        >
          Not a budgeting app. Not a robo-advisor.
        </h2>
        <p className="text-center text-[#6B7280] text-sm leading-relaxed max-w-xl mx-auto mb-12">
          Built for HENRYs who&apos;ve outgrown basic tools and can&apos;t
          justify $15K/year for a CFP.
        </p>

        {/* Desktop: table (md+) */}
        <div className="hidden md:block border border-[#E5E7EB] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#F9FAFB] border-b border-[#E5E7EB]">
                <th className="text-left px-6 py-4 text-[#6B7280] font-semibold">
                  Capability
                </th>
                <th className="text-center px-4 py-4 text-[#6B7280] font-semibold">
                  YNAB / Monarch
                </th>
                <th className="text-center px-4 py-4 text-[#6B7280] font-semibold">
                  Betterment
                </th>
                <th
                  className="text-center px-4 py-4 font-bold"
                  style={{ color: "#16A34A" }}
                >
                  Sir<span className="tracking-wide">HENRY</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F4F6]">
              {ROWS.map(([feature, col1, col2, col3]) => (
                <tr
                  key={String(feature)}
                  className="hover:bg-[#FAFAFA] transition-colors"
                >
                  <td className="px-6 py-3.5 text-[#374151] font-medium">
                    {String(feature)}
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    {col1 ? (
                      <CheckCircle size={16} className="text-[#22C55E] mx-auto" />
                    ) : (
                      <Minus size={16} className="text-[#D1D5DB] mx-auto" />
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    {col2 ? (
                      <CheckCircle size={16} className="text-[#22C55E] mx-auto" />
                    ) : (
                      <Minus size={16} className="text-[#D1D5DB] mx-auto" />
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-center bg-[#F0FDF4]">
                    {col3 ? (
                      <CheckCircle size={16} className="text-accent mx-auto" />
                    ) : (
                      <Minus size={16} className="text-[#D1D5DB] mx-auto" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile: cards (<md) */}
        <div className="md:hidden space-y-3">
          {ROWS.map(([feature, col1, col2, col3]) => (
            <div
              key={String(feature)}
              className="border border-[#E5E7EB] rounded-xl p-4"
            >
              <p className="text-[#111827] font-medium text-sm mb-3">
                {String(feature)}
              </p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-[#6B7280]">
                  {col1 ? (
                    <CheckCircle size={14} className="text-[#22C55E]" />
                  ) : (
                    <Minus size={14} className="text-[#D1D5DB]" />
                  )}
                  <span>YNAB</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-[#6B7280]">
                  {col2 ? (
                    <CheckCircle size={14} className="text-[#22C55E]" />
                  ) : (
                    <Minus size={14} className="text-[#D1D5DB]" />
                  )}
                  <span>Betterment</span>
                </div>
                <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                  {col3 ? (
                    <CheckCircle size={14} className="text-accent" />
                  ) : (
                    <Minus size={14} className="text-[#D1D5DB]" />
                  )}
                  <SirHenryBrand />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
