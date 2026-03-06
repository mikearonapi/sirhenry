"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Plus, RefreshCw, TrendingUp, Loader2, AlertCircle,
  Scissors, MessageCircle,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  getHoldings, createHolding, deleteHolding, refreshPrices,
  getPortfolioSummary, getTaxLossHarvest, getCryptoHoldings,
  getPortfolioPerformance, getRebalanceRecommendations, getPortfolioConcentration,
  getNetWorthTrend, getPlaidAccounts,
} from "@/lib/api";
import { getManualAssets } from "@/lib/api-assets";
import type {
  InvestmentHolding, PortfolioSummary, TaxLossHarvestResult, CryptoHoldingType,
  PortfolioPerformance, RebalanceRecommendation, PortfolioConcentration, NetWorthTrend,
  PlaidAccount,
} from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import ProgressBar from "@/components/ui/ProgressBar";
import OverviewTab from "@/components/portfolio/OverviewTab";
import TargetAllocationEditor from "@/components/portfolio/TargetAllocationEditor";
import SirHenryName from "@/components/ui/SirHenryName";
import {
  PieChart as RePie, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from "recharts";

const SECTOR_COLORS = [
  "#16A34A", "#3b82f6", "#22c55e", "#f59e0b", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f43f5e", "#6366f1",
  "#64748b", "#a855f7",
];

const ASSET_CLASSES = [
  { value: "stock", label: "Stock" },
  { value: "etf", label: "ETF" },
  { value: "mutual_fund", label: "Mutual Fund" },
  { value: "bond", label: "Bond" },
  { value: "reit", label: "REIT" },
  { value: "other", label: "Other" },
];

type TabId = "overview" | "holdings" | "performance" | "allocation" | "risk" | "networth";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "holdings", label: "Holdings" },
  { id: "performance", label: "Performance" },
  { id: "allocation", label: "Allocation" },
  { id: "risk", label: "Risk" },
  { id: "networth", label: "Net Worth" },
];

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<InvestmentHolding[]>([]);
  const [crypto, setCrypto] = useState<CryptoHoldingType[]>([]);
  const [manualInvestments, setManualInvestments] = useState<ManualAsset[]>([]);
  const [plaidAccounts, setPlaidAccounts] = useState<PlaidAccount[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [harvest, setHarvest] = useState<TaxLossHarvestResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [showHarvest, setShowHarvest] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [rebalance, setRebalance] = useState<RebalanceRecommendation[]>([]);
  const [concentration, setConcentration] = useState<PortfolioConcentration | null>(null);
  const [netWorth, setNetWorth] = useState<NetWorthTrend | null>(null);
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [rebalanceLoading, setRebalanceLoading] = useState(false);
  const [concentrationLoading, setConcentrationLoading] = useState(false);
  const [netWorthLoading, setNetWorthLoading] = useState(false);

  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [assetClass, setAssetClass] = useState("stock");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const [h, s, c, ma, pa] = await Promise.all([
        getHoldings(),
        getPortfolioSummary(),
        getCryptoHoldings(),
        getManualAssets()
          .then((a) => a.filter((x) => x.asset_type === "investment" && !x.is_liability))
          .catch(() => [] as ManualAsset[]),
        getPlaidAccounts()
          .then((accts) => accts.filter((a) => a.type === "investment"))
          .catch(() => [] as PlaidAccount[]),
      ]);
      if (signal?.aborted) return;
      setHoldings(Array.isArray(h) ? h : []);
      setSummary(s);
      setCrypto(Array.isArray(c) ? c : []);
      setManualInvestments(ma);
      setPlaidAccounts(pa);
    } catch (e: unknown) {
      if (!signal?.aborted) setError(getErrorMessage(e));
    }
    if (!signal?.aborted) setLoading(false);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (activeTab === "performance" && !performance) {
      setPerformanceLoading(true);
      getPortfolioPerformance()
        .then(setPerformance)
        .catch((e: unknown) => setError(getErrorMessage(e)))
        .finally(() => setPerformanceLoading(false));
    }
  }, [activeTab, performance]);

  useEffect(() => {
    if (activeTab === "allocation") {
      setRebalanceLoading(true);
      getRebalanceRecommendations()
        .then((r) => setRebalance(Array.isArray(r) ? r : []))
        .catch((e: unknown) => setError(getErrorMessage(e)))
        .finally(() => setRebalanceLoading(false));
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "risk") {
      setConcentrationLoading(true);
      getPortfolioConcentration()
        .then(setConcentration)
        .catch((e: unknown) => setError(getErrorMessage(e)))
        .finally(() => setConcentrationLoading(false));
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "networth") {
      setNetWorthLoading(true);
      getNetWorthTrend()
        .then(setNetWorth)
        .catch((e: unknown) => setError(getErrorMessage(e)))
        .finally(() => setNetWorthLoading(false));
    }
  }, [activeTab]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshPrices();
      await load();
      setPerformance(null);
      setRebalance([]);
      setConcentration(null);
      setNetWorth(null);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setRefreshing(false);
  }

  async function handleAdd() {
    if (!ticker || !shares) return;
    setSaving(true);
    try {
      await createHolding({
        ticker: ticker.toUpperCase(),
        shares: parseFloat(shares),
        cost_basis_per_share: costBasis ? parseFloat(costBasis) : undefined,
        purchase_date: purchaseDate || undefined,
        asset_class: assetClass,
      });
      setShowAdd(false);
      setTicker(""); setShares(""); setCostBasis(""); setPurchaseDate("");
      await load();
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setSaving(false);
  }

  async function handleDelete(id: number) {
    await deleteHolding(id);
    load();
  }

  async function loadHarvest() {
    setShowHarvest(!showHarvest);
    if (!harvest) {
      try {
        const h = await getTaxLossHarvest();
        setHarvest(h);
      } catch (e: unknown) { setError(getErrorMessage(e)); }
    }
  }

  const sectorData = summary ? Object.entries(summary.sector_allocation).map(([name, value]) => ({
    name: name.length > 18 ? name.slice(0, 16) + "..." : name, value: Math.round(value),
  })) : [];

  const classData = summary ? Object.entries(summary.asset_class_allocation).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1), value: Math.round(value),
  })) : [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Investment Portfolio"
        subtitle="Track holdings, monitor performance, and optimize taxes"
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "Analyze my portfolio allocation and risk. Am I well-diversified?" } }))}
              className="flex items-center gap-1.5 text-xs text-[#16A34A] hover:text-[#15803D] transition-colors"
            >
              <MessageCircle size={14} />
              Ask <SirHenryName />
            </button>
            <button
              onClick={loadHarvest}
              className="flex items-center gap-2 border border-stone-200 text-stone-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-stone-50"
            >
              <Scissors size={15} /> Tax-Loss Harvest
            </button>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-2 border border-stone-200 text-stone-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-stone-50 disabled:opacity-50"
            >
              <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
              {refreshing ? "Refreshing..." : "Refresh Prices"}
            </button>
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-2 bg-[#16A34A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm"
            >
              <Plus size={15} /> Add Holding
            </button>
          </div>
        }
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600 text-xs">Dismiss</button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="animate-spin text-stone-300" size={28} /></div>
      ) : (
        <>
          {summary && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
                <p className="text-xs text-stone-500 font-medium">Total Portfolio Value</p>
                <p className="text-2xl font-bold text-stone-900 mt-1 font-mono tabular-nums">{formatCurrency(summary.total_value, true)}</p>
                <p className="text-xs text-stone-400 mt-1">
                  {summary.holdings_count > 0 ? `${summary.holdings_count} holdings` : ""}
                  {summary.holdings_count > 0 && (summary.accounts_count ?? 0) > 0 ? " · " : ""}
                  {(summary.accounts_count ?? 0) > 0 ? `${summary.accounts_count} accounts` : ""}
                  {summary.holdings_count === 0 && (summary.accounts_count ?? 0) === 0 ? "No holdings" : ""}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
                {summary.has_cost_basis ? (
                  <>
                    <p className="text-xs text-stone-500 font-medium">Total Gain/Loss</p>
                    <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${summary.total_gain_loss >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {summary.total_gain_loss >= 0 ? "+" : ""}{formatCurrency(summary.total_gain_loss, true)}
                    </p>
                    <p className={`text-xs mt-1 ${summary.total_gain_loss_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {summary.total_gain_loss_pct >= 0 ? "+" : ""}{formatPercent(summary.total_gain_loss_pct)}
                    </p>
                  </>
                ) : summary.weighted_avg_return != null ? (
                  <>
                    <p className="text-xs text-stone-500 font-medium">Avg Annual Return</p>
                    <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${summary.weighted_avg_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {summary.weighted_avg_return >= 0 ? "+" : ""}{formatPercent(summary.weighted_avg_return)}
                    </p>
                    <p className="text-xs text-stone-400 mt-1">Weighted across accounts</p>
                  </>
                ) : (
                  <>
                    <p className="text-xs text-stone-500 font-medium">Total Gain/Loss</p>
                    <p className="text-xl font-semibold text-stone-400 mt-1">Not tracked</p>
                    <p className="text-xs text-stone-400 mt-1">Add cost basis to track</p>
                  </>
                )}
              </div>
              <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
                <p className="text-xs text-stone-500 font-medium">Cost Basis</p>
                {summary.has_cost_basis ? (
                  <p className="text-2xl font-bold text-stone-900 mt-1 font-mono tabular-nums">{formatCurrency(summary.total_cost_basis, true)}</p>
                ) : (
                  <>
                    <p className="text-xl font-semibold text-stone-400 mt-1">Not tracked</p>
                    <p className="text-xs text-stone-400 mt-1">Add purchase prices to accounts</p>
                  </>
                )}
              </div>
              <div className="bg-white rounded-xl border border-stone-100 p-5 shadow-sm">
                <p className="text-xs text-stone-500 font-medium">Allocation</p>
                <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs">
                  {summary.stock_value > 0 && <span className="text-blue-600">Stocks {formatCurrency(summary.stock_value, true)}</span>}
                  {summary.etf_value > 0 && <span className="text-emerald-600">ETFs {formatCurrency(summary.etf_value, true)}</span>}
                  {summary.crypto_value > 0 && <span className="text-amber-600">Crypto {formatCurrency(summary.crypto_value, true)}</span>}
                  {(summary.manual_investment_value ?? 0) > 0 && <span className="text-indigo-600">Accounts {formatCurrency(summary.manual_investment_value ?? 0, true)}</span>}
                </div>
              </div>
            </div>
          )}

          <div className="flex bg-stone-100 rounded-lg p-0.5 mb-6">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-white text-stone-900 shadow-sm"
                    : "text-stone-500 hover:text-stone-700"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "overview" && (
            <OverviewTab
              holdings={holdings}
              summary={summary}
              crypto={crypto}
              manualInvestments={manualInvestments}
              plaidAccounts={plaidAccounts}
            />
          )}

          {activeTab === "holdings" && (
            <>
              {showAdd && (
                <Card padding="lg">
                  <h2 className="font-semibold text-stone-800 mb-4">Add Investment Holding</h2>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs text-stone-500 mb-1.5">Ticker Symbol</label>
                      <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="e.g. AAPL" className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
                    </div>
                    <div>
                      <label className="block text-xs text-stone-500 mb-1.5">Shares</label>
                      <input type="number" value={shares} onChange={(e) => setShares(e.target.value)} placeholder="0" min="0" step="0.01" className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
                    </div>
                    <div>
                      <label className="block text-xs text-stone-500 mb-1.5">Cost Basis / Share</label>
                      <input type="number" value={costBasis} onChange={(e) => setCostBasis(e.target.value)} placeholder="Optional" min="0" step="0.01" className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
                    </div>
                    <div>
                      <label className="block text-xs text-stone-500 mb-1.5">Purchase Date</label>
                      <input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]" />
                    </div>
                    <div>
                      <label className="block text-xs text-stone-500 mb-1.5">Asset Class</label>
                      <select value={assetClass} onChange={(e) => setAssetClass(e.target.value)} className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A] bg-white">
                        {ASSET_CLASSES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-4">
                    <button onClick={handleAdd} disabled={saving || !ticker || !shares} className="flex items-center gap-2 bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D] disabled:opacity-60 shadow-sm">
                      {saving ? <Loader2 size={13} className="animate-spin" /> : null} Add Holding
                    </button>
                    <button onClick={() => setShowAdd(false)} className="text-sm text-stone-500 hover:text-stone-700 px-3">Cancel</button>
                  </div>
                </Card>
              )}

              {showHarvest && harvest && (
                <Card padding="lg" className="border-amber-200 bg-amber-50/30">
                  <div className="flex items-center gap-2 mb-4">
                    <Scissors size={18} className="text-amber-600" />
                    <h2 className="font-semibold text-stone-800">Tax-Loss Harvesting Opportunities</h2>
                  </div>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                    <div>
                      <p className="text-xs text-stone-500">Harvestable Losses</p>
                      <p className="text-lg font-bold text-red-600 font-mono tabular-nums">{formatCurrency(harvest.harvestable_losses)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-stone-500">Estimated Tax Savings</p>
                      <p className="text-lg font-bold text-green-600 font-mono tabular-nums">{formatCurrency(harvest.estimated_tax_savings)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-stone-500">Unrealized Gains</p>
                      <p className="text-lg font-bold text-green-600 font-mono tabular-nums">{formatCurrency(harvest.total_unrealized_gains)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-stone-500">Net Unrealized</p>
                      <p className={`text-lg font-bold font-mono tabular-nums ${harvest.net_unrealized >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {formatCurrency(harvest.net_unrealized)}
                      </p>
                    </div>
                  </div>
                  {harvest.candidates.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-stone-200 text-xs text-stone-500">
                            <th className="text-left py-2">Ticker</th>
                            <th className="text-right py-2">Shares</th>
                            <th className="text-right py-2">Cost Basis</th>
                            <th className="text-right py-2">Current Value</th>
                            <th className="text-right py-2">Loss</th>
                            <th className="text-right py-2">Tax Savings</th>
                            <th className="text-center py-2">Wash Sale</th>
                          </tr>
                        </thead>
                        <tbody>
                          {harvest.candidates.map((c, i) => (
                            <tr key={i} className="border-b border-stone-100">
                              <td className="py-2 font-medium">{c.ticker}</td>
                              <td className="text-right py-2 tabular-nums">{c.shares.toFixed(2)}</td>
                              <td className="text-right py-2 tabular-nums">{formatCurrency(c.cost_basis)}</td>
                              <td className="text-right py-2 tabular-nums">{formatCurrency(c.current_value)}</td>
                              <td className="text-right py-2 tabular-nums text-red-600">{formatCurrency(c.unrealized_loss)}</td>
                              <td className="text-right py-2 tabular-nums text-green-600">{formatCurrency(c.estimated_tax_savings)}</td>
                              <td className="text-center py-2">
                                {c.wash_sale_risk ? <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">Risk</span> : <span className="text-xs text-green-600">Clear</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Card>
              )}

              {holdings.length === 0 && crypto.length === 0 && manualInvestments.length === 0 && plaidAccounts.length === 0 && !showAdd ? (
                <EmptyState
                  icon={<TrendingUp size={40} />}
                  title="Build your investment portfolio"
                  description="Track your stocks, ETFs, crypto, and retirement accounts in one place. Get tax-loss harvesting alerts, rebalancing advice, and concentration risk analysis."
                  henryTip="Most HENRYs I work with are over-concentrated in their employer's stock. Getting your full portfolio picture is the first step to smarter diversification."
                  askHenryPrompt="What should I know about building a diversified portfolio as a high earner?"
                  action={
                    <button onClick={() => setShowAdd(true)} className="bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm">
                      Add First Holding
                    </button>
                  }
                  templates={[
                    { icon: <TrendingUp size={16} className="text-blue-600" />, label: "Add stock or ETF", description: "Track individual stocks, index funds, or ETFs", onClick: () => setShowAdd(true) },
                    { icon: <TrendingUp size={16} className="text-purple-600" />, label: "I have equity comp", description: "RSUs, ISOs, or ESPPs from your employer", onClick: () => { window.location.href = "/equity-comp"; } },
                    { icon: <TrendingUp size={16} className="text-emerald-600" />, label: "Connect via Plaid", description: "Auto-sync your brokerage accounts", onClick: () => { window.location.href = "/accounts"; } },
                  ]}
                />
              ) : (
                <Card padding="none">
                  <div className="px-5 py-4 border-b border-stone-100">
                    <h3 className="font-semibold text-stone-800">Holdings</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-stone-50 text-xs text-stone-500 uppercase tracking-wider">
                          <th className="text-left px-5 py-3">Ticker</th>
                          <th className="text-left px-3 py-3">Name</th>
                          <th className="text-right px-3 py-3">Shares</th>
                          <th className="text-right px-3 py-3">Price</th>
                          <th className="text-right px-3 py-3">Value</th>
                          <th className="text-right px-3 py-3">Cost Basis</th>
                          <th className="text-right px-3 py-3">Gain/Loss</th>
                          <th className="text-right px-3 py-3">%</th>
                          <th className="text-left px-3 py-3">Sector</th>
                          <th className="px-5 py-3"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {holdings.map((h) => (
                          <tr key={h.id} className="border-b border-stone-50 hover:bg-stone-50/50 transition-colors">
                            <td className="px-5 py-3 font-bold text-stone-900">{h.ticker}</td>
                            <td className="px-3 py-3 text-stone-600 max-w-[160px] truncate">{h.name || "-"}</td>
                            <td className="px-3 py-3 text-right tabular-nums">{h.shares.toFixed(2)}</td>
                            <td className="px-3 py-3 text-right tabular-nums">{h.current_price ? formatCurrency(h.current_price) : "-"}</td>
                            <td className="px-3 py-3 text-right tabular-nums font-medium">{h.current_value ? formatCurrency(h.current_value) : "-"}</td>
                            <td className="px-3 py-3 text-right tabular-nums text-stone-500">{h.total_cost_basis ? formatCurrency(h.total_cost_basis) : "-"}</td>
                            <td className={`px-3 py-3 text-right tabular-nums font-medium ${(h.unrealized_gain_loss ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                              {h.unrealized_gain_loss != null ? formatCurrency(h.unrealized_gain_loss) : "-"}
                            </td>
                            <td className={`px-3 py-3 text-right tabular-nums text-xs ${(h.unrealized_gain_loss_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                              {h.unrealized_gain_loss_pct != null ? `${h.unrealized_gain_loss_pct >= 0 ? "+" : ""}${h.unrealized_gain_loss_pct.toFixed(1)}%` : "-"}
                            </td>
                            <td className="px-3 py-3 text-xs text-stone-500">{h.sector || "-"}</td>
                            <td className="px-5 py-3">
                              <button onClick={() => handleDelete(h.id)} className="text-xs text-stone-400 hover:text-red-600">Remove</button>
                            </td>
                          </tr>
                        ))}
                        {crypto.map((c) => (
                          <tr key={`crypto-${c.id}`} className="border-b border-stone-50 hover:bg-stone-50/50 transition-colors bg-amber-50/20">
                            <td className="px-5 py-3 font-bold text-amber-700">{c.symbol}</td>
                            <td className="px-3 py-3 text-stone-600">{c.name || c.coin_id}</td>
                            <td className="px-3 py-3 text-right tabular-nums">{c.quantity.toFixed(4)}</td>
                            <td className="px-3 py-3 text-right tabular-nums">{c.current_price ? formatCurrency(c.current_price) : "-"}</td>
                            <td className="px-3 py-3 text-right tabular-nums font-medium">{c.current_value ? formatCurrency(c.current_value) : "-"}</td>
                            <td className="px-3 py-3 text-right tabular-nums text-stone-500">{c.total_cost_basis ? formatCurrency(c.total_cost_basis) : "-"}</td>
                            <td className={`px-3 py-3 text-right tabular-nums font-medium ${(c.unrealized_gain_loss ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                              {c.unrealized_gain_loss != null ? formatCurrency(c.unrealized_gain_loss) : "-"}
                            </td>
                            <td className={`px-3 py-3 text-right tabular-nums text-xs ${(c.price_change_24h_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                              {c.price_change_24h_pct != null ? `${c.price_change_24h_pct.toFixed(1)}% 24h` : "-"}
                            </td>
                            <td className="px-3 py-3 text-xs text-amber-600">Crypto</td>
                            <td className="px-5 py-3"></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}

              {/* Manual Investment Accounts */}
              {manualInvestments.length > 0 && (
                <Card padding="lg">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-stone-800">Investment Accounts</h3>
                    <span className="text-xs text-stone-400">
                      {manualInvestments.length} accounts · {formatCurrency(manualInvestments.reduce((s, a) => s + (a.current_value ?? 0), 0), true)}
                    </span>
                  </div>
                  <div className="space-y-3">
                    {manualInvestments.sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0)).map((asset, i) => {
                      const totalManual = manualInvestments.reduce((s, a) => s + (a.current_value ?? 0), 0);
                      const weight = totalManual > 0 ? ((asset.current_value ?? 0) / totalManual) * 100 : 0;
                      return (
                        <div key={asset.id}>
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-3">
                              <div
                                className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white shrink-0"
                                style={{ backgroundColor: SECTOR_COLORS[i % SECTOR_COLORS.length] }}
                              >
                                {(asset.account_subtype || "INV").slice(0, 3).toUpperCase()}
                              </div>
                              <div>
                                <p className="text-sm font-medium text-stone-800">{asset.name}</p>
                                <p className="text-xs text-stone-400">
                                  {[asset.custodian || asset.institution, asset.account_subtype?.replace(/_/g, " ")].filter(Boolean).join(" · ") || "Investment"}
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-semibold tabular-nums">{formatCurrency(asset.current_value ?? 0)}</p>
                              {asset.annual_return_pct != null && (
                                <p className={`text-xs ${asset.annual_return_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                                  {asset.annual_return_pct >= 0 ? "+" : ""}{asset.annual_return_pct.toFixed(1)}% annual return
                                </p>
                              )}
                            </div>
                          </div>
                          <ProgressBar value={weight} color={SECTOR_COLORS[i % SECTOR_COLORS.length]} size="xs" />
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-stone-400 mt-4 pt-3 border-t border-stone-100">
                    Manage investment accounts on the <a href="/accounts" className="text-[#16A34A] hover:underline">Accounts page</a>.
                    Add individual stock/ETF positions above to track detailed performance.
                  </p>
                </Card>
              )}
            </>
          )}

          {activeTab === "performance" && (
            performanceLoading ? (
              <div className="flex justify-center py-16"><Loader2 className="animate-spin text-stone-300" size={28} /></div>
            ) : (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Card padding="lg">
                  <p className="text-xs text-stone-500 font-medium">Time-Weighted Return</p>
                  <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${(performance?.time_weighted_return ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {performance ? `${performance.time_weighted_return >= 0 ? "+" : ""}${formatPercent(performance.time_weighted_return)}` : "-"}
                  </p>
                </Card>
                <Card padding="lg">
                  {summary?.has_cost_basis ? (
                    <>
                      <p className="text-xs text-stone-500 font-medium">Total Return</p>
                      <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${(summary?.total_gain_loss_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {summary ? `${summary.total_gain_loss_pct >= 0 ? "+" : ""}${formatPercent(summary.total_gain_loss_pct)}` : "-"}
                      </p>
                    </>
                  ) : summary?.weighted_avg_return != null ? (
                    <>
                      <p className="text-xs text-stone-500 font-medium">Avg Annual Return</p>
                      <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${summary.weighted_avg_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {summary.weighted_avg_return >= 0 ? "+" : ""}{formatPercent(summary.weighted_avg_return)}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-xs text-stone-500 font-medium">Total Return</p>
                      <p className="text-xl font-semibold text-stone-400 mt-1">-</p>
                    </>
                  )}
                </Card>
                <Card padding="lg">
                  <p className="text-xs text-stone-500 font-medium">Total Value</p>
                  <p className="text-2xl font-bold text-stone-900 mt-1 font-mono tabular-nums">{summary ? formatCurrency(summary.total_value, true) : "-"}</p>
                </Card>
                <Card padding="lg">
                  <p className="text-xs text-stone-500 font-medium">Cost Basis</p>
                  {summary?.has_cost_basis ? (
                    <p className="text-2xl font-bold text-stone-900 mt-1 font-mono tabular-nums">{formatCurrency(summary.total_cost_basis, true)}</p>
                  ) : (
                    <p className="text-xl font-semibold text-stone-400 mt-1">Not tracked</p>
                  )}
                </Card>
              </div>
            )
          )}

          {activeTab === "allocation" && (
            <>
              {summary && (sectorData.length > 0 || classData.length > 0) && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
                  {sectorData.length > 0 && (
                    <Card padding="lg">
                      <h3 className="text-sm font-semibold text-stone-800 mb-4">Sector Allocation</h3>
                      <ResponsiveContainer width="100%" height={220}>
                        <RePie>
                          <Pie data={sectorData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false} fontSize={10}>
                            {sectorData.map((_, i) => <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />)}
                          </Pie>
                          <Tooltip formatter={(v) => formatCurrency(Number(v))} />
                        </RePie>
                      </ResponsiveContainer>
                    </Card>
                  )}
                  {classData.length > 0 && (
                    <Card padding="lg">
                      <h3 className="text-sm font-semibold text-stone-800 mb-4">Asset Class Breakdown</h3>
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={classData} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f1f0" />
                          <XAxis type="number" tickFormatter={(v) => formatCurrency(v, true)} fontSize={11} />
                          <YAxis type="category" dataKey="name" width={80} fontSize={11} />
                          <Tooltip formatter={(v) => formatCurrency(Number(v))} />
                          <Bar dataKey="value" fill="#16A34A" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </Card>
                  )}
                </div>
              )}
              <Card padding="lg">
                <h3 className="text-sm font-semibold text-stone-800 mb-4">Rebalance Recommendations</h3>
                {rebalanceLoading ? (
                  <div className="flex justify-center py-12"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
                ) : rebalance.length === 0 ? (
                  <p className="text-sm text-stone-500 py-4">No rebalance recommendations.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-stone-200 text-xs text-stone-500">
                          <th className="text-left py-2">Ticker</th>
                          <th className="text-right py-2">Current %</th>
                          <th className="text-right py-2">Target %</th>
                          <th className="text-left py-2">Action</th>
                          <th className="text-right py-2">Amount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rebalance.map((r, i) => (
                          <tr key={i} className="border-b border-stone-100">
                            <td className="py-2 font-medium">{r.ticker}</td>
                            <td className="text-right py-2 tabular-nums">{formatPercent(r.current_pct)}</td>
                            <td className="text-right py-2 tabular-nums">{formatPercent(r.target_pct)}</td>
                            <td className="py-2">
                              <span className={`text-xs px-2 py-0.5 rounded ${
                                r.action === "buy" ? "bg-green-100 text-green-700" :
                                r.action === "sell" ? "bg-red-100 text-red-700" : "bg-stone-100 text-stone-600"
                              }`}>
                                {r.action}
                              </span>
                            </td>
                            <td className="text-right py-2 tabular-nums">{formatCurrency(r.amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
              <TargetAllocationEditor onSaved={() => {
                setRebalanceLoading(true);
                getRebalanceRecommendations()
                  .then((r) => setRebalance(Array.isArray(r) ? r : []))
                  .catch((e: unknown) => setError(getErrorMessage(e)))
                  .finally(() => setRebalanceLoading(false));
              }} />
            </>
          )}

          {activeTab === "risk" && (
            concentrationLoading ? (
              <div className="flex justify-center py-16"><Loader2 className="animate-spin text-stone-300" size={28} /></div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card padding="lg">
                    <p className="text-xs text-stone-500 font-medium">Top Holding %</p>
                    <p className="text-2xl font-bold text-stone-900 mt-1 font-mono tabular-nums">
                      {concentration?.top_holding_pct != null ? formatPercent(concentration.top_holding_pct) : "-"}
                    </p>
                  </Card>
                  <Card padding="lg">
                    <p className="text-xs text-stone-500 font-medium">Top 3 Holdings %</p>
                    <p className="text-2xl font-bold text-stone-900 mt-1 font-mono tabular-nums">
                      {concentration?.top_3_pct != null ? formatPercent(concentration.top_3_pct) : "-"}
                    </p>
                  </Card>
                  <Card padding="lg">
                    <p className="text-xs text-stone-500 font-medium">Single Stock Risk</p>
                    <p className="text-lg font-bold text-stone-900 mt-1 capitalize">
                      {concentration?.single_stock_risk_level ?? "-"}
                    </p>
                  </Card>
                </div>
                {concentration?.sector_concentration && Object.keys(concentration.sector_concentration).length > 0 && (
                  <Card padding="lg">
                    <h3 className="text-sm font-semibold text-stone-800 mb-4">Sector Concentration</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-stone-200 text-xs text-stone-500">
                            <th className="text-left py-2">Sector</th>
                            <th className="text-right py-2">Allocation %</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(concentration.sector_concentration).map(([sector, pct]) => (
                            <tr key={sector} className="border-b border-stone-100">
                              <td className="py-2">{sector}</td>
                              <td className="text-right py-2 tabular-nums">{formatPercent(pct)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                )}
              </div>
            )
          )}

          {activeTab === "networth" && (
            netWorthLoading ? (
              <div className="flex justify-center py-16"><Loader2 className="animate-spin text-stone-300" size={28} /></div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <Card padding="lg">
                    <p className="text-xs text-stone-500 font-medium">Current Net Worth</p>
                    <p className="text-2xl font-bold text-stone-900 mt-1 font-mono tabular-nums">
                      {netWorth ? formatCurrency(netWorth.current_net_worth, true) : "-"}
                    </p>
                  </Card>
                  <Card padding="lg">
                    <p className="text-xs text-stone-500 font-medium">Growth Rate</p>
                    <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${(netWorth?.growth_rate ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {netWorth ? `${netWorth.growth_rate >= 0 ? "+" : ""}${formatPercent(netWorth.growth_rate)}` : "-"}
                    </p>
                  </Card>
                </div>
                {netWorth && netWorth.monthly_series.length > 0 && (
                  <Card padding="lg">
                    <h3 className="text-sm font-semibold text-stone-800 mb-4">Monthly Net Worth</h3>
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart data={netWorth.monthly_series.map((d) => ({ ...d, value: d.net_worth }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f1f0" />
                        <XAxis dataKey="date" tickFormatter={(v) => new Date(v).toLocaleDateString("en-US", { month: "short", year: "2-digit" })} fontSize={11} />
                        <YAxis tickFormatter={(v) => formatCurrency(v, true)} fontSize={11} />
                        <Tooltip formatter={(v) => formatCurrency(Number(v))} labelFormatter={(v) => new Date(v).toLocaleDateString("en-US")} />
                        <Line type="monotone" dataKey="value" stroke="#16A34A" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </Card>
                )}
              </div>
            )
          )}
        </>
      )}
    </div>
  );
}
