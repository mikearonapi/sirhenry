const PARADOX_CARDS = [
  {
    stat: "36%",
    label: "of $250K+ earners live paycheck to paycheck",
    sub: "Lifestyle creep is silent. Every raise gets absorbed by a slightly bigger house, a slightly nicer car, one more thing.",
    source: "LendingClub, 2024",
  },
  {
    stat: "77%",
    label: "of HENRYs lose sleep over their finances",
    sub: "Not because they spend carelessly \u2014 because they have no scoreboard. No one can tell them if they\u2019re actually on track.",
    source: "Project Henry, 2025",
  },
  {
    stat: "$15K+",
    label: "per year to access a real financial advisor",
    sub: "Wealth managers require $1M minimums. CFPs charge $5K\u2013$15K/year. Reddit is free \u2014 and worth exactly that.",
    source: "Flat Fee Advisors, 2025",
  },
];

export default function HenryParadoxSection() {
  return (
    <section className="bg-white py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#9CA3AF] text-center mb-4">
          The HENRY paradox
        </p>
        <h2
          className="text-center font-bold text-[#111827] mb-6"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.75rem, 3.5vw, 2.25rem)",
          }}
        >
          High earner. Not rich yet.
        </h2>
        <p className="text-center text-[#6B7280] text-base leading-relaxed max-w-2xl mx-auto mb-16">
          You&apos;ve done everything right — the degree, the career, the
          raises. But the money doesn&apos;t feel like it adds up. You&apos;re
          not in debt trouble. You&apos;re in the advice gap.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PARADOX_CARDS.map((card) => (
            <div
              key={card.stat}
              className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-xl p-6"
            >
              <p
                className="text-[#16A34A] font-extrabold mb-1"
                style={{ fontSize: "clamp(2rem, 4vw, 2.5rem)", fontFamily: "var(--font-display)" }}
              >
                {card.stat}
              </p>
              <p className="font-semibold text-[#111827] text-sm mb-3">
                {card.label}
              </p>
              <p className="text-[#6B7280] text-sm leading-relaxed mb-3">
                {card.sub}
              </p>
              <p className="text-[#9CA3AF] text-xs">{card.source}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
