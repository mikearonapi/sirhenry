"use client";
import { useEffect, useState } from "react";
import {
  Briefcase, Plus, TrendingUp, AlertTriangle, PieChart, DollarSign,
  Calendar, ChevronDown, ChevronUp, Trash2, Calculator, ArrowRightLeft,
  LogOut, ShoppingCart, Loader2, X, RefreshCw, MessageCircle,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  getEquityGrants, createEquityGrant, deleteEquityGrant, getEquityDashboard,
  calcWithholdingGap, calcSellStrategy, calcAMTCrossover, calcConcentrationRisk,
} from "@/lib/api";
import { getHouseholdProfiles } from "@/lib/api-household";
import type {
  EquityGrant, EquityDashboard, WithholdingGapResult,
  SellStrategyResult, AMTCrossoverResult, ConcentrationRiskResult,
} from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import { request } from "@/lib/api-client";
import EmptyState from "@/components/ui/EmptyState";
import ESPPAnalysis from "@/components/equity-comp/ESPPAnalysis";
import SirHenryName from "@/components/ui/SirHenryName";
import VestingCalendar from "@/components/equity-comp/VestingCalendar";

const GRANT_TYPE_COLORS: Record<string, string> = {
  rsu: "bg-blue-100 text-blue-800",
  iso: "bg-green-100 text-green-800",
  nso: "bg-amber-100 text-amber-800",
  espp: "bg-purple-100 text-purple-800",
};

const RISK_COLORS: Record<string, string> = {
  low: "text-green-600",
  moderate: "text-yellow-600",
  elevated: "text-orange-500",
  high: "text-red-500",
  critical: "text-red-700",
};

type AnalysisTab = "withholding" | "sell" | "amt" | "leave" | "espp" | "vesting";

export default function EquityCompPage() {
  const [dashboard, setDashboard] = useState<EquityDashboard | null>(null);
  const [grants, setGrants] = useState<EquityGrant[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [activeTab, setActiveTab] = useState<AnalysisTab>("withholding");
  const [expandedGrant, setExpandedGrant] = useState<number | null>(null);

  // Analysis results
  const [gapResult, setGapResult] = useState<WithholdingGapResult | null>(null);
  const [sellResult, setSellResult] = useState<SellStrategyResult | null>(null);
  const [amtResult, setAmtResult] = useState<AMTCrossoverResult | null>(null);
  const [concentrationResult, setConcentrationResult] = useState<ConcentrationRiskResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Add form state
  const [form, setForm] = useState({
    employer_name: "", grant_type: "rsu" as "rsu" | "iso" | "nso" | "espp", grant_date: "",
    total_shares: 0, current_fmv: 0, strike_price: 0, ticker: "",
    vesting_schedule_json: JSON.stringify({ cliff_months: 12, frequency: "quarterly", total_months: 48 }),
  });

  // Analysis form state
  const [gapForm, setGapForm] = useState({ vest_income: 100000, other_income: 200000, filing_status: "mfj", state: "CA" });
  const [sellForm, setSellForm] = useState({ shares: 100, cost_basis_per_share: 100, current_price: 150, other_income: 200000, holding_period_months: 0 });
  const [amtForm, setAmtForm] = useState({ iso_shares_available: 1000, strike_price: 20, current_fmv: 80, other_income: 200000 });

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [d, g] = await Promise.all([getEquityDashboard(), getEquityGrants()]);
      setDashboard(d);
      setGrants(g);
      // Seed analysis form defaults from household data
      try {
        const profiles = await getHouseholdProfiles();
        const primary = profiles.find((p) => p.is_primary) ?? profiles[0];
        if (primary) {
          const income = primary.combined_income ?? 200000;
          const filing = primary.filing_status ?? "mfj";
          const state = primary.state ?? "CA";
          setGapForm((f) => ({ ...f, other_income: income, filing_status: filing, state }));
          setSellForm((f) => ({ ...f, other_income: income }));
          setAmtForm((f) => ({ ...f, other_income: income }));
        }
      } catch { /* non-fatal */ }
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setLoading(false);
  }

  async function handleAddGrant() {
    try {
      setError(null);
      await createEquityGrant({
        ...form,
        total_shares: Number(form.total_shares),
        current_fmv: Number(form.current_fmv) || undefined,
        strike_price: Number(form.strike_price) || undefined,
        ticker: form.ticker || undefined,
      });
      setShowAddForm(false);
      setForm({ employer_name: "", grant_type: "rsu", grant_date: "", total_shares: 0, current_fmv: 0, strike_price: 0, ticker: "", vesting_schedule_json: JSON.stringify({ cliff_months: 12, frequency: "quarterly", total_months: 48 }) });
      await loadData();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this grant?")) return;
    try {
      await deleteEquityGrant(id);
      await loadData();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
  }

  async function runWithholdingGap() {
    setAnalyzing(true);
    try {
      setError(null);
      const r = await calcWithholdingGap(gapForm);
      setGapResult(r);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setAnalyzing(false);
  }

  async function runSellStrategy() {
    setAnalyzing(true);
    try {
      setError(null);
      const r = await calcSellStrategy(sellForm);
      setSellResult(r);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setAnalyzing(false);
  }

  async function runAMT() {
    setAnalyzing(true);
    try {
      setError(null);
      const r = await calcAMTCrossover(amtForm);
      setAmtResult(r);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setAnalyzing(false);
  }

  async function runConcentration() {
    if (!dashboard) return;
    setAnalyzing(true);
    try {
      const r = await calcConcentrationRisk({ employer_stock_value: dashboard.total_equity_value, total_net_worth: dashboard.total_equity_value * 3 });
      setConcentrationResult(r);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setAnalyzing(false);
  }

  useEffect(() => { if (dashboard && !concentrationResult) runConcentration(); }, [dashboard]);

  const fmt = (n: number) => formatCurrency(n);
  const pct = (n: number) => formatPercent(n * 100);

  if (loading) return <div className="flex items-center justify-center h-96"><Loader2 className="animate-spin text-text-muted" size={32} /></div>;

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertTriangle size={18} />
          <p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600"><X size={14} /></button>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Equity Compensation</h1>
          <p className="text-text-secondary text-sm mt-1">Track grants, model tax impact, and optimize your equity strategy</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "Help me plan my equity compensation strategy. What should I know about RSU/ISO taxes?" } }))}
            className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
          >
            <MessageCircle size={14} />
            Ask <SirHenryName />
          </button>
          <button
            onClick={async () => {
              setRefreshing(true);
              try {
                await request("/equity-comp/refresh-prices", { method: "POST" });
                await loadData();
              } catch (e: unknown) { setError(getErrorMessage(e)); }
              setRefreshing(false);
            }}
            disabled={refreshing}
            className="flex items-center gap-2 border border-border text-text-secondary px-3 py-2 rounded-lg text-sm font-medium hover:bg-surface disabled:opacity-50"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? "Refreshing..." : "Refresh Prices"}
          </button>
          <button onClick={() => setShowAddForm(true)} className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover text-sm font-medium">
            <Plus size={16} /> Add Grant
          </button>
        </div>
      </div>

      {/* Dashboard Stats */}
      {dashboard && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-card rounded-xl border border-border p-5">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center"><DollarSign size={20} className="text-blue-600" /></div>
              <div><p className="text-xs text-text-secondary">Total Equity Value</p><p className="text-xl font-bold text-text-primary font-mono tabular-nums">{fmt(dashboard.total_equity_value)}</p></div>
            </div>
          </div>
          <div className="bg-card rounded-xl border border-border p-5">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center"><Calendar size={20} className="text-green-600" /></div>
              <div><p className="text-xs text-text-secondary">Upcoming Vests (12mo)</p><p className="text-xl font-bold text-text-primary font-mono tabular-nums">{fmt(dashboard.upcoming_vest_value_12mo)}</p></div>
            </div>
          </div>
          <div className="bg-card rounded-xl border border-border p-5">
            <div className="flex items-center gap-3 mb-2">
              <div className={`w-10 h-10 rounded-lg ${dashboard.total_withholding_gap > 5000 ? "bg-red-50" : "bg-surface"} flex items-center justify-center`}>
                <AlertTriangle size={20} className={dashboard.total_withholding_gap > 5000 ? "text-red-600" : "text-text-muted"} />
              </div>
              <div><p className="text-xs text-text-secondary">Withholding Gap</p><p className={`text-xl font-bold ${dashboard.total_withholding_gap > 5000 ? "text-red-600" : "text-text-primary"}`}>{fmt(dashboard.total_withholding_gap)}</p></div>
            </div>
          </div>
          <div className="bg-card rounded-xl border border-border p-5">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center"><PieChart size={20} className="text-purple-600" /></div>
              <div>
                <p className="text-xs text-text-secondary">Concentration Risk</p>
                <p className={`text-xl font-bold font-mono tabular-nums ${concentrationResult ? RISK_COLORS[concentrationResult.risk_level] : "text-text-primary"}`}>
                  {concentrationResult ? `${concentrationResult.concentration_pct.toFixed(0)}%` : "—"}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Grant Modal */}
      {showAddForm && (
        <div className="bg-card rounded-xl border border-border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-text-primary">Add Equity Grant</h2>
            <button onClick={() => setShowAddForm(false)}><X size={18} className="text-text-muted" /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Employer</label>
              <input className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={form.employer_name} onChange={e => setForm({ ...form, employer_name: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Grant Type</label>
              <select className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={form.grant_type} onChange={e => setForm({ ...form, grant_type: e.target.value as "rsu" | "iso" | "nso" | "espp" })}>
                <option value="rsu">RSU</option><option value="iso">ISO</option><option value="nso">NSO</option><option value="espp">ESPP</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Grant Date</label>
              <input type="date" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={form.grant_date} onChange={e => setForm({ ...form, grant_date: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Total Shares</label>
              <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={form.total_shares || ""} onChange={e => setForm({ ...form, total_shares: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Current FMV / Share</label>
              <input type="number" step="0.01" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={form.current_fmv || ""} onChange={e => setForm({ ...form, current_fmv: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Strike Price (options)</label>
              <input type="number" step="0.01" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={form.strike_price || ""} onChange={e => setForm({ ...form, strike_price: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Ticker</label>
              <input className="w-full border border-border rounded-lg px-3 py-2 text-sm" placeholder="e.g. ACN" value={form.ticker} onChange={e => setForm({ ...form, ticker: e.target.value })} />
            </div>
          </div>
          <button onClick={handleAddGrant} className="mt-4 px-6 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover">Save Grant</button>
        </div>
      )}

      {/* Grant Manager */}
      <div className="bg-card rounded-xl border border-border">
        <div className="px-5 py-4 border-b border-card-border"><h2 className="font-semibold text-text-primary">Your Grants</h2></div>
        {grants.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={<Briefcase size={36} />}
              title="Track your equity compensation"
              description="RSUs, ISOs, NSOs, ESPP — most HENRYs leave money on the table with equity comp. Model tax impact, avoid underwithholding, and time your sales."
              henryTip="At $200K+ income, your RSU vests are withheld at 22% but your marginal rate is likely 32-37%. That gap adds up fast — I can help you plan for it."
              askHenryPrompt="I just got a stock grant from my employer. What should I know about the tax implications?"
              action={
                <button onClick={() => setShowAddForm(true)} className="bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm">
                  Add Your First Grant
                </button>
              }
            />
          </div>
        ) : (
          <div className="divide-y divide-card-border">
            {grants.map(g => (
              <div key={g.id} className="px-5 py-4">
                <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpandedGrant(expandedGrant === g.id ? null : g.id)}>
                  <div className="flex items-center gap-3">
                    <Briefcase size={18} className="text-text-muted" />
                    <div>
                      <p className="font-medium text-text-primary">{g.employer_name} {g.ticker && <span className="text-text-muted text-sm">({g.ticker})</span>}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${GRANT_TYPE_COLORS[g.grant_type]}`}>{g.grant_type.toUpperCase()}</span>
                        <span className="text-xs text-text-muted">{g.total_shares.toLocaleString()} shares</span>
                        <span className="text-xs text-text-muted">Granted {g.grant_date}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="font-semibold text-text-primary font-mono tabular-nums">{g.current_fmv ? fmt(g.total_shares * g.current_fmv) : "—"}</p>
                      <p className="text-xs text-text-muted">{g.vested_shares.toLocaleString()} vested / {g.unvested_shares.toLocaleString()} unvested</p>
                    </div>
                    {expandedGrant === g.id ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
                  </div>
                </div>
                {expandedGrant === g.id && (
                  <div className="mt-4 pt-4 border-t border-card-border grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><p className="text-text-secondary text-xs">Grant Date</p><p className="font-medium">{g.grant_date}</p></div>
                    <div><p className="text-text-secondary text-xs">Current FMV</p><p className="font-medium">{g.current_fmv ? `$${g.current_fmv.toFixed(2)}` : "—"}</p></div>
                    <div><p className="text-text-secondary text-xs">Strike Price</p><p className="font-medium">{g.strike_price ? `$${g.strike_price.toFixed(2)}` : "N/A"}</p></div>
                    <div><p className="text-text-secondary text-xs">Expiration</p><p className="font-medium">{g.expiration_date || "N/A"}</p></div>
                    <div className="col-span-2 md:col-span-4 flex justify-end">
                      <button onClick={() => handleDelete(g.id)} className="text-red-500 hover:text-red-700 text-xs flex items-center gap-1"><Trash2 size={14} /> Delete</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Analysis Tools */}
      <div className="bg-card rounded-xl border border-border">
        <div className="px-5 py-4 border-b border-card-border">
          <h2 className="font-semibold text-text-primary mb-3">Analysis Tools</h2>
          <div className="flex gap-2 flex-wrap">
            {([
              ["vesting", "Vesting Calendar", Calendar],
              ["withholding", "Underwithholding", AlertTriangle],
              ["sell", "Sell Strategy", ArrowRightLeft],
              ["amt", "AMT Calculator", Calculator],
              ["leave", "What If I Leave?", LogOut],
              ["espp", "ESPP Optimizer", ShoppingCart],
            ] as const).map(([key, label, Icon]) => (
              <button key={key} onClick={() => setActiveTab(key)} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${activeTab === key ? "bg-accent text-white" : "bg-surface text-text-secondary hover:bg-surface"}`}>
                <Icon size={14} />{label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-5">
          {/* Withholding Gap Tab */}
          {activeTab === "withholding" && (
            <div className="space-y-4">
              <p className="text-sm text-text-secondary">Federal supplemental withholding is only 22%, but your actual marginal rate is likely 32-37%. This tool calculates the gap.</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Vest Income</label>
                  <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={gapForm.vest_income} onChange={e => setGapForm({ ...gapForm, vest_income: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Other W-2 Income</label>
                  <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={gapForm.other_income} onChange={e => setGapForm({ ...gapForm, other_income: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Filing Status</label>
                  <select className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={gapForm.filing_status} onChange={e => setGapForm({ ...gapForm, filing_status: e.target.value })}>
                    <option value="mfj">Married Filing Jointly</option><option value="single">Single</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">State</label>
                  <input className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={gapForm.state} onChange={e => setGapForm({ ...gapForm, state: e.target.value })} />
                </div>
              </div>
              <button onClick={runWithholdingGap} disabled={analyzing} className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50">
                {analyzing ? "Calculating..." : "Calculate Gap"}
              </button>
              {gapResult && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-surface rounded-lg p-4">
                  <div><p className="text-xs text-text-secondary">Withheld at 22%</p><p className="font-semibold font-mono tabular-nums">{fmt(gapResult.total_withholding_at_supplemental)}</p></div>
                  <div><p className="text-xs text-text-secondary">Actual Tax Owed</p><p className="font-semibold font-mono tabular-nums">{fmt(gapResult.total_tax_at_marginal)}</p></div>
                  <div><p className="text-xs text-text-secondary">Marginal Rate</p><p className="font-semibold font-mono tabular-nums">{pct(gapResult.actual_marginal_rate)}</p></div>
                  <div><p className="text-xs text-text-secondary">Withholding Gap</p><p className={`font-bold text-lg font-mono tabular-nums ${gapResult.withholding_gap > 0 ? "text-red-600" : "text-green-600"}`}>{fmt(gapResult.withholding_gap)}</p></div>
                  {gapResult.quarterly_payments.length > 0 && (
                    <div className="col-span-2 md:col-span-4">
                      <p className="text-xs font-medium text-text-secondary mb-2">Recommended Quarterly Estimated Payments</p>
                      <div className="flex gap-3">
                        {gapResult.quarterly_payments.map(q => (
                          <div key={q.quarter} className="bg-card rounded-lg p-3 border border-border flex-1 text-center">
                            <p className="text-xs text-text-secondary">Q{q.quarter} — {q.due_date}</p>
                            <p className="font-semibold text-text-primary">{fmt(q.amount)}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Sell Strategy Tab */}
          {activeTab === "sell" && (
            <div className="space-y-4">
              <p className="text-sm text-text-secondary">Compare immediate sell, hold for LTCG treatment, or staged selling to optimize after-tax proceeds.</p>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Shares</label>
                  <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={sellForm.shares} onChange={e => setSellForm({ ...sellForm, shares: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Cost Basis / Share</label>
                  <input type="number" step="0.01" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={sellForm.cost_basis_per_share} onChange={e => setSellForm({ ...sellForm, cost_basis_per_share: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Current Price</label>
                  <input type="number" step="0.01" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={sellForm.current_price} onChange={e => setSellForm({ ...sellForm, current_price: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Other Income</label>
                  <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={sellForm.other_income} onChange={e => setSellForm({ ...sellForm, other_income: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Holding (months)</label>
                  <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={sellForm.holding_period_months} onChange={e => setSellForm({ ...sellForm, holding_period_months: Number(e.target.value) })} />
                </div>
              </div>
              <button onClick={runSellStrategy} disabled={analyzing} className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50">
                {analyzing ? "Calculating..." : "Compare Strategies"}
              </button>
              {sellResult && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="bg-surface rounded-lg p-4 border border-border">
                      <p className="text-xs font-medium text-text-secondary mb-2">Sell Now</p>
                      <p className="text-lg font-bold text-text-primary font-mono tabular-nums">{fmt(sellResult.immediate_sell.net_proceeds)}</p>
                      <p className="text-xs text-text-secondary">Tax: {fmt(sellResult.immediate_sell.tax)} at {pct(sellResult.immediate_sell.tax_rate)}</p>
                    </div>
                    <div className="bg-surface rounded-lg p-4 border border-border">
                      <p className="text-xs font-medium text-text-secondary mb-2">Hold 1 Year (projected)</p>
                      <p className="text-lg font-bold text-text-primary font-mono tabular-nums">{fmt(sellResult.hold_one_year.net_proceeds)}</p>
                      <p className="text-xs text-text-secondary">Tax: {fmt(sellResult.hold_one_year.tax)} at {pct(sellResult.hold_one_year.tax_rate)}</p>
                    </div>
                    <div className="bg-surface rounded-lg p-4 border border-border">
                      <p className="text-xs font-medium text-text-secondary mb-2">Staged (50/50)</p>
                      <p className="text-lg font-bold text-text-primary font-mono tabular-nums">{fmt(sellResult.staged_sell.net_proceeds)}</p>
                      <p className="text-xs text-text-secondary">Tax: {fmt(sellResult.staged_sell.total_tax)}</p>
                    </div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800">{sellResult.recommendation}</div>
                </div>
              )}
            </div>
          )}

          {/* AMT Calculator Tab */}
          {activeTab === "amt" && (
            <div className="space-y-4">
              <p className="text-sm text-text-secondary">For ISO holders: calculate how many shares you can exercise without triggering the Alternative Minimum Tax.</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">ISO Shares Available</label>
                  <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={amtForm.iso_shares_available} onChange={e => setAmtForm({ ...amtForm, iso_shares_available: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Strike Price</label>
                  <input type="number" step="0.01" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={amtForm.strike_price} onChange={e => setAmtForm({ ...amtForm, strike_price: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Current FMV</label>
                  <input type="number" step="0.01" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={amtForm.current_fmv} onChange={e => setAmtForm({ ...amtForm, current_fmv: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Other Income</label>
                  <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={amtForm.other_income} onChange={e => setAmtForm({ ...amtForm, other_income: Number(e.target.value) })} />
                </div>
              </div>
              <button onClick={runAMT} disabled={analyzing} className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50">
                {analyzing ? "Calculating..." : "Calculate AMT Crossover"}
              </button>
              {amtResult && (
                <div className="bg-surface rounded-lg p-4 space-y-3">
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div><p className="text-xs text-text-secondary">Safe Exercise Shares</p><p className="text-xl font-bold text-green-600 font-mono tabular-nums">{amtResult.safe_exercise_shares.toLocaleString()}</p></div>
                    <div><p className="text-xs text-text-secondary">AMT Trigger Point</p><p className="font-semibold font-mono tabular-nums">{fmt(amtResult.amt_trigger_point)}</p></div>
                    <div><p className="text-xs text-text-secondary">Bargain Element / Share</p><p className="font-semibold font-mono tabular-nums">{fmt(amtResult.iso_bargain_element)}</p></div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800">{amtResult.recommendation}</div>
                </div>
              )}
            </div>
          )}

          {/* What If I Leave Tab */}
          {activeTab === "leave" && (
            <div className="space-y-4">
              <p className="text-sm text-text-secondary">See what you&apos;d forfeit and what it would cost to exercise if you left your employer. Uses your current grants above.</p>
              {grants.length === 0 ? (
                <p className="text-text-muted text-sm">Add grants above first.</p>
              ) : (
                <div className="bg-surface rounded-lg p-4">
                  <p className="text-sm text-text-secondary mb-2">Based on your {grants.length} active grant(s):</p>
                  {grants.map(g => (
                    <div key={g.id} className="flex justify-between py-2 border-b border-border last:border-0 text-sm">
                      <span>{g.employer_name} — {g.grant_type.toUpperCase()}</span>
                      <span className="text-red-600 font-medium">Forfeit: {g.current_fmv ? fmt(g.unvested_shares * g.current_fmv) : "—"}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Vesting Calendar Tab */}
          {activeTab === "vesting" && <VestingCalendar />}

          {/* ESPP Tab */}
          {activeTab === "espp" && (
            <ESPPAnalysis
              defaultIncome={gapForm.other_income}
              defaultFilingStatus={gapForm.filing_status}
            />
          )}
        </div>
      </div>
    </div>
  );
}
