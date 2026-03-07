"use client";
import { useCallback, useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Loader2, AlertCircle, Search,
  BarChart3, Globe, Percent, DollarSign, Activity, Building2, MessageCircle,
} from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  getEconomicIndicators, getQuote, getTickerHistory, researchCompany,
  getHoldings,
} from "@/lib/api";
import type { CompanyResearch, EconomicIndicator, MarketQuote } from "@/types/api";
import { getErrorMessage } from "@/lib/errors";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import SirHenryName from "@/components/ui/SirHenryName";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line,
} from "recharts";

const CATEGORY_ICONS: Record<string, React.ElementType> = {
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
  const [research, setResearch] = useState<CompanyResearch | null>(null);
  const [userTickers, setUserTickers] = useState<string[]>([]);

  useEffect(() => {
    getHoldings().then((h) => {
      const tickers = [...new Set(h.map((x) => x.ticker).filter(Boolean))] as string[];
      setUserTickers(tickers.slice(0, 10));
    }).catch(() => {});
  }, []);

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
      setQuote(q);
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
        actions={
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("ask-henry", { detail: { message: "How do current market conditions affect my portfolio? Any adjustments I should consider?" } }))}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
          >
            <MessageCircle size={14} /> Ask <SirHenryName />
          </button>
        }
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
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search any ticker (e.g. AAPL, MSFT, TSLA)..."
              className="w-full pl-10 pr-4 py-3 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
            />
          </div>
          <button
            onClick={() => handleSearch()}
            disabled={quoteLoading}
            className="bg-accent text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm disabled:opacity-60"
          >
            {quoteLoading ? <Loader2 size={16} className="animate-spin" /> : "Search"}
          </button>
        </div>
        {/* User's portfolio tickers */}
        {userTickers.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Your Portfolio</p>
            <div className="flex gap-2 flex-wrap">
              {userTickers.map((t) => (
                <button
                  key={t}
                  onClick={() => { setSearchTicker(t); handleSearch(t); }}
                  className="text-xs px-3 py-1.5 rounded-full border border-accent/30 text-accent bg-green-50 hover:bg-green-100 hover:border-accent/50 transition-colors font-medium"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className={userTickers.length > 0 ? "mt-2" : "mt-3"}>
          {userTickers.length > 0 && (
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Market Indices & Popular</p>
          )}
          <div className="flex gap-2 flex-wrap">
            {QUICK_TICKERS.filter((t) => !userTickers.includes(t)).map((t) => (
              <button
                key={t}
                onClick={() => { setSearchTicker(t); handleSearch(t); }}
                className="text-xs px-3 py-1.5 rounded-full border border-border text-text-secondary hover:bg-surface hover:border-border transition-colors"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Quote Result */}
      {quote && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2">
            <Card padding="lg">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-2xl font-bold text-text-primary">{quote.ticker}</p>
                  <p className="text-sm text-text-secondary">{quote.company_name}</p>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-text-primary font-mono tabular-nums">{quote.price ? formatCurrency(quote.price) : "N/A"}</p>
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
            <h3 className="text-sm font-semibold text-text-primary mb-3">Key Metrics</h3>
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
                  <span className="text-text-secondary">{label}</span>
                  <span className="font-medium text-text-primary tabular-nums">{value}</span>
                </div>
              ))}
            </div>
            {research && typeof research.description === "string" && (
              <div className="mt-4 pt-3 border-t border-card-border">
                <p className="text-xs text-text-secondary leading-relaxed line-clamp-4">{research.description}</p>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Economic Indicators */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
          Economic Indicators
        </h2>
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-text-muted" size={24} /></div>
        ) : indicators.length === 0 ? (
          <Card padding="lg">
            <div className="text-center py-8">
              <Globe size={32} className="text-text-muted mx-auto mb-3" />
              <p className="text-sm text-text-secondary">Economic indicators require an Alpha Vantage API key.</p>
              <p className="text-xs text-text-muted mt-1">Add ALPHA_VANTAGE_API_KEY to your .env file (free at alphavantage.co)</p>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {indicators.map((ind) => {
              const IconComp = CATEGORY_ICONS[ind.category] || Activity;
              const colorClass = CATEGORY_COLORS[ind.category] || "text-text-secondary bg-surface";
              const [textColor, bgColor] = colorClass.split(" ");
              return (
                <Card key={ind.series_id} padding="lg">
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`w-9 h-9 rounded-lg ${bgColor} flex items-center justify-center`}>
                      <IconComp size={18} className={textColor} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-text-primary">{ind.label}</p>
                      <p className="text-xs text-text-muted">{ind.latest_date}</p>
                    </div>
                    <p className="ml-auto text-xl font-bold text-text-primary font-mono tabular-nums">
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
