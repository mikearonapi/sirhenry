"use client";
import { useState } from "react";
import { AlertTriangle, CheckCircle, TrendingDown } from "lucide-react";
import { modelQBIDeduction } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { QBIDeductionResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent";

export default function QBIDeductionSim() {
  const [qbiIncome, setQbiIncome] = useState("");
  const [taxableIncome, setTaxableIncome] = useState("");
  const [w2WagesPaid, setW2WagesPaid] = useState("0");
  const [qualifiedProperty, setQualifiedProperty] = useState("0");
  const [filingStatus, setFilingStatus] = useState("mfj");
  const [isSSTB, setIsSSTB] = useState(false);
  const [result, setResult] = useState<QBIDeductionResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelQBIDeduction({
        qbi_income: Number(qbiIncome),
        taxable_income: Number(taxableIncome),
        w2_wages_paid: Number(w2WagesPaid),
        qualified_property: Number(qualifiedProperty),
        filing_status: filingStatus,
        is_sstb: isSSTB,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Qualified Business Income Deduction (Section 199A)"
      purpose="Pass-through business owners can deduct up to 20% of qualified business income — but income limits, service business rules, and W-2 wage requirements create traps. See exactly what you qualify for."
      bestFor="Sole proprietors, S-Corp owners, partners, and LLC members with pass-through income"
    >
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <LabeledInput label="Qualified Business Income" value={qbiIncome} onChange={setQbiIncome} />
        <LabeledInput label="Total Taxable Income" value={taxableIncome} onChange={setTaxableIncome} />
        <LabeledInput label="W-2 Wages Paid by Business" value={w2WagesPaid} onChange={setW2WagesPaid} />
        <LabeledInput label="Qualified Property (depreciable assets)" value={qualifiedProperty} onChange={setQualifiedProperty} />
        <div>
          <label className="block text-xs text-text-secondary mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="mfj">Married Filing Jointly</option>
            <option value="single">Single</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="hoh">Head of Household</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Business Type</label>
          <select value={isSSTB ? "sstb" : "non_sstb"} onChange={(e) => setIsSSTB(e.target.value === "sstb")} className={INPUT_CLS}>
            <option value="non_sstb">Non-service (manufacturing, retail, etc.)</option>
            <option value="sstb">Specified Service (law, medicine, consulting, etc.)</option>
          </select>
        </div>
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />

      {result && (
        <div className="mt-4 space-y-4">
          {/* Main result banner */}
          {result.final_deduction > 0 ? (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
              <CheckCircle size={16} className="text-green-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-green-800">
                  Business Income Deduction: {formatCurrency(result.final_deduction)} — saves {formatCurrency(result.tax_savings)} in taxes
                </p>
                <p className="text-xs text-green-600 mt-0.5">{result.recommendation}</p>
              </div>
            </div>
          ) : (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
              <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-800">No business income deduction available</p>
                <p className="text-xs text-amber-600 mt-0.5">{result.recommendation}</p>
              </div>
            </div>
          )}

          {/* Key metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <ResultBox label="Business Income Deduction" value={formatCurrency(result.final_deduction)} color="green" />
            <ResultBox label="Tax Savings" value={formatCurrency(result.tax_savings)} color="green" />
            <ResultBox label="20% of Business Income" value={formatCurrency(result.basic_20pct_deduction)} />
            <ResultBox label="Marginal Rate" value={`${(result.marginal_rate * 100).toFixed(1)}%`} />
          </div>

          {/* Limitation analysis */}
          <div className="bg-surface rounded-lg p-4 space-y-3">
            <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">Limitation Analysis</h4>
            <div className="grid grid-cols-3 gap-4">
              <LimitRow
                label="20% of Business Income"
                value={result.basic_20pct_deduction}
                binding={result.final_deduction === result.basic_20pct_deduction && result.final_deduction > 0}
              />
              <LimitRow
                label="W-2 Wage / Property Limit"
                value={result.w2_wage_limit}
                binding={result.final_deduction === result.w2_wage_limit && result.final_deduction > 0 && !result.sstb_eliminated}
              />
              <LimitRow
                label="20% of Taxable Income"
                value={result.taxable_income_cap}
                binding={result.final_deduction === result.taxable_income_cap && result.final_deduction > 0}
              />
            </div>
          </div>

          {/* Phaseout status */}
          {(result.in_phaseout || result.above_phaseout) && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
              <TrendingDown size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-800">
                  {result.sstb_eliminated
                    ? "Service business income fully phased out"
                    : result.in_phaseout
                    ? `In phaseout range (${formatCurrency(result.phaseout_start)} – ${formatCurrency(result.phaseout_end)})`
                    : "Above phaseout — W-2 wage and property limits fully apply"}
                </p>
                {result.is_sstb && !result.sstb_eliminated && (
                  <p className="text-xs text-amber-600 mt-0.5">
                    Service business income is being proportionally reduced in the phaseout range.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="bg-amber-50 rounded-lg p-3 space-y-1.5">
              <p className="text-xs text-amber-800 font-medium">Warnings:</p>
              {result.warnings.map((w, i) => (
                <p key={i} className="text-xs text-amber-700">• {w}</p>
              ))}
            </div>
          )}

          {/* SSTB info */}
          <div className="bg-blue-50 rounded-lg p-3 space-y-1.5">
            <p className="text-xs text-blue-800 font-medium">About Section 199A:</p>
            <p className="text-xs text-blue-800">
              • Your deduction is the lesser of: 20% of qualified business income, the W-2 wage / depreciable property limit, or 20% of taxable income.
            </p>
            <p className="text-xs text-blue-800">
              • Specified Service Businesses (law, accounting, health, consulting, athletics, financial services, performing arts) lose the deduction entirely above the phaseout.
            </p>
            <p className="text-xs text-blue-800">
              • W-2 wages paid by the business and depreciable property value only matter above the phaseout threshold.
            </p>
          </div>
        </div>
      )}
    </SimulatorCard>
  );
}

function LimitRow({ label, value, binding }: { label: string; value: number; binding: boolean }) {
  return (
    <div className={`rounded-lg p-3 ${binding ? "bg-green-50 border border-green-200" : "bg-card border border-border"}`}>
      <p className={`text-xs ${binding ? "text-green-600" : "text-text-secondary"} mb-1`}>
        {label} {binding && "(binding)"}
      </p>
      <p className={`text-sm font-semibold font-mono tabular-nums ${binding ? "text-green-700" : "text-text-primary"}`}>
        {formatCurrency(value)}
      </p>
    </div>
  );
}
