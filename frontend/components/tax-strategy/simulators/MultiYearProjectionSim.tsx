"use client";
import { useState } from "react";
import { modelMultiYearTax } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { MultiYearTaxProjection } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

export default function MultiYearProjectionSim({ defaultIncome, defaultFilingStatus }: {
  defaultIncome?: string;
  defaultFilingStatus?: string;
}) {
  const [income, setIncome] = useState(defaultIncome ?? "");
  const [growth, setGrowth] = useState("");
  const [filingStatus, setFilingStatus] = useState(defaultFilingStatus ?? "mfj");
  const [stateRate, setStateRate] = useState("");
  const [years, setYears] = useState(5);
  const [result, setResult] = useState<MultiYearTaxProjection | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelMultiYearTax({
        current_income: Number(income),
        income_growth_rate: Number(growth || 0) / 100,
        filing_status: filingStatus,
        state_rate: Number(stateRate || 0) / 100,
        years,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Multi-Year Tax Projection"
      purpose="Forecast your tax liability over the next several years based on income growth, helping you plan for bracket changes and timing strategies."
      bestFor="Anyone expecting income changes from promotions, equity vesting, or business growth"
    >
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <LabeledInput label="Current Income" value={income} onChange={setIncome} />
        <LabeledInput label="Growth Rate (%)" value={growth} onChange={setGrowth} />
        <div>
          <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="single">Single</option>
            <option value="mfj">Married Filing Jointly</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="hh">Head of Household</option>
          </select>
        </div>
        <LabeledInput label="State Rate (%)" value={stateRate} onChange={setStateRate} />
        <LabeledInput label="Years" value={String(years)} onChange={(v) => setYears(Number(v) || 5)} type="number" />
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Multi-year projection</caption>
            <thead className="bg-stone-50">
              <tr>
                {["Year", "Income", "Federal", "State", "Payroll", "Total Tax", "Effective %"].map((h) => (
                  <th key={h} className={`${h === "Year" ? "text-left" : "text-right"} px-3 py-2 text-xs font-semibold text-stone-500`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {result.years.map((r) => (
                <tr key={r.year}>
                  <td className="px-3 py-2 font-medium">{r.year}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.income)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.federal_tax)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.state_tax)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.fica)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.total_tax)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{(r.effective_rate * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SimulatorCard>
  );
}
