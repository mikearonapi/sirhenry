"use client";
import { useState } from "react";
import { modelDefinedBenefit } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { DefinedBenefitResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

export default function DefinedBenefitSim() {
  const [income, setIncome] = useState("");
  const [age, setAge] = useState("");
  const [retireAge, setRetireAge] = useState("65");
  const [filingStatus, setFilingStatus] = useState("mfj");
  const [result, setResult] = useState<DefinedBenefitResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelDefinedBenefit({
        self_employment_income: Number(income),
        age: Number(age),
        target_retirement_age: Number(retireAge),
        filing_status: filingStatus,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Defined Benefit Plan"
      purpose="Shelter $100K\u2013$300K/year from taxes with an employer pension plan, far exceeding Simplified Employee Pension (SEP) IRA limits."
      bestFor="Self-employed professionals age 45+ with $200K+ consistent annual income"
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <LabeledInput label="Self-Employment Income" value={income} onChange={setIncome} />
        <LabeledInput label="Current Age" value={age} onChange={setAge} />
        <LabeledInput label="Target Retirement Age" value={retireAge} onChange={setRetireAge} />
        <div>
          <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="single">Single</option>
            <option value="mfj">Married Filing Jointly</option>
          </select>
        </div>
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <ResultBox label="Defined Benefit Contribution" value={formatCurrency(result.max_annual_contribution)} color="green" />
            <ResultBox label="SEP IRA Contribution" value={formatCurrency(result.sep_ira_contribution)} />
            <ResultBox label="Additional Tax Savings" value={formatCurrency(result.additional_annual_savings)} color="green" />
            <ResultBox label="Projected at Retirement" value={formatCurrency(result.projected_accumulation)} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-stone-50 rounded-lg p-3">
              <p className="text-xs text-stone-500 mb-1">Defined Benefit vs SEP IRA (per year)</p>
              <div className="flex items-center gap-2">
                <span className="font-mono tabular-nums text-sm font-semibold text-green-700">{formatCurrency(result.annual_tax_savings)}</span>
                <span className="text-xs text-stone-400">vs</span>
                <span className="font-mono tabular-nums text-sm text-stone-600">{formatCurrency(result.sep_annual_tax_savings)}</span>
              </div>
            </div>
            <div className="bg-stone-50 rounded-lg p-3">
              <p className="text-xs text-stone-500 mb-1">Accumulation at Retirement</p>
              <div className="flex items-center gap-2">
                <span className="font-mono tabular-nums text-sm font-semibold text-green-700">{formatCurrency(result.projected_accumulation)}</span>
                <span className="text-xs text-stone-400">vs</span>
                <span className="font-mono tabular-nums text-sm text-stone-600">{formatCurrency(result.sep_projected_accumulation)}</span>
              </div>
            </div>
          </div>
          <p className="text-sm text-stone-700 bg-blue-50 rounded-lg p-3">{result.explanation}</p>
        </div>
      )}
    </SimulatorCard>
  );
}
