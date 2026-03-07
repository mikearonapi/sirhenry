"use client";
import { formatCurrency } from "@/lib/utils";
import type { InvestmentHolding, PortfolioSummary, CryptoHoldingType, PlaidAccount } from "@/types/api";
import type { ManualAsset } from "@/types/portfolio";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import Badge from "@/components/ui/Badge";

const COLORS = ["#16A34A", "#3b82f6", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#14b8a6", "#f97316"];

interface OverviewTabProps {
  holdings: InvestmentHolding[];
  summary: PortfolioSummary | null;
  crypto: CryptoHoldingType[];
  manualInvestments: ManualAsset[];
  plaidAccounts: PlaidAccount[];
}

export default function OverviewTab({ holdings, summary, crypto, manualInvestments, plaidAccounts }: OverviewTabProps) {
  const totalPlaidValue = plaidAccounts.reduce((s, a) => s + (a.current_balance ?? 0), 0);
  const totalManualValue = manualInvestments.reduce((s, a) => s + (a.current_value ?? 0), 0);
  const totalCryptoValue = crypto.reduce((s, c) => s + (c.current_value ?? 0), 0);
  const grandTotal = summary?.total_value ?? (
    holdings.reduce((s, h) => s + (h.current_value ?? 0), 0) + totalCryptoValue + totalManualValue + totalPlaidValue
  );
  const hasCostBasis = summary?.has_cost_basis ?? false;
  const totalGainLoss = summary?.total_gain_loss ?? 0;
  const totalGainLossPct = summary?.total_gain_loss_pct ?? 0;
  const weightedAvgReturn = summary?.weighted_avg_return ?? null;

  return (
    <div className="space-y-5">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card padding="lg">
          <p className="text-xs text-text-muted font-medium mb-1">Total Portfolio</p>
          <p className="text-2xl font-bold tracking-tight text-text-primary font-mono tabular-nums">{formatCurrency(grandTotal)}</p>
        </Card>
        <Card padding="lg">
          {hasCostBasis ? (
            <>
              <p className="text-xs text-text-muted font-medium mb-1">Total Gain/Loss</p>
              <p className={`text-2xl font-bold tracking-tight font-mono tabular-nums ${totalGainLoss >= 0 ? "text-green-600" : "text-red-600"}`}>
                {totalGainLoss >= 0 ? "+" : ""}{formatCurrency(totalGainLoss)}
              </p>
              {totalGainLossPct !== 0 && (
                <p className={`text-xs mt-0.5 ${totalGainLossPct >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {totalGainLossPct >= 0 ? "+" : ""}{totalGainLossPct.toFixed(2)}%
                </p>
              )}
            </>
          ) : weightedAvgReturn != null ? (
            <>
              <p className="text-xs text-text-muted font-medium mb-1">Avg Annual Return</p>
              <p className={`text-2xl font-bold tracking-tight font-mono tabular-nums ${weightedAvgReturn >= 0 ? "text-green-600" : "text-red-600"}`}>
                {weightedAvgReturn >= 0 ? "+" : ""}{weightedAvgReturn.toFixed(2)}%
              </p>
              <p className="text-xs text-text-muted mt-0.5">Weighted across accounts</p>
            </>
          ) : (
            <>
              <p className="text-xs text-text-muted font-medium mb-1">Total Gain/Loss</p>
              <p className="text-xl font-semibold text-text-muted">Not tracked</p>
              <p className="text-xs text-text-muted mt-0.5">Add cost basis to track</p>
            </>
          )}
        </Card>
        <Card padding="lg">
          <p className="text-xs text-text-muted font-medium mb-1">Holdings</p>
          <p className="text-2xl font-bold tracking-tight text-text-primary">{summary?.holdings_count ?? (holdings.length + crypto.length)}</p>
          <p className="text-xs text-text-muted mt-0.5">
            {holdings.length > 0 ? `${holdings.length} stocks/ETFs` : ""}
            {holdings.length > 0 && crypto.length > 0 ? " · " : ""}
            {crypto.length > 0 ? `${crypto.length} crypto` : ""}
          </p>
        </Card>
        <Card padding="lg">
          <p className="text-xs text-text-muted font-medium mb-1">Accounts</p>
          <p className="text-2xl font-bold tracking-tight text-text-primary">{plaidAccounts.length + manualInvestments.length}</p>
          <p className="text-xs text-text-muted mt-0.5">{plaidAccounts.length} linked · {manualInvestments.length} manual</p>
        </Card>
      </div>

      {/* Top Holdings */}
      {summary?.top_holdings && summary.top_holdings.length > 0 && (
        <Card padding="lg">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Top Holdings</h2>
          <div className="space-y-3">
            {summary.top_holdings.map((h, i) => {
              const pct = grandTotal > 0 ? (h.value / grandTotal) * 100 : 0;
              return (
                <div key={h.ticker} className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }}>
                    {h.ticker.slice(0, 2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-text-primary">{h.ticker}</span>
                        {h.name && <span className="text-xs text-text-muted truncate">{h.name}</span>}
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-semibold font-mono tabular-nums">{formatCurrency(h.value)}</span>
                        {h.gain_loss_pct !== 0 && (
                          <span className={`text-xs font-medium ${h.gain_loss_pct >= 0 ? "text-green-600" : "text-red-600"}`}>
                            {h.gain_loss_pct >= 0 ? "+" : ""}{h.gain_loss_pct.toFixed(1)}%
                            {h.is_annual_return ? " /yr" : ""}
                          </span>
                        )}
                      </div>
                    </div>
                    <ProgressBar value={pct} color={COLORS[i % COLORS.length]} size="xs" />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Linked Investment Accounts */}
      {plaidAccounts.length > 0 && (
        <Card padding="lg">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Linked Investment Accounts</h2>
          <div className="space-y-3">
            {plaidAccounts.map((acct, i) => {
              const weight = totalPlaidValue > 0 ? ((acct.current_balance ?? 0) / totalPlaidValue * 100) : 0;
              return (
                <div key={acct.id}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                      <span className="text-sm text-text-secondary">{acct.name}</span>
                      {acct.subtype && <Badge className="bg-surface text-text-secondary">{acct.subtype}</Badge>}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold font-mono tabular-nums">{formatCurrency(acct.current_balance ?? 0)}</span>
                      <span className="text-xs text-text-muted w-12 text-right tabular-nums">{weight.toFixed(1)}%</span>
                    </div>
                  </div>
                  <ProgressBar value={weight} color={COLORS[i % COLORS.length]} size="sm" />
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Manual Investment Accounts */}
      {manualInvestments.length > 0 && (
        <Card padding="lg">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Investment Accounts</h2>
          <div className="space-y-3">
            {manualInvestments.map((asset) => (
              <div key={asset.id} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-text-primary">{asset.name}</p>
                  <p className="text-xs text-text-muted">{asset.institution ?? asset.custodian ?? asset.account_subtype ?? "Investment"}</p>
                </div>
                <span className="text-sm font-semibold font-mono tabular-nums">{formatCurrency(asset.current_value)}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-text-muted mt-4 pt-3 border-t border-card-border">
            Manage accounts on the <a href="/accounts" className="text-accent hover:underline">Accounts page</a>.
          </p>
        </Card>
      )}

      {/* Cryptocurrency */}
      {crypto.length > 0 && (
        <Card padding="lg">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Cryptocurrency</h2>
          <div className="space-y-3">
            {crypto.map((c) => (
              <div key={c.id} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-amber-50 dark:bg-amber-950/40 flex items-center justify-center text-xs font-bold text-amber-600 dark:text-amber-400">
                    {c.symbol.slice(0, 3)}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text-primary">{c.symbol.toUpperCase()}</p>
                    <p className="text-xs text-text-muted">{c.name ?? c.coin_id} · {c.quantity} units</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold font-mono tabular-nums">{formatCurrency(c.current_value ?? 0)}</p>
                  {c.unrealized_gain_loss != null && (
                    <p className={`text-xs ${(c.unrealized_gain_loss ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {(c.unrealized_gain_loss ?? 0) >= 0 ? "+" : ""}{formatCurrency(c.unrealized_gain_loss ?? 0)}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
