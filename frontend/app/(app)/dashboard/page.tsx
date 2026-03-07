"use client";
import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import {
  Receipt, AlertCircle,
  Loader2,
  ChevronRight, Calendar, Lightbulb, LayoutDashboard, Sparkles,
} from "lucide-react";
import TabBar from "@/components/ui/TabBar";
import { useTabState } from "@/hooks/useTabState";
import { DASHBOARD_TABS } from "@/components/dashboard/constants";
import { getDashboard, getBudgetSummary, getRecurringSummary, getGoals, getBenchmarkSnapshot, getOrderOfOperations, getProactiveInsights } from "@/lib/api";
import { getFamilyMembers } from "@/lib/api-household";
import { getLifeEvents } from "@/lib/api-life-events";
import { formatCurrency, formatDate, monthName, segmentColor } from "@/lib/utils";
import type { Dashboard, BudgetSummary, RecurringSummary, Goal, BenchmarkData, FOOStep, ProactiveInsight } from "@/types/api";
import type { FamilyMember } from "@/types/household";
import type { LifeEvent } from "@/types/life-events";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import TrajectoryChart from "@/components/TrajectoryChart";
import Link from "next/link";
import { StatusCard, CashFlowWidget, ActionPlanWidget, InsightsSection } from "@/components/dashboard";
import SetupBanner from "@/components/setup/SetupBanner";
import EmptyState from "@/components/ui/EmptyState";

const now = new Date();
const CURRENT_YEAR = now.getFullYear();
const AVAILABLE_YEARS = Array.from({ length: 4 }, (_, i) => CURRENT_YEAR - i);

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [budget, setBudget] = useState<BudgetSummary | null>(null);
  const [recurring, setRecurring] = useState<RecurringSummary | null>(null);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkData | null>(null);
  const [fooSteps, setFooSteps] = useState<FOOStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedYear, setSelectedYear] = useState(CURRENT_YEAR);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [primaryName, setPrimaryName] = useState<string | null>(null);
  const [upcomingEvents, setUpcomingEvents] = useState<LifeEvent[]>([]);
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const [dismissedInsights, setDismissedInsights] = useState<Set<string>>(new Set());
  const [activeTab, setTab] = useTabState(DASHBOARD_TABS, "overview");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const budgetMonth = selectedMonth ?? (selectedYear === CURRENT_YEAR ? now.getMonth() + 1 : 12);
    Promise.all([
      getDashboard(selectedYear, selectedMonth ?? undefined),
      getBudgetSummary(selectedYear, budgetMonth).catch(() => null),
      getRecurringSummary().catch(() => null),
      getGoals().catch(() => []),
      getBenchmarkSnapshot().catch(() => null),
      getOrderOfOperations().catch(() => []),
      getProactiveInsights().catch(() => ({ insights: [] })),
    ])
      .then(([d, b, r, g, bench, foo, pi]) => {
        if (controller.signal.aborted) return;
        setData(d);
        setBudget(b);
        setRecurring(r);
        setGoals(Array.isArray(g) ? g.filter((x: Goal) => x.status === "active").slice(0, 4) : []);
        setBenchmarks(bench ?? null);
        setFooSteps(Array.isArray(foo) ? foo : []);
        setInsights((pi as { insights: ProactiveInsight[] }).insights);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [selectedYear, selectedMonth]);

  useEffect(() => {
    getFamilyMembers().then((members) => {
      const self = members.find((m) => m.relationship === "self") ?? members[0] ?? null;
      if (self?.name) setPrimaryName(self.name.split(" ")[0]);
    }).catch(() => {});

    getLifeEvents().then((events) => {
      const upcoming = events
        .filter((e) => e.status === "upcoming")
        .sort((a, b) => {
          if (!a.event_date) return 1;
          if (!b.event_date) return -1;
          return new Date(a.event_date).getTime() - new Date(b.event_date).getTime();
        })
        .slice(0, 3);
      setUpcomingEvents(upcoming);
    }).catch(() => {});

    // Load dismissed insights from localStorage
    try {
      const dismissed = localStorage.getItem("dismissed-insights");
      if (dismissed) setDismissedInsights(new Set(JSON.parse(dismissed)));
    } catch {}
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-text-muted">
        <Loader2 className="animate-spin" size={22} />
        <span>Loading dashboard...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <div className="flex items-center gap-3 text-red-700">
          <AlertCircle size={20} />
          <div>
            <p className="font-semibold">Cannot connect to API</p>
            <p className="text-sm mt-0.5">{error}</p>
            <p className="text-sm mt-1 text-red-500">
              Make sure the FastAPI server is running: <code className="bg-red-100 px-1 rounded">uvicorn api.main:app --reload</code>
            </p>
          </div>
        </div>
      </Card>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight font-display">
            Welcome to Sir HENRY
          </h1>
          <p className="text-text-secondary text-sm mt-0.5">Let&apos;s get your financial picture set up.</p>
        </div>
        <SetupBanner />
        <EmptyState
          icon={<LayoutDashboard size={40} />}
          title="Your dashboard is ready"
          description="Connect your accounts or import a statement to see your financial overview come to life."
          henryTip="Start by connecting your bank accounts — I'll automatically categorize your transactions and build your complete financial picture."
          action={
            <div className="flex items-center gap-3 justify-center">
              <Link
                href="/setup"
                className="inline-flex items-center gap-2 bg-accent text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover shadow-sm transition-colors"
              >
                <Sparkles size={14} />
                Start Setup
              </Link>
              <Link
                href="/import"
                className="inline-flex items-center gap-2 border border-border bg-card text-text-secondary px-5 py-2.5 rounded-lg text-sm font-medium hover:border-border transition-colors"
              >
                Import Statement
              </Link>
            </div>
          }
          askHenryPrompt="What should I set up first to get the most out of Sir HENRY?"
        />
      </div>
    );
  }

  const currentMonthName = monthName(data.current_month);
  const savingsRate = data.current_month_income > 0
    ? ((data.current_month_income - data.current_month_expenses) / data.current_month_income * 100)
    : 0;

  const chartData = data.monthly_trend.map((p) => ({
    name: monthName(p.month ?? 1).slice(0, 3),
    Income: Math.round(p.total_income),
    Expenses: Math.round(p.total_expenses),
    Net: Math.round(p.net_cash_flow),
  }));

  const effectiveSavingsRate = benchmarks && benchmarks.savings_rate > 0
    ? benchmarks.savings_rate
    : data.ytd_income > 0 ? (data.ytd_net / data.ytd_income) * 100 : 0;
  const effectiveNetWorth = benchmarks?.net_worth ?? 0;
  const targetSavingsRate = benchmarks?.required_savings_rate ?? 20;

  const statusLabel = effectiveSavingsRate >= targetSavingsRate ? "On Track" : effectiveSavingsRate >= targetSavingsRate * 0.5 ? "At Risk" : "Behind";
  const statusClass = effectiveSavingsRate >= targetSavingsRate ? "status-on-track" : effectiveSavingsRate >= targetSavingsRate * 0.5 ? "status-at-risk" : "status-behind";

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight font-display">
            Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}{primaryName ? `, ${primaryName}` : ""}
          </h1>
          <p className="text-text-secondary text-sm mt-0.5">{currentMonthName} {data.current_year}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-semibold px-3 py-1.5 rounded-full ${statusClass}`}>{statusLabel}</span>
          <div className="flex items-center gap-2">
            <select value={selectedYear} onChange={(e) => { setSelectedYear(Number(e.target.value)); setSelectedMonth(null); }} className="text-sm border border-border rounded-lg px-3 py-1.5 bg-card focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent">
              {AVAILABLE_YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <select value={selectedMonth ?? ""} onChange={(e) => setSelectedMonth(e.target.value ? Number(e.target.value) : null)} className="text-sm border border-border rounded-lg px-3 py-1.5 bg-card focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent">
              <option value="">{selectedYear === CURRENT_YEAR ? "Current Month" : "Full Year"}</option>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{monthName(m)}</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* TABS */}
      <TabBar tabs={DASHBOARD_TABS} activeTab={activeTab} onChange={setTab} variant="pill" />

      {activeTab === "insights" ? (
        <InsightsSection selectedYear={selectedYear} />
      ) : (
      <>
      {/* SETUP PROMPT */}
      <SetupBanner />

      {/* ACTION ITEMS */}
      {(() => {
        const visible = insights.filter((i) => !dismissedInsights.has(i.type + i.title));
        if (visible.length === 0) return null;
        const severityIcon = (s: string) => {
          if (s === "action") return <AlertCircle size={14} className="text-red-500" />;
          if (s === "warning") return <AlertCircle size={14} className="text-amber-500" />;
          return <Lightbulb size={14} className="text-blue-500" />;
        };
        const severityBg = (s: string) => {
          if (s === "action") return "bg-red-50";
          if (s === "warning") return "bg-amber-50";
          return "bg-blue-50";
        };
        return (
          <Card padding="none">
            <div className="flex items-center justify-between px-5 pt-5 pb-3">
              <div className="flex items-center gap-2">
                <Lightbulb size={16} className="text-accent" />
                <h2 className="text-sm font-semibold text-text-secondary">Action Items</h2>
              </div>
              <span className="text-xs text-text-muted">{visible.length} item{visible.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="divide-y divide-border-light">
              {visible.slice(0, 5).map((insight) => (
                <div key={insight.type + insight.title} className="flex items-center gap-3 px-5 py-3 hover:bg-surface/50">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${severityBg(insight.severity)}`}>
                    {severityIcon(insight.severity)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary">{insight.title}</p>
                    <p className="text-xs text-text-secondary mt-0.5">{insight.message}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {insight.link_to && (
                      <Link href={insight.link_to} className="text-xs text-accent hover:underline font-medium">
                        Review
                      </Link>
                    )}
                    <button
                      onClick={() => {
                        const key = insight.type + insight.title;
                        const next = new Set(dismissedInsights);
                        next.add(key);
                        setDismissedInsights(next);
                        try { localStorage.setItem("dismissed-insights", JSON.stringify([...next])); } catch {}
                      }}
                      className="text-text-muted hover:text-text-secondary p-1"
                      title="Dismiss"
                    >
                      <ChevronRight size={12} className="rotate-90" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        );
      })()}

      {/* STATUS */}
      <StatusCard effectiveSavingsRate={effectiveSavingsRate} effectiveNetWorth={effectiveNetWorth} targetSavingsRate={targetSavingsRate} />

      {/* TRAJECTORY */}
      <Card padding="lg">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-sm font-semibold text-text-secondary font-display">Trajectory</h2>
            <p className="text-xs text-text-muted mt-0.5">Retirement projection — pessimistic · base · optimistic</p>
          </div>
        </div>
        <TrajectoryChart />
      </Card>

      {/* MONEY FLOW */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Money Flow · {currentMonthName}</h2>
        <CashFlowWidget data={data} budget={budget} currentMonthName={currentMonthName} savingsRate={savingsRate} targetSavingsRate={targetSavingsRate} />
      </div>

      {/* ACTION PLAN */}
      <ActionPlanWidget fooSteps={fooSteps} />

      {/* UPCOMING LIFE EVENTS */}
      {upcomingEvents.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted">Upcoming Life Events</h2>
            <Link href="/life-events" className="text-xs text-accent hover:underline font-medium">View all →</Link>
          </div>
          <Card padding="none">
            <div className="divide-y divide-border-light">
              {upcomingEvents.map((event) => (
                <div key={event.id} className="flex items-center gap-4 px-5 py-3.5">
                  <div className="w-8 h-8 rounded-full bg-indigo-50 flex items-center justify-center shrink-0"><Calendar size={16} className="text-indigo-500" /></div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text-primary text-sm">{event.title}</p>
                    {event.event_date && <p className="text-xs text-text-muted mt-0.5">{formatDate(event.event_date)}</p>}
                  </div>
                  <Link href="/life-events" className="text-xs text-text-muted hover:text-accent shrink-0">Review →</Link>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* MONTHLY TREND CHART */}
      {chartData.length > 0 && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-text-secondary">Monthly Cash Flow</h2>
            <Link href="/cashflow" className="text-xs text-accent hover:underline font-medium">View Details →</Link>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 12, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #E5E7EB", boxShadow: "0 4px 12px rgba(0,0,0,0.08)", fontFamily: "var(--font-mono)" }} formatter={(v) => typeof v === "number" ? formatCurrency(v) : String(v ?? "")} />
              <Legend wrapperStyle={{ fontSize: 12, color: "#9CA3AF" }} />
              <Bar dataKey="Income" fill="#86EFAC" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Expenses" fill="#D1D5DB" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* TRANSACTIONS + DETAIL CARDS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card padding="none">
          <div className="flex items-center justify-between px-5 pt-5 pb-3">
            <h2 className="text-sm font-semibold text-text-secondary">Recent Transactions</h2>
            <Link href="/transactions" className="text-xs text-accent hover:underline font-medium flex items-center gap-1">All <ChevronRight size={12} /></Link>
          </div>
          {data.recent_transactions.length === 0 ? (
            <p className="text-text-muted text-sm text-center py-8 px-5">No transactions yet. Import a statement to get started.</p>
          ) : (
            <div className="divide-y divide-border-light">
              {data.recent_transactions.map((tx) => (
                <div key={tx.id} className="flex items-center justify-between px-5 py-3 hover:bg-surface/50">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${tx.amount >= 0 ? "bg-green-50 text-green-600" : "bg-surface text-text-secondary"}`}>{tx.description.charAt(0).toUpperCase()}</div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-text-primary truncate">{tx.description}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-text-muted">{formatDate(tx.date)}</span>
                        <Badge className={segmentColor(tx.effective_segment)}>{tx.effective_segment ?? tx.segment}</Badge>
                      </div>
                    </div>
                  </div>
                  <span className={`text-sm font-semibold tabular-nums ml-3 money ${tx.amount >= 0 ? "text-green-600" : "text-text-primary"}`}>{tx.amount >= 0 ? "+" : ""}{formatCurrency(tx.amount)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-5">
          <Card padding="lg">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-text-secondary">Recurring</h2>
              <Link href="/recurring" className="text-xs text-accent hover:underline font-medium">View All →</Link>
            </div>
            {recurring ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-surface rounded-lg p-3 text-center"><p className="text-lg font-bold text-text-primary money">{formatCurrency(recurring.total_monthly_cost, true)}</p><p className="text-xs text-text-muted uppercase">Monthly</p></div>
                  <div className="bg-surface rounded-lg p-3 text-center"><p className="text-lg font-bold text-text-primary money">{formatCurrency(recurring.total_annual_cost, true)}</p><p className="text-xs text-text-muted uppercase">Annual</p></div>
                </div>
                <p className="text-xs text-text-secondary">{recurring.subscription_count} active subscriptions</p>
              </div>
            ) : <p className="text-sm text-text-muted">No recurring items detected yet.</p>}
          </Card>

          <Card padding="lg">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-text-secondary">Goals</h2>
              <Link href="/goals" className="text-xs text-accent hover:underline font-medium">View All →</Link>
            </div>
            {goals.length === 0 ? <p className="text-sm text-text-muted">No goals set yet.</p> : (
              <div className="space-y-3">
                {goals.map((goal) => (
                  <div key={goal.id} className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0" style={{ backgroundColor: goal.color }}>{goal.name.charAt(0)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1"><span className="text-sm font-medium text-text-primary truncate">{goal.name}</span><span className="text-xs text-text-secondary money ml-2">{formatCurrency(goal.current_amount, true)}</span></div>
                      <ProgressBar value={goal.progress_pct} color={goal.color} size="xs" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card padding="lg">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-text-secondary">Tax Strategies</h2>
              <Link href="/tax-strategy" className="text-xs text-accent hover:underline font-medium">View All →</Link>
            </div>
            {data.top_strategies_count === 0 ? (
              <div className="text-center py-4">
                <Receipt className="mx-auto text-text-muted mb-2" size={24} />
                <p className="text-text-muted text-sm">No strategies yet.</p>
                <Link href="/tax-strategy" className="text-xs text-accent hover:underline mt-1 block">Run tax analysis →</Link>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <div className="text-3xl font-bold text-accent money">{data.top_strategies_count}</div>
                <div><p className="font-medium text-text-primary text-sm">Active strategies</p><p className="text-text-muted text-xs">identified for {data.current_year}</p></div>
              </div>
            )}
          </Card>
        </div>
      </div>

      </>
      )}
    </div>
  );
}
