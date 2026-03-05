import Image from "next/image";
import {
  TrendingUp,
  PieChart,
  Receipt,
  Target,
  Users,
  RefreshCw,
  Landmark,
  BarChart3,
  Brain,
  Shield,
  Zap,
  Calculator,
  Wallet,
  Clock,
  LineChart,
  ArrowDownUp,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

interface Callout {
  icon: LucideIcon;
  title: string;
  description: string;
}

interface Feature {
  id: string;
  tag: string;
  title: string;
  description: string;
  dark: boolean;
  screenshot: string;
  callouts: Callout[];
}

const FEATURES: Feature[] = [
  {
    id: "ai-advisor",
    tag: "Your AI advisor",
    title: "Meet Sir Henry.",
    description: "An AI financial advisor that knows your numbers. Ask anything \u2014 get specific, personalized answers backed by your actual financial data.",
    dark: true,
    screenshot: "/screenshots/sir-henry.png",
    callouts: [
      { icon: Brain, title: "Context-aware", description: "Analyzes your accounts, goals, and tax situation in real time" },
      { icon: Zap, title: "Tool-powered", description: "Runs calculations, compares scenarios, and models outcomes" },
      { icon: Shield, title: "Privacy-first", description: "Your data stays local \u2014 never shared, never sold" },
    ],
  },
  {
    id: "retirement",
    tag: "Retirement planning",
    title: "See your future, clearly.",
    description: "Monte Carlo simulations model 10,000 possible outcomes. Know your FIRE number, earliest retirement age, and exactly what to do next.",
    dark: false,
    screenshot: "/screenshots/retirement.png",
    callouts: [
      { icon: LineChart, title: "10,000 simulations", description: "P10/P50/P90 confidence intervals \u2014 not just one projection" },
      { icon: Target, title: "FIRE & Coast FIRE", description: "Know your number and when you can stop saving" },
      { icon: TrendingUp, title: "What-if scenarios", description: "Model career changes, home purchases, and market downturns" },
    ],
  },
  {
    id: "portfolio",
    tag: "Portfolio & investments",
    title: "Your complete portfolio picture.",
    description: "Track every holding across every account. See your true allocation, find rebalancing opportunities, and harvest tax losses.",
    dark: true,
    screenshot: "/screenshots/portfolio.png",
    callouts: [
      { icon: PieChart, title: "True allocation", description: "Cross-account view of your actual asset mix" },
      { icon: ArrowDownUp, title: "Rebalancing", description: "Actionable trades to match your target allocation" },
      { icon: Calculator, title: "Tax-loss harvesting", description: "Find losses to offset gains and reduce your tax bill" },
    ],
  },
  {
    id: "tax-strategy",
    tag: "Tax optimization",
    title: "Keep more of what you earn.",
    description: "Personalized tax strategies identified from your financial data. See your effective rate, find deductions, and track filing progress.",
    dark: false,
    screenshot: "/screenshots/tax-strategy.png",
    callouts: [
      { icon: Receipt, title: "Strategy finder", description: "Backdoor Roth, tax-loss harvesting, DAFs, and more" },
      { icon: BarChart3, title: "Rate analysis", description: "Effective vs. marginal rate with year-over-year comparison" },
      { icon: Sparkles, title: "Filing checklist", description: "Track documents and deadlines in one place" },
    ],
  },
  {
    id: "budget",
    tag: "Budget & forecasting",
    title: "Budget that thinks ahead.",
    description: "Grouped categories with spend velocity tracking. Know where you'll land before the month ends.",
    dark: true,
    screenshot: "/screenshots/budget.png",
    callouts: [
      { icon: BarChart3, title: "Smart categories", description: "Auto-grouped expenses with visual progress bars" },
      { icon: TrendingUp, title: "Spend velocity", description: "Real-time pace tracking vs. your monthly budget" },
      { icon: Clock, title: "Month-end forecast", description: "Predict your total spend before it happens" },
    ],
  },
  {
    id: "goals",
    tag: "Goal tracking",
    title: "Goals built for high earners.",
    description: "Emergency fund, backdoor Roth, down payment, 529 \u2014 templates designed for HENRYs with progress tracking and on-track alerts.",
    dark: false,
    screenshot: "/screenshots/goals.png",
    callouts: [
      { icon: Target, title: "HENRY templates", description: "Pre-built goals for the financial milestones that matter" },
      { icon: TrendingUp, title: "On-track alerts", description: "Know immediately when a goal falls behind" },
      { icon: Wallet, title: "Commitment tracking", description: "See your total monthly savings obligation at a glance" },
    ],
  },
  {
    id: "household",
    tag: "Household optimization",
    title: "Two incomes, one strategy.",
    description: "Dual-income households leave money on the table. See exactly where \u2014 filing status, 401(k) coordination, benefits, and more.",
    dark: true,
    screenshot: "/screenshots/household.png",
    callouts: [
      { icon: Users, title: "Dual-income view", description: "Side-by-side employer benefits and income analysis" },
      { icon: Calculator, title: "Tax coordination", description: "MFJ vs. MFS, withholding optimization, and more" },
      { icon: Zap, title: "Savings identified", description: "Concrete dollar amounts for every optimization" },
    ],
  },
  {
    id: "recurring",
    tag: "Recurring & subscriptions",
    title: "Know every dollar on repeat.",
    description: "Track all recurring charges, spot subscription bloat, and see your true fixed-cost footprint.",
    dark: false,
    screenshot: "/screenshots/recurring.png",
    callouts: [
      { icon: RefreshCw, title: "Auto-detection", description: "Recurring charges found automatically from transactions" },
      { icon: BarChart3, title: "Category breakdown", description: "Visual spending by category with trend analysis" },
      { icon: Receipt, title: "Annual view", description: "See the true yearly cost of your subscriptions" },
    ],
  },
  {
    id: "accounts",
    tag: "Accounts & bank sync",
    title: "All your money, one dashboard.",
    description: "Connect banks, brokerages, and credit cards via Plaid. Add real estate and manual accounts. See your full net worth in real time.",
    dark: true,
    screenshot: "/screenshots/accounts.png",
    callouts: [
      { icon: Landmark, title: "Plaid integration", description: "One-click bank sync with 12,000+ institutions" },
      { icon: Shield, title: "Bank-level security", description: "Your credentials never touch our servers" },
      { icon: PieChart, title: "Net worth breakdown", description: "Assets, liabilities, and equity at a glance" },
    ],
  },
];

function CalloutCard({ callout, dark }: { callout: Callout; dark: boolean }) {
  const Icon = callout.icon;
  return (
    <div className="flex items-start gap-3">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
        dark ? "bg-[#22C55E]/10" : "bg-[#F0FDF4]"
      }`}>
        <Icon size={18} className={dark ? "text-[#22C55E]" : "text-[#16A34A]"} />
      </div>
      <div>
        <p className={`text-sm font-semibold ${dark ? "text-[#F9FAFB]" : "text-[#111827]"}`}>
          {callout.title}
        </p>
        <p className={`text-xs leading-relaxed mt-0.5 ${dark ? "text-[#9CA3AF]" : "text-[#6B7280]"}`}>
          {callout.description}
        </p>
      </div>
    </div>
  );
}

function ScreenshotFrame({ src, alt, dark }: { src: string; alt: string; dark: boolean }) {
  return (
    <div className={`rounded-xl overflow-hidden border ${
      dark ? "border-[#27272A] shadow-2xl shadow-black/40" : "border-[#E5E7EB] shadow-xl shadow-black/10"
    }`}>
      {/* Browser chrome */}
      <div className={`flex items-center gap-1.5 px-4 py-2.5 ${
        dark ? "bg-[#141416]" : "bg-[#F9FAFB]"
      }`}>
        <span className="w-2.5 h-2.5 rounded-full bg-[#EF4444]/80" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#EAB308]/80" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#22C55E]/80" />
        <span className={`ml-3 text-[10px] ${dark ? "text-[#6B7280]" : "text-[#9CA3AF]"}`}>
          sirhenry.app
        </span>
      </div>
      {/* Screenshot */}
      <Image
        src={src}
        alt={alt}
        width={1280}
        height={800}
        className="w-full h-auto"
        quality={90}
        priority={false}
      />
    </div>
  );
}

export default function FeatureShowcaseSection() {
  return (
    <div id="features">
      {FEATURES.map((feature) => {
        const bg = feature.dark ? "bg-[#0A0A0B]" : "bg-white";
        const tagColor = feature.dark ? "text-[#22C55E]" : "text-[#16A34A]";
        const headingColor = feature.dark ? "text-[#F9FAFB]" : "text-[#111827]";
        const descColor = feature.dark ? "text-[#9CA3AF]" : "text-[#6B7280]";

        return (
          <section key={feature.id} id={feature.id} className={`${bg} py-24 px-6`}>
            <div className="max-w-5xl mx-auto">
              {/* Section header */}
              <div className="text-center mb-12">
                <p className={`text-[11px] font-semibold uppercase tracking-widest ${tagColor} mb-3`}>
                  {feature.tag}
                </p>
                <h2
                  className={`font-bold ${headingColor} mb-4`}
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: "clamp(1.75rem, 3.5vw, 2.25rem)",
                  }}
                >
                  {feature.title}
                </h2>
                <p className={`${descColor} text-base leading-relaxed max-w-2xl mx-auto`}>
                  {feature.description}
                </p>
              </div>

              {/* Screenshot */}
              <div className="mb-12">
                <ScreenshotFrame
                  src={feature.screenshot}
                  alt={`${feature.tag} — ${feature.title}`}
                  dark={feature.dark}
                />
              </div>

              {/* Callout cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {feature.callouts.map((callout) => (
                  <CalloutCard key={callout.title} callout={callout} dark={feature.dark} />
                ))}
              </div>
            </div>
          </section>
        );
      })}
    </div>
  );
}
