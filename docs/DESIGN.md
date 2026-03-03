# Henry — App Design

> The app should be so simple that a stressed, time-starved professional can open it, understand where they stand financially, and know what to do next — all in under 60 seconds.

---

## The Core Concept

Henry answers one question on repeat:

> **"Given everything about my financial life, what should I do next?"**

That question breaks into four parts, in order:

1. **"Am I okay?"** — show me where I stand
2. **"What should I do?"** — tell me what I'm missing
3. **"What if I...?"** — help me model a big decision
4. **"Help me think about this"** — be my advisor

Parts 1 and 2 are the Home page. Part 3 is the Decisions tab. Part 4 is Henry.

---

## Design Principles

1. **Clarity over completeness.** Show the one number that matters, not twenty that don't.
2. **Answers over data.** Don't show a chart and let them figure it out. Tell them what it means.
3. **5 minutes to value.** From first open to "this is useful" in under 5 minutes.
4. **Progressive depth.** Surface is simple. Depth is available. Don't overwhelm — reward exploration.
5. **No dead ends.** Every screen makes it obvious what to do next.
6. **Problem-driven.** Every element on screen exists to solve a validated problem. If it doesn't, remove it.

---

## How the 7 Problems Map to the App

HENRYs have 7 validated problems. Here's exactly where each one gets solved:

| # | Problem | User's words | Where it's solved | How |
|---|---|---|---|---|
| 1 | Cash Flow Mystery | "Where does my money go?" | **Home → Money Flow** | Income, expenses, savings, leak — at a glance |
| 2 | No Scoreboard | "Am I on track?" | **Home → Status + Trajectory** | Net worth, savings rate, status badge, retirement readiness |
| 3 | Decision Paralysis | "Can I afford this house?" | **Decisions tab** | Before/after modeling with your real numbers |
| 4 | Tax Complexity | "I'm overpaying on taxes" | **Home → Action Plan** | Tax moves surface as prioritized actions with dollar amounts |
| 5 | Equity Comp | "What do I do with my RSUs?" | **Home → Action Plan** | Vest alerts, tax shortfalls, concentration risk — as action items |
| 6 | Competing Priorities | "Where should my next dollar go?" | **Home → Action Plan** | Unified priority list ordered by impact |
| 7 | Advice Gap | "I need guidance" | **Henry tab** | AI advisor that knows your full picture |

**The key design decision:** Problems 4, 5, and 6 are all variations of "here's money you're leaving on the table." Instead of three separate features, they merge into ONE section on the home page: **Your Action Plan.** A single, prioritized list of what to do next — some items are tax moves, some are equity comp actions, some are allocation decisions. The user doesn't need to know which problem category each one belongs to. They just see: *"Here's what would make the biggest difference, in order, with dollar amounts."*

---

## Navigation

Three tabs. That's it.

```
┌─────────────────────────────────────────────────┐
│  Henry                                    [👤]  │
│                                                 │
│              [ Screen Content ]                 │
│                                                 │
├─────────────────┬─────────────┬─────────────────┤
│      Home       │  Decisions  │     Henry       │
│       🏠        │      ⚖️      │      💬         │
└─────────────────┴─────────────┴─────────────────┘
```

| Tab | User thinks... | Visits... |
|---|---|---|
| **Home** | "Show me my money" | Weekly |
| **Decisions** | "What if I..." | When facing a major choice |
| **Henry** | "I have a question" | Anytime |

Profile (👤) lives in the header. It's where you update your numbers and manage your account. Visited monthly or after life changes.

Three concepts. No ambiguity about what goes where.

---

## The Home Page

Home is the app. It's where you spend 90% of your time. It's a single scrollable page that tells a story in four sections. Each section answers a different question. You can stop scrolling at any point and you've already gotten value.

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  SECTION 1: YOUR STATUS                         │
│  "Am I okay?"                                   │
│  Solves: #2 No Scoreboard                       │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  SECTION 2: YOUR MONEY FLOW                     │
│  "Where does my money go?"                      │
│  Solves: #1 Cash Flow Mystery                   │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  SECTION 3: YOUR TRAJECTORY                     │
│  "Where am I headed?"                           │
│  Solves: #2 No Scoreboard (forward-looking)     │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  SECTION 4: YOUR ACTION PLAN                    │
│  "What should I do?"                            │
│  Solves: #4 Tax, #5 Equity Comp, #6 Priorities  │
│                                                 │
└─────────────────────────────────────────────────┘
```

The story: **Where you stand → Where your money goes → Where you're headed → What to do about it.**

---

### Section 1: Your Status

**Problem solved:** #2 — No Financial Scoreboard
**Time to scan:** 3 seconds
**Core insight:** "Am I okay or not?"

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  Good morning, Mike                 ⚠ AT RISK   │
│                                                 │
│  Net Worth              Savings Rate            │
│  $347,000               11.2%                   │
│  ↑ $12K (90d)           Need: 18%               │
│                                                 │
│  ┌────────┬──────────┬────────┬────────┐        │
│  │Liquid  │Retirement│ Home   │ Debt   │        │
│  │ $42K   │  $185K   │ $220K  │ -$100K │        │
│  └────────┴──────────┴────────┴────────┘        │
│                                                 │
│  38th percentile of HENRYs your age in SF       │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Components:**

| Component | What it does |
|---|---|
| `StatusBadge` | On Track (green) / At Risk (amber) / Behind (red). The single most important element. Derived from savings rate vs. required rate + trajectory probability. |
| `NetWorthDisplay` | Single number + trend arrow (30d or 90d change). Tap → net worth breakdown drill-down. |
| `SavingsRateDisplay` | Current rate + "Need: X%" comparison. The gap between these two numbers drives the status badge. |
| `AssetBar` | Mini horizontal bar showing liquid / retirement / home / debt proportions. Tap any segment → detail. |
| `BenchmarkLine` | "Xth percentile of HENRYs your age and income in [metro]." Comparison against the right cohort, not the general population. |

**Why this section works for Problem #2:**
The research says HENRYs need: net worth breakdown, savings rate (actual vs. required), clear signal (on track / at risk / behind), benchmarking against similar HENRYs, and trend over time. This section has all five, visible in 3 seconds.

---

### Section 2: Your Money Flow

**Problem solved:** #1 — Cash Flow Mystery
**Time to scan:** 5 seconds
**Core insight:** "You make $16,500/mo. Here's exactly where it goes."

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  THIS MONTH                                     │
│                                                 │
│  In        $16,500  ████████████████████████     │
│  Taxes     -$5,900  █████████░░░░░░░░░░░░░░     │
│  Living    -$5,400  ████████░░░░░░░░░░░░░░░     │
│  Saving    -$2,100  ███░░░░░░░░░░░░░░░░░░░░     │
│                     ─────────────────────────    │
│  Left       $3,100  ████░░░░░░░░░░░░░░░░░░░     │
│                                                 │
│  ~$3,100/mo isn't going anywhere specific.      │
│  That's $37,200/yr.                             │
│                                                 │
│                         [ See full breakdown → ] │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Components:**

| Component | What it does |
|---|---|
| `CashFlowBar` | Four horizontal bars — proportional, color-coded. Income (green), taxes (gray), living expenses (blue), savings (purple). Instant visual of where money goes. |
| `LeakCallout` | The "Left" line and its callout. This is the number that catches lifestyle creep. If it's large and positive, it's money evaporating. If it's negative, they're spending more than they earn. Either way: a wake-up call. |
| `BreakdownLink` | Tap → full cash flow drill-down with income by source, tax estimate, expenses by category, multi-year projections. |

**Why this section works for Problem #1:**
The research says HENRYs need a "cash flow x-ray" — not line-item budgeting, but the high-altitude view: what comes in, what goes to taxes, what goes to living, what gets saved, and what's left. The insight is never "you spent $47 at Starbucks." It's "you have $3,100/mo with no purpose — that's $37K/yr disappearing."

**Design note — four lines, not five:**
The original design had income, expenses, savings, and "remaining." But taxes are such a huge piece of the HENRY puzzle (effective rates of 35-45%) that they deserve their own line. Seeing "$5,900 in taxes" on a $16,500 income is a visceral moment. And it sets up the Action Plan section below, where tax optimization opportunities appear.

---

### Section 3: Your Trajectory

**Problem solved:** #2 — No Scoreboard (forward-looking)
**Time to scan:** 10 seconds
**Core insight:** "At your current pace, here's what happens."

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  WHERE YOU'RE HEADED                            │
│                                                 │
│       ╱‾‾‾‾‾‾╲                                 │
│     ╱──────────╲  Median: $1.6M at 55           │
│   ╱──────────────╲                              │
│  ╱                                              │
│  Now       10Y       20Y       Retire            │
│                                                 │
│  62% chance you'll reach your retirement goal    │
│                                                 │
│  At 55, that's ~$5,300/mo in today's dollars     │
│  You said you need ~$7,500/mo                    │
│                                                 │
│                            [ See full view → ]   │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Components:**

| Component | What it does |
|---|---|
| `MiniFanChart` | Simplified Monte Carlo fan chart. Three bands: optimistic (p75-p90), median (p50), conservative (p10-p25). Not interactive on the home page — tap for the full interactive version. |
| `ProbabilityStatement` | One sentence: "X% chance you'll reach your retirement goal." This is the number that drives behavior. |
| `RetirementGapLine` | What the trajectory delivers vs. what they said they need. "You'll have $5,300/mo. You said you need $7,500." This gap is the motivator. If there's no gap, it's a celebration. |
| `TrajectoryLink` | Tap → full trajectory with time horizon selector, interactive sliders, and retirement planner drill-down. |

**Why this section works for Problem #2 (forward-looking):**
Status (Section 1) answers "where am I now." Trajectory answers "where am I headed." The research says HENRYs want "something that shows me where I'll be in 20 years." The fan chart does that. The retirement gap line connects it to something real: "can I actually live the life I want?"

**Design note — retirement is woven in, not a separate page:**
Retirement planning isn't a standalone feature. It's the context that makes the trajectory meaningful. The home page shows the gap. The drill-down lets you adjust retirement age, expenses, income sources, and watch the numbers shift. You don't need to find a "Retirement Planner" — you tap your trajectory and it's right there.

---

### Section 4: Your Action Plan

**Problems solved:** #4 Tax Complexity, #5 Equity Comp, #6 Competing Priorities
**Time to scan:** 15-30 seconds
**Core insight:** "Here's what would make the biggest difference — in order."

This is the most important design decision in the app. Three separate problems — tax optimization, equity comp management, and dollar allocation — merge into **one unified, prioritized list of actions.** Each action has a dollar amount. They're ordered by impact. The user doesn't need to know which "problem category" each one belongs to. They just see: *what to do next.*

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  YOUR ACTION PLAN                               │
│  $38,600/yr in opportunities                    │
│                                                 │
│  ⚠ RSU vest Mar 15 — $37K incoming              │
│    Tax shortfall: $3,700 (22% withheld,          │
│    you owe 32%). Set aside now.                  │
│    41% of your wealth is in employer stock.      │
│    [ What should I do? → ]                       │
│                                                 │
│  ── YOUR PRIORITIES ────────────────────────     │
│                                                 │
│  ✅ 1. 401(k) to match — $4,500/yr (done)       │
│                                                 │
│  ⬜ 2. Pay off 7.2% debt — saves $864/yr        │
│     $12K balance · [ Walk me through this → ]    │
│                                                 │
│  ⬜ 3. Max HSA — $6,100/yr untapped             │
│     Triple tax advantage                         │
│     [ Walk me through this → ]                   │
│                                                 │
│  ⬜ 4. Backdoor Roth — $14,000/yr               │
│     Tax-free growth for both spouses             │
│     [ Walk me through this → ]                   │
│                                                 │
│  ⬜ 5. Pay off 5.5% loans — saves $4,675/yr     │
│                                                 │
│     + 3 more priorities                          │
│     [ See full plan → ]                          │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Components:**

| Component | What it does | Problem |
|---|---|---|
| `OpportunityTotal` | "$38,600/yr in opportunities" — the aggregate dollar amount of everything they're not doing. Grabs attention. | All three |
| `EquityAlert` | Shown only if user has RSU/option data. Surfaces the next vesting event, tax withholding gap, and concentration risk. Time-sensitive, so it appears first when relevant. | #5 Equity Comp |
| `PriorityList` | Ordered list of actions. Each has: status (done/not done), dollar impact, one-line explanation, and "Walk me through this" link to Henry. The order is personalized — driven by interest rates, tax brackets, employer match, and what they're already doing. | #6 Priorities |
| `TaxMoves` | Tax optimization opportunities (backdoor Roth, HSA, tax-loss harvesting) appear as items in the priority list with their dollar amounts. They're not labeled "tax strategy" — they're just high-impact actions. | #4 Tax |
| `WalkMeThroughLink` | On each priority item. Opens Henry with the topic pre-loaded: "Walk me through how a backdoor Roth works with my specific situation." | #7 Advice Gap |
| `FullPlanLink` | "See full plan →" expands to the complete waterfall with all steps, detailed math, and completion tracking. | #6 Priorities |

**Why this section works for Problems #4, #5, and #6:**

The research says:
- Tax (#4): "You're leaving $8,400/yr on the table by not doing a backdoor Roth." → The backdoor Roth shows up as priority #4 with "$14,000/yr" right there.
- Equity (#5): "Your RSU vesting will push you into the 35% bracket." → The equity alert appears at the top with exact dollar amounts.
- Priorities (#6): "Given your rates and brackets, here's the waterfall for your next dollar." → The priority list IS the waterfall, personalized with their numbers.

**Design note — why these merge into one section:**
A HENRY doesn't think "I have a tax problem AND an equity comp problem AND an allocation problem." They think "what should I do with my money?" The Action Plan answers that question holistically. A tax move and an equity comp action appear in the same list because they're competing for the same dollars. The user sees one unified, ordered plan — not three separate frameworks.

**Design note — the equity alert:**
The equity comp alert sits above the priority list when relevant (vest approaching, concentration risk high). It's not a permanent fixture — it appears when there's something time-sensitive. This makes it attention-grabbing without cluttering the home page for users who don't have equity comp.

---

### Home Page Summary

| Section | Problems | User question | Time to scan |
|---|---|---|---|
| 1. Status | #2 | "Am I okay?" | 3 seconds |
| 2. Money Flow | #1 | "Where does my money go?" | 5 seconds |
| 3. Trajectory | #2 | "Where am I headed?" | 10 seconds |
| 4. Action Plan | #4, #5, #6 | "What should I do?" | 15-30 seconds |

Total scan time: **under 60 seconds.** A HENRY opens the app, scrolls once, and knows: where they stand, where their money goes, where they're headed, and what to do about it. Every one of the "awareness" and "optimization" problems is addressed on a single scrollable page.

---

## The Decisions Tab

**Problem solved:** #3 — Decision Paralysis
**User thinks:** "I'm considering something big. What happens if I do it?"

This is the highest-impact feature in the app. Major financial decisions cost $50K-$500K+ when wrong. The Decision Lab shows the before/after impact on your real trajectory — not generic calculators, not Reddit opinions, but your actual numbers.

### Decisions Home (`/decisions`)

```
┌─────────────────────────────────────────────────┐
│  Decisions                       [ + New ]      │
├─────────────────────────────────────────────────┤
│                                                 │
│  What are you thinking about?                   │
│                                                 │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │🏠 Buy  │ │💼 New  │ │🏦 Pay  │ │🎯 When │   │
│  │a Home  │ │Job     │ │Off Debt│ │to      │   │
│  │        │ │        │ │vs.     │ │Retire  │   │
│  │        │ │        │ │Invest  │ │        │   │
│  └────────┘ └────────┘ └────────┘ └────────┘   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │💰 Wind-│ │🚗 Buy │ │🎓 Fund │ │📈 Boost│   │
│  │fall /  │ │a Car   │ │School /│ │Savings │   │
│  │Bonus   │ │        │ │College │ │Rate    │   │
│  └────────┘ └────────┘ └────────┘ └────────┘   │
│                                                 │
│  Or just ask Henry:                             │
│  "Can I afford a $700K house?"                  │
│                                                 │
│  ── SAVED SCENARIOS ────────────────────────    │
│                                                 │
│  🏠 Buy a Home — $750K             2 weeks ago  │
│     Retirement: 55 → 60 · Savings: 18% → 9%    │
│                                                 │
│  🏠 Buy a Home — $650K             2 weeks ago  │
│     Retirement: 55 → 57 · Savings: 18% → 13%   │
│     [ Compare these two → ]                     │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Components:**

| Component | What it does |
|---|---|
| `DecisionTypeGrid` | 8 decision types as tappable cards. Covers the decisions HENRYs actually face (from r/HENRYfinance research). |
| `HenryShortcut` | "Or just ask Henry" — for users who'd rather describe their decision in words than pick a category. Opens Henry pre-filled. |
| `SavedScenarioCard` | Previously modeled decisions with key impact stats. Tap to view full result. |
| `CompareLink` | When 2+ scenarios of the same type exist: "Compare these." Opens side-by-side view. |

### Decision Builder (`/decisions/new/[type]`)

The decision builder is conversational — a few questions, not a form. Each decision type has its own inputs, but the output format is universal: before vs. after.

```
┌─────────────────────────────────────────────────┐
│  ← Back                  Buy a Home             │
├─────────────────────────────────────────────────┤
│                                                 │
│  What price range?          [ $750,000    ]     │
│  Down payment?              [ 20% ▾ ] = $150K   │
│  Mortgage rate?             [ 6.5%  ]           │
│                                                 │
│  Your current rent: $2,800/mo (from profile)    │
│                                                 │
│                        [ See the Impact → ]     │
│                                                 │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
│                                                 │
│  ┌──────────────────┬──────────────────┐        │
│  │     BEFORE       │     AFTER        │        │
│  │                  │                  │        │
│  │  Savings:  18%   │  Savings:   9% ↓ │        │
│  │  Retire:   55    │  Retire:   60  ↓ │        │
│  │  Success:  84%   │  Success:  51% ↓ │        │
│  │  @55:      $2.1M │  @55:     $1.4M↓ │        │
│  └──────────────────┴──────────────────┘        │
│                                                 │
│  Monthly housing: $2,800 → $4,600 (+$1,800)     │
│  Down payment from savings: -$150K              │
│                                                 │
│  "This pushes retirement back ~5 years and       │
│   cuts your savings rate in half."               │
│                                                 │
│  [ Save ] [ Try different price ] [ Ask Henry ]  │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Components:**

| Component | What it does |
|---|---|
| `DecisionInputs` | Type-specific inputs. Kept minimal — 3-5 fields per decision. Pre-fills known values from profile ("Your current rent: $2,800"). |
| `BeforeAfterCard` | The core value. Side-by-side comparison of 4 key metrics: savings rate, retirement age, probability of success, net worth at retirement. Direction arrows (↑/↓) and color-coded (green = better, red = worse). |
| `ImpactDetails` | Specific dollar impacts: monthly cost change, one-time cost, etc. |
| `InsightSentence` | One plain-English sentence interpreting the result. Written by the engine, not the user. |
| `ActionBar` | Save, iterate (try different numbers), or ask Henry for advice on the result. |

**Decision types and their inputs:**

| Decision | Inputs needed | Key output |
|---|---|---|
| Buy a Home | Price, down payment %, rate | Monthly payment change, retirement shift |
| New Job | New salary, bonus, RSUs, signing bonus | Net income change after tax, trajectory impact |
| Pay Off Debt vs. Invest | Debt details, extra payment amount | Interest saved vs. investment gained |
| When to Retire | Target age (or "find earliest") | Required portfolio, probability, lifestyle supported |
| Windfall / Bonus | Amount, allocation (debt/invest/spend) | Net worth impact at 5/10/20 years by strategy |
| Buy a Car | Price, down payment, loan terms | Monthly cost, savings rate impact |
| Fund School / College | Tuition/yr, years, kids | Total cost, retirement shift, 529 contribution needed |
| Boost Savings Rate | New target rate | Retirement shift, probability improvement |

**Why this works for Problem #3:**
The research says HENRYs ask Reddit "can I afford a $1.6M house on $450K?" because they have no tool that models it against their full picture. The Decision Lab does exactly that — and unlike Reddit, it uses their actual numbers, not opinions from strangers.

---

## The Henry Tab

**Problem solved:** #7 — The Advice Gap (and all other problems through conversation)
**User thinks:** "I have a question and I want a real answer."

Sir Henry is the AI advisor that knows your complete financial picture. It's the feature that closes the advice gap — the thing a $15K/year CFP does, available instantly, for $20/month.

### Chat Home (`/henry`)

```
┌─────────────────────────────────────────────────┐
│  Sir Henry                        [ + New Chat ] │
├─────────────────────────────────────────────────┤
│                                                 │
│  Recent:                                        │
│  ┌─────────────────────────────────────────┐    │
│  │ RSU vesting strategy              2d ago│    │
│  │ Backdoor Roth walkthrough        1w ago│    │
│  │ Can we afford private school?    2w ago│    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ┌──────────────────┐ ┌──────────────────┐      │
│  │ Am I on track    │ │ What should I    │      │
│  │ for retirement?  │ │ do with my RSUs? │      │
│  └──────────────────┘ └──────────────────┘      │
│  ┌──────────────────┐ ┌──────────────────┐      │
│  │ Can I afford     │ │ Should I max my  │      │
│  │ this house?      │ │ 401(k) or pay    │      │
│  │                  │ │ off loans?       │      │
│  └──────────────────┘ └──────────────────┘      │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  Ask Henry anything...              [→] │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Chat Thread (`/henry/[id]`)

```
┌─────────────────────────────────────────────────┐
│  ← Back              RSU Vesting Strategy       │
├─────────────────────────────────────────────────┤
│                                                 │
│              Should I sell my RSUs  ┐            │
│              when they vest?        │ YOU        │
│                                    ┘            │
│                                                 │
│  HENRY:                                         │
│                                                 │
│  Your next vest is March 15 — 200 shares        │
│  at ~$185 = $37,000.                            │
│                                                 │
│  Tax: At your 32% rate, that's $11,840.         │
│  Payroll withholds 22% ($8,140) — you'll        │
│  owe an extra $3,700 in April.                  │
│                                                 │
│  Concentration: 41% of your investable          │
│  assets are in employer stock. That's high.     │
│                                                 │
│  I'd sell on vest, set aside $3,700 for         │
│  taxes, and invest the rest in a diversified    │
│  index fund.                                    │
│                                                 │
│  Want me to model what diversifying             │
│  looks like over 10 years?                      │
│                                                 │
│  [ Model This Decision ]                        │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  Type a message...                  [→] │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Components:**

| Component | What it does |
|---|---|
| `RecentConversations` | Past chats with title and timestamp. Persistent — reference past advice. |
| `SuggestedQuestions` | 4 personalized prompts based on profile + time of year + what they haven't asked about yet. |
| `ChatInput` | Text input + send. Always visible at bottom. |
| `MessageBubble` | User messages (right) and Henry messages (left). |
| `HenryResponse` | Henry's messages use **bold** for key numbers, structured formatting for clarity, and inline action buttons when relevant. |
| `InlineActionButton` | "Model This Decision" appears when Henry's answer involves a decision that could be modeled in the Decision Lab. Bridges directly. |
| `TypingIndicator` | "Henry is thinking..." while response generates. |

**What Henry can do:**

| Capability | Example | Problem |
|---|---|---|
| Answer with your numbers | "Should I sell RSUs?" → response uses their marginal rate, share count, concentration % | #5 Equity |
| Walk through strategies | "How does a backdoor Roth work?" → step-by-step with their IRA balance and income | #4 Tax |
| Explain the Action Plan | "Why is HSA my #3 priority?" → explains the math behind the ordering | #6 Priorities |
| Trigger Decision Lab | "What if I buy a $700K house?" → starts a decision scenario | #3 Decisions |
| Interpret trajectory | "Why is my probability only 62%?" → explains the drivers | #2 Scoreboard |
| Prioritize a windfall | "What do I do with a $50K bonus?" → runs through waterfall with allocations | #6 Priorities |

**Why this works for Problem #7:**
The research says HENRYs need "an accessible, knowledgeable advisor that knows their complete financial picture, is available when they have a question, gives specific personalized answers, and doesn't cost $15K/year." That's Henry.

---

## How Everything Connects

Every element in the app links to related elements. The user should never hit a dead end or wonder "where do I go to learn more about this?"

```
                    HOME
                     │
       ┌─────────────┼─────────────┐
       │             │             │
   Status      Money Flow     Trajectory
       │             │             │
       │        ┌────┘             │
       │        │                  │
       ▼        ▼                  ▼
            ACTION PLAN ──────► HENRY ◄───── DECISIONS
                │                  │              │
                │                  └──────────────┘
                │
                ▼
           (drill-downs)
```

**Specific cross-links:**

| From | To | How |
|---|---|---|
| Status → savings rate gap | Action Plan | Scroll down (it's the same page) |
| Money Flow → taxes line | Action Plan (tax items) | Scroll down |
| Money Flow → "see full breakdown" | Cash Flow drill-down | Tap link |
| Trajectory → "62% chance" | Trajectory drill-down | Tap chart |
| Trajectory → retirement gap | Retirement planner (in drill-down) | Tap link |
| Action Plan → equity alert | Henry (pre-filled: "tell me about my RSU vest") | "What should I do?" link |
| Action Plan → any priority item | Henry (pre-filled with that topic) | "Walk me through this" link |
| Action Plan → "see full plan" | Waterfall drill-down | Tap link |
| Henry response → decision | Decision Lab (pre-filled) | "Model This Decision" button |
| Henry response → numbers | Home (scrolls to relevant section) | "See your numbers" link |
| Decision result → Henry | Henry (pre-filled with scenario context) | "Ask Henry" button |
| Decision result → trajectory | Home trajectory with overlay | "See on trajectory" link |
| Profile → any data edit | Home recalculates everything | Automatic |

---

## Drill-Downs (Depth Behind Home Sections)

Each home section is scannable in seconds. Tapping "→" reveals depth. These are not separate pages in the navigation — they're detail views accessed from Home. The back button always returns to Home.

### Cash Flow Detail (from Section 2)

**Route:** `/home/cash-flow`

Shows the full monthly cash flow broken into:
- Income by source (salary, bonus, RSU, partner, other)
- Tax estimate breakdown (federal, state, FICA)
- Expenses by category (housing, childcare, transport, food, etc.)
- Savings by destination (401k, HSA, taxable, etc.)
- Multi-year projections (toggle: 2Y / 3Y / 5Y / 10Y)

Multi-year projections account for salary growth, RSU vesting schedules, time-bound expenses ending (childcare, car loan payoff), and scheduled life events. The key event timeline shows: "2028: childcare ends → frees $2,400/mo."

### Trajectory Detail (from Section 3)

**Route:** `/home/trajectory`

Full interactive Monte Carlo fan chart with:
- Time horizon selector (2Y / 5Y / 10Y / To Retirement)
- Savings rate slider — change it, watch the fan chart shift in real-time
- Key milestone markers ("50% chance of $1M by age 42")
- Decision overlay — toggle a saved Decision Lab scenario onto the chart

Below the chart: **Retirement Planner** — a section (not a separate page) where you can adjust:
- Retirement age (slider)
- Life expectancy (slider)
- Monthly retirement expenses (% of current or custom breakdown)
- Retirement income sources (Social Security, pension, rental, part-time)
- See: required portfolio, current trajectory, gap, probability

Every slider change recalculates in real-time.

### Full Action Plan (from Section 4)

**Route:** `/home/actions`

The complete priority waterfall with all steps. Each step shows:
- Priority number and action
- Dollar impact per year
- Completion status (done / in progress / not started)
- Why this is the priority (one-sentence explanation)
- "Walk me through this →" link to Henry

If equity comp data exists: full vesting calendar, concentration risk analysis, hold vs. sell guidance for each upcoming vest.

---

## Onboarding

**Purpose:** Collect minimum data to generate a meaningful Home page in under 5 minutes.
**Principle:** Get to the aha moment fast. Capture the basics. Refine later.

### The Aha Moment

The goal of onboarding is to get the user to this screen as fast as possible:

```
"You're saving 11% of your income.
 You need 18% to retire at 55.
 You're leaving $38,600/yr on the table."
```

If they see that — with their real numbers — they're hooked.

### Flow

```
Sign Up → Step 1 → Step 2 → Step 3 → Step 4 → Home (instant Scoreboard)
           30s       60s       60s       60s
```

**Step 1: About You (30 seconds)**

| Field | Purpose | Default |
|---|---|---|
| Your age | Retirement timeline, benchmarking | Required |
| Partner? (Y/N → age) | Dual income modeling | No |
| Kids? (Y/N → count, ages) | Childcare, education timelines | No |
| Where you live (state + metro) | Tax rate, HCOL benchmarking | Required |
| Retirement target age | The anchor for all projections | 65 |

**Step 2: What You Earn (60 seconds)**

| Field | Purpose | Shown when... |
|---|---|---|
| Compensation types (checkboxes) | Determines which fields appear | Always |
| Base salary (annual) | Core income | Always |
| Bonus target (%) | Bonus income | "Bonus" checked |
| RSU annual vest value | Equity income | "RSUs" checked |
| Partner's salary | Second income | Partner = Yes |
| Household total (derived) | Confirmation | Always (bottom) |

Only show fields for selected comp types. RSU starts simple ("annual vest value") — they can add vesting schedule detail later in Profile.

**Step 3: What You Have & Owe (60 seconds)**

| Field | Purpose |
|---|---|
| Retirement accounts (combined) | Net worth - retirement |
| Cash & savings | Net worth - liquid |
| Taxable investments | Net worth - invested |
| Home equity (value - mortgage) | Net worth - home ($0 if renting) |
| Student loans (balance + rate) | Debt + priority ordering |
| Other debt (balance + rate) | Debt + priority ordering |
| Net worth (derived) | Confirmation (bottom) |

**Step 4: Monthly Snapshot (60 seconds)**

| Field | Purpose |
|---|---|
| Housing (rent/mortgage + tax + ins) | Expense - fixed |
| Childcare / education | Expense - fixed, time-bound |
| Everything else | Expense - variable (one number) |
| Retirement contributions (401k, IRA) | Savings |
| Other savings / investing | Savings |
| Savings rate (derived) | The aha moment preview (bottom) |

The savings rate appears at the bottom of Step 4 with context: "Your savings rate: ~11%. Most HENRYs need 15-20%." This is the first hint of the aha moment. Then: **"See Your Results →"**

### Post-Onboarding Enrichment

After the user sees their Home page, they're motivated to add detail. The app prompts them where it matters:

| Enrichment | Prompt | Where shown |
|---|---|---|
| RSU vesting details | "Add your vesting schedule for precise projections and tax alerts" | Action Plan equity section |
| Expense breakdown | "Break down your expenses for a sharper cash flow picture" | Money Flow section |
| Individual accounts | "Add your accounts for contribution tracking and optimization" | Profile |
| Retirement expenses | "What does your ideal retirement look like?" | Trajectory → Retirement planner |
| Life goals | "What are you planning for?" (house, school, etc.) | Profile |

Each enrichment makes the app smarter. The user sees the improvement: "Adding your RSU details made your projections 40% more precise."

---

## Profile (👤 Header Icon)

**Route:** `/profile`
**Purpose:** View and edit all financial data. Manage account.
**Visit frequency:** Monthly, or after life changes.

### Profile Home

Summary cards with edit links:

```
┌─────────────────────────────────────────────────┐
│  ← Back                   Your Profile          │
├─────────────────────────────────────────────────┤
│                                                 │
│  💰 INCOME                      [ Edit → ]      │
│  Household: $377,000/yr                         │
│  Salary: $180K · Bonus: $27K · RSU: $50K        │
│  Partner: $120K                                 │
│                                                 │
│  📋 EXPENSES                    [ Edit → ]      │
│  Monthly: $8,700                                │
│  Housing: $3,800 · Childcare: $2,400            │
│                                                 │
│  🏦 ASSETS                      [ Edit → ]      │
│  Total: $362,000                                │
│  Retirement: $185K · Liquid: $42K · Home: $120K │
│                                                 │
│  💳 DEBTS                       [ Edit → ]      │
│  Total: $97,000 · Avg rate: 5.8%               │
│                                                 │
│  👤 PERSONAL                    [ Edit → ]      │
│  34 · SF, CA · Married, 2 kids · Retire at 55  │
│                                                 │
│  ─────────────────────────────────────────      │
│  Plan: Pro ($20/mo)     [ Manage → ]            │
│  [ Sign Out ]                                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

Each "Edit →" opens an editor for that section. Editors have:
- Editable fields matching the data model in FEATURES.md
- Running total at top (updates as you type)
- "Save" button (sticky at bottom)
- "Add" capability (add income streams, expense categories, accounts, debts)

---

## Free vs. Pro

| Feature | Free | Pro |
|---|---|---|
| **Home — Status** | Full | Full |
| **Home — Money Flow** | This month only | + multi-year projections |
| **Home — Trajectory** | 10-year, no interaction | Full horizons + sliders + retirement planner |
| **Home — Action Plan** | Top 3 priorities | Full waterfall + equity comp detail |
| **Decisions** | 1 saved scenario | Unlimited + comparison |
| **Henry** | 5 messages/month | Unlimited |
| **Benchmarks** | Basic percentile | Detailed (age + income + metro) |
| **Price** | $0 | ~$20/month |

The free tier delivers a real aha moment. The paywall hits when they want depth.

---

## Complete Route Map

| Route | Parent | Purpose |
|---|---|---|
| `/` | — | Landing page |
| `/login` | — | Sign in |
| `/signup` | — | Create account |
| `/onboarding` | — | Step 1: About You |
| `/onboarding/income` | — | Step 2: What You Earn |
| `/onboarding/balance-sheet` | — | Step 3: Have & Owe |
| `/onboarding/monthly` | — | Step 4: Monthly Snapshot |
| `/home` | Tab 1 | Home (scrollable: Status + Flow + Trajectory + Actions) |
| `/home/cash-flow` | Home | Cash flow detail + projections |
| `/home/trajectory` | Home | Full trajectory + retirement planner |
| `/home/actions` | Home | Full action plan + waterfall + equity detail |
| `/decisions` | Tab 2 | Decision types + saved scenarios |
| `/decisions/new/[type]` | Decisions | Decision builder (type-specific) |
| `/decisions/[id]` | Decisions | Saved decision result |
| `/decisions/compare` | Decisions | Side-by-side comparison |
| `/henry` | Tab 3 | Chat home + recent + suggested |
| `/henry/[id]` | Henry | Conversation thread |
| `/profile` | Header | Profile overview |
| `/profile/income` | Profile | Compensation editor |
| `/profile/expenses` | Profile | Expense editor |
| `/profile/assets` | Profile | Asset editor |
| `/profile/debts` | Profile | Debt editor |
| `/profile/settings` | Profile | Account settings + subscription |

**22 routes total.** Every one has a purpose mapped to a validated problem.

---

## Cross-Platform

| Element | Web | Mobile |
|---|---|---|
| Navigation | Bottom tab bar | Bottom tab bar |
| Home page | Single column (could be two on wide screens) | Single column, scrollable |
| Decision Lab | Side-by-side before/after | Stacked before/after |
| Henry Chat | Panel or full-page | Full-screen |
| Charts | Hover for details | Tap for details |

Mobile-first. If it works great on a phone, it works everywhere.

---

## What's NOT in V1

- Account linking (Plaid) — manual entry only
- Portfolio analysis or investment picks
- Tax filing
- Transaction tracking
- Push notifications
- Multiple currencies
- Proactive nudges (time-sensitive alerts like "RSU vest in 3 days")

V1 must nail: **Home (all 4 sections) → Decisions → Henry.** The 7 problems, addressed simply.

---

*This document is the authoritative source for app design. For data models and calculation logic, see `docs/FEATURES.md`. For research behind the problems, see `research/problems.md`.*

*Last updated: February 8, 2026*
