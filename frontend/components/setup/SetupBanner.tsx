"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { getHouseholdProfiles } from "@/lib/api-household";
import { getAccounts } from "@/lib/api-accounts";
import { getInsurancePolicies } from "@/lib/api-insurance";
import type { HouseholdProfile } from "@/types/household";
import type { Account } from "@/types/accounts";
import type { InsurancePolicy } from "@/types/insurance";

export default function SetupBanner() {
  const [show, setShow] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [completionPct, setCompletionPct] = useState(0);

  const checkCompletion = useCallback(async () => {
    try {
      const [profiles, accounts, policies] = await Promise.all([
        getHouseholdProfiles().catch(() => []),
        getAccounts().catch(() => []),
        getInsurancePolicies().catch(() => []),
      ]);

      let done = 0;
      const total = 3; // household, accounts, insurance
      if ((profiles as HouseholdProfile[]).length > 0) done++;
      if ((accounts as Account[]).filter((a) => a.is_active).length > 0) done++;
      if ((policies as InsurancePolicy[]).filter((p) => p.is_active).length > 0) done++;

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
    <div className="relative bg-gradient-to-r from-green-50 to-emerald-50 border border-[#16A34A]/20 rounded-xl p-4">
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-3 right-3 text-stone-400 hover:text-stone-600 transition-colors"
      >
        <X size={14} />
      </button>
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-[#16A34A]/10 flex items-center justify-center flex-shrink-0">
          <Sparkles size={20} className="text-[#16A34A]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-stone-800">
            Complete your financial profile
          </p>
          <p className="text-xs text-stone-500 mt-0.5">
            {completionPct === 0
              ? "Set up your household, accounts, and insurance to unlock personalized optimization."
              : `${completionPct}% complete — finish setting up to get the most from Sir Henry.`
            }
          </p>
          {/* Mini progress bar */}
          <div className="mt-2 h-1 w-32 bg-stone-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-[#16A34A] rounded-full transition-all"
              style={{ width: `${completionPct}%` }}
            />
          </div>
        </div>
        <Link
          href="/setup"
          className="flex items-center gap-1.5 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm transition-colors flex-shrink-0"
        >
          Set up
          <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  );
}
