"use client";
import { useState } from "react";
import { modelDAFBunching } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

export default function DAFBunchingSim() {
  const [annual, setAnnual] = useState("");
  const [standard, setStandard] = useState("");
  const [itemizedExcl, setItemizedExcl] = useState("");
  const [bunchYears, setBunchYears] = useState(2);
  const [result, setResult] = useState<{ annual_tax: number; bunched_tax: number; savings: number } | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelDAFBunching({
        annual_charitable: Number(annual),
        standard_deduction: Number(standard),
        itemized_deductions_excl_charitable: Number(itemizedExcl),
        bunch_years: bunchYears,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Donor-Advised Fund Charitable Bunching"
      purpose="Bunch multiple years of charitable giving into a Donor-Advised Fund (DAF) in one year to exceed the standard deduction and maximize your tax benefit."
      bestFor="Families giving $10K+/year to charity who normally take the standard deduction"
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <LabeledInput label="Annual Charitable" value={annual} onChange={setAnnual} />
        <LabeledInput label="Standard Deduction" value={standard} onChange={setStandard} />
        <LabeledInput label="Itemized excl. Charitable" value={itemizedExcl} onChange={setItemizedExcl} />
        <LabeledInput label="Bunch Years" value={String(bunchYears)} onChange={(v) => setBunchYears(Number(v) || 2)} type="number" />
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 grid grid-cols-3 gap-4">
          <ResultBox label="Annual Tax" value={formatCurrency(result.annual_tax)} />
          <ResultBox label="Bunched Tax" value={formatCurrency(result.bunched_tax)} />
          <ResultBox label="Savings" value={formatCurrency(result.savings)} color="green" />
        </div>
      )}
    </SimulatorCard>
  );
}
