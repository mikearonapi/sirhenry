"use client";
import { useState } from "react";
import { CheckCircle, XCircle } from "lucide-react";
import { modelRealEstateSTR } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { RealEstateSTRResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent";

export default function RealEstateSTRSim() {
  const [propertyValue, setPropertyValue] = useState("");
  const [rentalIncome, setRentalIncome] = useState("");
  const [avgStay, setAvgStay] = useState("3");
  const [hoursPerWeek, setHoursPerWeek] = useState("3");
  const [w2Income, setW2Income] = useState("");
  const [filingStatus, setFilingStatus] = useState("mfj");
  const [result, setResult] = useState<RealEstateSTRResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelRealEstateSTR({
        property_value: Number(propertyValue),
        annual_rental_income: Number(rentalIncome),
        average_stay_days: Number(avgStay),
        hours_per_week_managing: Number(hoursPerWeek),
        w2_income: Number(w2Income),
        filing_status: filingStatus,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Short-Term Rental Tax Loophole"
      purpose="Offset W-2 income with real estate losses using the short-term rental loophole and cost segregation depreciation."
      bestFor="High-income W-2 earners interested in short-term rental properties (Airbnb, VRBO)"
    >
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <LabeledInput label="Property Value" value={propertyValue} onChange={setPropertyValue} />
        <LabeledInput label="Annual Rental Income" value={rentalIncome} onChange={setRentalIncome} />
        <LabeledInput label="Avg Stay (days)" value={avgStay} onChange={setAvgStay} />
        <LabeledInput label="Hours/Week Managing" value={hoursPerWeek} onChange={setHoursPerWeek} />
        <LabeledInput label="W-2 Income" value={w2Income} onChange={setW2Income} />
        <div>
          <label className="block text-xs text-text-secondary mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="single">Single</option>
            <option value="mfj">Married Filing Jointly</option>
          </select>
        </div>
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />
      {result && (
        <div className="mt-4 space-y-4">
          {/* Qualification status */}
          <div className="flex flex-wrap gap-3">
            <QualBadge ok={result.qualifies_str} label="Short-Term Rental Qualified" />
            <QualBadge ok={result.material_participation} label="Material Participation" />
            <QualBadge ok={result.can_offset_w2} label="Can Offset W-2" />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <ResultBox label="Year-One Tax Savings" value={formatCurrency(result.tax_savings_year_one)} color="green" />
            <ResultBox label="W-2 Offset" value={formatCurrency(result.w2_offset_year_one)} color="green" />
            <ResultBox label="Accelerated Depreciation" value={formatCurrency(result.cost_seg_year_one_depreciation)} />
            <ResultBox label="Standard Depreciation" value={formatCurrency(result.standard_annual_depreciation)} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-surface rounded-lg p-3">
              <p className="text-xs text-text-secondary mb-1">With Cost Segregation (Year 1)</p>
              <p className={`font-semibold font-mono tabular-nums ${result.cost_seg_net_income_year_one < 0 ? "text-green-700" : "text-text-primary"}`}>
                Net: {formatCurrency(result.cost_seg_net_income_year_one)}
              </p>
            </div>
            <div className="bg-surface rounded-lg p-3">
              <p className="text-xs text-text-secondary mb-1">Standard Depreciation</p>
              <p className={`font-semibold font-mono tabular-nums ${result.standard_net_income < 0 ? "text-green-700" : "text-text-primary"}`}>
                Net: {formatCurrency(result.standard_net_income)}
              </p>
            </div>
          </div>

          <div className="bg-blue-50 rounded-lg p-3 space-y-1">
            {result.qualification_notes.map((note, i) => (
              <p key={i} className="text-xs text-blue-800">{note}</p>
            ))}
          </div>
        </div>
      )}
    </SimulatorCard>
  );
}

function QualBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium ${ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
      {ok ? <CheckCircle size={12} /> : <XCircle size={12} />}
      {label}
    </span>
  );
}
