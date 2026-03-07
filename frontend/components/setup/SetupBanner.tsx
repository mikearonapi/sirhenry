"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Sparkles, X } from "lucide-react";
import Link from "next/link";
import SirHenryName from "@/components/ui/SirHenryName";
import { isSetupComplete } from "@/components/AppShell";
import { getSetupStatus } from "@/lib/api-setup";

export default function SetupBanner() {
  const [show, setShow] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [completionPct, setCompletionPct] = useState(0);

  const checkCompletion = useCallback(async () => {
    if (isSetupComplete()) {
      setShow(false);
      return;
    }

    try {
      const status = await getSetupStatus();

      let done = 0;
      const total = 3;
      if (status.household) done++;
      if (status.income) done++;
      if (status.accounts) done++;

      const pct = Math.round((done / total) * 100);
      setCompletionPct(pct);
      setShow(pct < 100);
    } catch {
      // Silent
    }
  }, []);

  useEffect(() => {
    checkCompletion();
  }, [checkCompletion]);

  if (!show || dismissed) return null;

  return (
    <div className="relative bg-gradient-to-r from-green-50 to-emerald-50 border border-accent/20 rounded-xl p-4">
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-3 right-3 text-text-muted hover:text-text-secondary transition-colors"
      >
        <X size={14} />
      </button>
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
          <Sparkles size={20} className="text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-primary">
            Complete your financial profile
          </p>
          <p className="text-xs text-text-secondary mt-0.5">
            {completionPct === 0
              ? "Set up your household, accounts, and insurance to unlock personalized optimization."
              : <>{completionPct}% complete — finish setting up to get the most from <SirHenryName />.</>
            }
          </p>
          {/* Mini progress bar */}
          <div className="mt-2 h-1 w-32 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all"
              style={{ width: `${completionPct}%` }}
            />
          </div>
        </div>
        <Link
          href="/setup"
          className="flex items-center gap-1.5 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm transition-colors flex-shrink-0"
        >
          Set up
          <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  );
}
