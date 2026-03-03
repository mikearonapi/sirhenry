# Henry — Feature Requirements

> This document defines the detailed feature requirements, data models, and user flows for Henry. It is the authoritative source for what each feature does, what data it needs, and how features connect to each other.

---

## Guiding Principle

Henry is a **life planning** tool, not a budgeting app. The core loop is:

1. **Understand where you are** — income, expenses, assets, liabilities
2. **Define where you want to go** — goals, retirement, lifestyle choices
3. **See the gap** — what's on track, what's at risk, what's behind
4. **Make decisions that close the gap** — model choices before committing
5. **Repeat as life changes**

Every feature exists to serve this loop. If it doesn't, it doesn't belong.

---

## Table of Contents

1. [Core Data Model](#1-core-data-model)
2. [The Cash Flow Engine](#2-the-cash-flow-engine)
3. [Feature Specifications](#3-feature-specifications)
4. [Information Architecture](#4-information-architecture)
5. [Onboarding Flow](#5-onboarding-flow)
6. [Updated Page Map](#6-updated-page-map)

---

## 1. Core Data Model

Everything in Henry flows from three inputs: **what comes in** (compensation), **what goes out** (expenses), and **what you have and owe** (balance sheet). These feed every calculation, projection, and recommendation.

### 1.1 Personal Profile

```
PersonalProfile
├── age: number
├── dateOfBirth: date (optional — for precise calculations)
├── retirementAge: number (user-selected, default 65)
├── lifeExpectancy: number (user-selected, default 85)
├── location: { state, metro } (for tax estimates + benchmarking)
├── filingStatus: single | married_jointly | married_separately | head_of_household
├── dependents: number
├── partner: {
│     age: number
│     hasIncome: boolean
│     retirementAge: number (if different)
│   } | null
└── kids: [{ age: number, name?: string }] (for education planning timelines)
```

**Why each field matters:**
- `retirementAge` + `lifeExpectancy` → years of retirement to fund
- `location` → state tax rate, HCOL benchmarking, SALT implications
- `filingStatus` → tax bracket calculation
- `dependents` → tax credits, childcare planning
- `partner` → dual-income modeling, social security timing
- `kids` → education timelines, childcare cost windows

---

### 1.2 Compensation Model

This is the most important data structure in the app. It must be flexible enough to handle a tech PM with RSUs, a doctor with a W-2 salary, a consultant with 1099 income, or a dual-income family with a mix of all of the above.

```
CompensationModel
├── incomeStreams: IncomeStream[]  (one or more — supports dual income, side gigs)
└── totalEstimatedAnnual: number  (derived — sum of all streams)
```

#### Income Stream Types

Each person can have multiple income streams. Each stream has a type and type-specific fields:

```
IncomeStream
├── id: string
├── label: string (e.g. "Mike's salary", "Sarah's medical practice")
├── owner: "self" | "partner"
├── type: IncomeStreamType
├── details: (varies by type — see below)
├── annualGrowthRate: number (default 3% — salary raises, inflation)
├── startDate: date | null (null = already active)
├── endDate: date | null (null = until retirement)
└── estimatedAnnualValue: number (derived)
```

**Supported income stream types:**

| Type | Key Fields | Example |
|---|---|---|
| `salary` | baseSalary (annual) | $180,000 W-2 salary |
| `bonus` | targetPercent, frequency (annual/quarterly) | 15% target, paid annually |
| `rsu` | totalGrantValue, vestingSchedule, currentSharePrice, grantDate | $200K over 4yr, quarterly vest |
| `stock_options` | grantSize, strikePrice, currentFMV, type (ISO/NSO), vestingSchedule | 10,000 ISOs at $15 strike |
| `espp` | contributionPercent, discount, purchasePeriod | 10% of salary, 15% discount |
| `commission` | estimatedAnnual, variability (low/medium/high) | ~$60K/yr commission |
| `freelance_1099` | estimatedAnnual, variability | ~$30K/yr consulting |
| `rental_income` | monthlyGross, monthlyExpenses | $3,200/mo gross, $1,800/mo expenses |
| `investment_income` | estimatedAnnual (dividends + interest) | ~$5,000/yr |
| `pension` | monthlyAmount, startAge | $2,500/mo starting at 62 |
| `social_security` | estimatedMonthly, startAge | $2,800/mo starting at 67 |
| `other` | estimatedAnnual, description | Misc income |

#### RSU Detail Structure

RSUs are common enough and complex enough to warrant a dedicated model:

```
RSUDetail
├── company: string
├── grantDate: date
├── totalShares: number
├── currentSharePrice: number
├── vestingSchedule: {
│     type: "standard_4yr" | "backloaded" | "monthly" | "custom"
│     cliffMonths: number (typically 12)
│     vestingPeriodMonths: number (typically 48)
│     vestingFrequency: "monthly" | "quarterly" | "annually"
│   }
├── sharesSoldToDate: number
├── sharesVestedToDate: number (derived from schedule + grant date)
├── estimatedAnnualVestValue: number (derived)
└── taxWithholdingRate: number (default 22% supplemental — actual marginal is usually higher)
```

#### Why this structure matters for cash flow modeling:

- A salary is steady cash flow — easy to project
- A bonus is lumpy — arrives once or twice a year
- RSUs vest on a schedule — you can see exactly what's coming quarter by quarter
- Stock options have exercise decisions — hold, exercise, or let them expire
- Commission is variable — you need confidence bands, not a single number
- Rental income has its own P&L — gross minus expenses
- Social Security and pensions start at a future age — they fill the gap in retirement

The cash flow engine uses all of these to build month-by-month and year-by-year projections.

---

### 1.3 Expense Model

Not line-item budgeting. Category-level estimates that give a complete picture of where money goes. The insight isn't "you spent $47 at Starbucks" — it's "your fixed costs consume 62% of your take-home pay."

```
ExpenseModel
├── categories: ExpenseCategory[]
├── totalMonthly: number (derived)
├── totalAnnual: number (derived)
└── inflationRate: number (default 3%)
```

#### Expense Categories

```
ExpenseCategory
├── id: string
├── category: ExpenseCategoryType
├── monthlyAmount: number
├── annualAmount: number (derived, or entered directly for irregular expenses)
├── growthRate: number (default: inflation rate)
├── isFixed: boolean (fixed vs. discretionary — for cash flow classification)
├── timebound: {
│     endsWhen: "never" | "age" | "date" | "event"
│     endsAtAge: number | null
│     endsAtDate: date | null
│     endsAtEvent: string | null (e.g. "youngest_child_18")
│   } | null
└── notes: string | null
```

**Standard categories (pre-populated, user adjusts amounts):**

| Category | Type | Typical HENRY Range | Fixed? | Example Timebound |
|---|---|---|---|---|
| `housing` | Mortgage/rent + tax + insurance + HOA | $3,000–$8,000/mo | Yes | Until paid off / forever if renting |
| `childcare` | Daycare, nanny, au pair | $2,000–$5,000/mo per child | Yes | Until youngest starts school |
| `transportation` | Car payment + insurance + gas + maintenance | $500–$1,500/mo | Mixed | Car paid off in X years |
| `food_dining` | Groceries + restaurants | $800–$2,000/mo | No | — |
| `insurance` | Health, life, disability (not auto/home) | $200–$1,500/mo | Yes | — |
| `healthcare` | Out-of-pocket medical, dental, vision | $100–$500/mo | No | — |
| `utilities` | Electric, water, internet, phone | $200–$500/mo | Yes | — |
| `subscriptions` | Streaming, gym, software, memberships | $100–$500/mo | Mixed | — |
| `education` | Private school tuition, tutoring | $1,000–$4,000/mo per child | Yes | Duration of enrollment |
| `travel` | Vacations, flights, hotels | $200–$1,000/mo (averaged) | No | — |
| `personal` | Clothing, hobbies, gifts | $200–$800/mo | No | — |
| `debt_payments` | Student loan, credit card minimums | $500–$3,000/mo | Yes | Until paid off |
| `charitable` | Donations, tithing | $100–$2,000/mo | Mixed | — |
| `other` | Anything else | Varies | Mixed | — |

**Key design decisions:**
- Pre-populate categories with $0 — user enters what applies
- Show "typical HENRY range" as a helper for each category
- Categories are collapsible — power users can break them down further
- Total monthly expense is always visible as you fill things in
- "What's left" (income minus expenses) updates in real-time during entry

---

### 1.4 Balance Sheet

Assets and liabilities, categorized for net worth calculation and retirement planning.

```
BalanceSheet
├── assets: Asset[]
├── liabilities: Liability[]
├── totalAssets: number (derived)
├── totalLiabilities: number (derived)
└── netWorth: number (derived)
```

#### Assets

```
Asset
├── id: string
├── category: "cash" | "taxable_investment" | "retirement_401k" | "retirement_ira" 
│             | "retirement_roth" | "hsa" | "five29" | "home_equity" 
│             | "other_real_estate" | "vehicle" | "employer_stock" | "crypto" | "other"
├── label: string (e.g. "Fidelity 401k", "Chase savings")
├── currentValue: number
├── monthlyContribution: number (if applicable)
├── employerMatch: { percent: number, upToPercent: number } | null (for 401k)
├── expectedReturnRate: number (default by category)
└── notes: string | null
```

**Default expected return rates by category:**

| Category | Default Return | Rationale |
|---|---|---|
| Cash / savings | 4.5% | Current HYSA rates |
| Taxable investment | 7% | Broad market historical average |
| 401k / IRA | 7% | Assumes diversified allocation |
| Roth IRA | 7% | Same — tax-free growth |
| HSA (invested) | 7% | Triple tax advantage |
| 529 | 6% | Age-based allocation, slightly conservative |
| Home equity | 3.5% | Real estate appreciation |
| Employer stock | N/A | Too volatile to default — use RSU model |
| Crypto | N/A | No default — user enters |
| Other | 3% | Conservative default |

#### Liabilities

```
Liability
├── id: string
├── category: "mortgage" | "student_loan" | "auto_loan" | "credit_card" 
│             | "personal_loan" | "heloc" | "other"
├── label: string (e.g. "Federal student loans", "Chase Sapphire")
├── currentBalance: number
├── interestRate: number
├── minimumMonthlyPayment: number
├── remainingTermMonths: number | null
└── isFixedRate: boolean
```

---

### 1.5 Life Goals

Goals are what give the projections meaning. Without goals, trajectories are just charts. With goals, they're answers to "can I do this?"

```
LifeGoal
├── id: string
├── type: LifeGoalType
├── name: string
├── priority: number (user-ranked, 1 = highest)
├── targetDate: date | null
├── targetAge: number | null (alternative to date)
├── details: (varies by type — see below)
├── status: "planning" | "in_progress" | "achieved" | "deferred"
└── linkedDecisionIds: string[] (Decision Lab scenarios modeling this goal)
```

**Goal types and their specific fields:**

| Goal Type | Key Fields | Cash Flow Impact |
|---|---|---|
| `home_purchase` | targetPrice, downPaymentPercent, estimatedRate | One-time (down payment) + ongoing (mortgage replaces rent) |
| `car_purchase` | targetPrice, downPayment, loanTerm, estimatedRate | One-time or ongoing (loan payments) |
| `private_school` | annualTuition, numberOfKids, startAge, endAge | Ongoing, time-bound |
| `college_529` | targetPerChild, numberOfKids, yearsUntilCollege | Ongoing contributions, lump withdrawal later |
| `retirement` | retirementAge, monthlyRetirementExpenses, lifestyle | Changes everything — the master goal |
| `fire` | fireNumber, targetAge, withdrawalRate | Variant of retirement with specific number |
| `debt_freedom` | targetDate, targetDebt | Accelerated payments |
| `emergency_fund` | targetMonths (of expenses) | Savings allocation |
| `career_change` | expectedNewIncome, transitionCosts, timelineMonths | Income change + possible gap |
| `start_business` | startupCosts, expectedTimeToRevenue, expectedRevenue | Cash outflow → eventual income |
| `sabbatical` | durationMonths, expenses, incomeReduction | Temporary income drop |
| `relocation` | newLocation, housingCostChange, incomeChange | Multiple expense line changes |
| `wedding` | estimatedCost, timeline | One-time expense |
| `custom` | description, estimatedCost, timeline, isRecurring | Flexible |

---

### 1.6 Tax Profile (Derived + User-Adjusted)

Henry estimates taxes — it doesn't file them. But accurate tax estimates are critical for cash flow modeling.

```
TaxProfile
├── filingStatus: (from PersonalProfile)
├── state: (from PersonalProfile.location)
├── estimatedFederalRate: number (marginal, derived from income)
├── estimatedEffectiveRate: number (derived)
├── estimatedStateRate: number (from state tables)
├── estimatedFICA: number (Social Security + Medicare)
├── estimatedAnnualTaxBurden: number (derived)
├── deductionType: "standard" | "itemized"
├── estimatedDeductions: number
├── hasAMTRisk: boolean (derived from income + state + ISOs)
└── userOverrides: {
│     effectiveTaxRate: number | null (if they know their actual rate)
│   }
```

**Tax estimation approach:**
- Use 2025/2026 federal brackets + state tables to estimate taxes
- Factor in FICA (Social Security caps, Medicare surtax at $200K+)
- Detect AMT risk for high-income + high-SALT + ISO exercise scenarios
- Allow user to override with their actual effective rate if they know it
- RSU/bonus income taxed at supplemental rate (22% withholding, but flag the shortfall at actual marginal rate)

---

## 2. The Cash Flow Engine

The cash flow engine is the heart of Henry. Every feature reads from it. It answers: **"Given what I earn, what I spend, and what I owe — what happens over time?"**

### 2.1 Monthly Cash Flow Calculation

```
Monthly Cash Flow:

  Gross Income (all streams, monthly allocation)
- Estimated Taxes (federal + state + FICA)
────────────────────────────────────
= Net Take-Home Pay

- Fixed Expenses (housing, childcare, insurance, debt payments)
- Variable Expenses (food, travel, personal, subscriptions)
────────────────────────────────────
= Net Cash Flow

- Savings & Investments (401k, IRA, HSA, taxable, 529)
────────────────────────────────────
= Unallocated Cash (the "where does my money go?" number)
```

**The "Unallocated Cash" metric is critical.** It's the gap between what someone *thinks* they save and what actually remains. For many HENRYs, this number is negative — meaning they're spending more than they realize, often on credit or by depleting liquid savings.

### 2.2 Multi-Year Cash Flow Projections

Project cash flow forward at 2, 3, 5, and 10 year horizons. Each projection accounts for:

| Factor | How it changes over time |
|---|---|
| Salary | Grows at user-defined rate (default 3%/yr) |
| Bonus | Grows proportionally to salary |
| RSUs | Follows vesting schedule — may cliff, ramp, or end |
| Stock options | Modeled as exercisable at user's discretion |
| ESPP | Proportional to salary |
| Expenses | Grow at inflation rate (category-specific overrides) |
| Time-bound expenses | Start and stop at specified dates (childcare ends, loan paid off) |
| Tax brackets | Adjust as income grows (bracket creep) |
| Life events | Scheduled goals inject costs at their target dates |
| Debt paydown | Balances decrease per amortization schedule |
| Investment growth | Portfolio compounds at expected return rates |

#### Cash Flow Projection Output

```
CashFlowProjection
├── timeHorizon: 2 | 3 | 5 | 10 (years)
├── yearByYear: [
│     {
│       year: number,
│       grossIncome: number,
│       taxes: number,
│       netIncome: number,
│       totalExpenses: number,
│       totalSavings: number,
│       netCashFlow: number,
│       cumulativeNetWorth: number,
│       incomeBreakdown: { salary, bonus, rsu, other },
│       expenseBreakdown: { fixed, variable, goals },
│       savingsBreakdown: { retirement, taxable, education, other },
│       keyEvents: string[] (e.g. "RSU cliff vest", "Car loan paid off")
│     }
│   ]
├── summary: {
│     totalEarnings: number,
│     totalTaxes: number,
│     totalExpenses: number,
│     totalSaved: number,
│     endingNetWorth: number,
│     averageSavingsRate: number,
│     keyMilestones: string[]
│   }
```

#### Visualization

The cash flow projection is displayed as:
- **Stacked bar chart** (year by year): income sources stacked, expenses overlaid, savings highlighted
- **Summary cards**: total earnings, total taxes, total saved, ending net worth
- **Timeline markers**: key events (RSU vests, loan payoffs, goal costs)
- **Time horizon selector**: 2Y | 3Y | 5Y | 10Y (tabs at top of chart)

---

## 3. Feature Specifications

### 3.1 The Scoreboard

**Problem:** "Where do I stand right now?"
**Data dependencies:** CompensationModel, ExpenseModel, BalanceSheet, TaxProfile
**Visit frequency:** Weekly

The scoreboard is the home screen. It distills the entire financial picture into 4 key metrics:

| Metric | Calculation | Why it matters |
|---|---|---|
| **Net Worth** | Total assets - total liabilities | The single number that summarizes wealth |
| **Savings Rate** | (Annual savings + investments) / gross annual income | Are you building wealth fast enough? |
| **Monthly Cash Flow** | Net income - expenses - savings | Is there a leak? |
| **Status** | On Track / At Risk / Behind (from trajectory analysis) | The emotional anchor |

**Benchmark context:**
- Net worth percentile vs. HENRYs of same age, income, and metro
- Savings rate vs. what's required for their retirement goal
- Trend arrows (30-day, 90-day change)

**The Scoreboard links to everything:**
- Tap net worth → asset/liability breakdown
- Tap savings rate → cash flow detail
- Tap status → trajectory with explanation
- "What Would Help Most" card → top priority action (links to Decision Lab or Sir Henry)

---

### 3.2 Cash Flow Detail

**Problem:** "Where does my money go? What's coming in and out over the next few years?"
**Data dependencies:** CompensationModel, ExpenseModel, TaxProfile
**Visit frequency:** Monthly, or after income/expense changes

This is the detailed view behind the Scoreboard's cash flow number. Two modes:

#### Current Month View

```
┌─────────────────────────────────────────────┐
│  MONTHLY CASH FLOW                          │
│                                             │
│  Income                        $16,500/mo   │
│    Base salary      $12,000                 │
│    RSU vest (avg)    $3,500                 │
│    ESPP proceeds       $600                 │
│    Investment income   $400                 │
│                                             │
│  Taxes (estimated)             -$5,940/mo   │
│    Federal            $3,960                │
│    State (CA)         $1,485                │
│    FICA                $495                 │
│                                             │
│  Take-Home                     $10,560/mo   │
│                                             │
│  Expenses                      -$7,800/mo   │
│    Housing            $3,800   ████████░░   │
│    Childcare          $2,400   █████░░░░░   │
│    Transport            $600   █░░░░░░░░░   │
│    Food & dining        $500   █░░░░░░░░░   │
│    Everything else      $500   █░░░░░░░░░   │
│                                             │
│  Savings & Investing           -$2,100/mo   │
│    401(k)             $1,917                │
│    HSA                  $183                 │
│                                             │
│  ── NET ──────────────────────              │
│  Unallocated                     $660/mo    │
│                                             │
│  "You have ~$660/mo not assigned to savings │
│   or specific expenses. Over a year, that's │
│   $7,920 that tends to disappear."          │
│                                             │
└─────────────────────────────────────────────┘
```

#### Projection View (2Y / 3Y / 5Y / 10Y)

Shows year-by-year cash flow with the stacked bar chart described in section 2.2. Key interactions:
- Tap a year to see the detailed breakdown for that year
- Key events appear as markers on the timeline (RSU cliff vest in year 2, car loan paid off in year 3, childcare ends in year 4)
- "What if" toggle: switch between "current trajectory" and any saved Decision Lab scenario

---

### 3.3 The Trajectory

**Problem:** "Where am I headed? Will I have enough?"
**Data dependencies:** Everything (full financial picture)
**Visit frequency:** Weekly (the hero screen that drives retention)

The Trajectory is a Monte Carlo simulation of the user's **entire financial life**, not a single investment or portfolio. It accounts for all income streams, all expenses, all savings, all growth rates, all goals, and runs thousands of simulations to show the range of probable outcomes.

#### Key Outputs

| Output | Description |
|---|---|
| **Fan Chart** | 10th/25th/50th/75th/90th percentile wealth curves over time |
| **Retirement Readiness** | "72% chance of reaching your target by age 55" |
| **Projected Retirement Income** | "At the median outcome, you'd have $8,200/mo in today's dollars" |
| **Key Milestones** | "50% chance of hitting $1M by age 42" |
| **Savings Rate Sensitivity** | "Increasing savings by $500/mo moves retirement from 60 to 57" |

#### Time Horizons

| Selector | What it shows |
|---|---|
| **2Y** | Near-term cash accumulation, RSU vests, debt paydown |
| **3Y** | Medium-term trajectory, early goal progress |
| **5Y** | Goal achievement likelihood, major life event impact |
| **10Y** | Significant wealth building, mid-career check |
| **To Retirement** | Full trajectory to retirement age (the default hero view) |

#### Monte Carlo Parameters

| Parameter | Default | Source |
|---|---|---|
| Simulation count | 10,000 | Backend config |
| Equity return distribution | μ=10%, σ=18% | Historical S&P |
| Bond return distribution | μ=4.5%, σ=6% | Historical aggregate |
| Inflation distribution | μ=3%, σ=1.5% | Historical CPI |
| Income growth | User-defined | CompensationModel |
| Expense growth | Category-specific inflation | ExpenseModel |

---

### 3.4 Retirement Planner

**Problem:** "How much do I actually need to retire? What does that retirement look like?"
**Data dependencies:** PersonalProfile, CompensationModel, ExpenseModel, BalanceSheet, LifeGoals
**Visit frequency:** Monthly, or when retirement thinking changes

This is the feature that turns "save for retirement" from a vague anxiety into a specific, actionable plan. It works **backwards from the life you want** rather than forwards from what you're saving.

#### The Core Retirement Calculation

```
Inputs:
  Retirement age:           [60]  (slider, 50-75)
  Life expectancy:          [85]  (slider, 75-100)
  Years in retirement:       25   (derived)

  Monthly retirement expenses (in today's dollars):
    ┌──────────────────────────────────────┐
    │ Option A: Percentage of current      │
    │   [80%] of current spending          │
    │   = $6,240/mo ($74,880/yr)           │
    │                                      │
    │ Option B: Custom breakdown           │
    │   Housing        $2,500 (paid off?)  │
    │   Healthcare     $1,200              │
    │   Food           $800                │
    │   Travel         $1,500              │
    │   Insurance      $500                │
    │   Other          $1,000              │
    │   Total:         $7,500/mo           │
    └──────────────────────────────────────┘

  Retirement income sources:
    Social Security:     $2,800/mo starting at 67
    Pension:             $0/mo
    Part-time work:      $0/mo
    Rental income:       $1,400/mo (net)
    Other:               $0/mo

  ── THE GAP ──────────────────────────────
  Monthly expenses:              $7,500
  Monthly retirement income:    -$4,200
  Monthly shortfall:             $3,300

  Portfolio must provide:        $3,300/mo
  At 4% withdrawal rate:         $990,000 needed
  Adjusted for inflation to 60:  $1,340,000 needed

Outputs:
  Required portfolio at retirement:  $1,340,000
  Current retirement savings:        $285,000
  Gap to close:                      $1,055,000
  Years until retirement:            26
  Required annual savings:           $22,400/yr ($1,867/mo)
  Current annual savings:            $23,000/yr
  Status:                            ✅ On Track (barely)
  Probability of success:            68% (Monte Carlo)
```

#### What Makes This Different

Most retirement calculators ask "how much are you saving?" and show a number. Henry asks **"what life do you want in retirement?"** and works backwards:

1. **Define retirement lifestyle** — not a number, but actual expense categories. "I want to travel more, so travel goes up. My mortgage will be paid off, so housing drops. Healthcare goes up as I age."
2. **Subtract guaranteed income** — Social Security, pensions, rental income. What's the gap?
3. **Calculate the portfolio needed** to fill the gap for the full retirement duration.
4. **Show whether current trajectory gets there** — with probability bands, not a single line.
5. **Show the levers** — "Retire at 62 instead of 60? Need drops by $180K." / "Cut travel by $500/mo? Retire 2 years earlier."

#### Retirement Scenarios (Interactive)

| What they adjust | What changes |
|---|---|
| Retirement age slider | Required portfolio, savings gap, probability |
| Life expectancy slider | Duration of retirement, required portfolio |
| Monthly expenses | Required portfolio, gap, probability |
| Withdrawal rate (advanced) | Required portfolio size |
| Social Security start age | Monthly income, gap |
| One-time future income (inheritance, sale) | Reduces gap |
| Relocate to lower-cost area | Expenses drop, probability improves |

Every slider change re-runs the calculation in real-time. The user sees instantly: "if I retire at 62 instead of 60 and move to a lower-cost city, my probability goes from 68% to 89%."

---

### 3.5 The Decision Lab

**Problem:** "What happens to my financial trajectory if I do X?"
**Data dependencies:** Everything (full picture) + decision-specific inputs
**Visit frequency:** When facing a major financial choice (3-5x per year)

The Decision Lab models the impact of a specific decision on the user's full financial trajectory. It shows **before vs. after** — not in isolation, but against the full Monte Carlo projection.

#### Supported Decision Types

**Tier 1 — Launch (highest frequency, highest impact):**

| Decision | Inputs | Key Outputs |
|---|---|---|
| **Buy a Home** | Price, down payment %, rate, property tax, insurance, HOA, maintenance | Monthly payment, savings rate change, retirement date shift, rent vs. buy comparison |
| **Change Jobs** | New salary, new bonus, new RSUs, relocation cost, commute change | Net income change (after tax), trajectory impact, RSU forfeiture cost |
| **Retire Early / When Can I?** | Target age (or "find earliest") | Required portfolio, probability, lifestyle adjustments needed |
| **Pay Off Debt vs. Invest** | Debt details, extra payment amount | Interest saved, opportunity cost of not investing, break-even rate |
| **Windfall / Bonus Allocation** | Amount, allocation options (debt, invest, spend, mix) | Impact on net worth at 5Y/10Y/20Y by allocation strategy |
| **Savings Rate Change** | New monthly savings amount or target rate | Retirement date shift, probability change, net worth impact |

**Tier 2 — Post-Launch:**

| Decision | Inputs | Key Outputs |
|---|---|---|
| **Buy a Car** | Price, down payment, loan term, rate, insurance, maintenance | Monthly cost, savings rate impact, buy vs. lease comparison |
| **Private School** | Annual tuition, number of kids, years of enrollment | Total cost, savings rate impact, retirement shift |
| **Fund College (529)** | Target amount per child, years until college, monthly contribution | Total saved, gap at college start, tax benefit |
| **Spouse Stops Working** | Income lost, expenses saved (childcare), duration | Cash flow impact, retirement shift, savings gap |
| **Equity Comp Strategy** | RSU/option details, hold vs. sell strategy | Tax impact, concentration risk change, diversification benefit |
| **Start a Business** | Startup costs, income loss period, expected eventual income | Break-even timeline, cash reserve needed, trajectory impact |
| **Career Break / Sabbatical** | Duration, expenses during, income loss | Cash reserve needed, trajectory setback, recovery time |
| **Relocate** | New location, housing cost change, income change, tax change | Net financial impact, quality of life trade-off framing |

#### Decision Lab Output Format

Every decision shows:

```
┌───────────── BEFORE ──────────────┬──────────── AFTER ──────────────┐
│ Savings rate:          18%        │ Savings rate:         11%       │
│ Monthly cash flow:     $2,100     │ Monthly cash flow:    $400      │
│ Retire at:             55         │ Retire at:            59        │
│ P(reach goal):         84%        │ P(reach goal):        61%       │
│ Net worth at 55:       $2.1M      │ Net worth at 55:      $1.4M    │
└───────────────────────────────────┴─────────────────────────────────┘

Key Insight:
"Buying this home reduces your savings rate by 7 points and
pushes retirement back ~4 years. You can partially offset this
by increasing your 401(k) contribution by $500/mo."

[ Save Scenario ] [ Compare Options ] [ Ask Henry ]
```

**Compare Options** allows side-by-side comparison of up to 3 scenarios (e.g., $650K house vs. $750K house vs. continue renting).

---

### 3.6 Priority Waterfall

**Problem:** "I have money to save/invest — where should it go first?"
**Data dependencies:** CompensationModel (employer match), Liabilities (interest rates), TaxProfile (brackets), Assets (existing contributions)
**Visit frequency:** After income changes, annually at minimum

Not a standalone page — embedded in the Scoreboard and surfaced by Sir Henry. Generates a personalized "next dollar" priority order based on the user's actual numbers.

#### Waterfall Logic

```
1. 401(k) up to employer match        → if match exists and not maxed
   Reason: 50-100% immediate return (free money)

2. Pay off debt above 7% interest     → credit cards, high-rate loans
   Reason: Guaranteed return above expected market return

3. Max HSA (if eligible)              → $4,150 individual / $8,300 family (2025)
   Reason: Triple tax advantage (deduction + growth + withdrawal)

4. Max 401(k)                         → $23,500 (2025)
   Reason: Tax-deferred compounding at marginal rate

5. Backdoor Roth IRA                  → $7,000/person (2025)
   Reason: Tax-free growth, no RMDs

6. Mega Backdoor Roth (if available)  → up to $69,000 total 401k limit
   Reason: Additional tax-free growth

7. Pay off debt 4-7%                  → student loans, moderate-rate debt
   Reason: Guaranteed return in uncertain market

8. 529 Plan                           → if kids, state tax deduction may apply
   Reason: Tax-free growth for education

9. Taxable Investing                  → after all tax-advantaged space used
   Reason: Wealth building with tax-loss harvesting opportunity

10. Pay off debt below 4%             → low-rate mortgage, etc.
    Reason: Expected market return exceeds interest savings
```

**This order adjusts based on the user's actual numbers:**
- No employer match? Skip step 1.
- No high-interest debt? Skip step 2.
- Not HSA eligible? Skip step 3.
- Already maxing 401(k)? Show it as complete, move to next.
- No kids? Skip step 8.

Each step shows:
- The specific dollar amount to allocate
- The annual benefit in dollars
- Whether the user is currently doing this (checkmark) or not (opportunity flag)

---

### 3.7 Sir Henry (AI Advisor)

**Problem:** "I have a question about my finances and want a specific, personalized answer."
**Data dependencies:** Full user context (all models)
**Visit frequency:** Ad hoc, when questions arise

Sir Henry is the conversational interface to the entire system. It has access to the user's complete financial picture and can reference any calculation, projection, or recommendation.

#### What Sir Henry Can Do

| Capability | Example |
|---|---|
| Answer questions with user's numbers | "Should I sell my RSUs on vest?" → response with their marginal rate, concentration %, and specific dollar amounts |
| Explain projections | "Why does my trajectory show only 62%?" → walks through the factors driving the probability |
| Walk through strategies | "How does a backdoor Roth work?" → step-by-step with their specific IRA balance and income |
| Trigger Decision Lab | "What if I buy a $700K house?" → starts a decision scenario pre-filled with context |
| Explain tax implications | "What's the tax hit on my March RSU vest?" → calculates at their marginal rate, shows withholding gap |
| Prioritize actions | "What should I do with a $50K bonus?" → runs through priority waterfall with specific allocations |
| Proactive nudges (future) | "Your RSUs vest next month — here's what to prepare for" |

#### What Sir Henry Cannot Do

- Execute trades or move money
- Provide legally binding financial advice (always disclaims)
- Recommend specific securities
- Predict market movements
- Access external accounts or real-time market data (V1)

---

## 4. Information Architecture

### 4.1 How Features Connect

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA ENTRY LAYER                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Comp    │  │ Expenses │  │ Balance  │  │  Goals   │       │
│  │  Model   │  │  Model   │  │  Sheet   │  │          │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │              │             │
│       └──────────────┴──────────┬───┴──────────────┘             │
│                                 │                                │
│                     ┌───────────▼──────────┐                     │
│                     │   CASH FLOW ENGINE   │                     │
│                     │  (the core math)     │                     │
│                     └───────────┬──────────┘                     │
│                                 │                                │
├─────────────────────────────────┼────────────────────────────────┤
│                      FEATURES LAYER                              │
│       ┌─────────────┬──────────┼──────────┬──────────┐          │
│       │             │          │          │          │          │
│  ┌────▼─────┐ ┌─────▼────┐ ┌──▼───┐ ┌───▼────┐ ┌──▼──────┐  │
│  │Scoreboard│ │Cash Flow │ │Traj- │ │Retire- │ │Decision │  │
│  │          │ │Projection│ │ectory│ │ment    │ │Lab      │  │
│  │(summary) │ │(2-10yr)  │ │(MC)  │ │Planner │ │(what-if)│  │
│  └────┬─────┘ └──────────┘ └──┬───┘ └───┬────┘ └────┬────┘  │
│       │                        │         │           │         │
│       └────────────────────────┴─────┬───┴───────────┘         │
│                                      │                          │
│                            ┌─────────▼─────────┐               │
│                            │    SIR HENRY      │               │
│                            │  (AI — reads all,  │               │
│                            │   references all)  │               │
│                            └───────────────────┘               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                      GUIDANCE LAYER                              │
│       ┌──────────────────┐  ┌──────────────────┐               │
│       │Priority Waterfall│  │Proactive Nudges  │               │
│       │(next dollar)     │  │(timely actions)  │               │
│       └──────────────────┘  └──────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

**Key principle:** Data flows down. Every feature reads from the same Cash Flow Engine. Change a number in the data entry layer, and every feature updates.

### 4.2 Navigation Structure

Maintain the 4-tab structure from DESIGN.md, but with richer content within each tab:

```
Tab 1: Dashboard (home)
├── Scoreboard (always visible — net worth, savings rate, status)
├── Cash Flow Summary (income vs. expenses, this month)
├── Trajectory Preview (fan chart, key milestone)
├── Retirement Readiness (one-line status)
├── What Would Help Most (top priority action)
└── Tap any section → expands to full detail view

Tab 2: Plan
├── Cash Flow Projections (2Y / 3Y / 5Y / 10Y)
├── Retirement Planner (the full retirement modeling tool)
├── Goals (life goals with progress tracking)
└── Priority Waterfall (next-dollar guidance)

Tab 3: Decisions
├── Saved Scenarios (list)
├── New Decision (pick type → model → see impact)
└── Compare Scenarios (side-by-side)

Tab 4: Henry
├── Recent Conversations
├── Suggested Questions (personalized)
└── New Chat

Profile (accessible from header, not a tab)
├── Your Numbers (edit compensation, expenses, assets, debts)
├── Account Settings
└── Subscription
```

**Change from current DESIGN.md:** The "Profile" tab becomes "Plan" (a much more valuable use of a primary tab slot). Profile moves to a header icon — it's visited monthly, not weekly.

### 4.3 Feature Cross-Links

Every feature should link to related features. The user should never hit a dead end.

| From | To | Trigger |
|---|---|---|
| Scoreboard status (At Risk) | Trajectory | "See why →" |
| Scoreboard savings rate | Cash Flow Detail | Tap the number |
| Scoreboard "What Would Help" | Decision Lab or Sir Henry | Action buttons |
| Cash Flow unallocated amount | Priority Waterfall | "Where should this go?" |
| Cash Flow projection events | Decision Lab | "Model this change" |
| Trajectory retirement readiness | Retirement Planner | "Plan your retirement →" |
| Trajectory milestone | Sir Henry | "Ask Henry about this" |
| Retirement Planner gap | Priority Waterfall | "How to close the gap" |
| Retirement Planner scenario | Decision Lab | "Model this change" |
| Decision Lab result | Sir Henry | "Ask Henry about this" |
| Decision Lab result | Trajectory | "See on your trajectory" |
| Sir Henry response | Decision Lab | "Model This Decision" button |
| Sir Henry response | Cash Flow / Trajectory | "See your numbers" links |
| Priority Waterfall step | Sir Henry | "Walk me through this" |
| Goal progress | Decision Lab | "What happens if I accelerate this?" |

---

## 5. Onboarding Flow

### 5.1 Quick Setup (Under 5 Minutes → Instant Value)

Onboarding captures the minimum viable data to generate a meaningful Scoreboard. Deeper data entry happens progressively after the user sees initial value.

#### Step 1: About You (30 seconds)

```
"Let's get the lay of the land."

- Your age:                    [ 34 ]
- Partner?                     ○ No  ● Yes → Partner's age: [ 32 ]
- Kids?                        ● Yes → How many: [ 2 ]  Ages: [ 4, 1 ]
- Where do you live?           [ San Francisco, CA ▾ ]
- When do you want to retire?  [ 55 ] (slider, 50-75, default 65)
```

#### Step 2: What You Earn (60 seconds)

```
"How are you compensated?"

Select all that apply:
  ☑ Base salary
  ☑ Annual bonus
  ☑ RSUs / stock grants
  ☐ Stock options
  ☐ Commission
  ☐ Freelance / 1099
  ☐ Rental income
  ☐ Other

Based on selections:
  Base salary (annual, pre-tax):   [ $180,000 ]
  Bonus target (%):                [ 15% ]     = ~$27,000
  RSU annual vest value:           [ $50,000 ]  💡 Total grant / vesting years
  
  Partner's income (if applicable):
  Base salary:                     [ $120,000 ]

  Total estimated household:       $377,000/yr
```

**Key UX:** Only show fields for selected compensation types. RSU entry starts simple (annual vest value) — they can add detailed vesting schedules later.

#### Step 3: What You Have & Owe (60 seconds)

```
"What's your balance sheet?"

Assets (best estimates are fine):
  Retirement accounts (401k, IRA, Roth):  [ $185,000 ]
  Cash & liquid savings:                   [ $42,000 ]
  Taxable investments:                     [ $15,000 ]
  Home equity (value - mortgage):          [ $120,000 ]  💡 $0 if renting

Debts:
  Student loans:        [ $85,000 ]  Rate: [ 5.5% ]
  Other debt:           [ $12,000 ]  Rate: [ 7.2% ]
```

#### Step 4: Monthly Snapshot (60 seconds)

```
"Roughly, what does a typical month look like?"

Monthly expenses (estimates are fine — we're not counting pennies):
  Housing (mortgage/rent + tax + insurance):  [ $3,800 ]
  Childcare / education:                       [ $2,400 ]
  Everything else (food, transport, etc.):     [ $2,500 ]

Monthly savings (what you actively put away):
  Retirement contributions (401k, IRA):        [ $1,917 ]
  Other savings/investing:                     [ $500 ]

  💡 Not sure? That's exactly why you're here.
     Your best guess works — we'll refine together.
```

#### Step 5: Instant Scoreboard

```
"Here's where you stand."

→ Redirect to Dashboard with populated Scoreboard, initial Trajectory, and first "What Would Help Most" recommendation.

Below the Scoreboard:
"Want more precision? Add detail to your compensation, 
 expenses, and goals — and your projections get sharper."
[ Refine My Numbers → ]
```

### 5.2 Progressive Enrichment (Post-Onboarding)

After the user has seen their Scoreboard and experienced the aha moment, they can optionally deepen their data:

| Enrichment | What it adds | Prompt |
|---|---|---|
| **Detailed compensation** | RSU vesting schedules, ESPP, options, side income | "Add your RSU details for precise vesting projections" |
| **Expense breakdown** | Full category-level expenses | "Break down your expenses for a sharper cash flow picture" |
| **Debt detail** | Individual loans with rates and terms | "Add your debts for payoff projections" |
| **Asset detail** | Individual accounts with contribution rates | "Add your accounts for contribution optimization" |
| **Life goals** | Specific goals with timelines and costs | "Tell us what you're planning — we'll show you if it works" |
| **Retirement detail** | Retirement expenses, income sources, SS estimate | "Design your retirement — not just a number, but a life" |

Each enrichment is accessible from the relevant feature and from the Profile/Numbers section. The app gets smarter as they add data, and it tells them: "Adding your RSU details would make your projections 40% more accurate."

---

## 6. Updated Page Map

### Unauthenticated

```
/                             Landing page
/login                        Sign in
/signup                       Create account
```

### Onboarding (first-time, post-auth)

```
/onboarding                   Step 1: About You
/onboarding/income            Step 2: What You Earn
/onboarding/balance-sheet     Step 3: What You Have & Owe
/onboarding/monthly           Step 4: Monthly Snapshot
```

### Core App (4 tabs)

```
/dashboard                    Tab 1: Scoreboard + summaries
/dashboard/cash-flow          Cash Flow detail + projections
/dashboard/trajectory         Full trajectory view (Monte Carlo)

/plan                         Tab 2: Life Planning hub
/plan/retirement              Retirement Planner
/plan/goals                   Life Goals overview
/plan/goals/[id]              Individual goal detail
/plan/waterfall               Priority Waterfall

/decisions                    Tab 3: Decision Lab
/decisions/new                New decision (type selection)
/decisions/new/[type]         Decision builder (type-specific inputs)
/decisions/[id]               Saved decision result
/decisions/compare            Side-by-side comparison

/henry                        Tab 4: Sir Henry chat home
/henry/[id]                   Conversation thread
```

### Profile (header icon, not a tab)

```
/profile                      Profile overview
/profile/income               Detailed compensation editor
/profile/expenses             Detailed expense editor
/profile/assets               Asset detail editor
/profile/debts                Debt detail editor
/profile/settings             Account settings
/profile/subscription         Billing / plan management
```

**Total routes: ~22** (up from 12 in DESIGN.md, but each route serves a clear, validated purpose).

---

## Appendix A: Feature Priority for V1

| Priority | Feature | Rationale |
|---|---|---|
| **P0 — Must Have** | Onboarding (quick setup) | No data = no product |
| **P0** | Scoreboard | The hook — instant value |
| **P0** | Cash Flow (current month) | Answers "where does my money go?" |
| **P0** | Trajectory (Monte Carlo) | The hero screen — retention driver |
| **P0** | Sir Henry (basic chat) | The differentiator |
| **P1 — Should Have** | Cash Flow Projections (2-10yr) | Forward-looking clarity |
| **P1** | Retirement Planner | The "how much do I need" answer |
| **P1** | Decision Lab (home, career, debt) | The "what if" answer |
| **P1** | Priority Waterfall | The "what should I do" answer |
| **P2 — Nice to Have** | Detailed RSU modeling | High value for tech HENRYs |
| **P2** | Life Goals tracking | Longer-term engagement |
| **P2** | Decision Lab (car, school, sabbatical) | More decision types |
| **P2** | Scenario comparison | Side-by-side decision view |
| **P3 — Future** | Proactive nudges | Requires event-driven architecture |
| **P3** | Account linking (Plaid) | Reduces manual entry friction |
| **P3** | Tax optimization engine | Deep tax strategy recommendations |
| **P3** | Mobile app | After web experience is validated |

---

## Appendix B: Key Metrics to Track

| Metric | Target | Why |
|---|---|---|
| Onboarding completion rate | >70% | Users who start should finish |
| Time to first Scoreboard | <5 minutes | Speed to value |
| Weekly active rate (Dashboard views) | >40% | Retention signal |
| Decision Lab usage (monthly) | >20% of active users | Feature engagement |
| Sir Henry messages (monthly) | >3 per active user | AI engagement |
| Upgrade to Pro conversion | >5% of free users | Revenue signal |
| NPS | >50 | User satisfaction |

---

*This document is authoritative for feature requirements. It supersedes any conflicting information in DESIGN.md (which will be updated to align). Types in `packages/types/` should be updated to match these data models before implementation begins.*

*Last updated: February 7, 2026*
