"use client";
import { X, Shield, Lock, Database, Cloud, CheckCircle2, EyeOff } from "lucide-react";
import SirHenryName from "@/components/ui/SirHenryName";

interface Props {
  onClose: () => void;
}

export default function DataPrivacyModal({ onClose }: Props) {
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/25 backdrop-blur-sm z-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 flex items-center justify-center z-50 p-4 pointer-events-none">
        <div className="bg-card rounded-2xl shadow-2xl border border-border w-full max-w-lg max-h-[88vh] overflow-y-auto pointer-events-auto">

          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-card-border sticky top-0 bg-card rounded-t-2xl z-10">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-green-50 border border-green-100 flex items-center justify-center">
                <Shield size={18} className="text-accent" />
              </div>
              <div>
                <h2
                  className="font-bold text-text-primary text-[15px]"
                  style={{ fontFamily: "var(--font-display, sans-serif)" }}
                >
                  Your Privacy
                </h2>
                <p className="text-xs text-text-muted">How <SirHenryName /> handles your financial data</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-surface text-text-muted hover:text-text-secondary transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          <div className="px-6 py-5 space-y-5">

            {/* Local-first */}
            <section>
              <div className="flex items-center gap-2 mb-2">
                <Database size={14} className="text-accent" />
                <h3 className="font-semibold text-text-primary text-[13px]">Your data stays on your device</h3>
              </div>
              <p className="text-[12.5px] text-text-secondary leading-relaxed">
                SirHENRY is <strong className="text-text-secondary">local-first</strong>. Your financial data is stored in an encrypted SQLite database on your own machine — not on our servers. We never have direct access to your raw financial data.
              </p>
            </section>

            {/* What is sent to Claude */}
            <section>
              <div className="flex items-center gap-2 mb-2">
                <Cloud size={14} className="text-amber-500" />
                <h3 className="font-semibold text-text-primary text-[13px]">What may be sent to Claude</h3>
              </div>
              <p className="text-[12.5px] text-text-secondary leading-relaxed mb-2.5">
                When you ask a question, <SirHenryName /> shares only what{"'"}s needed to answer it — fetched live from your local database:
              </p>
              <ul className="space-y-1.5">
                {[
                  "Transaction descriptions, amounts, dates, and categories",
                  "Account names and balances (not account numbers)",
                  "Budget targets and actual spending summaries",
                  "Financial goals and progress toward them",
                  "Household income range and filing status",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2 text-[12px] text-text-secondary">
                    <CheckCircle2 size={13} className="text-amber-400 flex-shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>

            {/* PII Sanitizer — highlighted */}
            <section className="bg-green-50 rounded-xl p-4 border border-green-100">
              <div className="flex items-center gap-2 mb-1.5">
                <EyeOff size={14} className="text-accent" />
                <h3 className="font-semibold text-green-800 text-[13px]">Names & identifiers are anonymized</h3>
              </div>
              <p className="text-[12.5px] text-green-700 leading-relaxed">
                Before any data reaches Claude, our <strong>PII Sanitizer</strong> automatically replaces personal identifiers — your name, family members, employer — with generic labels like <em>"Person A"</em> or <em>"Employer 1"</em>. Claude never sees who you actually are.
              </p>
            </section>

            {/* Never sent */}
            <section>
              <div className="flex items-center gap-2 mb-2">
                <Lock size={14} className="text-text-secondary" />
                <h3 className="font-semibold text-text-primary text-[13px]">Never sent to Claude</h3>
              </div>
              <ul className="space-y-1.5">
                {[
                  "Bank account numbers or routing numbers",
                  "Social Security Numbers or tax IDs",
                  "Plaid access tokens (encrypted at rest, never transmitted)",
                  "Passwords or authentication credentials",
                  "Your actual name or employer",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2 text-[12px] text-text-secondary">
                    <div className="w-3.5 h-3.5 rounded-full bg-surface border border-border flex items-center justify-center flex-shrink-0 mt-0.5">
                      <X size={7} className="text-text-muted" />
                    </div>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>

            {/* Anthropic */}
            <section className="bg-surface rounded-xl p-4 border border-card-border">
              <p className="text-[12px] text-text-secondary leading-relaxed">
                AI responses are generated by{" "}
                <strong className="text-text-primary">Anthropic Claude</strong>.{" "}
                Anthropic's{" "}
                <a
                  href="https://www.anthropic.com/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent underline hover:text-accent-hover"
                >
                  privacy policy
                </a>{" "}
                governs how your anonymized queries are handled. Claude does not retain your data between sessions.
              </p>
            </section>

            <p className="text-xs text-text-muted text-center pb-1">
              You can revoke AI access at any time in <strong className="text-text-secondary">Settings → Privacy</strong>.
            </p>
          </div>

          <div className="px-6 pb-6">
            <button
              onClick={onClose}
              className="w-full py-2.5 bg-stone-900 dark:bg-stone-700 text-white text-[13px] font-semibold rounded-xl hover:bg-stone-800 dark:hover:bg-stone-600 transition-colors"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
