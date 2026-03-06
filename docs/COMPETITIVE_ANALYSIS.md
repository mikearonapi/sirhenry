# SirHENRY — Competitive Analysis & Value Proposition

Last updated: 2026-03-06

## The Market Gap

Every personal finance product falls into one of two buckets:

1. **Budgeting tools** (Monarch, Rocket Money, Simplifi) — track where money went, help you spend less
2. **Wealth management** (Empower, Betterment, Wealthfront) — manage investments for people who already have wealth

**Nobody serves the HENRY in the middle** — the person earning $150–500K who needs to figure out how to *become* wealthy. That's SirHENRY.

---

## Competitor Breakdown

### Monarch Money — $8–15/mo
- Account aggregation (13,000+ institutions via Plaid)
- Category + flex budgeting with rollover
- Couples/family collaboration (invite partner or advisor at no extra cost)
- Investment tracking (allocation, gains/losses, trends)
- Goals & savings with progress tracking
- AI assistant (GPT-4 powered — answers questions, but can't take actions)
- Customizable dashboard & reports
- Cross-platform: web + iOS + Android
- No free tier
- **Positioning:** The post-Mint default. Middle ground between simple and advanced budgeting.

### Rocket Money — $6–12/mo premium (free tier available)
- Subscription management & cancellation concierge (killer feature)
- Bill negotiation service (charges 35–60% of savings)
- Basic budgeting (2 custom categories free, unlimited on premium)
- Smart Savings automation (auto-transfers to savings pods)
- Credit score monitoring
- 10M+ users, $2.5B saved for users
- Web access is premium-only
- **Positioning:** "We save you money." Focused on cutting waste, not building wealth.

### TurboTax — $0–139+/filing
- Tax filing software (not financial planning)
- AI-powered Intuit Assist searches 450+ deductions
- Agentic AI automates 90% of standard form data entry
- Expert access: live assisted, full service, physical storefronts (600+ locations in 2026)
- CompleteCheck accuracy guarantee
- Free audit support
- QuickBooks integration for self-employed
- **Positioning:** Tax filing. Reactive, once a year. Not year-round optimization.

### Quicken Simplifi — $4–6/mo
- Spending plan approach (income minus bills = what's left)
- Investment tracking with market data
- Credit score monitoring (VantageScore 3.0 via Equifax)
- Bills & subscription tracking
- Savings goals
- Vehicle tracking (KBB integration)
- Privacy mode for demos
- Account sharing (1 person)
- **Positioning:** Budget-friendly, lightweight personal finance. Not built for complexity.

### Empower (formerly Personal Capital) — 0.49–0.89% AUM
- Requires $100K minimum investable assets
- Robo-advisor + human CFP access
- Tax-loss harvesting, daily rebalancing
- Private client tier at $1M+ (dedicated advisors, investment committee)
- Free financial aggregation tools (net worth, spending, retirement planner)
- **Positioning:** Wealth management for the already-wealthy. A HENRY with $500K pays $2,450–4,450/year.

### Betterment — 0.25% AUM (Premium: 0.65%)
- No minimum to start ($4/mo for accounts under $20K)
- Automated investing, rebalancing, tax-loss harvesting
- Premium tier ($100K min): unlimited CFP access
- Simple goal-based investing
- **Positioning:** Set-and-forget robo-advisor. Low cost, low complexity.

### Wealthfront — 0.25% AUM
- $10 minimum to start
- Modern Portfolio Theory-based ETF portfolios
- Tax-loss harvesting, direct indexing at $100K+
- ESG/SRI options, crypto exposure
- Customizable ETF selection
- **Positioning:** Algorithm-driven investing for hands-off investors.

---

## SirHENRY's Differentiators

### 1. HENRY-Specific Focus
No competitor targets this demographic. Monarch helps you budget groceries. Empower manages millions. SirHENRY answers the question HENRYs actually ask: "I earn well — why am I not wealthy yet, and what do I do about it?"

### 2. Local-First Privacy Architecture
Every competitor centralizes your financial data on their servers. SirHENRY stores everything in a per-user SQLite database — data never leaves your device (except encrypted Plaid sync and PII-scrubbed AI calls). In a post-breach world, this is a genuine competitive moat.

### 3. Agentic AI vs. Chatbot AI
Monarch's AI answers questions. Sir Henry has 30+ tools — recategorizes transactions, triggers bank syncs, updates asset values, manages budgets, creates goals, runs scenarios. The difference between "ask me anything" and "I'll handle it for you."

### 4. Equity Compensation Engine
Nobody else does this. RSU withholding gap analysis, AMT crossover for ISOs, ESPP analysis, concentration risk scoring, departure modeling, vest-by-vest tax projections. A CPA charges $2–5K/year for this analysis.

### 5. Decision Lab (Life Scenario Modeling)
No competitor offers "what if" modeling at this depth. "Can I afford this $700K house?" runs against your full trajectory — exact impact on retirement date, savings rate, Monte Carlo probability, net worth, with before/after comparisons.

### 6. Year-Round Tax Strategy
TurboTax files. SirHENRY optimizes — year-round. Backdoor Roth, mega backdoor, Roth conversion ladders, S-Corp analysis, QBI deductions, tax-loss harvesting, DAF bunching. Proactive, not reactive.

### 7. Priority Waterfall
"Where does my next dollar go?" A personalized, dollar-quantified 10-step financial order of operations based on your actual numbers — not generic advice.

### 8. Flat Fee vs. AUM
~$20/mo ($240/year). A HENRY with $500K in investments pays Empower $2,450–4,450/year. Betterment $1,250/year. SirHENRY provides more comprehensive analysis at a fraction of the cost, with no conflict of interest.

---

## Competitive Positioning Matrix

| Problem | Competitor "Solution" | SirHENRY |
|---|---|---|
| "Where does my money go?" | Monarch: category budgets | Cash flow x-ray with lifestyle creep detection |
| "Am I on track for retirement?" | Simplifi: basic projection | 10,000-run Monte Carlo with equity comp, dual income, life events |
| "What do I do with my RSUs?" | Nobody | Full equity comp engine: withholding gap, AMT, sell strategy |
| "Can I afford this house?" | Nobody | Decision Lab: before/after on everything |
| "Am I overpaying taxes?" | TurboTax: finds deductions at filing time | Year-round AI tax strategy with simulators |
| "Where should my next dollar go?" | Nobody | Priority Waterfall: personalized, dollar-quantified |
| "I need financial advice" | Empower: $2,500+/yr for a CFP | Sir Henry: unlimited AI advisor at $20/mo |
| "Is my data safe?" | Monarch: "trust us" | Local-first: data never leaves your device |

---

## Platform Strategy

### Current
- Web app (Next.js, desktop browser)

### Planned
- **Desktop app** — native experience, local data stays local
- **Mobile app** — need to solve data sync (local-first architecture means figuring out secure device-to-device sync without centralizing data)
- **Family collaboration** — multi-user access for households (partner views, shared goals, combined dashboards)

### Under Evaluation (adds significant complexity)
- **Investment execution** — could integrate with brokerages or provide "one-click" links to execute recommended trades. Risk: becomes an RIA, regulatory burden. Alternative: deep integrations with existing brokerages rather than managing money directly.
- **Tax filing integration** — SirHENRY does strategy, TurboTax does filing. An export/integration that feeds strategy recommendations into filing software would close the loop without building a tax filing engine.
- **Credit score monitoring** — nice-to-have for holistic financial picture. Could integrate a third-party service (Equifax, TransUnion API) rather than building from scratch.

### Not Pursuing (not core to HENRY value prop)
- Bill negotiation / subscription cancellation — HENRYs' problem isn't $12/mo subscriptions, it's $50K/year in lifestyle creep
- Bill negotiation savings — saving $200/year on cable matters less when optimizing $15K in tax strategy

---

## Value Proposition

### One-Liner
> The financial advisor HENRYs actually need — AI-powered, privacy-first, and a fraction of what a wealth manager charges.

### Expanded
> Budgeting apps track where your money went. Wealth managers want clients who are already rich. SirHENRY is built for the gap in between — high earners who need to turn income into wealth. AI that optimizes your taxes, models life decisions against your real numbers, manages your equity comp, and tells you exactly where your next dollar should go. Your data stays on your device. $20/mo, not 1% of your assets.

### The 3 Pillars
1. **See everything** — Cash flow x-ray, net worth, retirement trajectory, peer benchmarks
2. **Decide with confidence** — Model any life decision against your real financial picture
3. **Act on AI guidance** — Not a chatbot. An AI advisor with 30+ tools that works for you.

---

## Free vs. Pro Tier

| Feature | Free | Pro (~$20/mo) |
|---|---|---|
| Financial scoreboard | Full | Full |
| Cash flow (this month) | Full | Full + multi-year projections |
| Retirement trajectory | 10-year, view only | Full horizons + sliders + planner |
| Action plan | Top 3 priorities | Full waterfall + equity comp detail |
| Decision Lab | 1 saved scenario | Unlimited + comparison |
| Sir Henry AI | 5 messages/month | Unlimited |
| Benchmarks | Basic percentile | Detailed (age + income + metro) |
| Tax strategy | — | Full AI tax analyzer + simulators |
| Equity comp engine | — | Full (RSU, ISO, ESPP analysis) |
