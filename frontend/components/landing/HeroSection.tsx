import Image from "next/image";
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
              href="#features"
              className="text-sm text-[#9CA3AF] hover:text-[#F9FAFB] transition-colors"
            >
              Features
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

          {/* Product Visual */}
          <div className="max-w-4xl mx-auto mt-16">
            <div className="rounded-xl overflow-hidden border border-[#27272A] shadow-2xl shadow-black/40">
              {/* Browser chrome */}
              <div className="flex items-center gap-1.5 px-4 py-2.5 bg-[#141416]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#EF4444]/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#EAB308]/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#22C55E]/80" />
                <span className="ml-3 text-[10px] text-[#6B7280]">sirhenry.app</span>
              </div>
              <Image
                src="/screenshots/dashboard.png"
                alt="SirHENRY Dashboard — your financial command center"
                width={1280}
                height={800}
                className="w-full h-auto"
                quality={90}
                priority
              />
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
