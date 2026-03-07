"use client";

import { useState, useEffect } from "react";
import { Shield, X, Loader2, Check } from "lucide-react";
import { getPrivacyDisclosure, setPrivacyConsent } from "@/lib/api";
import type { PrivacyDisclosure } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";

interface ConsentModalProps {
  onAccept: () => void;
  onDecline: () => void;
}

export default function ConsentModal({ onAccept, onDecline }: ConsentModalProps) {
  const [disclosure, setDisclosure] = useState<PrivacyDisclosure | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPrivacyDisclosure()
      .then(setDisclosure)
      .catch((e: unknown) => setError(getErrorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  async function handleAccept() {
    setSubmitting(true);
    setError(null);
    try {
      await setPrivacyConsent("ai_features", true);
      onAccept();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="relative mx-4 w-full max-w-lg rounded-2xl bg-card shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-card-border px-6 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-50">
            <Shield size={18} className="text-emerald-600" />
          </div>
          <div>
            <h2 className="font-display text-lg font-semibold text-text-primary">
              AI Privacy Disclosure
            </h2>
            <p className="text-xs text-text-secondary">
              Please review before using AI features
            </p>
          </div>
          <button
            onClick={onDecline}
            className="ml-auto rounded-lg p-1.5 text-text-muted hover:bg-surface hover:text-text-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={24} className="animate-spin text-text-muted" />
            </div>
          ) : error && !disclosure ? (
            <p className="py-4 text-sm text-red-600">{error}</p>
          ) : disclosure ? (
            <div className="space-y-4">
              <DisclosureSection title="Your Data" items={disclosure.data_handling} />
              <DisclosureSection title="AI Privacy" items={disclosure.ai_privacy} />
              <DisclosureSection title="Encryption" items={disclosure.encryption} />
              <DisclosureSection title="Data Retention" items={disclosure.data_retention} />
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="border-t border-card-border px-6 py-4">
          {error && disclosure && (
            <p className="mb-3 text-xs text-red-600">{error}</p>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={onDecline}
              className="flex-1 rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-surface"
            >
              Not Now
            </button>
            <button
              onClick={handleAccept}
              disabled={loading || submitting}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Check size={16} />
              )}
              I Understand &amp; Accept
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DisclosureSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-1.5 text-sm font-semibold text-text-primary">{title}</h3>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
            <Check size={14} className="mt-0.5 shrink-0 text-emerald-500" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
