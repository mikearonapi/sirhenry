"use client";
import { useState } from "react";
import { modelEstimatedPayments } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";

export default function EstimatedPaymentsSim() {
  const [underwithholding, setUnderwithholding] = useState("");
  const [priorTax, setPriorTax] = useState("");
  const [currentWithholding, setCurrentWithholding] = useState("");
  const [result, setResult] = useState<{ quarterly_payments: Array<{ quarter: number; due_date: string; amount: number }> } | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelEstimatedPayments({
        total_underwithholding: Number(underwithholding),
        prior_year_tax: Number(priorTax),
        current_withholding: Number(currentWithholding),
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Estimated Quarterly Payments"
      purpose="Calculate your quarterly estimated tax payments to avoid IRS underpayment penalties."
      bestFor="Self-employed, freelancers, or anyone with significant non-W-2 income"
    >
      <div className="grid grid-cols-3 gap-4">
        <LabeledInput label="Total Underwithholding" value={underwithholding} onChange={setUnderwithholding} />
        <LabeledInput label="Prior Year Tax" value={priorTax} onChange={setPriorTax} />
        <LabeledInput label="Current Withholding" value={currentWithholding} onChange={setCurrentWithholding} />
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Quarterly payments</caption>
            <thead className="bg-stone-50">
              <tr>
                <th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">Quarter</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-stone-500">Due Date</th>
                <th className="text-right px-3 py-2 text-xs font-semibold text-stone-500">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {result.quarterly_payments.map((q) => (
                <tr key={q.quarter}>
                  <td className="px-3 py-2 font-medium">Q{q.quarter}</td>
                  <td className="px-3 py-2">{q.due_date}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(q.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SimulatorCard>
  );
}
