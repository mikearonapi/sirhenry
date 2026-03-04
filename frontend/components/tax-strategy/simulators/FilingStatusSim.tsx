"use client";
import { useState } from "react";
import { ArrowLeftRight, AlertTriangle, CheckCircle } from "lucide-react";
import { modelFilingStatusCompare } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { FilingStatusCompareResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

export default function FilingStatusSim() {
  const [spouseAIncome, setSpouseAIncome] = useState("");
  const [spouseBIncome, setSpouseBIncome] = useState("");
  const [investmentIncome, setInvestmentIncome] = useState("0");
  const [itemizedDeductions, setItemizedDeductions] = useState("0");
  const [studentLoanPayment, setStudentLoanPayment] = useState("0");
  const [state, setState] = useState("CA");
  const [result, setResult] = useState<FilingStatusCompareResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelFilingStatusCompare({
        spouse_a_income: Number(spouseAIncome),
        spouse_b_income: Number(spouseBIncome),
        investment_income: Number(investmentIncome),
        itemized_deductions: Number(itemizedDeductions),
        student_loan_payment: Number(studentLoanPayment),
        state,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Filing Status Optimizer (Joint vs Separate)"
      purpose="Most married couples file jointly, but filing separately can save thousands in specific situations — especially if you have student loans on income-driven repayment or a big income disparity."
      bestFor="Married couples with student loans, disparate incomes, or high itemized deductions"
    >
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <LabeledInput label="Spouse A Income (W-2)" value={spouseAIncome} onChange={setSpouseAIncome} />
        <LabeledInput label="Spouse B Income (W-2)" value={spouseBIncome} onChange={setSpouseBIncome} />
        <LabeledInput label="Investment Income" value={investmentIncome} onChange={setInvestmentIncome} />
        <LabeledInput label="Total Itemized Deductions" value={itemizedDeductions} onChange={setItemizedDeductions} />
        <LabeledInput label="Annual Student Loan Payment" value={studentLoanPayment} onChange={setStudentLoanPayment} />
        <div>
          <label className="block text-xs text-stone-500 mb-1">State</label>
          <select value={state} onChange={(e) => setState(e.target.value)} className={INPUT_CLS}>
            <option value="CA">California</option>
            <option value="NY">New York</option>
            <option value="NJ">New Jersey</option>
            <option value="TX">Texas</option>
            <option value="FL">Florida</option>
            <option value="WA">Washington</option>
            <option value="MA">Massachusetts</option>
            <option value="IL">Illinois</option>
            <option value="CO">Colorado</option>
            <option value="GA">Georgia</option>
            <option value="VA">Virginia</option>
            <option value="PA">Pennsylvania</option>
            <option value="NC">North Carolina</option>
            <option value="OH">Ohio</option>
            <option value="MD">Maryland</option>
          </select>
        </div>
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />

      {result && (
        <div className="mt-4 space-y-5">
          {/* Winner banner */}
          <div className={`rounded-lg p-3 flex items-start gap-2 ${
            result.better === "mfj"
              ? "bg-green-50 border border-green-200"
              : "bg-amber-50 border border-amber-200"
          }`}>
            {result.better === "mfj" ? (
              <CheckCircle size={16} className="text-green-600 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
            )}
            <div>
              <p className={`text-sm font-medium ${result.better === "mfj" ? "text-green-800" : "text-amber-800"}`}>
                {result.better === "mfj" ? "Married Filing Jointly" : "Married Filing Separately"} saves you {formatCurrency(result.difference)}
              </p>
              <p className={`text-xs mt-0.5 ${result.better === "mfj" ? "text-green-600" : "text-amber-600"}`}>
                {result.recommendation}
              </p>
            </div>
          </div>

          {/* Side-by-side comparison */}
          <div className="grid grid-cols-2 gap-4">
            <ComparisonColumn
              title="Married Filing Jointly"
              data={result.mfj}
              isWinner={result.better === "mfj"}
            />
            <ComparisonColumn
              title="Married Filing Separately"
              data={result.mfs}
              isWinner={result.better === "mfs"}
            />
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <ResultBox label="Tax Difference" value={formatCurrency(result.difference)} color="green" />
            <ResultBox label="Joint Effective Rate" value={`${(result.mfj.effective_rate * 100).toFixed(1)}%`} />
            <ResultBox label="Separate Effective Rate" value={`${(result.mfs.effective_rate * 100).toFixed(1)}%`} />
            <ResultBox label="Better Filing Status" value={result.better === "mfj" ? "Joint" : "Separate"} color={result.better === "mfs" ? "green" : undefined} />
          </div>

          {/* IDR benefit */}
          {result.idr_benefit > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-start gap-2">
              <ArrowLeftRight size={16} className="text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-blue-800">
                  Student Loan Income-Driven Repayment Savings: {formatCurrency(result.idr_benefit)}/year
                </p>
                <p className="text-xs text-blue-600 mt-0.5">{result.idr_note}</p>
              </div>
            </div>
          )}

          {/* MFS limitations */}
          {result.better === "mfs" && (
            <div className="bg-amber-50 rounded-lg p-3 space-y-1.5">
              <p className="text-xs text-amber-800 font-medium">Filing Separately Limitations to Consider:</p>
              {result.mfs_limitations.map((note, i) => (
                <p key={i} className="text-xs text-amber-700">• {note}</p>
              ))}
            </div>
          )}

          {/* General tips */}
          <div className="bg-blue-50 rounded-lg p-3 space-y-1.5">
            <p className="text-xs text-blue-800 font-medium">When Filing Separately Might Win:</p>
            <p className="text-xs text-blue-800">
              • Student loans on income-driven repayment (SAVE, PAYE, IBR plans) — filing separately excludes your spouse&apos;s income from the payment calculation.
            </p>
            <p className="text-xs text-blue-800">
              • Large medical expenses — easier to exceed the 7.5% adjusted gross income threshold with one income.
            </p>
            <p className="text-xs text-blue-800">
              • Community property states (CA, TX, AZ, etc.) have special separate-filing rules — consult a CPA.
            </p>
          </div>
        </div>
      )}
    </SimulatorCard>
  );
}

function ComparisonColumn({ title, data, isWinner }: {
  title: string;
  data: FilingStatusCompareResult["mfj"];
  isWinner: boolean;
}) {
  return (
    <div className={`rounded-lg p-4 ${isWinner ? "bg-green-50 border-2 border-green-200" : "bg-stone-50 border border-stone-200"}`}>
      <div className="flex items-center gap-2 mb-3">
        {isWinner && <CheckCircle size={14} className="text-green-600" />}
        <h4 className={`text-sm font-semibold ${isWinner ? "text-green-800" : "text-stone-800"}`}>{title}</h4>
      </div>
      <div className="space-y-2">
        <TaxRow label="Federal Tax" value={data.federal_tax} />
        <TaxRow label="State Tax" value={data.state_tax} />
        <TaxRow label="Payroll Tax (FICA)" value={data.fica} />
        {data.niit > 0 && <TaxRow label="Net Investment Income Tax" value={data.niit} />}
        {data.student_loan_benefit > 0 && (
          <TaxRow label="Student Loan Deduction" value={-data.student_loan_benefit} isCredit />
        )}
        <div className="border-t border-stone-200 pt-2 mt-2">
          <TaxRow label="Total Tax" value={data.total_tax} bold />
        </div>
        <div className="flex justify-between text-xs text-stone-500 pt-1">
          <span>Effective Rate</span>
          <span className="font-mono tabular-nums">{(data.effective_rate * 100).toFixed(1)}%</span>
        </div>
        <div className="flex justify-between text-xs text-stone-500">
          <span>Deduction</span>
          <span className="font-mono tabular-nums">{formatCurrency(data.deduction_used)} ({data.itemizing ? "itemized" : "standard"})</span>
        </div>
      </div>
    </div>
  );
}

function TaxRow({ label, value, bold, isCredit }: { label: string; value: number; bold?: boolean; isCredit?: boolean }) {
  return (
    <div className={`flex justify-between text-sm ${bold ? "font-semibold" : ""}`}>
      <span className="text-stone-600">{label}</span>
      <span className={`font-mono tabular-nums ${isCredit ? "text-green-600" : "text-stone-800"}`}>
        {isCredit ? `-${formatCurrency(Math.abs(value))}` : formatCurrency(value)}
      </span>
    </div>
  );
}
