"use client";
import { useCallback, useEffect, useState } from "react";
import {
  RefreshCw, Loader2, AlertCircle, MessageCircle,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  getHoldings, refreshPrices,
  getPortfolioSummary, getCryptoHoldings,
  getPortfolioPerformance, getRebalanceRecommendations, getPortfolioConcentration,
  getNetWorthTrend, getPlaidAccounts,
} from "@/lib/api";
import { getManualAssets } from "@/lib/api-assets";
import type {
  InvestmentHolding, PortfolioSummary, CryptoHoldingType,
  PortfolioPerformance, RebalanceRecommendation, PortfolioConcentration, NetWorthTrend,
  PlaidAccount,
} from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";
import { getErrorMessage } from "@/lib/errors";
import PageHeader from "@/components/ui/PageHeader";
import TabBar from "@/components/ui/TabBar";
import SirHenryName from "@/components/ui/SirHenryName";
import OverviewTab from "@/components/portfolio/OverviewTab";
import HoldingsTab from "@/components/portfolio/HoldingsTab";
import PerformanceTab from "@/components/portfolio/PerformanceTab";
import AllocationTab from "@/components/portfolio/AllocationTab";
import RiskTab from "@/components/portfolio/RiskTab";
import NetWorthTab from "@/components/portfolio/NetWorthTab";
import { TABS } from "@/components/portfolio/constants";
import { useTabState } from "@/hooks/useTabState";

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<InvestmentHolding[]>([]);
  const [crypto, setCrypto] = useState<CryptoHoldingType[]>([]);
  const [manualInvestments, setManualInvestments] = useState<ManualAsset[]>([]);
  const [plaidAccounts, setPlaidAccounts] = useState<PlaidAccount[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useTabState(TABS, "overview");

  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [rebalance, setRebalance] = useState<RebalanceRecommendation[]>([]);
  const [concentration, setConcentration] = useState<PortfolioConcentration | null>(null);
  const [netWorth, setNetWorth] = useState<NetWorthTrend | null>(null);
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [rebalanceLoading, setRebalanceLoading] = useState(false);
  const [concentrationLoading, setConcentrationLoading] = useState(false);
  const [netWorthLoading, setNetWorthLoading] = useState(false);

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

  // Lazy-load tab-specific data
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

  function handleRebalanceRefresh() {
    setRebalanceLoading(true);
    getRebalanceRecommendations()
      .then((r) => setRebalance(Array.isArray(r) ? r : []))
      .catch((e: unknown) => setError(getErrorMessage(e)))
      .finally(() => setRebalanceLoading(false));
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Investment Portfolio"
        subtitle="Track holdings, monitor performance, and optimize taxes"
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "Analyze my portfolio allocation and risk. Am I well-diversified?" } }))}
              className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
            >
              <MessageCircle size={14} />
              Ask <SirHenryName />
            </button>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-2 border border-border text-text-secondary px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface disabled:opacity-50"
            >
              <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
              {refreshing ? "Refreshing..." : "Refresh Prices"}
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
        <div className="flex justify-center py-16"><Loader2 className="animate-spin text-text-muted" size={28} /></div>
      ) : (
        <>
          {summary && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
                <p className="text-xs text-text-secondary font-medium">Total Portfolio Value</p>
                <p className="text-2xl font-bold text-text-primary mt-1 font-mono tabular-nums">{formatCurrency(summary.total_value, true)}</p>
                <p className="text-xs text-text-muted mt-1">
                  {summary.holdings_count > 0 ? `${summary.holdings_count} holdings` : ""}
                  {summary.holdings_count > 0 && (summary.accounts_count ?? 0) > 0 ? " · " : ""}
                  {(summary.accounts_count ?? 0) > 0 ? `${summary.accounts_count} accounts` : ""}
                  {summary.holdings_count === 0 && (summary.accounts_count ?? 0) === 0 ? "No holdings" : ""}
                </p>
              </div>
              <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
                {summary.has_cost_basis ? (
                  <>
                    <p className="text-xs text-text-secondary font-medium">Total Gain/Loss</p>
                    <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${summary.total_gain_loss >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {summary.total_gain_loss >= 0 ? "+" : ""}{formatCurrency(summary.total_gain_loss, true)}
                    </p>
                    <p className={`text-xs mt-1 ${summary.total_gain_loss_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {summary.total_gain_loss_pct >= 0 ? "+" : ""}{formatPercent(summary.total_gain_loss_pct)}
                    </p>
                  </>
                ) : summary.weighted_avg_return != null ? (
                  <>
                    <p className="text-xs text-text-secondary font-medium">Avg Annual Return</p>
                    <p className={`text-2xl font-bold mt-1 font-mono tabular-nums ${summary.weighted_avg_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {summary.weighted_avg_return >= 0 ? "+" : ""}{formatPercent(summary.weighted_avg_return)}
                    </p>
                    <p className="text-xs text-text-muted mt-1">Weighted across accounts</p>
                  </>
                ) : (
                  <>
                    <p className="text-xs text-text-secondary font-medium">Total Gain/Loss</p>
                    <p className="text-xl font-semibold text-text-muted mt-1">Not tracked</p>
                    <p className="text-xs text-text-muted mt-1">Add cost basis to track</p>
                  </>
                )}
              </div>
              <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
                <p className="text-xs text-text-secondary font-medium">Cost Basis</p>
                {summary.has_cost_basis ? (
                  <p className="text-2xl font-bold text-text-primary mt-1 font-mono tabular-nums">{formatCurrency(summary.total_cost_basis, true)}</p>
                ) : (
                  <>
                    <p className="text-xl font-semibold text-text-muted mt-1">Not tracked</p>
                    <p className="text-xs text-text-muted mt-1">Add purchase prices to accounts</p>
                  </>
                )}
              </div>
              <div className="bg-card rounded-xl border border-card-border p-5 shadow-sm">
                <p className="text-xs text-text-secondary font-medium">Allocation</p>
                <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs">
                  {summary.stock_value > 0 && <span className="text-blue-600">Stocks {formatCurrency(summary.stock_value, true)}</span>}
                  {summary.etf_value > 0 && <span className="text-emerald-600">ETFs {formatCurrency(summary.etf_value, true)}</span>}
                  {summary.crypto_value > 0 && <span className="text-amber-600">Crypto {formatCurrency(summary.crypto_value, true)}</span>}
                  {(summary.manual_investment_value ?? 0) > 0 && <span className="text-indigo-600">Accounts {formatCurrency(summary.manual_investment_value ?? 0, true)}</span>}
                </div>
              </div>
            </div>
          )}

          <TabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} variant="pill" />

          {activeTab === "overview" && (
            <OverviewTab holdings={holdings} summary={summary} crypto={crypto} manualInvestments={manualInvestments} plaidAccounts={plaidAccounts} />
          )}
          {activeTab === "holdings" && (
            <HoldingsTab holdings={holdings} crypto={crypto} manualInvestments={manualInvestments} plaidAccounts={plaidAccounts} summary={summary} onReload={() => load()} onError={setError} />
          )}
          {activeTab === "performance" && (
            <PerformanceTab performance={performance} summary={summary} loading={performanceLoading} />
          )}
          {activeTab === "allocation" && (
            <AllocationTab summary={summary} rebalance={rebalance} rebalanceLoading={rebalanceLoading} onRebalanceRefresh={handleRebalanceRefresh} onError={setError} />
          )}
          {activeTab === "risk" && (
            <RiskTab concentration={concentration} loading={concentrationLoading} />
          )}
          {activeTab === "networth" && (
            <NetWorthTab netWorth={netWorth} loading={netWorthLoading} />
          )}
        </>
      )}
    </div>
  );
}
