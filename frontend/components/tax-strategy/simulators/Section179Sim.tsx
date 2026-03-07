"use client";
import { useState } from "react";
import { CheckCircle, XCircle, TrendingUp, Truck, DollarSign, ArrowRightLeft } from "lucide-react";
import { modelSection179 } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { Section179Result } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent";

const CATEGORIES = [
  { value: "excavators", label: "Excavators" },
  { value: "skid_steers", label: "Skid Steers / Track Loaders" },
  { value: "trucks_trailers", label: "Trucks & Trailers" },
  { value: "earthmoving", label: "Earthmoving (Dozers, Loaders)" },
  { value: "aerial_lifts", label: "Aerial Lifts & Telehandlers" },
  { value: "concrete_masonry", label: "Concrete & Masonry" },
  { value: "vehicles", label: "Heavy Vehicles (>6,000 lbs)" },
];

const DEMAND_COLORS = {
  high: "text-green-700 bg-green-50",
  medium: "text-amber-700 bg-amber-50",
  low: "text-red-700 bg-red-50",
};

export default function Section179Sim() {
  const [equipmentCost, setEquipmentCost] = useState("");
  const [businessIncome, setBusinessIncome] = useState("");
  const [filingStatus, setFilingStatus] = useState("mfj");
  const [category, setCategory] = useState("excavators");
  const [businessUsePct, setBusinessUsePct] = useState("100");
  const [willRent, setWillRent] = useState(true);
  const [hasBusiness, setHasBusiness] = useState(true);
  const [result, setResult] = useState<Section179Result | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelSection179({
        equipment_cost: Number(equipmentCost),
        business_income: Number(businessIncome),
        filing_status: filingStatus,
        equipment_category: category,
        equipment_index: 0,
        business_use_pct: Number(businessUsePct) / 100,
        will_rent_out: willRent,
        has_existing_business: hasBusiness,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Section 179 Heavy Equipment"
      purpose="Buy equipment like excavators or trucks, deduct the full cost in year one, and rent it out to generate income — a popular tax strategy for business owners."
      bestFor="Business owners or self-employed looking to reduce taxable income with equipment that pays for itself through rental"
    >
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <LabeledInput label="Equipment Cost" value={equipmentCost} onChange={setEquipmentCost} />
        <LabeledInput label="Business Income" value={businessIncome} onChange={setBusinessIncome} />
        <div>
          <label className="block text-xs text-text-secondary mb-1">Equipment Type</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className={INPUT_CLS}>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="single">Single</option>
            <option value="mfj">Married Filing Jointly</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="hh">Head of Household</option>
          </select>
        </div>
        <LabeledInput label="Business Use %" value={businessUsePct} onChange={setBusinessUsePct} />
        <div className="flex flex-col gap-2 justify-end">
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
            <input type="checkbox" checked={willRent} onChange={(e) => setWillRent(e.target.checked)} className="rounded border-border" />
            Plan to rent it out
          </label>
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
            <input type="checkbox" checked={hasBusiness} onChange={(e) => setHasBusiness(e.target.checked)} className="rounded border-border" />
            Have existing business/LLC
          </label>
        </div>
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />

      {result && (
        <div className="mt-4 space-y-5">
          {/* Qualification + headline numbers */}
          <div className="flex flex-wrap gap-3">
            <QualBadge ok={result.qualifies_section_179} label="Section 179 Qualified" />
            <QualBadge ok={result.business_use_pct > 0.5} label="Business Use >50%" />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <ResultBox label="Year-One Deduction" value={formatCurrency(result.year_one_total_deduction)} color="green" />
            <ResultBox label="Year-One Tax Savings" value={formatCurrency(result.year_one_tax_savings)} color="green" />
            <ResultBox label="§179 Deduction" value={formatCurrency(result.section_179_deduction)} />
            <ResultBox label="Bonus Depreciation" value={formatCurrency(result.bonus_depreciation)} />
          </div>

          {/* Rental Analysis */}
          {result.rental_analysis && (
            <div className="bg-surface rounded-lg p-4 space-y-3">
              <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <TrendingUp size={14} className="text-accent" />
                Rental Income Strategy: {result.rental_analysis.equipment_name}
              </h4>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <MiniStat label="Monthly Rental Rate" value={formatCurrency(result.rental_analysis.monthly_rental_rate)} />
                <MiniStat label="Expected Utilization" value={`${(result.rental_analysis.utilization_rate * 100).toFixed(0)}%`} />
                <MiniStat label="Annual Gross Rental" value={formatCurrency(result.rental_analysis.annual_rental_gross)} />
                <MiniStat label="Annual Net Rental" value={formatCurrency(result.rental_analysis.annual_net_rental)} highlight />
              </div>
              <div className="grid grid-cols-4 gap-2 text-xs text-text-secondary">
                <span>Maintenance: {formatCurrency(result.rental_analysis.expense_breakdown.maintenance)}</span>
                <span>Insurance: {formatCurrency(result.rental_analysis.expense_breakdown.insurance)}</span>
                <span>Storage: {formatCurrency(result.rental_analysis.expense_breakdown.storage)}</span>
                <span>Transport: {formatCurrency(result.rental_analysis.expense_breakdown.transport)}</span>
              </div>
              <div className="flex gap-4 pt-1 text-sm">
                <span className="text-text-secondary">5-yr Resale: <strong className="font-mono tabular-nums">{formatCurrency(result.rental_analysis.resale_value_5yr)}</strong></span>
                <span className="text-text-secondary">5-yr Total Return: <strong className={`font-mono tabular-nums ${result.rental_analysis.total_return_5yr > 0 ? "text-green-700" : "text-red-700"}`}>{formatCurrency(result.rental_analysis.total_return_5yr)}</strong></span>
              </div>
            </div>
          )}

          {/* 5-Year Projection */}
          {result.five_year_projection.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">5-year cash flow projection</caption>
                <thead className="bg-surface">
                  <tr>
                    {["Year", "Rental Income", "Depreciation", "Tax Savings", "Net Cash Flow", "Cumulative"].map((h) => (
                      <th key={h} className={`${h === "Year" ? "text-left" : "text-right"} px-3 py-2 text-xs font-semibold text-text-secondary`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-card-border">
                  {result.five_year_projection.map((yr) => (
                    <tr key={yr.year}>
                      <td className="px-3 py-2 font-medium">{yr.year}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">{formatCurrency(yr.rental_income)}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">{formatCurrency(yr.depreciation_deduction)}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums text-green-600">{formatCurrency(yr.tax_savings)}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">{formatCurrency(yr.net_cash_flow)}</td>
                      <td className={`px-3 py-2 text-right font-mono tabular-nums ${yr.cumulative_cash >= 0 ? "text-green-600" : "text-red-600"}`}>{formatCurrency(yr.cumulative_cash)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Exit strategies - what to do with it */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <ArrowRightLeft size={14} className="text-accent" />
              What To Do With It
            </h4>
            <div className="grid gap-2">
              {result.exit_strategies.filter((s) => s.applicable).map((s) => (
                <div key={s.strategy} className="bg-card border border-border rounded-lg p-3">
                  <p className="text-sm font-medium text-text-primary">{s.strategy}</p>
                  <p className="text-xs text-text-secondary mt-0.5">{s.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Equipment recommendations */}
          {result.recommended_equipment.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Truck size={14} className="text-accent" />
                Equipment In Your Budget With Rental Demand
              </h4>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
                {result.recommended_equipment.map((eq) => (
                  <div key={eq.name} className="bg-card border border-border rounded-lg p-3 flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-text-primary">{eq.name}</p>
                      <p className="text-xs text-text-secondary">{eq.category} · {eq.cost_range}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-mono tabular-nums text-text-primary">{formatCurrency(eq.monthly_rental)}/mo</p>
                      <span className={`inline-block text-xs px-1.5 py-0.5 rounded ${DEMAND_COLORS[eq.demand]}`}>{eq.demand} demand</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Qualification notes */}
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

function MiniStat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <p className="text-xs text-text-secondary">{label}</p>
      <p className={`text-sm font-semibold font-mono tabular-nums ${highlight ? "text-green-700" : "text-text-primary"}`}>{value}</p>
    </div>
  );
}
