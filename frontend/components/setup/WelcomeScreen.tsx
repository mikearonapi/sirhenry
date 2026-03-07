"use client";
import { ArrowRight, HardDrive, Lock, Brain, Clock } from "lucide-react";
import { OB_HEADING, OB_SUBTITLE, OB_CTA } from "./styles";

/**
 * Full-screen welcome — merges the old Welcome + Privacy screens into one.
 * Shows value prop, time estimate, and three trust pillars inline.
 */
export default function WelcomeScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-background flex items-center justify-center overflow-y-auto">
      <div className="max-w-lg mx-auto px-6 py-12 text-center">
        {/* Brand */}
        <h1 className="text-3xl md:text-4xl tracking-tight text-text-primary">
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
        <h2 className={`${OB_HEADING} mt-6`}>
          Let&apos;s set up your financial&nbsp;profile
        </h2>
        <p className={`${OB_SUBTITLE} max-w-md mx-auto`}>
          In about 10 minutes, Sir HENRY will know your income, accounts,
          benefits, and tax situation&nbsp;&mdash; and start optimizing
          immediately.
        </p>

        {/* Time estimate badge */}
        <div className="mt-5 inline-flex items-center gap-1.5 bg-surface text-text-secondary px-3 py-1.5 rounded-full text-xs font-medium">
          <Clock size={13} />
          ~10 minutes to complete
        </div>

        {/* Trust pillars — inline row */}
        <div className="mt-10 grid grid-cols-1 gap-4 text-left">
          <Pillar
            icon={HardDrive}
            title="Everything stays local"
            body="Your financial data lives on your device. Not our servers, not the cloud."
          />
          <Pillar
            icon={Lock}
            title="Bank connections encrypted"
            body="Plaid connects with read-only access. Credentials are never stored."
          />
          <Pillar
            icon={Brain}
            title="AI respects boundaries"
            body="Only anonymized patterns go to the AI. Personal details stay on your device."
          />
        </div>

        {/* CTA */}
        <button onClick={onStart} className={`${OB_CTA} w-full max-w-sm mx-auto mt-10`}>
          Get Started
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
    <div className="flex gap-3.5 items-start">
      <div className="w-9 h-9 rounded-lg bg-surface flex items-center justify-center flex-shrink-0">
        <Icon size={18} className="text-text-secondary" />
      </div>
      <div>
        <p className="text-sm font-semibold text-text-primary font-display">
          {title}
        </p>
        <p className="text-xs text-text-secondary mt-0.5 leading-relaxed">{body}</p>
      </div>
    </div>
  );
}
