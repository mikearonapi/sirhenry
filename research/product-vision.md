# Henry — Product Vision

> "The financial advisor you've been earning."

---

## The One-Liner

**Henry is the AI financial advisor that HENRYs can't currently access — personalized to your situation, focused on the decisions that actually move the needle.**

---

## The Core Insight

The HENRY problem isn't "I don't have enough information about the stock market." It's:

> **"I make great money but I don't know if I'm making the right financial decisions, and I can't tell if I'm on track."**

Every feature, every screen, every interaction in Henry should ladder up to resolving that anxiety.

---

## The Core Loop

Henry answers one meta-question on repeat:

> **"Given everything about my financial life, what should I do next?"**

```
  ┌──────────────────────────────────────────────────────┐
  │                                                      │
  │   ┌──────────┐    ┌──────────┐    ┌──────────┐      │
  │   │ SNAPSHOT │───▶│TRAJECTORY│───▶│ DECISION │      │
  │   │          │    │          │    │          │      │
  │   │ Where am │    │ Where am │    │ What     │      │
  │   │ I now?   │    │ I headed?│    │ should I │      │
  │   │          │    │          │    │ do?      │      │
  │   └──────────┘    └──────────┘    └──────────┘      │
  │        ▲                               │             │
  │        │         ┌──────────┐          │             │
  │        │         │SIR HENRY │          │             │
  │        └─────────│          │◀─────────┘             │
  │                  │ Guide me │                        │
  │                  │ through  │                        │
  │                  │ this     │                        │
  │                  └──────────┘                        │
  │                                                      │
  │              ↻ Repeat as life changes                │
  └──────────────────────────────────────────────────────┘
```

---

## The Four Capabilities

### 1. The Scoreboard — "Where do I stand?"

**Problem it solves**: Cash Flow Mystery (#1) + No Financial Scoreboard (#2)

What it shows:
- **Net worth** with breakdown: liquid / retirement / home equity / other
- **Cash flow summary**: income → taxes → fixed costs → discretionary → wealth building rate
- **Savings rate**: actual vs. required for stated goals
- **On Track / At Risk / Behind** signal — clear, simple, unambiguous
- **HENRY benchmarks**: how you compare to HENRYs your age, income, and metro
- **Trend**: are things improving or deteriorating over time?

What it does NOT show:
- Individual transactions
- Spending by category (no "you spent $X on restaurants")
- Stock prices or market data

**Key design principle**: This screen should be understandable in 10 seconds. One glance tells you whether you're OK or not.

**Data input**: Manual entry to start (income, major expenses, account balances). Account linking as a future enhancement. The barrier to entry should be as low as possible — a 5-minute setup that gives you an instant scoreboard.

---

### 2. The Trajectory — "Where am I headed?"

**Problem it solves**: No Financial Scoreboard (#2) + Decision Paralysis (#3)

What it shows:
- **Monte Carlo projection** of your wealth over 10/20/30 years
- **Confidence bands**: 10th, 25th, 50th, 75th, 90th percentile outcomes
- **Key milestones**: "72% chance of reaching $2.5M by 55"
- **Retirement readiness**: "At your current pace, you can retire at 57 with $8,200/month in today's dollars"
- **What-if adjustments**: slide your savings rate, see the trajectory shift in real-time
- **Time selectors**: 10Y, 20Y, 30Y, To Retirement

What it does NOT show:
- Individual stock projections
- Market predictions
- Portfolio-level analysis

**Key design principle**: This is the hero screen. The thing that draws people back weekly. It should feel powerful but not overwhelming — a single fan chart with clear labels and one or two key numbers.

**Technical note**: Monte Carlo simulations should run on the user's full financial picture (income, savings rate, existing assets, expected returns by asset class, inflation assumptions), not on a single stock or portfolio. This is projecting a *life*, not an investment.

---

### 3. The Decision Lab — "What happens if...?"

**Problem it solves**: Decision Paralysis (#3) + Competing Priorities (#6)

What it shows:
- **Input a decision**: "Buy a $750K house with 20% down"
- **See the impact**: on your trajectory, savings rate, retirement date, risk level
- **Before vs. after**: side-by-side projection comparison
- **Quantified trade-offs**: "This pushes retirement from 55 to 58" or "Your savings rate drops from 18% to 9%"
- **Scenario comparison**: Option A vs. Option B vs. Do Nothing

Decision types to support (prioritized):
1. **Housing**: Buy a home, upgrade, downsize, rent vs. buy
2. **Retirement timing**: "When can I realistically retire?"
3. **Debt decisions**: Pay off loans vs. invest, refinance analysis
4. **Career changes**: New job (salary + equity comp change), one spouse stops working
5. **Education funding**: 529 contributions, private school impact
6. **Equity comp**: Hold vs. sell RSUs, exercise ISOs, ESPP participation
7. **Windfalls**: Bonus, inheritance, settlement — where does it go?
8. **Savings changes**: "What if I increase my 401(k) to max?"

What it does NOT do:
- Execute any transactions
- Recommend specific investments or securities
- Provide legally binding advice

**Key design principle**: The Decision Lab should feel like a conversation, not a form. "I'm thinking about buying a house for around $700K" → Henry asks a few clarifying questions → shows you the impact. Low friction.

---

### 4. Sir Henry — "Talk me through this"

**Problem it solves**: The Advice Gap (#7) + all other problems through conversation

What it does:
- **Conversational AI** that knows your full financial picture
- Ask anything in plain language:
  - "Should I sell my RSUs on vest?"
  - "Can I afford private school for two kids?"
  - "What should I do with a $50K bonus?"
  - "Am I saving enough for retirement?"
  - "Should I do a backdoor Roth? How?"
  - "My RSUs vest in March — what do I need to know?"
- Responds with **your specific numbers** — not generic advice
- **Tax-aware**: knows your bracket, suggests strategies, flags opportunities
- **Equity comp literate**: understands RSUs, ISOs, NSOs, ESPP
- **Points to action**: "Based on your numbers, here's what I'd prioritize" + links to the Priority Waterfall or Decision Lab
- **Proactive nudges** (future): "Your RSUs vest next month — here's what to prepare for" or "You haven't done your backdoor Roth this year — want me to walk you through it?"

What it does NOT do:
- Manage your money
- Execute trades
- Provide legally binding financial advice (always includes appropriate disclaimers)
- Discuss individual stock picks or market predictions

**Key design principle**: Sir Henry should feel like texting a brilliant friend who happens to be a CFP. Direct. Specific. Uses your numbers. Never preachy or condescending. Slightly witty.

---

## The Priority Waterfall (Embedded Feature)

Not a separate page, but a key piece of guidance embedded in the Scoreboard and Sir Henry:

Given your specific situation, here's the order of operations for your next dollar:

```
Example for a typical HENRY ($250K household, 32% bracket, employer match):

1. 401(k) up to employer match      → $4,500/yr free money
2. Pay off 7.2% student loan        → $3,600/yr saved in interest
3. Max HSA (family)                  → $8,300/yr, triple tax advantage
4. Max 401(k)                        → $23,000/yr tax-deferred
5. Backdoor Roth IRA (both spouses) → $14,000/yr tax-free growth
6. Pay off 4.5% student loan        → $2,250/yr saved in interest
7. 529 plan (2 children)            → $10,000/yr for education
8. Taxable investing                 → remainder, tax-loss harvest
```

Personalized. Specific dollar amounts. Updates when circumstances change (new job, new rate, new child, etc.)

---

## What Henry Explicitly Is NOT

These boundaries are as important as the features:

| Henry is NOT | Why not |
|---|---|
| A budgeting app | HENRYs don't need to track every coffee. We work at a higher altitude. |
| A stock trading platform | We don't pick stocks or execute trades. Different product, different problem. |
| A robo-advisor | We don't manage your portfolio. You (or Betterment/Wealthfront) do that. |
| A market data terminal | No S&P charts, no sector heatmaps, no commodity prices. Not relevant to the core problem. |
| An equity screener | No factor scoring, no stock rankings. Not what HENRYs need from us. |
| A tax filing tool | We identify tax strategies; your CPA or TurboTax files the return. |
| For everyone | Built for HENRYs ($150K-$500K). The benchmarks, the language, the decision types — all calibrated for this audience. |

---

## The Value Proposition (In Dollars)

Henry's value isn't abstract. It's quantifiable:

| Optimization | Annual Impact | 20-Year Impact |
|---|---|---|
| Increase savings rate from 12% to 18% (on $250K) | $15,000/year | ~$614,000 |
| Execute backdoor Roth annually ($7K/yr × 2 spouses) | $14,000/year tax-free | ~$575,000 |
| Optimize RSU strategy (sell on vest + diversify) | Prevents $50K-$200K in concentration risk losses | Depends on market |
| Avoid buying $100K more house than you can afford | $600+/month | ~$215,000 |
| Max HSA and invest (not spend) | $8,300/year, triple tax advantage | ~$340,000 |
| Tax-loss harvesting in taxable account | $2,000-$5,000/year in tax savings | $40,000-$100,000 |

A human CFP charges $5K-$15K/year to provide this guidance. Henry provides ~80% of the planning value at a fraction of the cost.

---

## Pricing Philosophy (Preliminary)

Not decided yet, but directional thinking:

- Must be **dramatically cheaper than a human advisor** ($5K-$15K/year)
- Must be **more expensive than a simple calculator** ($80-$120/year) to signal quality
- Sweet spot is likely **$15-$30/month** ($180-$360/year)
- Free tier could include the Scoreboard (hook) with Trajectory + Decision Lab + Sir Henry as premium
- The value delivered ($10K+/year in optimizations) makes even $360/year a 25x+ ROI

---

## The Journey (Brand)

> "Every knight was once a HENRY."

Henry isn't just a tool. It's a guide on the path from high earner to genuinely wealthy. The product should feel like leveling up — from confusion to clarity, from anxiety to confidence, from HENRY to wealthy.

---

*Last updated: February 7, 2026*
