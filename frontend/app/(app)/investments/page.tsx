"use client";
import { useEffect, useState } from "react";
import {
  TrendingUp, Loader2, AlertCircle,
} from "lucide-react";
import { getPlaidAccounts } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { PlaidAccount } from "@/types/api";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import ProgressBar from "@/components/ui/ProgressBar";

type ViewTab = "investments" | "holdings" | "allocation";

export default function InvestmentsPage() {
  const [accounts, setAccounts] = useState<PlaidAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<ViewTab>("investments");

  useEffect(() => {
    getPlaidAccounts()
      .then((accts) => setAccounts(accts.filter((a) => a.type === "investment")))
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const totalValue = accounts.reduce((s, a) => s + (a.current_balance ?? 0), 0);

  const hasInvestmentAccounts = accounts.length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Investments"
        subtitle="Portfolio performance and holdings"
      />

      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex bg-stone-100 rounded-lg p-0.5">
          {(["investments", "holdings", "allocation"] as ViewTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize ${
                tab === t ? "bg-white text-stone-900 shadow-sm" : "text-stone-500 hover:text-stone-700"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
      ) : error ? (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} />
          <p className="text-sm">{error}</p>
        </div>
      ) : tab === "investments" ? (
        <>
          {/* Portfolio summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card padding="lg">
              <p className="text-xs text-stone-400 font-medium mb-1">Total Value</p>
              <p className="text-2xl font-bold tracking-tight text-stone-900">{formatCurrency(totalValue)}</p>
            </Card>
            <Card padding="lg">
              <p className="text-xs text-stone-400 font-medium mb-1">Accounts</p>
              <p className="text-2xl font-bold tracking-tight text-stone-900">{accounts.length}</p>
            </Card>
          </div>

          {!hasInvestmentAccounts ? (
            <EmptyState
              icon={<TrendingUp size={40} />}
              title="No investment accounts connected"
              description="Connect your brokerage or retirement accounts via Plaid on the Accounts page to see portfolio performance, holdings, and allocation."
              action={
                <a href="/accounts" className="inline-flex items-center gap-2 bg-[#16A34A] text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm">
                  Go to Accounts
                </a>
              }
            />
          ) : (
            <Card padding="lg">
              <h2 className="text-sm font-semibold text-stone-700 mb-4">Investment Accounts Overview</h2>
              <div className="space-y-3">
                {accounts.map((acct, i) => {
                  const weight = totalValue > 0 ? ((acct.current_balance ?? 0) / totalValue * 100) : 0;
                  const colors = ["#16A34A", "#3b82f6", "#16a34a", "#f59e0b", "#8b5cf6", "#06b6d4"];
                  const color = colors[i % colors.length];
                  return (
                    <div key={acct.id}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: color }} />
                          <span className="text-sm text-stone-700">{acct.name}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold tabular-nums">{formatCurrency(acct.current_balance ?? 0)}</span>
                          <span className="text-xs text-stone-400 w-12 text-right tabular-nums">{weight.toFixed(1)}%</span>
                        </div>
                      </div>
                      <ProgressBar value={weight} color={color} size="sm" />
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </>
      ) : tab === "holdings" ? (
        <>
          {/* Holdings Table */}
          <Card padding="none">
            <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-stone-700">Holdings</h2>
              <span className="text-xs text-stone-400">Total: {formatCurrency(totalValue)}</span>
            </div>

            {accounts.length === 0 ? (
              <div className="p-12 text-center">
                <p className="text-stone-400 text-sm">No investment accounts connected. Connect via Plaid to see holdings.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-stone-100">
                    <tr>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wider">Account</th>
                      <th className="text-right px-5 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wider">Value</th>
                      <th className="text-right px-5 py-3 text-xs font-semibold text-stone-500 uppercase tracking-wider">Weight</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-50">
                    {accounts.map((acct) => {
                      const weight = totalValue > 0 ? ((acct.current_balance ?? 0) / totalValue * 100) : 0;
                      return (
                        <tr key={acct.id} className="hover:bg-stone-50/50">
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full bg-indigo-50 flex items-center justify-center">
                                <TrendingUp size={14} className="text-indigo-500" />
                              </div>
                              <div>
                                <p className="font-medium text-stone-800">{acct.name}</p>
                                <p className="text-xs text-stone-400">{acct.official_name ?? acct.subtype ?? "Investment"}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-5 py-3.5 text-right font-semibold tabular-nums text-stone-900">
                            {acct.current_balance != null ? formatCurrency(acct.current_balance) : "—"}
                          </td>
                          <td className="px-5 py-3.5 text-right text-stone-500 tabular-nums">
                            {weight.toFixed(1)}%
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      ) : (
        /* Allocation View */
        <>
          <Card padding="lg">
            <h2 className="text-sm font-semibold text-stone-700 mb-4">Asset Allocation</h2>
            {accounts.length === 0 ? (
              <p className="text-stone-400 text-sm text-center py-8">Connect investment accounts to see allocation.</p>
            ) : (
              <div className="space-y-3">
                {accounts.map((acct, i) => {
                  const weight = totalValue > 0 ? ((acct.current_balance ?? 0) / totalValue * 100) : 0;
                  const colors = ["#16A34A", "#3b82f6", "#16a34a", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899"];
                  const color = colors[i % colors.length];
                  return (
                    <div key={acct.id}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: color }} />
                          <span className="text-sm text-stone-700">{acct.name}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold tabular-nums">{formatCurrency(acct.current_balance ?? 0)}</span>
                          <span className="text-xs text-stone-400 w-12 text-right tabular-nums">{weight.toFixed(1)}%</span>
                        </div>
                      </div>
                      <ProgressBar value={weight} color={color} size="sm" />
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
