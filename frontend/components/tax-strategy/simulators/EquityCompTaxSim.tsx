"use client";
import { useState } from "react";
import { AlertTriangle, DollarSign, Shield } from "lucide-react";
import { calcWithholdingGap, calcAMTCrossover } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { WithholdingGapResult, AMTCrossoverResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

type Mode = "rsu" | "iso";

export default function EquityCompTaxSim() {
  const [mode, setMode] = useState<Mode>("rsu");

  // RSU / ESPP inputs
  const [vestIncome, setVestIncome] = useState("");
  const [otherIncome, setOtherIncome] = useState("");
  const [filingStatus, setFilingStatus] = useState("mfj");
  const [state, setState] = useState("CA");
  const [rsuResult, setRsuResult] = useState<WithholdingGapResult | null>(null);

  // ISO inputs
  const [isoShares, setIsoShares] = useState("");
  const [strikePrice, setStrikePrice] = useState("");
  const [currentFmv, setCurrentFmv] = useState("");
  const [isoOtherIncome, setIsoOtherIncome] = useState("");
  const [isoFiling, setIsoFiling] = useState("mfj");
  const [isoResult, setIsoResult] = useState<AMTCrossoverResult | null>(null);

  const [loading, setLoading] = useState(false);

  async function handleRSUCalc() {
    setLoading(true);
    setRsuResult(null);
    try {
      setRsuResult(await calcWithholdingGap({
        vest_income: Number(vestIncome),
        other_income: Number(otherIncome),
        filing_status: filingStatus,
        state,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  async function handleISOCalc() {
    setLoading(true);
    setIsoResult(null);
    try {
      setIsoResult(await calcAMTCrossover({
        iso_shares_available: Number(isoShares),
        strike_price: Number(strikePrice),
        current_fmv: Number(currentFmv),
        other_income: Number(isoOtherIncome),
        filing_status: isoFiling,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="Equity Compensation Tax Planner"
      purpose="Your employer withholds only 22% on stock vest income and bonuses, but your actual tax rate is likely 35–45%. See how much extra you owe — or find how many Incentive Stock Options you can exercise without triggering Alternative Minimum Tax."
      bestFor="Tech workers, executives, and anyone with stock grants (RSUs, ISOs, NSOs, or ESPP)"
    >
      {/* Mode toggle */}
      <div className="flex bg-stone-100 rounded-lg p-0.5 mb-4 w-fit">
        <button
          onClick={() => setMode("rsu")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            mode === "rsu" ? "bg-white shadow-sm text-stone-900" : "text-stone-500 hover:text-stone-700"
          }`}
        >
          Withholding Gap
        </button>
        <button
          onClick={() => setMode("iso")}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            mode === "iso" ? "bg-white shadow-sm text-stone-900" : "text-stone-500 hover:text-stone-700"
          }`}
        >
          Stock Option AMT Finder
        </button>
      </div>

      {mode === "rsu" && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <LabeledInput label="Stock Vest Income" value={vestIncome} onChange={setVestIncome} />
            <LabeledInput label="Other W-2 Income" value={otherIncome} onChange={setOtherIncome} />
            <div>
              <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
              <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
                <option value="single">Single</option>
                <option value="mfj">Married Filing Jointly</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-stone-500 mb-1">State</label>
              <select value={state} onChange={(e) => setState(e.target.value)} className={INPUT_CLS}>
                <option value="CA">California</option>
                <option value="NY">New York</option>
                <option value="WA">Washington</option>
                <option value="TX">Texas</option>
                <option value="NJ">New Jersey</option>
                <option value="MA">Massachusetts</option>
                <option value="IL">Illinois</option>
                <option value="CO">Colorado</option>
                <option value="GA">Georgia</option>
                <option value="FL">Florida</option>
              </select>
            </div>
          </div>
          <CalcButton loading={loading} onClick={handleRSUCalc} />

          {rsuResult && (
            <div className="mt-4 space-y-4">
              {rsuResult.withholding_gap > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
                  <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-amber-800">
                      Withholding gap: you&apos;ll owe {formatCurrency(rsuResult.withholding_gap)} extra at tax time
                    </p>
                    <p className="text-xs text-amber-600 mt-0.5">
                      Your employer withholds at the 22% supplemental rate but your actual marginal rate is {(rsuResult.actual_marginal_rate * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <ResultBox label="Withholding Gap" value={formatCurrency(rsuResult.withholding_gap)} color="green" />
                <ResultBox label="Actual Marginal Rate" value={`${(rsuResult.actual_marginal_rate * 100).toFixed(1)}%`} />
                <ResultBox label="Withheld at 22%" value={formatCurrency(rsuResult.total_withholding_at_supplemental)} />
                <ResultBox label="Tax Actually Owed" value={formatCurrency(rsuResult.total_tax_at_marginal)} />
              </div>

              {rsuResult.state_tax > 0 && (
                <div className="bg-stone-50 rounded-lg p-3">
                  <p className="text-xs text-stone-500 mb-1">State Tax Impact</p>
                  <p className="text-sm font-mono tabular-nums text-stone-800">
                    {formatCurrency(rsuResult.state_tax)} at {(rsuResult.state_rate * 100).toFixed(1)}% state rate
                  </p>
                </div>
              )}

              {rsuResult.quarterly_payments.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-stone-800 flex items-center gap-2 mb-2">
                    <DollarSign size={14} className="text-[#16A34A]" />
                    Estimated Quarterly Payments
                  </h4>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    {rsuResult.quarterly_payments.map((q) => (
                      <div key={q.quarter} className="bg-white border border-stone-200 rounded-lg p-3 text-center">
                        <p className="text-xs text-stone-500">Q{q.quarter} — {q.due_date}</p>
                        <p className="text-lg font-semibold font-mono tabular-nums text-stone-800">{formatCurrency(q.amount)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {mode === "iso" && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
            <LabeledInput label="Option Shares Available" value={isoShares} onChange={setIsoShares} />
            <LabeledInput label="Strike Price" value={strikePrice} onChange={setStrikePrice} />
            <LabeledInput label="Current Market Value / Share" value={currentFmv} onChange={setCurrentFmv} />
            <LabeledInput label="Other Income (W-2)" value={isoOtherIncome} onChange={setIsoOtherIncome} />
            <div>
              <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
              <select value={isoFiling} onChange={(e) => setIsoFiling(e.target.value)} className={INPUT_CLS}>
                <option value="single">Single</option>
                <option value="mfj">Married Filing Jointly</option>
              </select>
            </div>
          </div>
          <CalcButton loading={loading} onClick={handleISOCalc} />

          {isoResult && (
            <div className="mt-4 space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
                <Shield size={16} className="text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-green-800">
                    Safe to exercise: {isoResult.safe_exercise_shares.toLocaleString()} shares without triggering Alternative Minimum Tax
                  </p>
                  <p className="text-xs text-green-600 mt-0.5">{isoResult.recommendation}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <ResultBox label="Safe Exercise Count" value={isoResult.safe_exercise_shares.toLocaleString()} color="green" />
                <ResultBox label="AMT Trigger Point" value={formatCurrency(isoResult.amt_trigger_point)} />
                <ResultBox label="Spread per Share" value={formatCurrency(isoResult.iso_bargain_element)} />
                <ResultBox label="AMT Exemption Amount" value={formatCurrency(isoResult.amt_exemption)} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-stone-50 rounded-lg p-3">
                  <p className="text-xs text-stone-500 mb-1">Regular Tax (without exercise)</p>
                  <p className="text-sm font-semibold font-mono tabular-nums text-stone-800">
                    {formatCurrency(isoResult.regular_tax)}
                  </p>
                </div>
                <div className="bg-stone-50 rounded-lg p-3">
                  <p className="text-xs text-stone-500 mb-1">Alternative Minimum Tax (if all exercised)</p>
                  <p className={`text-sm font-semibold font-mono tabular-nums ${isoResult.amt_tax_with_exercise > isoResult.regular_tax ? "text-red-700" : "text-stone-800"}`}>
                    {formatCurrency(isoResult.amt_tax_with_exercise)}
                    {isoResult.amt_tax_with_exercise > isoResult.regular_tax && (
                      <span className="text-xs font-normal ml-1">
                        (+{formatCurrency(isoResult.amt_tax_with_exercise - isoResult.regular_tax)})
                      </span>
                    )}
                  </p>
                </div>
              </div>

              <div className="bg-blue-50 rounded-lg p-3 space-y-1">
                <p className="text-xs text-blue-800">
                  The spread (market value − strike price) is {formatCurrency(isoResult.iso_bargain_element)} per share.
                  Exercising {isoResult.safe_exercise_shares} shares keeps you under the Alternative Minimum Tax crossover point.
                </p>
                <p className="text-xs text-blue-800">
                  If you hold the shares for 1 year after exercise and 2 years after grant, the gain qualifies for long-term capital gains rates.
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </SimulatorCard>
  );
}
