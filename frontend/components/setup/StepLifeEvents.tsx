"use client";
import { useState } from "react";
import { Check, ChevronDown, ChevronUp, Plus, Sparkles, MessageCircle } from "lucide-react";
import Card from "@/components/ui/Card";
import type { SetupData } from "./SetupWizard";
import { createLifeEvent } from "@/lib/api-life-events";
import { getErrorMessage } from "@/lib/errors";
import SirHenryName from "@/components/ui/SirHenryName";

// Life event categories organized by user relevance, with clear explanations of
// WHY each event matters for taxes, cash flow, wealth, and insurance.

interface EventOption {
  type: string;
  subtype: string;
  label: string;
  impacts: string[];
  example: string;
}

interface EventCategory {
  key: string;
  label: string;
  icon: string;
  color: string;
  desc: string;
  events: EventOption[];
}

const CATEGORIES: EventCategory[] = [
  {
    key: "employment",
    label: "Employment Changes",
    icon: "💼",
    color: "bg-amber-50 border-amber-100",
    desc: "Job changes affect your W-4 withholding, 401k rollover, and benefits enrollment windows.",
    events: [
      {
        type: "employment", subtype: "job_change", label: "Changed jobs",
        impacts: ["W-4 optimization for new salary", "401k rollover within 60 days", "COBRA vs new health plan decision"],
        example: "Started a new position with different salary, benefits, or equity comp",
      },
      {
        type: "employment", subtype: "promotion", label: "Got a promotion / raise",
        impacts: ["Higher tax bracket planning", "Increased retirement contribution capacity"],
        example: "Significant salary increase that changes your tax picture",
      },
      {
        type: "employment", subtype: "layoff", label: "Job loss / layoff",
        impacts: ["Severance is taxable income", "COBRA enrollment deadline (60 days)", "Emergency fund runway planning"],
        example: "Laid off or terminated — need to manage transition finances",
      },
      {
        type: "employment", subtype: "start_business", label: "Started a business",
        impacts: ["Self-employment tax (15.3%)", "Quarterly estimated tax payments", "SEP-IRA / Solo 401k eligibility"],
        example: "Freelancing, consulting, or started an LLC / S-Corp",
      },
      {
        type: "employment", subtype: "retirement", label: "Retired",
        impacts: ["RMD planning at age 73+", "Social Security timing strategy", "Medicare enrollment at 65"],
        example: "Left the workforce — need to plan withdrawal strategy",
      },
    ],
  },
  {
    key: "family",
    label: "Family Changes",
    icon: "👨‍👩‍👧",
    color: "bg-pink-50 border-pink-100",
    desc: "Family events trigger tax credit eligibility, insurance enrollment windows, and estate planning updates.",
    events: [
      {
        type: "family", subtype: "marriage", label: "Got married",
        impacts: ["Filing status changes to MFJ (usually saves money)", "W-4 recalculation for combined income", "Consolidate insurance policies"],
        example: "Marriage creates a 30-day special enrollment period for insurance",
      },
      {
        type: "family", subtype: "birth", label: "Had a baby",
        impacts: ["Child Tax Credit ($2,000/child)", "Dependent Care FSA eligibility", "Life insurance coverage increase needed"],
        example: "New dependent — opens 529 planning and increases insurance needs",
      },
      {
        type: "family", subtype: "adoption", label: "Adopted a child",
        impacts: ["Adoption Tax Credit (up to $16,810)", "Child Tax Credit ($2,000)", "30-day insurance enrollment window"],
        example: "Adoption expenses are eligible for a significant federal tax credit",
      },
      {
        type: "family", subtype: "divorce", label: "Got divorced",
        impacts: ["Filing status reverts to Single/HoH", "QDRO for retirement account division", "Beneficiary updates on all policies"],
        example: "Legal separation or divorce — major tax and insurance changes needed",
      },
    ],
  },
  {
    key: "real_estate",
    label: "Real Estate",
    icon: "🏠",
    color: "bg-blue-50 border-blue-100",
    desc: "Property events affect your net worth, mortgage interest deductions, and insurance requirements.",
    events: [
      {
        type: "real_estate", subtype: "purchase", label: "Bought a home",
        impacts: ["Mortgage interest deduction (if itemizing)", "Property tax deduction (SALT cap $10k)", "Homeowner's insurance required"],
        example: "Purchased primary residence, investment property, or vacation home",
      },
      {
        type: "real_estate", subtype: "sale", label: "Sold a home",
        impacts: ["Capital gains exclusion ($250k/$500k MFJ)", "Cost basis documentation needed", "Update insurance and net worth"],
        example: "Sold a property — need to track gain/loss for tax purposes",
      },
      {
        type: "real_estate", subtype: "rental", label: "Started renting out property",
        impacts: ["Rental income on Schedule E", "Annual depreciation deduction", "Landlord insurance needed"],
        example: "Converting property to rental or purchasing an investment property",
      },
      {
        type: "real_estate", subtype: "refinance", label: "Refinanced mortgage",
        impacts: ["Points amortized over loan term", "New payment changes cash flow", "Update payoff timeline"],
        example: "Refinanced for lower rate, shorter term, or cash-out",
      },
    ],
  },
  {
    key: "education",
    label: "Education",
    icon: "🎓",
    color: "bg-green-50 border-green-100",
    desc: "Education events unlock tax credits and affect your savings strategy.",
    events: [
      {
        type: "education", subtype: "529_open", label: "Opened a 529 account",
        impacts: ["State tax deduction (varies by state)", "Tax-free growth for education", "Superfunding option: $90k front-load"],
        example: "Started saving for a child's or grandchild's college education",
      },
      {
        type: "education", subtype: "college", label: "Child started college",
        impacts: ["American Opportunity Credit (up to $2,500/yr)", "529 qualified withdrawal tracking", "Student loan interest deduction"],
        example: "Paying tuition — need to track qualified expenses for credits",
      },
    ],
  },
  {
    key: "estate",
    label: "Estate & Gifts",
    icon: "📜",
    color: "bg-purple-50 border-purple-100",
    desc: "Inheritance, gifts, and estate planning affect your tax liability and wealth transfer strategy.",
    events: [
      {
        type: "estate", subtype: "inheritance", label: "Received an inheritance",
        impacts: ["Step-up in cost basis (resets capital gains)", "Inherited IRA 10-year distribution rule", "Estate tax filing if estate > $13.6M"],
        example: "Inherited cash, investments, or property from a deceased family member",
      },
      {
        type: "estate", subtype: "gift", label: "Made a large gift",
        impacts: ["Annual exclusion: $19,000/person (2025)", "Form 709 if over exclusion", "Reduces lifetime exemption ($13.6M)"],
        example: "Gift to family member, 529 contribution, or charitable giving over $19k",
      },
    ],
  },
  {
    key: "medical",
    label: "Major Medical",
    icon: "🏥",
    color: "bg-red-50 border-red-100",
    desc: "Major medical events affect your deductions, disability coverage, and HSA strategy.",
    events: [
      {
        type: "medical", subtype: "major", label: "Major medical event",
        impacts: ["Medical deduction if > 7.5% of AGI", "HSA reimbursement for eligible costs", "Disability coverage review"],
        example: "Surgery, hospitalization, or significant out-of-pocket medical costs",
      },
    ],
  },
  {
    key: "business",
    label: "Business Events",
    icon: "🏢",
    color: "bg-orange-50 border-orange-100",
    desc: "Business transactions can create significant tax events — capital gains, depreciation, and entity structure decisions.",
    events: [
      {
        type: "business", subtype: "asset_sale", label: "Sold a business asset",
        impacts: ["Short vs long-term capital gains", "Section 1231 gain treatment", "Installment sale option"],
        example: "Sold equipment, intellectual property, or a business division",
      },
      {
        type: "business", subtype: "entity_formation", label: "Formed a business entity",
        impacts: ["Entity type affects SE tax rate", "Quarterly estimated payments", "Business liability insurance"],
        example: "Created an LLC, S-Corp, or C-Corp",
      },
    ],
  },
];

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

interface Props {
  data: SetupData;
  onRefresh: () => void;
}

export default function StepLifeEvents({ data, onRefresh }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [addedEvents, setAddedEvents] = useState<string[]>([]);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const existingKeys = new Set(
    data.lifeEvents.map((e) => `${e.event_type}:${e.event_subtype}`)
  );

  async function handleAddEvent(event: EventOption) {
    const key = `${event.type}:${event.subtype}`;
    setSaving(key);
    setError(null);
    try {
      const today = new Date().toISOString().split("T")[0];
      await createLifeEvent({
        event_type: event.type,
        event_subtype: event.subtype,
        title: event.label,
        event_date: today,
        tax_year: new Date().getFullYear(),
        status: "completed",
        household_id: data.household?.id ?? null,
      });
      setAddedEvents([...addedEvents, key]);
      onRefresh();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(null);
    }
  }

  const isAdded = (type: string, subtype: string) => {
    const key = `${type}:${subtype}`;
    return existingKeys.has(key) || addedEvents.includes(key);
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 font-display">
          Recent life events
        </h2>
        <p className="text-sm text-stone-500 mt-0.5">
          Life events have major tax, insurance, and planning implications.
          Select anything that happened in the last 1-2 years.
        </p>
        <p className="text-[10px] text-stone-400 mt-1">
          Unlocks: Tax Impact Checklists &middot; Action Items &middot; Timeline Tracking
        </p>
      </div>

      {/* Tip */}
      <Card padding="sm" className="bg-[#DCFCE7]/50 border-[#16A34A]/10">
        <div className="flex items-start gap-2">
          <Sparkles size={14} className="text-[#16A34A] mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-stone-600">
              Each event auto-generates a checklist of tax and insurance actions.
              You can review and complete them on the Life Events page anytime.
            </p>
            <button
              type="button"
              onClick={() => askHenry("Based on my household situation, what life events should I be tracking? Which ones have the biggest tax and financial planning impact?")}
              className="flex items-center gap-1 mt-1.5 text-[11px] text-[#16A34A] hover:underline"
            >
              <MessageCircle size={10} />
              Not sure what to log? Ask <SirHenryName />
            </button>
          </div>
        </div>
      </Card>

      {/* Existing events */}
      {data.lifeEvents.length > 0 && (
        <Card padding="sm">
          <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-2">
            Already logged ({data.lifeEvents.length})
          </p>
          <div className="space-y-1">
            {data.lifeEvents.slice(0, 5).map((e) => (
              <div key={e.id} className="flex items-center gap-2 py-1">
                <Check size={14} className="text-[#16A34A]" />
                <span className="text-sm text-stone-600">{e.title}</span>
              </div>
            ))}
            {data.lifeEvents.length > 5 && (
              <p className="text-xs text-stone-400">+{data.lifeEvents.length - 5} more</p>
            )}
          </div>
        </Card>
      )}

      {/* Categories */}
      <div className="space-y-2">
        {CATEGORIES.map((cat) => {
          const isExpanded = expanded === cat.key;
          const catEventCount = cat.events.filter(
            (e) => isAdded(e.type, e.subtype)
          ).length;

          return (
            <div key={cat.key}>
              <button
                onClick={() => setExpanded(isExpanded ? null : cat.key)}
                className={`w-full p-3 rounded-lg border transition-all text-left flex items-center gap-3 ${
                  catEventCount > 0
                    ? "border-[#16A34A]/20 bg-green-50/30"
                    : `${cat.color}`
                }`}
              >
                <span className="text-lg">{cat.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-stone-800">{cat.label}</span>
                    {catEventCount > 0 && (
                      <span className="text-[10px] font-medium text-[#16A34A] bg-green-100 px-1.5 py-0.5 rounded">
                        {catEventCount} logged
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-stone-400 mt-0.5">{cat.desc}</p>
                </div>
                {isExpanded ? (
                  <ChevronUp size={16} className="text-stone-400" />
                ) : (
                  <ChevronDown size={16} className="text-stone-400" />
                )}
              </button>

              {isExpanded && (
                <div className="ml-4 mt-1 space-y-1.5 mb-2">
                  {cat.events.map((event) => {
                    const key = `${event.type}:${event.subtype}`;
                    const added = isAdded(event.type, event.subtype);
                    const isSaving = saving === key;

                    return (
                      <div
                        key={key}
                        className={`p-3 rounded-lg border transition-all ${
                          added
                            ? "border-[#16A34A]/20 bg-green-50/50"
                            : "border-stone-150 bg-white"
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <div className="flex-1">
                            <p className="text-sm font-medium text-stone-700">{event.label}</p>
                            <p className="text-[11px] text-stone-400 mt-0.5">{event.example}</p>
                            <div className="mt-2 space-y-0.5">
                              {event.impacts.map((impact, i) => (
                                <div key={i} className="flex items-start gap-1.5">
                                  <span className="text-[10px] text-stone-300 mt-0.5">&#8226;</span>
                                  <span className="text-[11px] text-stone-500">{impact}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                          {added ? (
                            <div className="flex items-center gap-1 text-[#16A34A]">
                              <Check size={14} />
                              <span className="text-xs font-medium">Logged</span>
                            </div>
                          ) : (
                            <button
                              onClick={() => handleAddEvent(event)}
                              disabled={isSaving}
                              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-stone-100 text-xs font-medium text-stone-600 hover:bg-stone-200 disabled:opacity-50 transition-colors flex-shrink-0"
                            >
                              {isSaving ? "..." : <><Plus size={12} /> Log this</>}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

      <Card padding="sm" className="bg-stone-50 border-stone-100">
        <p className="text-[11px] text-stone-500">
          Nothing happened recently? No problem — skip this step. You can log events anytime from the{" "}
          <a href="/life-events" className="text-[#16A34A] hover:underline">Life Events page</a>.
        </p>
      </Card>
    </div>
  );
}
