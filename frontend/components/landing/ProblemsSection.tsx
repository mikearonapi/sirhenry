import { DollarSign, BarChart3, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import SirHenryName from "@/components/ui/SirHenryName";

interface Problem {
  icon: LucideIcon;
  number: string;
  title: string;
  quote: string;
  detail: string;
  fix: ReactNode;
}

const PROBLEMS: Problem[] = [
  {
    icon: DollarSign,
    number: "01",
    title: "Cash Flow Mystery",
    quote: "\"Where does all my money go?\"",
    detail:
      "You earn $300K. You save like you earn $150K. Lifestyle creep happens in slow motion and no one\u2019s tracking it at the right altitude.",
    fix: "Cash flow x-ray \u2014 income, fixed costs, discretionary, and your actual wealth-building rate.",
  },
  {
    icon: BarChart3,
    number: "02",
    title: "No Financial Scoreboard",
    quote: "\"Am I actually on track?\"",
    detail:
      "You check your 401(k) quarterly and your bank balance daily \u2014 but you have no idea if you\u2019re ahead, behind, or just treading water.",
    fix: "A personalized scoreboard: net worth, savings rate vs. required, and a clear on-track / at-risk signal.",
  },
  {
    icon: Zap,
    number: "03",
    title: "The Advice Gap",
    quote: "\"I need guidance but I can't access it.\"",
    detail:
      "Wealth managers want $1M+ to talk to you. CFPs charge $5K\u2013$15K/year. You\u2019re too sophisticated for robo-advisors and too busy for Reddit.",
    fix: <><SirHenryName /> — an AI advisor who knows your complete financial picture and is available right now.</>,
  },
];

export default function ProblemsSection() {
  return (
    <section className="bg-[#0A0A0B] py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6B7280] text-center mb-4">
          The problems we solve
        </p>
        <h2
          className="text-center font-bold text-[#F9FAFB] mb-4"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.75rem, 3.5vw, 2.25rem)",
          }}
        >
          Three problems. One platform.
        </h2>
        <p className="text-center text-[#6B7280] text-base leading-relaxed max-w-2xl mx-auto mb-16">
          These aren&apos;t generic money problems. They&apos;re the core
          frustrations of earning a lot and still not having clear answers.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PROBLEMS.map((problem) => (
            <div
              key={problem.number}
              className="bg-[#141416] border border-[#27272A] rounded-xl p-6 flex flex-col gap-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#22C55E]/10 flex items-center justify-center shrink-0">
                  <problem.icon size={20} className="text-[#22C55E]" />
                </div>
                <span className="text-[#27272A] font-mono text-xs font-bold mt-1">
                  {problem.number}
                </span>
              </div>
              <div>
                <h3
                  className="text-[#F9FAFB] font-semibold text-base mb-1"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {problem.title}
                </h3>
                <p className="text-[#22C55E] text-xs font-medium mb-2">
                  {problem.quote}
                </p>
                <p className="text-[#6B7280] text-xs leading-relaxed mb-3">
                  {problem.detail}
                </p>
                <div className="border-t border-[#27272A] pt-3">
                  <p className="text-[#9CA3AF] text-xs leading-relaxed">
                    <span className="text-[#22C55E] font-semibold">
                      How we solve it:{" "}
                    </span>
                    {problem.fix}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
