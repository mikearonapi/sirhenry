"use client";
import { ArrowRight, Wallet, Users, Building2, Brain, Shield, Clock } from "lucide-react";

/**
 * Full-screen welcome shown after the splash, before onboarding begins.
 * Sets expectations: ~10 minutes, what they'll do, why it matters.
 */
export default function WelcomeScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-[#faf9f7] flex items-center justify-center">
      <div className="max-w-lg mx-auto px-6 text-center">
        {/* Brand */}
        <h1 className="text-3xl md:text-4xl tracking-tight text-stone-900">
          <span
            className="italic font-light"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Sir
          </span>
          <span
            className="ml-[0.15em] tracking-wide font-extrabold"
            style={{ fontFamily: "var(--font-display)" }}
          >
            HENRY
          </span>
        </h1>

        {/* Headline */}
        <h2
          className="mt-6 text-xl md:text-2xl font-semibold text-stone-800"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Let&apos;s set up your financial profile
        </h2>
        <p className="mt-2 text-sm text-stone-500 max-w-md mx-auto leading-relaxed">
          In about 10 minutes, Sir HENRY will know your income, accounts, benefits,
          and tax situation — and start optimizing immediately.
        </p>

        {/* Time estimate badge */}
        <div className="mt-5 inline-flex items-center gap-1.5 bg-[#16A34A]/10 text-[#16A34A] px-3 py-1.5 rounded-full text-xs font-medium">
          <Clock size={13} />
          ~10 minutes to complete
        </div>

        {/* What you'll do */}
        <div className="mt-8 grid grid-cols-1 gap-2.5 text-left max-w-sm mx-auto">
          {[
            { icon: Users, text: "Set up your household & income" },
            { icon: Wallet, text: "Connect your bank accounts" },
            { icon: Building2, text: "Link employer & benefits" },
            { icon: Shield, text: "Review insurance coverage" },
            { icon: Brain, text: "AI learns your patterns & optimizes" },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-center gap-3 py-2">
              <div className="w-8 h-8 rounded-lg bg-stone-100 flex items-center justify-center flex-shrink-0">
                <Icon size={16} className="text-stone-500" />
              </div>
              <span className="text-sm text-stone-600">{text}</span>
            </div>
          ))}
        </div>

        {/* CTA */}
        <button
          onClick={onStart}
          className="mt-8 w-full max-w-sm mx-auto flex items-center justify-center gap-2 bg-[#16A34A] text-white px-6 py-3.5 rounded-xl text-base font-semibold hover:bg-[#15803d] shadow-sm transition-colors"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Get Started
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
