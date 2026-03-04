"use client";
import { useState } from "react";
import { Heart, TrendingUp, Shield } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import SimulatorCard from "../shared/SimulatorCard";
import LabeledInput from "../shared/LabeledInput";
import CalcButton from "../shared/CalcButton";
import ResultBox from "../shared/ResultBox";

const INPUT_CLS = "w-full text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]";

// 2025 HSA limits
const HSA_LIMIT = { individual: 4_300, family: 8_550 };
const HSA_CATCHUP = 1_000; // age 55+

interface HSAResult {
  max_contribution: number;
  catchup_amount: number;
  total_limit: number;
  employer_contribution: number;
  your_remaining_room: number;
  year_one_tax_savings: number;
  year_one_fica_savings: number;
  year_one_total_savings: number;
  projected_balance_10yr: number;
  projected_balance_20yr: number;
  projected_balance_30yr: number;
  tax_free_withdrawals_value: number;
  triple_tax_advantage: number;
  marginal_rate: number;
}

// 2025 federal brackets (simplified for client-side calc)
function getMarginalRate(income: number, filing: string): number {
  const brackets = filing === "single" || filing === "mfs" ? [
    [11_925, 0.10], [48_475, 0.12], [103_350, 0.22], [197_300, 0.24],
    [250_525, 0.32], [375_800, 0.35], [Infinity, 0.37],
  ] : [
    [23_850, 0.10], [96_950, 0.12], [206_700, 0.22], [394_600, 0.24],
    [501_050, 0.32], [751_600, 0.35], [Infinity, 0.37],
  ];
  for (const [ceiling, rate] of brackets) {
    if (income <= ceiling) return rate as number;
  }
  return 0.37;
}

function calculateHSA(
  coverage: "individual" | "family",
  age: number,
  employerContribution: number,
  currentBalance: number,
  income: number,
  filingStatus: string,
): HSAResult {
  const baseLimit = HSA_LIMIT[coverage];
  const catchup = age >= 55 ? HSA_CATCHUP : 0;
  const totalLimit = baseLimit + catchup;
  const yourRoom = Math.max(0, totalLimit - employerContribution);

  const marginal = getMarginalRate(income, filingStatus);
  // HSA contributions are pre-tax (reduce federal + state + FICA)
  const ficaRate = 0.0765; // 7.65% employee share
  const yearOneTaxSavings = yourRoom * marginal;
  const yearOneFicaSavings = yourRoom * ficaRate;
  const yearOneTotalSavings = yearOneTaxSavings + yearOneFicaSavings;

  const growthRate = 0.07; // assumed annual return
  const annualContrib = yourRoom;

  // Future value of current balance + annual contributions
  function fvBalance(years: number): number {
    const fvCurrent = currentBalance * Math.pow(1 + growthRate, years);
    const fvContrib = annualContrib * ((Math.pow(1 + growthRate, years) - 1) / growthRate);
    return fvCurrent + fvContrib;
  }

  const bal10 = fvBalance(10);
  const bal20 = fvBalance(20);
  const bal30 = fvBalance(30);

  // Triple-tax advantage: tax saved on contributions + tax-free growth + tax-free withdrawals
  // Over 20 years, total tax benefit vs taxable account
  const totalContributed = yourRoom * 20;
  const taxOnContribs = totalContributed * marginal; // deduction savings
  const taxFreeGrowth = (bal20 - currentBalance - totalContributed) * marginal; // growth never taxed
  const tripleTaxAdvantage = taxOnContribs + taxFreeGrowth + yearOneFicaSavings * 20;

  return {
    max_contribution: baseLimit,
    catchup_amount: catchup,
    total_limit: totalLimit,
    employer_contribution: employerContribution,
    your_remaining_room: yourRoom,
    year_one_tax_savings: yearOneTaxSavings,
    year_one_fica_savings: yearOneFicaSavings,
    year_one_total_savings: yearOneTotalSavings,
    projected_balance_10yr: bal10,
    projected_balance_20yr: bal20,
    projected_balance_30yr: bal30,
    tax_free_withdrawals_value: bal20 * marginal, // tax you'd pay if this were in a taxable account
    triple_tax_advantage: tripleTaxAdvantage,
    marginal_rate: marginal,
  };
}

export default function HSAMaxSim() {
  const [coverage, setCoverage] = useState<"individual" | "family">("family");
  const [age, setAge] = useState("40");
  const [employerHSA, setEmployerHSA] = useState("0");
  const [currentBalance, setCurrentBalance] = useState("0");
  const [income, setIncome] = useState("");
  const [filingStatus, setFilingStatus] = useState("mfj");
  const [result, setResult] = useState<HSAResult | null>(null);
  const [loading, setLoading] = useState(false);

  function handleCalc() {
    setLoading(true);
    setResult(null);
    // Client-side — simulate async
    setTimeout(() => {
      setResult(calculateHSA(
        coverage,
        Number(age),
        Number(employerHSA),
        Number(currentBalance),
        Number(income),
        filingStatus,
      ));
      setLoading(false);
    }, 200);
  }

  return (
    <SimulatorCard
      title="Health Savings Account (HSA) Maximization Planner"
      purpose="The Health Savings Account is the only triple-tax-advantaged account: contributions are tax-deductible, growth is tax-free, and withdrawals for medical expenses are never taxed. See how much you're leaving on the table."
      bestFor="Anyone with a high-deductible health plan (HDHP) eligible for an HSA"
    >
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs text-stone-500 mb-1">Coverage Type</label>
          <select value={coverage} onChange={(e) => setCoverage(e.target.value as "individual" | "family")} className={INPUT_CLS}>
            <option value="individual">Individual</option>
            <option value="family">Family</option>
          </select>
        </div>
        <LabeledInput label="Your Age" value={age} onChange={setAge} />
        <LabeledInput label="Employer HSA Contribution" value={employerHSA} onChange={setEmployerHSA} />
        <LabeledInput label="Current HSA Balance" value={currentBalance} onChange={setCurrentBalance} />
        <LabeledInput label="Household Income" value={income} onChange={setIncome} />
        <div>
          <label className="block text-xs text-stone-500 mb-1">Filing Status</label>
          <select value={filingStatus} onChange={(e) => setFilingStatus(e.target.value)} className={INPUT_CLS}>
            <option value="single">Single</option>
            <option value="mfj">Married Filing Jointly</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="hh">Head of Household</option>
          </select>
        </div>
      </div>
      <CalcButton loading={loading} onClick={handleCalc} />

      {result && (
        <div className="mt-4 space-y-5">
          {/* Triple tax advantage banner */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
            <Shield size={16} className="text-green-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-green-800">
                Triple tax advantage: {formatCurrency(result.year_one_total_savings)} saved in year one
              </p>
              <p className="text-xs text-green-600 mt-0.5">
                {formatCurrency(result.year_one_tax_savings)} federal tax + {formatCurrency(result.year_one_fica_savings)} payroll tax (FICA) savings at your {(result.marginal_rate * 100).toFixed(0)}% marginal rate
              </p>
            </div>
          </div>

          {/* Key numbers */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <ResultBox label="2025 Contribution Limit" value={formatCurrency(result.total_limit)} />
            <ResultBox label="Employer Contributes" value={formatCurrency(result.employer_contribution)} />
            <ResultBox label="Your Room Left" value={formatCurrency(result.your_remaining_room)} color="green" />
            <ResultBox label="Year-One Tax Savings" value={formatCurrency(result.year_one_total_savings)} color="green" />
          </div>

          {result.catchup_amount > 0 && (
            <div className="bg-blue-50 rounded-lg p-3 flex items-start gap-2">
              <Heart size={14} className="text-blue-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-blue-800">
                Age 55+ catch-up: you can contribute an extra {formatCurrency(result.catchup_amount)} beyond the standard limit.
              </p>
            </div>
          )}

          {/* Growth projections */}
          <div className="bg-stone-50 rounded-lg p-4 space-y-3">
            <h4 className="text-sm font-semibold text-stone-800 flex items-center gap-2">
              <TrendingUp size={14} className="text-[#16A34A]" />
              Projected Account Balance (7% annual growth)
            </h4>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <p className="text-xs text-stone-500 mb-1">In 10 Years</p>
                <p className="text-lg font-semibold font-mono tabular-nums text-stone-800">{formatCurrency(result.projected_balance_10yr)}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-stone-500 mb-1">In 20 Years</p>
                <p className="text-lg font-semibold font-mono tabular-nums text-stone-800">{formatCurrency(result.projected_balance_20yr)}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-stone-500 mb-1">In 30 Years</p>
                <p className="text-lg font-semibold font-mono tabular-nums text-green-700">{formatCurrency(result.projected_balance_30yr)}</p>
              </div>
            </div>
          </div>

          {/* 20-year triple-tax value */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white border border-stone-200 rounded-lg p-3">
              <p className="text-xs text-stone-500 mb-1">20-Year Triple-Tax Advantage</p>
              <p className="text-lg font-semibold font-mono tabular-nums text-green-700">{formatCurrency(result.triple_tax_advantage)}</p>
              <p className="text-xs text-stone-500 mt-1">vs same investments in a taxable brokerage account</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-lg p-3">
              <p className="text-xs text-stone-500 mb-1">Tax-Free Withdrawal Value (20yr)</p>
              <p className="text-lg font-semibold font-mono tabular-nums text-stone-800">{formatCurrency(result.projected_balance_20yr)}</p>
              <p className="text-xs text-stone-500 mt-1">100% tax-free for qualified medical expenses</p>
            </div>
          </div>

          {/* Tips */}
          <div className="bg-blue-50 rounded-lg p-3 space-y-1.5">
            <p className="text-xs text-blue-800 font-medium">Health Savings Account Tips:</p>
            <p className="text-xs text-blue-800">
              • Pay medical expenses out-of-pocket now, keep receipts, and let your HSA grow tax-free. Reimburse yourself years later for a tax-free withdrawal.
            </p>
            <p className="text-xs text-blue-800">
              • After age 65, these funds can be used for any purpose (taxed like a traditional retirement account) — making it a stealth retirement account.
            </p>
            <p className="text-xs text-blue-800">
              • Invest your HSA balance in index funds rather than leaving it in cash — the tax-free growth is the most powerful part.
            </p>
          </div>
        </div>
      )}
    </SimulatorCard>
  );
}
