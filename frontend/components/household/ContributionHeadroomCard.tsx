"use client";
import { formatCurrency } from "@/lib/utils";
import type { BenefitPackageType, ManualAsset } from "@/types/api";
import Card from "@/components/ui/Card";
import { LIMITS_2025 } from "./constants";

// ---------------------------------------------------------------------------
// ContributionHeadroomCard — 401k/HSA/FSA contribution progress bars
// ---------------------------------------------------------------------------

export interface ContributionHeadroomCardProps {
  benA: BenefitPackageType | undefined;
  benB: BenefitPackageType | undefined;
  assets: ManualAsset[];
  hasDependents: boolean;
}

export default function ContributionHeadroomCard({
  benA, benB, assets, hasDependents,
}: ContributionHeadroomCardProps) {
  const ytd401k = assets
    .filter((a) => a.account_subtype === "401k_traditional" || a.account_subtype === "401k_roth")
    .reduce((sum, a) => sum + (a.employee_contribution_ytd || 0), 0);
  const ytdHsa = assets
    .filter((a) => a.account_subtype === "hsa")
    .reduce((sum, a) => sum + (a.employee_contribution_ytd || 0) + (a.employer_contribution_ytd || 0), 0);

  const hsaLimit = hasDependents ? LIMITS_2025.hsa_family : LIMITS_2025.hsa_self;
  const k401Limit = LIMITS_2025.k401;
  const k401Pct = Math.min((ytd401k / k401Limit) * 100, 100);
  const hsaPct = Math.min((ytdHsa / hsaLimit) * 100, 100);

  const hasFsa = (benA?.has_fsa || false) || (benB?.has_fsa || false);
  const hasDepFsa = (benA?.has_dep_care_fsa || false) || (benB?.has_dep_care_fsa || false);

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-stone-900">Tax-Advantaged Contribution Headroom</h3>
          <p className="text-xs text-stone-500 mt-0.5">
            2025 limits — pulled from your linked accounts. <a href="/accounts" className="text-[#16A34A] underline underline-offset-2">Update accounts</a> to keep this current.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {/* 401(k) */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-stone-700">401(k) / 403(b) — Employee Contributions</span>
            <span className="text-xs text-stone-500">
              {formatCurrency(ytd401k)} of {formatCurrency(k401Limit)}
            </span>
          </div>
          <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${k401Pct >= 100 ? "bg-green-500" : k401Pct >= 75 ? "bg-amber-400" : "bg-[#16A34A]"}`}
              style={{ width: `${k401Pct}%` }}
            />
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className={`text-[11px] ${k401Pct >= 100 ? "text-green-600 font-medium" : "text-stone-400"}`}>
              {k401Pct >= 100 ? "Max reached" : `${formatCurrency(k401Limit - ytd401k)} remaining`}
            </span>
            {ytd401k === 0 && (
              <span className="text-[11px] text-amber-600 italic">No YTD data — update accounts to track this</span>
            )}
          </div>
        </div>

        {/* HSA */}
        {(benA?.has_hsa || benB?.has_hsa) && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-stone-700">
                HSA — {hasDependents ? "Family" : "Individual"} Coverage
              </span>
              <span className="text-xs text-stone-500">
                {formatCurrency(ytdHsa)} of {formatCurrency(hsaLimit)}
              </span>
            </div>
            <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${hsaPct >= 100 ? "bg-green-500" : hsaPct >= 75 ? "bg-amber-400" : "bg-blue-500"}`}
                style={{ width: `${hsaPct}%` }}
              />
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className={`text-[11px] ${hsaPct >= 100 ? "text-green-600 font-medium" : "text-stone-400"}`}>
                {hsaPct >= 100 ? "Max reached" : `${formatCurrency(hsaLimit - ytdHsa)} remaining`}
              </span>
              {ytdHsa === 0 && (
                <span className="text-[11px] text-amber-600 italic">No YTD data — link HSA account</span>
              )}
            </div>
          </div>
        )}

        {/* FSA */}
        {hasFsa && (
          <div className="flex items-center justify-between py-2 border-t border-stone-100">
            <div>
              <span className="text-xs font-medium text-stone-700">FSA (Healthcare)</span>
              <p className="text-[11px] text-stone-400">Use-it-or-lose-it annual limit</p>
            </div>
            <span className="text-xs font-semibold text-stone-700">{formatCurrency(LIMITS_2025.fsa)} / year</span>
          </div>
        )}
        {hasDepFsa && (
          <div className="flex items-center justify-between py-2 border-t border-stone-100">
            <div>
              <span className="text-xs font-medium text-stone-700">Dependent Care FSA</span>
              <p className="text-[11px] text-stone-400">Reduces taxable income for childcare costs</p>
            </div>
            <span className="text-xs font-semibold text-stone-700">{formatCurrency(LIMITS_2025.dep_care_fsa)} / year</span>
          </div>
        )}

        {/* Footer */}
        <div className="pt-2 border-t border-stone-100">
          <p className="text-[11px] text-stone-400">
            YTD contribution data comes from manual assets with a 401(k) or HSA account subtype.
            {" "}<a href="/tax-strategy" className="text-[#16A34A] underline underline-offset-2">View Tax Strategy</a> to see how maxing these accounts reduces your tax liability.
          </p>
        </div>
      </div>
    </Card>
  );
}
