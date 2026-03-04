"use client";
import { useState } from "react";
import { MapPin, TrendingDown, CheckCircle } from "lucide-react";
import { modelStateComparison } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { StateComparisonResult } from "@/types/api";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

const STATE_OPTIONS = [
  { code: "CA", name: "California" }, { code: "NY", name: "New York" },
  { code: "NJ", name: "New Jersey" }, { code: "OR", name: "Oregon" },
  { code: "MN", name: "Minnesota" }, { code: "HI", name: "Hawaii" },
  { code: "DC", name: "Washington DC" }, { code: "VT", name: "Vermont" },
  { code: "WI", name: "Wisconsin" }, { code: "ME", name: "Maine" },
  { code: "CT", name: "Connecticut" }, { code: "MA", name: "Massachusetts" },
  { code: "IL", name: "Illinois" }, { code: "CO", name: "Colorado" },
  { code: "GA", name: "Georgia" }, { code: "VA", name: "Virginia" },
  { code: "MD", name: "Maryland" }, { code: "NC", name: "North Carolina" },
  { code: "PA", name: "Pennsylvania" }, { code: "OH", name: "Ohio" },
  { code: "AZ", name: "Arizona" }, { code: "UT", name: "Utah" },
  { code: "SC", name: "South Carolina" }, { code: "KY", name: "Kentucky" },
  { code: "MO", name: "Missouri" }, { code: "OK", name: "Oklahoma" },
  { code: "KS", name: "Kansas" }, { code: "IN", name: "Indiana" },
  { code: "MI", name: "Michigan" }, { code: "ND", name: "North Dakota" },
  { code: "TX", name: "Texas" }, { code: "FL", name: "Florida" },
  { code: "WA", name: "Washington" }, { code: "NV", name: "Nevada" },
  { code: "WY", name: "Wyoming" }, { code: "TN", name: "Tennessee" },
  { code: "NH", name: "New Hampshire" }, { code: "SD", name: "South Dakota" },
  { code: "AK", name: "Alaska" },
];

const NO_TAX_STATES = ["TX", "FL", "WA", "NV", "WY", "TN", "NH", "SD", "AK"];

export default function StateComparisonSim() {
  const [income, setIncome] = useState("");
  const [filingStatus, setFilingStatus] = useState("mfj");
  const [currentState, setCurrentState] = useState("CA");
  const [compareStates, setCompareStates] = useState<string[]>(["TX", "FL", "WA", "NV", "TN"]);
  const [result, setResult] = useState<StateComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);

  function toggleCompareState(code: string) {
    setCompareStates((prev) =>
      prev.includes(code)
        ? prev.filter((s) => s !== code)
        : prev.length < 8
        ? [...prev, code]
        : prev,
    );
  }

  async function handleCalc() {
    setLoading(true);
    setResult(null);
    try {
      setResult(await modelStateComparison({
        income: Number(income),
        filing_status: filingStatus,
        current_state: currentState,
        comparison_states: compareStates,
      }));
    } catch { /* handled */ } finally { setLoading(false); }
  }

  return (
    <SimulatorCard
      title="State Residency Tax Comparison"
      purpose="State income tax can range from 0% to 13.3%. See how much you'd save by relocating — or confirm you're already in the right place."
      bestFor="Remote workers, relocating professionals, and anyone considering a state move"
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <LabeledInput label="Total Annual Income" value={income} onChange={setIncome} />
        <div>
          <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="mfj">Married Filing Jointly</option>
            <option value="single">Single</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="hoh">Head of Household</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-stone-500 mb-1">Current State</label>
          <select value={currentState} onChange={(e) => setCurrentState(e.target.value)} className={INPUT_CLS}>
            {STATE_OPTIONS.map((s) => (
              <option key={s.code} value={s.code}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Compare states multi-select */}
      <div>
        <label className="block text-xs text-stone-500 mb-2">Compare With (select up to 8)</label>
        <div className="flex flex-wrap gap-1.5">
          {STATE_OPTIONS.filter((s) => s.code !== currentState).map((s) => {
            const selected = compareStates.includes(s.code);
            const isNoTax = NO_TAX_STATES.includes(s.code);
            return (
              <button
                key={s.code}
                onClick={() => toggleCompareState(s.code)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  selected
                    ? "bg-[#16A34A] text-white"
                    : isNoTax
                    ? "bg-green-50 text-green-700 hover:bg-green-100 border border-green-200"
                    : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                }`}
              >
                {s.code}
              </button>
            );
          })}
        </div>
        <p className="text-[10px] text-stone-400 mt-1">
          Green borders = no state income tax · {compareStates.length}/8 selected
        </p>
      </div>

      <CalcButton loading={loading} onClick={handleCalc} />

      {result && (
        <div className="mt-4 space-y-4">
          {/* Top banner */}
          {result.max_savings > 0 ? (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
              <MapPin size={16} className="text-green-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-green-800">{result.recommendation}</p>
              </div>
            </div>
          ) : (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-start gap-2">
              <CheckCircle size={16} className="text-blue-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm font-medium text-blue-800">{result.recommendation}</p>
            </div>
          )}

          {/* Key metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <ResultBox label="Max Annual Savings" value={formatCurrency(result.max_savings)} color="green" />
            <ResultBox label="Current State Tax" value={formatCurrency(result.current_state_tax)} />
            <ResultBox label="Federal Tax" value={formatCurrency(result.federal_tax)} />
            <ResultBox label="Payroll Tax (FICA)" value={formatCurrency(result.fica)} />
          </div>

          {/* State comparison table */}
          <div className="rounded-lg border border-stone-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-stone-50 border-b border-stone-200">
                  <th className="text-left px-3 py-2 text-xs font-semibold text-stone-600">State</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-stone-600">State Rate</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-stone-600">State Tax</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-stone-600">Total Tax</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-stone-600">Effective Rate</th>
                  <th className="text-right px-3 py-2 text-xs font-semibold text-stone-600">Savings vs Current</th>
                </tr>
              </thead>
              <tbody>
                {result.states.map((s, i) => (
                  <tr
                    key={s.state}
                    className={`border-b border-stone-100 last:border-0 ${
                      s.is_current ? "bg-amber-50" : i === 0 && !s.is_current ? "bg-green-50" : ""
                    }`}
                  >
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        {s.is_current && <span className="text-[10px] bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded font-medium">Current</span>}
                        {!s.is_current && i === 0 && <CheckCircle size={12} className="text-green-600" />}
                        <span className="font-medium text-stone-800">{s.state}</span>
                        <span className="text-stone-400 text-xs">{s.state_name}</span>
                        {s.is_no_tax && <span className="text-[10px] bg-green-100 text-green-700 px-1 py-0.5 rounded">0% tax</span>}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-stone-700">
                      {(s.state_rate * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-stone-700">
                      {formatCurrency(s.state_tax)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums font-medium text-stone-800">
                      {formatCurrency(s.total_tax)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-stone-700">
                      {(s.effective_total_rate * 100).toFixed(1)}%
                    </td>
                    <td className={`px-3 py-2 text-right font-mono tabular-nums font-medium ${
                      s.savings_vs_current > 0 ? "text-green-700" : s.savings_vs_current < 0 ? "text-red-600" : "text-stone-400"
                    }`}>
                      {s.savings_vs_current > 0 && (
                        <span className="inline-flex items-center gap-0.5">
                          <TrendingDown size={12} />
                          {formatCurrency(s.savings_vs_current)}
                        </span>
                      )}
                      {s.savings_vs_current < 0 && `+${formatCurrency(Math.abs(s.savings_vs_current))}`}
                      {s.savings_vs_current === 0 && "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Caveats */}
          <div className="bg-blue-50 rounded-lg p-3 space-y-1.5">
            <p className="text-xs text-blue-800 font-medium">Important Considerations:</p>
            <p className="text-xs text-blue-800">
              • This uses simplified top marginal state rates. Actual taxes depend on state-specific brackets, deductions, and credits.
            </p>
            <p className="text-xs text-blue-800">
              • Some states have no income tax but higher property, sales, or other taxes — compare total tax burden before moving.
            </p>
            <p className="text-xs text-blue-800">
              • Establish genuine domicile in the new state. California and New York aggressively audit departures — keep documentation.
            </p>
            <p className="text-xs text-blue-800">
              • Remote workers: your tax obligation may depend on your employer&apos;s state, not just where you live (varies by state).
            </p>
          </div>
        </div>
      )}
    </SimulatorCard>
  );
}
