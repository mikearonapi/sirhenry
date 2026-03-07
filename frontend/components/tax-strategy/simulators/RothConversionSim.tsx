"use client";
import { useState } from "react";
import { MessageCircle } from "lucide-react";
import { modelRothConversion } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { RothConversionResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function RothConversionSim({ defaultIncome, defaultTraditional }: {
  defaultIncome?: string;
  defaultTraditional?: string;
}) {
  const [traditional, setTraditional] = useState(defaultTraditional ?? "");
  const [currentIncome, setCurrentIncome] = useState(defaultIncome ?? "");
  const [years, setYears] = useState(10);
  const [targetBracket, setTargetBracket] = useState("");
  const [result, setResult] = useState<RothConversionResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelRothConversion({
        traditional_balance: Number(traditional),
        current_income: Number(currentIncome),
        years,
        target_bracket_rate: Number(targetBracket || 0) / 100,
      }));
    } catch { /* handled by empty state */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Roth Conversion Ladder"
      purpose="Convert traditional retirement account (IRA or 401k) to Roth over time, paying tax now at a lower rate to get tax-free withdrawals in retirement."
      bestFor="Anyone expecting higher tax rates in the future, or in a lower-income transition year"
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <LabeledInput label="Traditional Balance" value={traditional} onChange={setTraditional} />
        <LabeledInput label="Current Income" value={currentIncome} onChange={setCurrentIncome} />
        <div>
          <label className="block text-xs text-text-secondary mb-1">Years (1-20): {years}</label>
          <input type="range" min={1} max={20} value={years} onChange={(e) => setYears(Number(e.target.value))} className="w-full" />
        </div>
        <LabeledInput label="Target Bracket Rate (%)" value={targetBracket} onChange={setTargetBracket} />
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Roth conversion projection</caption>
            <thead className="bg-surface">
              <tr>
                {["Year", "Conversion", "Tax", "Marginal Rate", "Remaining Trad.", "Roth Balance"].map((h) => (
                  <th key={h} className={`${h === "Year" ? "text-left" : "text-right"} px-3 py-2 text-xs font-semibold text-text-secondary`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-card-border">
              {result.year_by_year.map((r) => (
                <tr key={r.year}>
                  <td className="px-3 py-2 font-medium">{r.year}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.conversion_amount)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.tax_on_conversion)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{(r.marginal_rate * 100).toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.remaining_traditional)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.roth_balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex gap-4 text-sm">
            <span>Total Converted: <span className="font-mono tabular-nums">{formatCurrency(result.total_converted)}</span></span>
            <span>Total Tax: <span className="font-mono tabular-nums">{formatCurrency(result.total_tax_paid)}</span></span>
            <span>Projected Roth: <span className="font-mono tabular-nums">{formatCurrency(result.projected_roth_at_retirement)}</span></span>
          </div>
          <button type="button" onClick={() => askHenry("I just ran a Roth conversion projection. Can you explain what these numbers mean and whether this strategy makes sense for my situation?")} className="flex items-center gap-1.5 text-xs text-accent hover:underline mt-2">
            <MessageCircle size={12} /> What does this mean?
          </button>
        </div>
      )}
    </SimulatorCard>
  );
}
