"use client";
import { useState } from "react";
import { Plus, Trash2, Heart, ChevronDown, ChevronUp } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import Card from "@/components/ui/Card";
import {
  LIMITS_2025, MARGINAL_RATE_EST, UTILIZATION_SCENARIOS,
  calcPlanCost, type PlanOption,
} from "./constants";

// ---------------------------------------------------------------------------
// BenefitsPlanComparison — Health plan comparison calculator
// ---------------------------------------------------------------------------

export interface BenefitsPlanComparisonProps {
  spouseAName: string;
  spouseBName: string;
}

export default function BenefitsPlanComparison({ spouseAName, spouseBName }: BenefitsPlanComparisonProps) {
  const emptyPlan = (): PlanOption => ({
    id: Math.random().toString(36).slice(2),
    name: "",
    type: "ppo",
    premium_monthly: 0,
    deductible: 0,
    oop_max: 0,
    hsa_eligible: false,
    employer_hsa_contribution: 0,
  });

  const [plans, setPlans] = useState<PlanOption[]>([
    { ...emptyPlan(), name: "Spouse A — HDHP", type: "hdhp", hsa_eligible: true },
    { ...emptyPlan(), name: "Spouse A — PPO", type: "ppo" },
  ]);
  const [open, setOpen] = useState(false);

  function addPlan() { setPlans((p) => [...p, { ...emptyPlan() }]); }
  function removePlan(id: string) { setPlans((p) => p.filter((x) => x.id !== id)); }
  function updatePlan(id: string, patch: Partial<PlanOption>) {
    setPlans((p) => p.map((x) => x.id === id ? { ...x, ...patch } : x));
  }

  const costMatrix = plans.map((plan) => ({
    plan,
    costs: UTILIZATION_SCENARIOS.map((s) => calcPlanCost(plan, s.value)),
  }));

  const winners = UTILIZATION_SCENARIOS.map((_, si) => {
    const minCost = Math.min(...costMatrix.map((r) => r.costs[si]));
    return costMatrix.findIndex((r) => r.costs[si] === minCost);
  });

  return (
    <Card padding="lg">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Heart size={16} className="text-[#16A34A]" />
          <h3 className="text-sm font-semibold text-stone-900">Health Plan Comparison Calculator</h3>
        </div>
        {open ? <ChevronUp size={16} className="text-stone-400" /> : <ChevronDown size={16} className="text-stone-400" />}
      </button>

      {!open && (
        <p className="text-xs text-stone-500 mt-1 ml-6">
          Compare HDHP vs PPO vs HMO options across both employers — includes HSA tax savings.
        </p>
      )}

      {open && (
        <div className="mt-4 space-y-4">
          <p className="text-xs text-stone-500">
            Enter the plans available from {spouseAName}&apos;s and {spouseBName}&apos;s employers.
            Costs shown include the HSA tax benefit (est. 28% marginal rate) for eligible plans.
          </p>

          <div className="space-y-3">
            {plans.map((plan, pi) => (
              <div key={plan.id} className="p-3 bg-stone-50 rounded-xl border border-stone-100">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-stone-500 w-5">{pi + 1}.</span>
                  <input
                    value={plan.name}
                    onChange={(e) => updatePlan(plan.id, { name: e.target.value })}
                    placeholder="Plan name (e.g. Aetna HDHP)"
                    className="flex-1 text-sm border border-stone-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20"
                  />
                  <select
                    value={plan.type}
                    onChange={(e) => {
                      const t = e.target.value as PlanOption["type"];
                      updatePlan(plan.id, { type: t, hsa_eligible: t === "hdhp" });
                    }}
                    className="text-xs border border-stone-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none"
                  >
                    <option value="hdhp">HDHP</option>
                    <option value="ppo">PPO</option>
                    <option value="hmo">HMO</option>
                  </select>
                  <button onClick={() => removePlan(plan.id)} className="text-stone-300 hover:text-red-400">
                    <Trash2 size={13} />
                  </button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 ml-7">
                  <div>
                    <label className="text-[11px] text-stone-400">Premium/mo</label>
                    <input type="number" value={plan.premium_monthly || ""}
                      onChange={(e) => updatePlan(plan.id, { premium_monthly: Number(e.target.value) || 0 })}
                      className="w-full mt-0.5 text-xs border border-stone-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                  </div>
                  <div>
                    <label className="text-[11px] text-stone-400">Deductible</label>
                    <input type="number" value={plan.deductible || ""}
                      onChange={(e) => updatePlan(plan.id, { deductible: Number(e.target.value) || 0 })}
                      className="w-full mt-0.5 text-xs border border-stone-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                  </div>
                  <div>
                    <label className="text-[11px] text-stone-400">OOP Max</label>
                    <input type="number" value={plan.oop_max || ""}
                      onChange={(e) => updatePlan(plan.id, { oop_max: Number(e.target.value) || 0 })}
                      className="w-full mt-0.5 text-xs border border-stone-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                  </div>
                  {plan.hsa_eligible && (
                    <div>
                      <label className="text-[11px] text-stone-400">Employer HSA $</label>
                      <input type="number" value={plan.employer_hsa_contribution || ""}
                        onChange={(e) => updatePlan(plan.id, { employer_hsa_contribution: Number(e.target.value) || 0 })}
                        className="w-full mt-0.5 text-xs border border-stone-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20" />
                    </div>
                  )}
                </div>
                {plan.type === "hdhp" && (
                  <p className="text-[11px] text-blue-600 ml-7 mt-1">
                    HSA tax savings included: ~{formatCurrency(Math.max(0, LIMITS_2025.hsa_family - plan.employer_hsa_contribution) * MARGINAL_RATE_EST)}/yr at 28% marginal rate
                  </p>
                )}
              </div>
            ))}
          </div>

          <button onClick={addPlan}
            className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:text-[#15803d] font-medium">
            <Plus size={13} /> Add plan option
          </button>

          {plans.length > 0 && plans.some((p) => p.name) && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-stone-200">
                    <th className="text-left py-2 text-stone-500 font-medium">Plan</th>
                    {UTILIZATION_SCENARIOS.map((s) => (
                      <th key={s.label} className="text-right py-2 text-stone-500 font-medium px-3">
                        {s.label}<br />
                        <span className="font-normal text-stone-400">{formatCurrency(s.value)} care</span>
                      </th>
                    ))}
                    <th className="text-right py-2 text-stone-500 font-medium px-3">Premium/yr</th>
                  </tr>
                </thead>
                <tbody>
                  {costMatrix.map((row, ri) => (
                    <tr key={row.plan.id} className="border-b border-stone-100">
                      <td className="py-2 pr-4">
                        <div className="font-medium text-stone-800">{row.plan.name || `Plan ${ri + 1}`}</div>
                        <div className="text-stone-400">{row.plan.type.toUpperCase()}{row.plan.hsa_eligible ? " + HSA" : ""}</div>
                      </td>
                      {row.costs.map((cost, si) => (
                        <td key={si} className={`text-right py-2 px-3 font-semibold ${winners[si] === ri ? "text-green-600" : "text-stone-700"}`}>
                          {formatCurrency(cost)}
                          {winners[si] === ri && (
                            <span className="ml-1 text-[10px] bg-green-100 text-green-600 px-1 py-0.5 rounded">best</span>
                          )}
                        </td>
                      ))}
                      <td className="text-right py-2 px-3 text-stone-500">
                        {formatCurrency(row.plan.premium_monthly * 12)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-[11px] text-stone-400 mt-2">
                Costs include premiums + estimated OOP (20% coinsurance after deductible). HDHP net cost subtracts HSA tax savings ({LIMITS_2025.hsa_family.toLocaleString()} family limit 2025).
              </p>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
