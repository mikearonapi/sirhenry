"use client";
import { useCallback, useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Loader2, AlertCircle, Search,
  BarChart3, Globe, Percent, DollarSign, Activity, Building2,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  getEconomicIndicators, getQuote, getTickerHistory, researchCompany,
} from "@/lib/api";
import type { EconomicIndicator, MarketQuote } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line,
} from "recharts";

const CATEGORY_ICONS: Record<string, any> = {
  rates: Percent, inflation: TrendingUp, employment: Activity, consumer: DollarSign, growth: BarChart3,
};

const CATEGORY_COLORS: Record<string, string> = {
  rates: "text-blue-600 bg-blue-50", inflation: "text-red-600 bg-red-50",
  employment: "text-green-600 bg-green-50", consumer: "text-purple-600 bg-purple-50",
  growth: "text-amber-600 bg-amber-50",
};

const QUICK_TICKERS = ["SPY", "QQQ", "DIA", "IWM", "VTI", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"];

export default function MarketPage() {
  const [indicators, setIndicators] = useState<EconomicIndicator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTicker, setSearchTicker] = useState("");
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [history, setHistory] = useState<Array<{ date: string; close: number }>>([]);
  const [research, setResearch] = useState<Record<string, unknown> | null>(null);

  const loadIndicators = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getEconomicIndicators();
      setIndicators(data.indicators || []);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setLoading(false);
  }, []);

  useEffect(() => { loadIndicators(); }, [loadIndicators]);

  async function handleSearch(ticker?: string) {
    const t = (ticker || searchTicker).toUpperCase().trim();
    if (!t) return;
    setQuoteLoading(true);
    setQuote(null);
    setHistory([]);
    setResearch(null);
    try {
      const [q, h] = await Promise.all([
        getQuote(t),
        getTickerHistory(t, "1y"),
      ]);
      setQuote(q as any);
      setHistory(h.data || []);
      try {
        const r = await researchCompany(t);
        setResearch(r);
      } catch {}
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    setQuoteLoading(false);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Market Pulse"
        subtitle="Economic indicators, market data, and research for informed decisions"
      />

      {error && (
        <div className="bg-red-50 text-red-700 rounded-xl p-4 flex items-center gap-3 border border-red-100">
          <AlertCircle size={18} /><p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto text-xs text-red-400">Dismiss</button>
        </div>
      )}

      {/* Ticker Search */}
      <Card padding="lg">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
            <input
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search any ticker (e.g. AAPL, MSFT, TSLA)..."
              className="w-full pl-10 pr-4 py-3 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#16A34A]/20 focus:border-[#16A34A]"
            />
          </div>
          <button
            onClick={() => handleSearch()}
            disabled={quoteLoading}
            className="bg-[#16A34A] text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-[#15803D] shadow-sm disabled:opacity-60"
          >
            {quoteLoading ? <Loader2 size={16} className="animate-spin" /> : "Search"}
          </button>
        </div>
        <div className="flex gap-2 mt-3 flex-wrap">
          {QUICK_TICKERS.map((t) => (
            <button
              key={t}
              onClick={() => { setSearchTicker(t); handleSearch(t); }}
              className="text-xs px-3 py-1.5 rounded-full border border-stone-200 text-stone-600 hover:bg-stone-50 hover:border-stone-300 transition-colors"
            >
              {t}
            </button>
          ))}
        </div>
      </Card>

      {/* Quote Result */}
      {quote && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2">
            <Card padding="lg">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-2xl font-bold text-stone-900">{quote.ticker}</p>
                  <p className="text-sm text-stone-500">{quote.company_name}</p>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-stone-900 tabular-nums">{quote.price ? formatCurrency(quote.price) : "N/A"}</p>
                  {quote.change != null && (
                    <p className={`text-sm font-medium ${quote.change >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {quote.change >= 0 ? "+" : ""}{formatCurrency(quote.change)} ({quote.change_pct?.toFixed(2)}%)
                    </p>
                  )}
                </div>
              </div>
              {history.length > 0 && (
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={history}>
                    <defs>
                      <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#16A34A" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#16A34A" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f1f0" />
                    <XAxis dataKey="date" fontSize={10} interval={Math.floor(history.length / 6)} />
                    <YAxis fontSize={10} domain={["auto", "auto"]} tickFormatter={(v) => `$${v}`} />
                    <Tooltip formatter={(v) => formatCurrency(Number(v))} />
                    <Area type="monotone" dataKey="close" stroke="#16A34A" fill="url(#priceGrad)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>

          <Card padding="lg">
            <h3 className="text-sm font-semibold text-stone-800 mb-3">Key Metrics</h3>
            <div className="space-y-2.5">
              {[
                { label: "Market Cap", value: quote.market_cap ? formatCurrency(quote.market_cap, true) : "N/A" },
                { label: "P/E Ratio", value: quote.pe_ratio?.toFixed(2) ?? "N/A" },
                { label: "Forward P/E", value: quote.forward_pe?.toFixed(2) ?? "N/A" },
                { label: "Dividend Yield", value: quote.dividend_yield ? formatPercent(quote.dividend_yield * 100) : "N/A" },
                { label: "Beta", value: quote.beta?.toFixed(2) ?? "N/A" },
                { label: "52W High", value: quote.fifty_two_week_high ? formatCurrency(quote.fifty_two_week_high) : "N/A" },
                { label: "52W Low", value: quote.fifty_two_week_low ? formatCurrency(quote.fifty_two_week_low) : "N/A" },
                { label: "Volume", value: quote.volume?.toLocaleString() ?? "N/A" },
                { label: "Sector", value: quote.sector ?? "N/A" },
                { label: "Industry", value: quote.industry ?? "N/A" },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between text-sm">
                  <span className="text-stone-500">{label}</span>
                  <span className="font-medium text-stone-800 tabular-nums">{value}</span>
                </div>
              ))}
            </div>
            {research && (research as any).description && (
              <div className="mt-4 pt-3 border-t border-stone-100">
                <p className="text-xs text-stone-500 leading-relaxed line-clamp-4">{(research as any).description}</p>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Economic Indicators */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">
          Economic Indicators
        </h2>
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-stone-300" size={24} /></div>
        ) : indicators.length === 0 ? (
          <Card padding="lg">
            <div className="text-center py-8">
              <Globe size={32} className="text-stone-300 mx-auto mb-3" />
              <p className="text-sm text-stone-500">Economic indicators require an Alpha Vantage API key.</p>
              <p className="text-xs text-stone-400 mt-1">Add ALPHA_VANTAGE_API_KEY to your .env file (free at alphavantage.co)</p>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {indicators.map((ind) => {
              const IconComp = CATEGORY_ICONS[ind.category] || Activity;
              const colorClass = CATEGORY_COLORS[ind.category] || "text-stone-600 bg-stone-50";
              const [textColor, bgColor] = colorClass.split(" ");
              return (
                <Card key={ind.series_id} padding="lg">
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`w-9 h-9 rounded-lg ${bgColor} flex items-center justify-center`}>
                      <IconComp size={18} className={textColor} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-stone-800">{ind.label}</p>
                      <p className="text-xs text-stone-400">{ind.latest_date}</p>
                    </div>
                    <p className="ml-auto text-xl font-bold text-stone-900 tabular-nums">
                      {ind.latest_value?.toFixed(ind.unit === "percent" ? 2 : 1)}{ind.unit === "percent" ? "%" : ""}
                    </p>
                  </div>
                  {ind.trend && ind.trend.length > 2 && (
                    <ResponsiveContainer width="100%" height={80}>
                      <LineChart data={[...ind.trend].reverse()}>
                        <Line type="monotone" dataKey="value" stroke={textColor.replace("text-", "#").replace("-600", "")} strokeWidth={2} dot={false} />
                        <Tooltip
                          formatter={(v) => `${Number(v).toFixed(2)}${ind.unit === "percent" ? "%" : ""}`}
                          labelFormatter={(_, payload) => payload?.[0]?.payload?.date || ""}
                          contentStyle={{ fontSize: 11 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
