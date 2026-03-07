import { BarChart3, TrendingUp, Brain, MessageSquare } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import SirHenryBrand from "./SirHenryBrand";
import SirHenryName from "@/components/ui/SirHenryName";
import type { ReactNode } from "react";

interface Capability {
  icon: LucideIcon;
  title: ReactNode;
  tag: string;
  description: string;
}

const CAPABILITIES: Capability[] = [
  {
    icon: BarChart3,
    title: "The Scoreboard",
    tag: "Where you stand",
    description:
      "Net worth broken down by category. Your real savings rate vs. what you need. A clear signal \u2014 on track, at risk, or behind \u2014 benchmarked against HENRYs with similar age, income, and goals. No more guessing.",
  },
  {
    icon: TrendingUp,
    title: "The Trajectory",
    tag: "Where you're headed",
    description:
      "Monte Carlo projections across 10, 20, and 30 years. Retirement date with a probability range, not a vague estimate. Shown as a fan chart so you can see confidence, not just a single line.",
  },
  {
    icon: Brain,
    title: "The Decision Lab",
    tag: "What happens if...",
    description:
      "Model any major decision before you make it. Buy the house. Take the job. Pay off the loans. Each scenario shows the real impact on your retirement date, savings rate, and net worth trajectory \u2014 side by side.",
  },
  {
    icon: MessageSquare,
    title: <SirHenryName />,
    tag: "Your AI financial advisor",
    description:
      "Ask anything. Sir Henry knows your complete financial picture and gives specific, numbers-backed answers \u2014 not generic advice. Available right now, not in 3 weeks. Thinks like a CFP, talks like a smart friend.",
  },
];

export default function CapabilitiesSection() {
  return (
    <section id="how-it-works" className="bg-card py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#9CA3AF] text-center mb-4">
          How it works
        </p>
        <h2
          className="text-center font-bold text-[#111827] mb-4"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.75rem, 3.5vw, 2.25rem)",
          }}
        >
          Four capabilities. One complete picture.
        </h2>
        <p className="text-center text-[#6B7280] text-base leading-relaxed max-w-2xl mx-auto mb-16">
          Most apps give you data. <SirHenryBrand className="text-[#111827]" /> gives
          you answers — connected across your full financial life.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {CAPABILITIES.map((cap) => (
            <div
              key={cap.tag}
              className="border border-[#E5E7EB] rounded-xl p-7 hover:border-accent/30 hover:bg-[#F0FDF4]/30 transition-colors"
            >
              <div className="flex items-start gap-4 mb-4">
                <div className="w-11 h-11 rounded-lg bg-[#F0FDF4] flex items-center justify-center shrink-0">
                  <cap.icon size={22} className="text-accent" />
                </div>
                <div>
                  <p className="text-accent text-xs font-semibold uppercase tracking-wide mb-0.5">
                    {cap.tag}
                  </p>
                  <h3
                    className="text-[#111827] font-semibold text-lg"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {cap.title}
                  </h3>
                </div>
              </div>
              <p className="text-[#6B7280] text-sm leading-relaxed">
                {cap.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
