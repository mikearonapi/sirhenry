"use client";
import { useState } from "react";
import { modelStudentLoan } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { StudentLoanResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

export default function StudentLoanSim({ defaultMonthlyIncome, defaultFilingStatus }: {
  defaultMonthlyIncome?: string;
  defaultFilingStatus?: string;
}) {
  const [balance, setBalance] = useState("");
  const [rate, setRate] = useState("");
  const [monthlyIncome, setMonthlyIncome] = useState(defaultMonthlyIncome ?? "");
  const [filingStatus, setFilingStatus] = useState(defaultFilingStatus ?? "single");
  const [pslf, setPslf] = useState(false);
  const [result, setResult] = useState<StudentLoanResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelStudentLoan({
        loan_balance: Number(balance),
        interest_rate: Number(rate),
        monthly_income: Number(monthlyIncome),
        filing_status: filingStatus,
        pslf_eligible: pslf,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Student Loan Optimizer"
      purpose="Compare repayment strategies (standard, income-driven, Public Service Loan Forgiveness) to find the approach that minimizes total cost."
      bestFor="HENRYs with student loan balances considering forgiveness vs aggressive payoff"
    >
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <LabeledInput label="Balance" value={balance} onChange={setBalance} />
        <LabeledInput label="Interest Rate (%)" value={rate} onChange={setRate} />
        <LabeledInput label="Monthly Income" value={monthlyIncome} onChange={setMonthlyIncome} />
        <div>
          <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="single">Single</option>
            <option value="mfj">Married Filing Jointly</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="hh">Head of Household</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input type="checkbox" id="pslf" checked={pslf} onChange={(e) => setPslf(e.target.checked)} className="rounded border-stone-300" />
          <label htmlFor="pslf" className="text-sm text-stone-600">Public Service Loan Forgiveness Eligible</label>
        </div>
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 space-y-3">
          <table className="w-full text-sm">
            <caption className="sr-only">Repayment strategies</caption>
            <thead className="bg-stone-50">
              <tr>
                {["Strategy", "Monthly", "Total Paid", "Interest", "Payoff Yrs", "Forgiveness"].map((h) => (
                  <th key={h} className={`${h === "Strategy" ? "text-left" : "text-right"} px-3 py-2 text-xs font-semibold text-stone-500`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {result.strategies.map((s, i) => (
                <tr key={i}>
                  <td className="px-3 py-2 font-medium">{s.name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.monthly_payment)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.total_paid)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.total_interest)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.payoff_years}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.forgiveness_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.recommendation && (
            <p className="text-sm text-stone-700 bg-blue-50 rounded-lg p-3">{result.recommendation}</p>
          )}
        </div>
      )}
    </SimulatorCard>
  );
}
