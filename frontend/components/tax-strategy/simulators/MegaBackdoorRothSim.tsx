"use client";
import { useState } from "react";
import { modelMegaBackdoor } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { MegaBackdoorResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

export default function MegaBackdoorRothSim() {
  const [allows, setAllows] = useState(true);
  const [employeeContrib, setEmployeeContrib] = useState("23500");
  const [employerMatch, setEmployerMatch] = useState("10000");
  const [planLimit, setPlanLimit] = useState("69000");
  const [result, setResult] = useState<MegaBackdoorResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelMegaBackdoor({
        employer_plan_allows: allows,
        current_employee_contrib: Number(employeeContrib),
        employer_match_contrib: Number(employerMatch),
        plan_limit: Number(planLimit),
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Mega Backdoor Roth"
      purpose="Contribute up to $46,500 extra to a Roth through after-tax 401(k) contributions with in-plan Roth conversion."
      bestFor="High earners whose employer plan allows after-tax contributions and in-service withdrawals"
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="flex items-center gap-2">
          <input type="checkbox" id="allows-aftertax" checked={allows} onChange={(e) => setAllows(e.target.checked)} className="rounded border-stone-300" />
          <label htmlFor="allows-aftertax" className="text-sm text-stone-600">Plan Allows After-Tax</label>
        </div>
        <LabeledInput label="Employee Contributions" value={employeeContrib} onChange={setEmployeeContrib} />
        <LabeledInput label="Employer Match" value={employerMatch} onChange={setEmployerMatch} />
        <LabeledInput label="Plan Limit" value={planLimit} onChange={setPlanLimit} />
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-3 gap-4">
            <ResultBox label="Available Space" value={formatCurrency(result.available_space)} color={result.available ? "green" : undefined} />
            <ResultBox label="20-Year Growth" value={formatCurrency(result.tax_free_growth_value_20yr)} color="green" />
            <ResultBox label="Status" value={result.available ? "Eligible" : "Not Available"} />
          </div>
          {result.explanation && (
            <p className="text-sm text-stone-700 bg-blue-50 rounded-lg p-3">{result.explanation}</p>
          )}
        </div>
      )}
    </SimulatorCard>
  );
}
