"use client";
import { CheckCircle2, ArrowRight, ChevronRight, MessageCircle } from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData, SetupStep } from "./SetupWizard";
import Link from "next/link";
import SirHenryName from "@/components/ui/SirHenryName";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

interface Props {
  data: SetupData;
  onGoTo: (step: SetupStep) => void;
}

interface CompletionItem {
  label: string;
  done: boolean;
  detail: string;
  unlocks: string;
  step: SetupStep;
  link: string;
}

export default function StepComplete({ data, onGoTo }: Props) {
  const activeAccounts = data.accounts.filter((a) => a.is_active).length;
  const activePolicies = data.policies.filter((p) => p.is_active).length;

  const items: CompletionItem[] = [
    {
      label: "Household Profile",
      done: !!data.household,
      detail: data.household
        ? `${data.household.filing_status?.toUpperCase()} · $${(data.household.combined_income || 0).toLocaleString()} income`
        : "Not set up",
      unlocks: "Tax Strategy · W-4 Optimization · Insurance Gap Analysis",
      step: "household",
      link: "/household",
    },
    {
      label: "Accounts & Assets",
      done: activeAccounts > 0,
      detail: `${activeAccounts} accounts`,
      unlocks: "Cash Flow · Budget Tracking · Spending Insights",
      step: "accounts",
      link: "/accounts",
    },
    {
      label: "Employer & Benefits",
      done: !!data.household,
      detail: data.household ? "Configured" : "Needs household first",
      unlocks: "401k Optimization · HSA Strategy · Retirement Projections",
      step: "employer",
      link: "/household",
    },
    {
      label: "Insurance Coverage",
      done: activePolicies > 0,
      detail: `${activePolicies} policies`,
      unlocks: "Coverage Gap Analysis · Premium Optimization",
      step: "insurance",
      link: "/insurance",
    },
    {
      label: "Business Entities",
      done: true, // Always "done" — it's optional
      detail: data.entities.length > 0
        ? `${data.entities.length} entities`
        : "No business income (OK)",
      unlocks: "Business Expense Tracking · Schedule C/K-1 Tax Planning",
      step: "business",
      link: "/business",
    },
    {
      label: "Life Events",
      done: data.lifeEvents.length > 0,
      detail: `${data.lifeEvents.length} events logged`,
      unlocks: "Tax Impact Checklists · Action Items",
      step: "life-events",
      link: "/life-events",
    },
    {
      label: "AI Learning",
      done: true, // Optional — always marked done
      detail: "Rules & insights ready",
      unlocks: "Auto-Categorization · Spending Insights · Tax Optimization",
      step: "rules",
      link: "/rules",
    },
  ];

  const completedCount = items.filter((i) => i.done).length;
  const totalCount = items.length;

  // Build contextual nudges for missing or incomplete data
  const nudges: string[] = [];
  if (!data.household) {
    nudges.push("Complete your household profile to unlock tax strategy and W-4 optimization");
  } else {
    if (!data.household.spouse_a_income && !data.household.spouse_b_income) {
      nudges.push("Add income details to get accurate tax bracket analysis");
    }
  }
  if (activeAccounts === 0) {
    nudges.push("Connect bank accounts via Plaid for automatic transaction import and spending insights");
  }
  for (const ent of data.entities) {
    if (!ent.owner) {
      nudges.push(`Assign an owner to "${ent.name}" for per-spouse tax attribution`);
    }
  }
  if (activePolicies === 0 && data.household) {
    nudges.push("Add your insurance policies for coverage gap analysis");
  }

  return (
    <div className="space-y-6">
      {/* Success header */}
      <div className="text-center py-6">
        <CheckCircle2 size={48} className="mx-auto text-[#16A34A] mb-3" />
        <h2 className="text-2xl font-bold text-stone-900 font-display">
          You&apos;re all set!
        </h2>
        <p className="text-sm text-stone-500 mt-1 max-w-md mx-auto">
          {completedCount === totalCount
            ? <>Your financial profile is complete. <SirHenryName /> can now provide personalized tax, insurance, and wealth optimization.</>

            : `${completedCount} of ${totalCount} sections configured. You can always come back to add more details.`
          }
        </p>
      </div>

      {/* Completion checklist */}
      <Card padding="md">
        <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-3">
          Setup Summary
        </p>
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.label}
              className="py-2 border-b border-stone-50 last:border-0"
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                    item.done
                      ? "bg-[#16A34A]"
                      : "bg-stone-200"
                  }`}
                >
                  {item.done && <CheckCircle2 size={14} className="text-white" />}
                </div>
                <div className="flex-1 min-w-0">
                  <span className={`text-sm ${item.done ? "text-stone-700" : "text-stone-400"}`}>
                    {item.label}
                  </span>
                  <p className="text-[11px] text-stone-400">{item.detail}</p>
                </div>
                {!item.done && (
                  <button
                    onClick={() => onGoTo(item.step)}
                    className="text-xs text-[#16A34A] hover:underline flex items-center gap-0.5"
                  >
                    Set up <ChevronRight size={12} />
                  </button>
                )}
              </div>
              {item.done && (
                <p className="text-[10px] text-[#16A34A]/60 ml-8 mt-0.5">
                  {item.unlocks}
                </p>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Nudges for missing data */}
      {nudges.length > 0 && (
        <Card padding="sm" className="bg-amber-50/50 border-amber-100">
          <p className="text-xs font-medium text-amber-700 mb-1.5">Tips to get more from <SirHenryName /></p>
          <div className="space-y-1">
            {nudges.map((nudge, i) => (
              <p key={i} className="text-[11px] text-amber-600/80">
                &bull; {nudge}
              </p>
            ))}
          </div>
        </Card>
      )}

      {/* Ask Sir Henry */}
      <button
        type="button"
        onClick={() => askHenry("Now that my setup is complete, what should I focus on first? What are the most impactful financial optimizations I should look into?")}
        className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg border border-[#16A34A]/20 text-sm text-[#16A34A] hover:bg-green-50 transition-colors"
      >
        <MessageCircle size={14} />
        Ask <SirHenryName /> what to focus on first
      </button>

      {/* CTA */}
      <Link
        href="/dashboard"
        className="flex items-center justify-center gap-2 w-full bg-[#16A34A] text-white px-4 py-3 rounded-lg text-sm font-medium hover:bg-[#15803d] shadow-sm transition-colors"
      >
        Go to Dashboard
        <ArrowRight size={14} />
      </Link>

      <p className="text-center text-[11px] text-stone-400">
        You can always update your profile from the sidebar navigation.
      </p>
    </div>
  );
}
