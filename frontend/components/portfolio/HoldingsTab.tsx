"use client";
import { useState } from "react";
import { Plus, Loader2, TrendingUp, Scissors } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { createHolding, deleteHolding, getTaxLossHarvest } from "@/lib/api";
import type {
  InvestmentHolding, PortfolioSummary, TaxLossHarvestResult, CryptoHoldingType,
  PlaidAccount,
} from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import ProgressBar from "@/components/ui/ProgressBar";
import { SECTOR_COLORS, ASSET_CLASSES } from "./constants";

interface HoldingsTabProps {
  holdings: InvestmentHolding[];
  crypto: CryptoHoldingType[];
  manualInvestments: ManualAsset[];
  plaidAccounts: PlaidAccount[];
  summary: PortfolioSummary | null;
  onReload: () => void;
  onError: (msg: string) => void;
}

export default function HoldingsTab({
  holdings, crypto, manualInvestments, plaidAccounts, summary,
  onReload, onError,
}: HoldingsTabProps) {
  const [showAdd, setShowAdd] = useState(false);
  const [showHarvest, setShowHarvest] = useState(false);
  const [harvest, setHarvest] = useState<TaxLossHarvestResult | null>(null);
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [assetClass, setAssetClass] = useState("stock");
  const [saving, setSaving] = useState(false);

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
      onReload();
    } catch (e: unknown) { onError(getErrorMessage(e)); }
    setSaving(false);
  }

  async function handleDelete(id: number) {
    await deleteHolding(id);
    onReload();
  }

  async function loadHarvest() {
    setShowHarvest(!showHarvest);
    if (!harvest) {
      try { setHarvest(await getTaxLossHarvest()); }
      catch (e: unknown) { onError(getErrorMessage(e)); }
    }
  }

  const isEmpty = holdings.length === 0 && crypto.length === 0 && manualInvestments.length === 0 && plaidAccounts.length === 0;

  return (
    <div className="space-y-6">
      <div className="flex gap-2 justify-end">
        <button onClick={loadHarvest} className="flex items-center gap-2 border border-border text-text-secondary px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface">
          <Scissors size={15} /> Tax-Loss Harvest
        </button>
        <button onClick={() => setShowAdd(true)} className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm">
          <Plus size={15} /> Add Holding
        </button>
      </div>

      {showAdd && (
        <Card padding="lg">
          <h2 className="font-semibold text-text-primary mb-4">Add Investment Holding</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Ticker Symbol</label>
              <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="e.g. AAPL" className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Shares</label>
              <input type="number" value={shares} onChange={(e) => setShares(e.target.value)} placeholder="0" min="0" step="0.01" className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Cost Basis / Share</label>
              <input type="number" value={costBasis} onChange={(e) => setCostBasis(e.target.value)} placeholder="Optional" min="0" step="0.01" className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Purchase Date</label>
              <input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1.5">Asset Class</label>
              <select value={assetClass} onChange={(e) => setAssetClass(e.target.value)} className="w-full text-sm border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-card">
                {ASSET_CLASSES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button onClick={handleAdd} disabled={saving || !ticker || !shares} className="flex items-center gap-2 bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60 shadow-sm">
              {saving ? <Loader2 size={13} className="animate-spin" /> : null} Add Holding
            </button>
            <button onClick={() => setShowAdd(false)} className="text-sm text-text-secondary hover:text-text-primary px-3">Cancel</button>
          </div>
        </Card>
      )}

      {showHarvest && harvest && (
        <Card padding="lg" className="border-amber-200 bg-amber-50/30">
          <div className="flex items-center gap-2 mb-4">
            <Scissors size={18} className="text-amber-600" />
            <h2 className="font-semibold text-text-primary">Tax-Loss Harvesting Opportunities</h2>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-xs text-text-secondary">Harvestable Losses</p>
              <p className="text-lg font-bold text-red-600 font-mono tabular-nums">{formatCurrency(harvest.harvestable_losses)}</p>
            </div>
            <div>
              <p className="text-xs text-text-secondary">Estimated Tax Savings</p>
              <p className="text-lg font-bold text-green-600 font-mono tabular-nums">{formatCurrency(harvest.estimated_tax_savings)}</p>
            </div>
            <div>
              <p className="text-xs text-text-secondary">Unrealized Gains</p>
              <p className="text-lg font-bold text-green-600 font-mono tabular-nums">{formatCurrency(harvest.total_unrealized_gains)}</p>
            </div>
            <div>
              <p className="text-xs text-text-secondary">Net Unrealized</p>
              <p className={`text-lg font-bold font-mono tabular-nums ${harvest.net_unrealized >= 0 ? "text-green-600" : "text-red-600"}`}>
                {formatCurrency(harvest.net_unrealized)}
              </p>
            </div>
          </div>
          {harvest.candidates.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-text-secondary">
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
                    <tr key={i} className="border-b border-card-border">
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

      {isEmpty && !showAdd ? (
        <EmptyState
          icon={<TrendingUp size={40} />}
          title="Build your investment portfolio"
          description="Track your stocks, ETFs, crypto, and retirement accounts in one place. Get tax-loss harvesting alerts, rebalancing advice, and concentration risk analysis."
          henryTip="Most HENRYs I work with are over-concentrated in their employer's stock. Getting your full portfolio picture is the first step to smarter diversification."
          askHenryPrompt="What should I know about building a diversified portfolio as a high earner?"
          action={
            <button onClick={() => setShowAdd(true)} className="bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm">
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
          <div className="px-5 py-4 border-b border-card-border">
            <h3 className="font-semibold text-text-primary">Holdings</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface text-xs text-text-secondary uppercase tracking-wider">
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
                  <tr key={h.id} className="border-b border-border-light hover:bg-surface/50 transition-colors">
                    <td className="px-5 py-3 font-bold text-text-primary">{h.ticker}</td>
                    <td className="px-3 py-3 text-text-secondary max-w-[160px] truncate">{h.name || "-"}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{h.shares.toFixed(2)}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{h.current_price ? formatCurrency(h.current_price) : "-"}</td>
                    <td className="px-3 py-3 text-right tabular-nums font-medium">{h.current_value ? formatCurrency(h.current_value) : "-"}</td>
                    <td className="px-3 py-3 text-right tabular-nums text-text-secondary">{h.total_cost_basis ? formatCurrency(h.total_cost_basis) : "-"}</td>
                    <td className={`px-3 py-3 text-right tabular-nums font-medium ${(h.unrealized_gain_loss ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {h.unrealized_gain_loss != null ? formatCurrency(h.unrealized_gain_loss) : "-"}
                    </td>
                    <td className={`px-3 py-3 text-right tabular-nums text-xs ${(h.unrealized_gain_loss_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {h.unrealized_gain_loss_pct != null ? `${h.unrealized_gain_loss_pct >= 0 ? "+" : ""}${h.unrealized_gain_loss_pct.toFixed(1)}%` : "-"}
                    </td>
                    <td className="px-3 py-3 text-xs text-text-secondary">{h.sector || "-"}</td>
                    <td className="px-5 py-3">
                      <button onClick={() => handleDelete(h.id)} className="text-xs text-text-muted hover:text-red-600">Remove</button>
                    </td>
                  </tr>
                ))}
                {crypto.map((c) => (
                  <tr key={`crypto-${c.id}`} className="border-b border-border-light hover:bg-surface/50 transition-colors bg-amber-50/20">
                    <td className="px-5 py-3 font-bold text-amber-700">{c.symbol}</td>
                    <td className="px-3 py-3 text-text-secondary">{c.name || c.coin_id}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{c.quantity.toFixed(4)}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{c.current_price ? formatCurrency(c.current_price) : "-"}</td>
                    <td className="px-3 py-3 text-right tabular-nums font-medium">{c.current_value ? formatCurrency(c.current_value) : "-"}</td>
                    <td className="px-3 py-3 text-right tabular-nums text-text-secondary">{c.total_cost_basis ? formatCurrency(c.total_cost_basis) : "-"}</td>
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

      {manualInvestments.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-text-primary">Investment Accounts</h3>
            <span className="text-xs text-text-muted">
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
                        <p className="text-sm font-medium text-text-primary">{asset.name}</p>
                        <p className="text-xs text-text-muted">
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
          <p className="text-xs text-text-muted mt-4 pt-3 border-t border-card-border">
            Manage investment accounts on the <a href="/accounts" className="text-accent hover:underline">Accounts page</a>.
            Add individual stock/ETF positions above to track detailed performance.
          </p>
        </Card>
      )}
    </div>
  );
}
