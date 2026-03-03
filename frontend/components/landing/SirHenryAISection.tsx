const EXCHANGES = [
  {
    question:
      "Can I afford a $1.4M house on our combined $380K income?",
    answer:
      "Yes \u2014 but it delays retirement from 54 to 59. Your savings rate drops from 19% to 11%, which pushes your trajectory outside the confidence band. Here\u2019s the scenario side by side.",
  },
  {
    question: "My RSUs vest next month. What should I do?",
    answer:
      "Your March vest is $62K. At your marginal rate, that\u2019s a $21,700 tax event \u2014 your withholding will only cover $13,640. Set aside $8,060 now. I\u2019d recommend selling on vest to avoid concentration risk.",
  },
  {
    question:
      "Should I pay off my student loans or invest the extra $3K/month?",
    answer:
      "At 5.5% interest, investing wins mathematically \u2014 expected 7%+ return after tax. But your emergency fund is thin. First: build 3 months of expenses, then redirect to maxing your backdoor Roth, then taxable investing.",
  },
  {
    question: "Am I on track to retire at 55?",
    answer:
      "At your current savings rate of 14%, you reach your $3.2M target at 57 with 68% confidence. To hit 55, you\u2019d need to increase savings by $1,800/month \u2014 or your trajectory shifts if your RSUs keep their current pace.",
  },
];

export default function SirHenryAISection() {
  return (
    <section className="bg-[#0A0A0B] py-24 px-6">
      <div className="max-w-4xl mx-auto">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6B7280] text-center mb-4">
          Your AI advisor
        </p>
        <h2
          className="text-center font-bold text-[#F9FAFB] mb-4"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.75rem, 3.5vw, 2.25rem)",
          }}
        >
          Meet Sir Henry
        </h2>
        <p className="text-center text-[#9CA3AF] text-base leading-relaxed max-w-2xl mx-auto mb-16">
          Not a chatbot. Not a generic calculator. Sir Henry is the AI advisor
          woven through every part of the app — and available to answer any
          financial question, right now, based on your actual numbers.
        </p>

        {/* Example exchanges */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
          {EXCHANGES.map((exchange) => (
            <div
              key={exchange.question}
              className="bg-[#141416] border border-[#27272A] rounded-xl p-6"
            >
              <div className="flex items-start gap-3 mb-4">
                <div className="w-7 h-7 rounded-full bg-[#27272A] flex items-center justify-center shrink-0 text-[#9CA3AF] text-xs font-bold mt-0.5">
                  Q
                </div>
                <p className="text-[#D1D5DB] text-sm leading-relaxed italic">
                  &ldquo;{exchange.question}&rdquo;
                </p>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-[#22C55E]/20 border border-[#22C55E]/30 flex items-center justify-center shrink-0 text-[#22C55E] text-xs font-bold mt-0.5">
                  SH
                </div>
                <p className="text-[#9CA3AF] text-sm leading-relaxed">
                  {exchange.answer}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-[#141416] border border-[#22C55E]/20 rounded-xl p-6 text-center">
          <p className="text-[#22C55E] text-xs font-semibold uppercase tracking-wide mb-2">
            The difference
          </p>
          <p className="text-[#F9FAFB] font-semibold text-lg mb-2" style={{ fontFamily: "var(--font-display)" }}>
            Specific. Personalized. Based on your numbers.
          </p>
          <p className="text-[#6B7280] text-sm max-w-lg mx-auto">
            Not &ldquo;housing is a personal decision that depends on many
            factors.&rdquo; Sir Henry gives you the answer — and shows its
            work.
          </p>
        </div>
      </div>
    </section>
  );
}
