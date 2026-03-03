import { ShieldCheck } from "lucide-react";
import SirHenryBrand from "./SirHenryBrand";
import WaitlistForm from "./WaitlistForm";

export default function HeroSection() {
  return (
    <>
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-[#0A0A0B]/95 backdrop-blur-md border-b border-[#27272A]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <SirHenryBrand className="text-white text-xl font-bold" />
          <div className="hidden md:flex items-center gap-8">
            <a
              href="#how-it-works"
              className="text-sm text-[#9CA3AF] hover:text-[#F9FAFB] transition-colors"
            >
              How it works
            </a>
            <a
              href="#compare"
              className="text-sm text-[#9CA3AF] hover:text-[#F9FAFB] transition-colors"
            >
              Compare
            </a>
            <a
              href="#community"
              className="text-sm text-[#9CA3AF] hover:text-[#F9FAFB] transition-colors"
            >
              Community
            </a>
          </div>
          <a
            href="#waitlist"
            className="text-sm font-semibold bg-[#16A34A] hover:bg-[#15803D] text-white px-5 py-2 rounded-lg transition-colors"
          >
            Join the waitlist
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="bg-[#0A0A0B] pt-20 pb-16 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-[#EAB308]/10 border border-[#EAB308]/20 rounded-full px-4 py-1.5 mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-[#EAB308] animate-pulse" />
            <span className="text-[#EAB308] text-xs font-semibold tracking-wide uppercase">
              Coming soon &middot; Spring 2026
            </span>
          </div>

          <h1
            className="text-[#F9FAFB] font-extrabold leading-[1.1] mb-6"
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "clamp(2.5rem, 6vw, 4rem)",
            }}
          >
            The financial advisor
            <br />
            <span className="text-[#22C55E]">you&apos;ve been earning.</span>
          </h1>

          <p className="text-[#9CA3AF] text-lg leading-relaxed max-w-2xl mx-auto mb-10">
            You earn well. You earn <em>really</em> well. But 36% of households
            earning $250K+ still live paycheck to paycheck — and 77% lose sleep
            over money. <SirHenryBrand className="text-[#F9FAFB]" /> is your AI
            financial advisor, built for the way high earners actually live.
          </p>

          <WaitlistForm dark />

          {/* Social proof strip */}
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 mt-12 text-[#6B7280] text-xs font-medium">
            <div className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-[#22C55E]" />
              No minimums
            </div>
            <div className="w-px h-4 bg-[#27272A] hidden sm:block" />
            <div className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-[#22C55E]" />
              No commissions
            </div>
            <div className="w-px h-4 bg-[#27272A] hidden sm:block" />
            <div className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-[#22C55E]" />
              Your data stays yours
            </div>
          </div>

          {/* Product Visual Placeholder */}
          <div className="max-w-4xl mx-auto mt-16">
            <div className="relative rounded-xl border border-[#27272A] bg-[#141416] overflow-hidden shadow-2xl shadow-[#22C55E]/5">
              {/* Window chrome */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[#27272A]">
                <div className="w-3 h-3 rounded-full bg-[#EF4444]/60" />
                <div className="w-3 h-3 rounded-full bg-[#EAB308]/60" />
                <div className="w-3 h-3 rounded-full bg-[#22C55E]/60" />
                <span className="ml-3 text-[#6B7280] text-xs">SirHENRY Dashboard</span>
              </div>

              {/* Dashboard content */}
              <div className="p-5 sm:p-8">
                {/* Top metrics row */}
                <div className="grid grid-cols-3 gap-3 sm:gap-4 mb-5 sm:mb-6">
                  <div className="bg-[#1C1C1F] rounded-lg p-3 sm:p-4 border border-[#27272A]">
                    <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">
                      Net Worth
                    </p>
                    <p className="text-[#F9FAFB] text-base sm:text-xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
                      $347,000
                    </p>
                    <p className="text-[#22C55E] text-[10px] sm:text-xs font-medium mt-1">
                      +$12K (90d)
                    </p>
                  </div>
                  <div className="bg-[#1C1C1F] rounded-lg p-3 sm:p-4 border border-[#27272A]">
                    <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">
                      Savings Rate
                    </p>
                    <p className="text-[#F9FAFB] text-base sm:text-xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
                      18.2%
                    </p>
                    <p className="text-[#22C55E] text-[10px] sm:text-xs font-medium mt-1">
                      On track
                    </p>
                  </div>
                  <div className="bg-[#1C1C1F] rounded-lg p-3 sm:p-4 border border-[#27272A]">
                    <p className="text-[#6B7280] text-[10px] font-semibold uppercase tracking-wider mb-1">
                      Retire By
                    </p>
                    <p className="text-[#F9FAFB] text-base sm:text-xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>
                      Age 54
                    </p>
                    <p className="text-[#22C55E] text-[10px] sm:text-xs font-medium mt-1">
                      84% confidence
                    </p>
                  </div>
                </div>

                {/* Trajectory chart placeholder */}
                <div className="bg-[#1C1C1F] rounded-lg p-4 sm:p-5 border border-[#27272A] mb-5 sm:mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[#9CA3AF] text-[10px] sm:text-xs font-semibold uppercase tracking-wider">
                      30-Year Trajectory
                    </p>
                    <div className="flex gap-1.5 sm:gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#22C55E]/10 text-[#22C55E] font-medium">
                        10Y
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#27272A] text-[#6B7280] font-medium">
                        20Y
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#27272A] text-[#6B7280] font-medium">
                        30Y
                      </span>
                    </div>
                  </div>
                  <div className="relative h-28 sm:h-40">
                    <svg
                      viewBox="0 0 400 120"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                      className="w-full h-full"
                      preserveAspectRatio="none"
                    >
                      {/* Grid lines */}
                      <line x1="0" y1="30" x2="400" y2="30" stroke="#27272A" strokeWidth="0.5" />
                      <line x1="0" y1="60" x2="400" y2="60" stroke="#27272A" strokeWidth="0.5" />
                      <line x1="0" y1="90" x2="400" y2="90" stroke="#27272A" strokeWidth="0.5" />
                      {/* Confidence band (fan) */}
                      <path
                        d="M0,105 Q80,95 160,75 Q240,50 320,30 Q360,20 400,8 L400,45 Q360,52 320,60 Q240,75 160,88 Q80,100 0,108 Z"
                        fill="#22C55E"
                        opacity="0.06"
                      />
                      <path
                        d="M0,103 Q80,92 160,70 Q240,45 320,25 Q360,16 400,5 L400,40 Q360,47 320,55 Q240,68 160,82 Q80,97 0,106 Z"
                        fill="#22C55E"
                        opacity="0.1"
                      />
                      {/* Median trajectory line */}
                      <path
                        d="M0,104 Q80,93 160,72 Q240,47 320,27 Q360,18 400,7"
                        stroke="#22C55E"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                    </svg>
                  </div>
                </div>

                {/* Action plan preview */}
                <div className="bg-[#1C1C1F] rounded-lg p-4 sm:p-5 border border-[#27272A]">
                  <p className="text-[#9CA3AF] text-[10px] sm:text-xs font-semibold uppercase tracking-wider mb-3">
                    Your Action Plan
                  </p>
                  <div className="space-y-2.5">
                    <div className="flex items-center gap-3">
                      <div className="w-5 h-5 rounded bg-[#22C55E]/20 flex items-center justify-center shrink-0">
                        <div className="w-2 h-2 rounded-sm bg-[#22C55E]" />
                      </div>
                      <span className="text-[#D1D5DB] text-xs flex-1 truncate">
                        Max out backdoor Roth IRA
                      </span>
                      <span className="text-[#22C55E] text-xs font-medium shrink-0" style={{ fontFamily: "var(--font-mono)" }}>
                        +$14,000/yr
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-5 h-5 rounded border border-[#3F3F46] shrink-0" />
                      <span className="text-[#D1D5DB] text-xs flex-1 truncate">
                        Fund HSA to maximum
                      </span>
                      <span className="text-[#22C55E] text-xs font-medium shrink-0" style={{ fontFamily: "var(--font-mono)" }}>
                        +$8,300/yr
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-5 h-5 rounded border border-[#3F3F46] shrink-0" />
                      <span className="text-[#D1D5DB] text-xs flex-1 truncate">
                        Diversify RSU concentration
                      </span>
                      <span className="text-[#9CA3AF] text-xs font-medium shrink-0" style={{ fontFamily: "var(--font-mono)" }}>
                        Reduce risk
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Subtle gradient overlay at bottom */}
              <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-[#0A0A0B]/60 to-transparent pointer-events-none" />
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
