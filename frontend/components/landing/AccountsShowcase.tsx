import { DEMO_ACCOUNTS } from "./demo-data";
import MockupFrame from "./MockupFrame";

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export default function AccountsShowcase() {
  const a = DEMO_ACCOUNTS;
  const totalPositive = a.byType.filter((t) => t.value > 0).reduce((s, t) => s + t.value, 0);

  return (
    <MockupFrame title="SirHENRY \u2014 Accounts">
      {/* Net worth header */}
      <div className="mb-5 pb-4 border-b border-[#27272A]">
        <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">Total Net Worth</p>
        <p className="text-[#F9FAFB] text-3xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
          ${fmt(a.totalNetWorth)}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Left: Account type breakdown */}
        <div>
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-3">By Account Type</p>

          {/* Stacked bar */}
          <div className="flex h-3 rounded-full overflow-hidden mb-4">
            {a.byType.filter((t) => t.value > 0).map((t) => (
              <div
                key={t.type}
                className="h-full first:rounded-l-full last:rounded-r-full"
                style={{ width: `${(t.value / totalPositive) * 100}%`, backgroundColor: t.color }}
              />
            ))}
          </div>

          <div className="space-y-3">
            {a.byType.map((t) => (
              <div key={t.type} className="flex items-center gap-3">
                <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: t.color }} />
                <div className="flex-1">
                  <p className="text-[#D1D5DB] text-xs">{t.type}</p>
                  <p className="text-[#6B7280] text-[10px]">{t.accounts} account{t.accounts !== 1 ? "s" : ""}</p>
                </div>
                <span className={`text-sm font-medium ${t.value < 0 ? "text-[#EF4444]" : "text-[#F9FAFB]"}`} style={{ fontFamily: "var(--font-mono)" }}>
                  {t.value < 0 ? "-" : ""}${fmt(Math.abs(t.value))}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Connected institutions */}
        <div>
          <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-3">Connected Banks</p>
          <div className="space-y-2">
            {a.connections.map((c) => (
              <div key={c.institution} className="bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A] flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#27272A] flex items-center justify-center shrink-0">
                  <span className="text-xs font-bold text-[#D1D5DB]">{c.institution.slice(0, 2)}</span>
                </div>
                <div className="flex-1">
                  <p className="text-[#D1D5DB] text-sm font-medium">{c.institution}</p>
                  <p className="text-[#6B7280] text-[10px]">{c.accounts} accounts</p>
                </div>
                <div className="text-right shrink-0">
                  <div className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" />
                    <span className="text-[#22C55E] text-[10px] font-medium">Connected</span>
                  </div>
                  <p className="text-[#6B7280] text-[10px]">{c.lastSynced}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Plaid badge */}
          <div className="mt-4 bg-[#1C1C1F] rounded-lg p-3 border border-[#27272A] flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span className="text-[#9CA3AF] text-[10px]">
              Bank-level encryption via Plaid &middot; Your credentials never touch our servers
            </span>
          </div>
        </div>
      </div>
    </MockupFrame>
  );
}
