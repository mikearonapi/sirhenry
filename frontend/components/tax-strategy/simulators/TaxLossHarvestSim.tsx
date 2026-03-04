"use client";
import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { getTaxLossHarvest } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { TaxLossHarvestResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

export default function TaxLossHarvestSim() {
  const [marginalRate, setMarginalRate] = useState("37");
  const [result, setResult] = useState<TaxLossHarvestResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await getTaxLossHarvest(Number(marginalRate) / 100));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Tax-Loss Harvesting"
      purpose="Offset capital gains by strategically selling losing positions, reducing your tax bill while maintaining market exposure."
      bestFor="Investors with taxable brokerage accounts and unrealized losses"
    >
      <div className="grid grid-cols-2 gap-4 max-w-md">
        <LabeledInput label="Marginal Tax Rate (%)" value={marginalRate} onChange={setMarginalRate} />
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <ResultBox label="Harvestable Losses" value={formatCurrency(result.harvestable_losses)} />
            <ResultBox label="Est. Tax Savings" value={formatCurrency(result.estimated_tax_savings)} color="green" />
            <ResultBox label="Loss Carryover" value={formatCurrency(result.capital_loss_carryover)} />
          </div>
          {result.candidates.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Harvest candidates</caption>
                <thead className="bg-stone-50">
                  <tr>
                    {["Ticker", "Loss", "Loss %", "Term", "Tax Savings", "Wash Sale Risk"].map((h) => (
                      <th key={h} className={`${h === "Ticker" ? "text-left" : "text-right"} px-3 py-2 text-xs font-semibold text-stone-500`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {result.candidates.slice(0, 10).map((c) => (
                    <tr key={c.holding_id}>
                      <td className="px-3 py-2 font-medium">{c.ticker}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums text-red-600">{formatCurrency(c.unrealized_loss)}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">{(c.loss_pct * 100).toFixed(1)}%</td>
                      <td className="px-3 py-2 text-right capitalize">{c.term}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums text-green-600">{formatCurrency(c.estimated_tax_savings)}</td>
                      <td className="px-3 py-2 text-right">
                        {c.wash_sale_risk && <span className="inline-flex items-center gap-1 text-xs text-amber-600"><AlertTriangle size={12} /> Risk</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {result.candidates.length === 0 && (
            <p className="text-sm text-stone-500 text-center py-4">No holdings with harvestable losses found. Import your portfolio to see candidates.</p>
          )}
        </div>
      )}
    </SimulatorCard>
  );
}
