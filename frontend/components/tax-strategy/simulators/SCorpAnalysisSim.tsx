"use client";
import { useState } from "react";
import { MessageCircle } from "lucide-react";
import { modelSCorp } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { SCorpAnalysisResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

function askHenry(message: string) {
  window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message } }));
}

export default function SCorpAnalysisSim() {
  const [gross, setGross] = useState("");
  const [salary, setSalary] = useState("");
  const [expenses, setExpenses] = useState("");
  const [result, setResult] = useState<SCorpAnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelSCorp({
        gross_1099_income: Number(gross),
        reasonable_salary: Number(salary),
        business_expenses: Number(expenses),
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="S-Corp Election Analysis"
      purpose="Compare Schedule C (sole proprietorship) vs S-Corp election to see how much you'd save on self-employment tax."
      bestFor="Self-employed or side-business owners netting $60K+ from their business"
    >
      <div className="grid grid-cols-3 gap-4">
        <LabeledInput label="Gross 1099 Income" value={gross} onChange={setGross} />
        <LabeledInput label="Reasonable Salary" value={salary} onChange={setSalary} />
        <LabeledInput label="Expenses" value={expenses} onChange={setExpenses} />
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <ResultBox label="Schedule C Tax" value={formatCurrency(result.schedule_c_tax)} />
            <ResultBox label="S-Corp Tax" value={formatCurrency(result.scorp_tax)} />
            <ResultBox label="Self-Employment Tax Savings" value={formatCurrency(result.se_tax_savings)} color="green" />
            <ResultBox label="Total Savings" value={formatCurrency(result.total_savings)} />
          </div>
          <button type="button" onClick={() => askHenry(`I compared Schedule C vs. S-Corp. The S-Corp saves ${formatCurrency(result.total_savings)}. Should I elect S-Corp status? What are the pros and cons?`)} className="flex items-center gap-1.5 text-xs text-accent hover:underline">
            <MessageCircle size={12} /> Should I elect S-Corp?
          </button>
        </div>
      )}
    </SimulatorCard>
  );
}
