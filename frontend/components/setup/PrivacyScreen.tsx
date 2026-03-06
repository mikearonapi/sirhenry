"use client";
import { ArrowRight, HardDrive, Lock, Brain } from "lucide-react";

/**
 * Full-screen privacy & security screen — shown once during onboarding
 * between Welcome and Setup. Apple-style: punchy, confident, minimal.
 */
export default function PrivacyScreen({ onContinue }: { onContinue: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-[#faf9f7] flex items-center justify-center">
      <div className="max-w-lg mx-auto px-6">
        {/* Headline */}
        <h1
          className="text-3xl md:text-4xl font-bold text-stone-900 tracking-tight text-center"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Your finances.
          <br />
          Your device.
          <br />
          <span className="text-[#16A34A]">Your control.</span>
        </h1>

        {/* Three pillars */}
        <div className="mt-10 space-y-6">
          <Pillar
            icon={HardDrive}
            title="Everything stays local."
            body="Your financial data lives in a database on your computer. Not our servers. Not the cloud. Just your machine."
          />
          <Pillar
            icon={Lock}
            title="Bank connections are encrypted."
            body="Plaid connects to your accounts with read-only access. Your bank credentials are never stored — only a secure token, encrypted on your device."
          />
          <Pillar
            icon={Brain}
            title="AI that respects boundaries."
            body="When Sir HENRY analyzes your finances, personal details are stripped. Only anonymized patterns go to the AI. Everything else stays put."
          />
        </div>

        {/* CTA */}
        <button
          onClick={onContinue}
          className="mt-10 w-full flex items-center justify-center gap-2 bg-[#16A34A] text-white px-6 py-3.5 rounded-xl text-base font-semibold hover:bg-[#15803d] shadow-sm transition-colors"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Continue
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}

function Pillar({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-4">
      <div className="w-10 h-10 rounded-xl bg-stone-100 flex items-center justify-center flex-shrink-0">
        <Icon size={20} className="text-stone-600" />
      </div>
      <div>
        <p
          className="text-base font-semibold text-stone-900"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {title}
        </p>
        <p className="text-sm text-stone-500 mt-0.5 leading-relaxed">{body}</p>
      </div>
    </div>
  );
}
