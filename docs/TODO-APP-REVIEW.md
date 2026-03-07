# SirHENRY App Review — Strategic TODO

> Generated from full codebase audit (March 2026).
> Organized into 5 phases, ordered by dependency and impact.
> Each task includes the specific files to modify and what the change is.

---

## Phase 1: Foundation & Critical Fixes

These must be correct before anything else. Bugs and gaps that affect data integrity or basic functionality.

### 1.1 Create `frontend/middleware.ts` (route protection)
- **Problem:** CLAUDE.md says middleware blocks all routes except `/`, but the file was never committed. All 30+ internal pages are publicly accessible.
- **Files:** Create `frontend/middleware.ts`
- **What:** Export a Next.js middleware that:
  - Allows `/` (landing page) and `/api/` routes through
  - Allows static assets (`_next/`, `favicon`, images)
  - For all other routes: check for a session cookie or auth header; if missing, redirect to `/`
  - In pre-launch mode, block everything except `/` (waitlist)
- **Note:** Since auth is temporarily disabled, this is primarily about the pre-launch gate described in CLAUDE.md. The middleware should be easy to extend when Supabase auth is enabled.

### 1.2 Fix `selectMode()` fire-and-forget race on web reload
- **Problem:** `AppShell.tsx` lines 53-58 call `selectMode()` without awaiting, then immediately set `phase = "done"`. If the API is slow, the app renders before the DB switch completes.
- **Files:** `frontend/components/AppShell.tsx`
- **What:** Await `selectMode()` before setting phase to `"done"`. Show a brief loading state while the mode switch is in progress. Add a catch handler that falls back to a retry or error state.
- **Apply same fix to** the Tauri `useEffect` at lines 66-76.

### 1.3 Fix dashboard blank state on null data
- **Problem:** `dashboard/page.tsx` line 132: `if (!data) return null;` renders a completely blank page for new users with no transactions.
- **Files:** `frontend/app/(app)/dashboard/page.tsx`
- **What:** Replace `return null` with a proper empty state that:
  - Uses the `EmptyState` component
  - Shows a welcome message for new users
  - Links to the setup wizard or account connection
  - Includes a Sir Henry tip about getting started
  - Shows the `SetupBanner` if setup is incomplete

### 1.4 Add save-before-continue guards in onboarding wizard
- **Problem:** In `StepHousehold`, `StepBenefits`, and `StepBusiness`, users must click "Save" then "Continue" separately. Clicking "Continue" without saving silently discards data.
- **Files:**
  - `frontend/components/setup/SetupWizard.tsx` — add dirty-state tracking
  - `frontend/components/setup/StepHousehold.tsx` — expose `isDirty` state
  - `frontend/components/setup/StepBenefits.tsx` — expose `isDirty` state
  - `frontend/components/setup/StepBusiness.tsx` — expose `isDirty` state
- **What:** Two options (pick one):
  - **Option A (preferred):** Auto-save when clicking "Continue". Each step exposes a `save()` function via ref or callback. The wizard calls it before advancing. If save fails, show error and don't advance.
  - **Option B:** Show a confirmation dialog when advancing with unsaved changes ("You have unsaved changes. Save before continuing?").

---

## Phase 2: Loading & Data Experience

Make the app feel fast and polished. Eliminate jarring spinner-to-content transitions.

### 2.1 Add `loading.tsx` files for all app routes
- **Problem:** No route-level loading states exist. Next.js App Router supports instant loading UI via `loading.tsx` files that show during navigation, but none are defined.
- **Files:** Create `loading.tsx` in every route directory under `frontend/app/(app)/`:
  - `dashboard/loading.tsx`
  - `accounts/loading.tsx`
  - `transactions/loading.tsx`
  - `sir-henry/loading.tsx`
  - `budget/loading.tsx`
  - `cashflow/loading.tsx`
  - `retirement/loading.tsx`
  - `portfolio/loading.tsx`
  - `market/loading.tsx`
  - `tax-strategy/loading.tsx`
  - `household/loading.tsx`
  - `insurance/loading.tsx`
  - `goals/loading.tsx`
  - `equity-comp/loading.tsx`
  - `business/loading.tsx`
  - `recurring/loading.tsx`
  - `life-events/loading.tsx`
  - `life-planner/loading.tsx`
  - `statements/loading.tsx`
  - `reports/loading.tsx`
  - `rules/loading.tsx`
  - `setup/loading.tsx`
  - `insights/loading.tsx`
  - `import/loading.tsx`
  - `admin/loading.tsx`
  - `tax/loading.tsx`
  - `tax-documents/loading.tsx`
  - `tax-reports/loading.tsx`
  - `investments/loading.tsx`
- **What:** Each `loading.tsx` should render a skeleton layout matching the page's structure (header skeleton, card skeletons, etc.), not just a spinner.

### 2.2 Create shared skeleton components
- **Problem:** Zero skeleton loader components exist. Every page shows a centered spinner over blank space.
- **Files:** Create in `frontend/components/ui/`:
  - `Skeleton.tsx` — base shimmer component (configurable width/height/rounded)
  - `PageSkeleton.tsx` — standard page layout skeleton (header + card grid)
  - `DashboardSkeleton.tsx` — dashboard-specific skeleton (stat cards + chart + transaction list)
  - `TableSkeleton.tsx` — table skeleton (header row + N body rows)
  - `CardSkeleton.tsx` — card skeleton with optional header/body/footer slots
- **What:** Pulse/shimmer animation matching the app's color scheme (stone-100/stone-200). Used by `loading.tsx` files and in-page loading states.

### 2.3 Add client-side data caching with SWR
- **Problem:** No caching. Every component mount fires fresh API requests. Navigating away and back reloads everything. Dashboard fires 7 requests on every mount.
- **Files:**
  - `frontend/package.json` — add `swr` dependency
  - `frontend/lib/api-client.ts` — add SWR fetcher wrapper
  - `frontend/lib/hooks/` — create `use{Domain}.ts` hooks (e.g., `useDashboard.ts`, `useAccounts.ts`)
  - All page files that currently use `useEffect` + `useState` for data fetching
- **What:**
  - Install SWR (`npm install swr`)
  - Create a `fetcher` function wrapping `request()` from `api-client.ts`
  - Create custom hooks: `useDashboard()`, `useAccounts()`, `useBudget()`, etc.
  - Each hook uses `useSWR(key, fetcher)` with appropriate `revalidateOnFocus` and `dedupingInterval` settings
  - Migrate pages one at a time from `useEffect`/`useState` to SWR hooks
  - Benefits: automatic deduplication, background revalidation, stale-while-revalidate, no re-spinner on navigation
- **Priority pages to migrate first:** Dashboard, Accounts, Transactions, Chat

### 2.4 Add Plaid sync completion polling
- **Problem:** After connecting a bank, the frontend waits a fixed 10 seconds then reloads. No way to know when background sync actually finishes.
- **Files:**
  - `api/routes/plaid.py` — add a `/plaid/sync-status/{item_id}` endpoint
  - `pipeline/db/schema.py` — add `sync_status` and `last_sync_at` fields to `PlaidItem` if not present
  - `frontend/components/setup/StepAccounts.tsx` — replace `setTimeout(10000)` with polling
  - `frontend/app/(app)/accounts/page.tsx` — same polling after sync trigger
- **What:**
  - Backend: Update `PlaidItem.sync_status` at each phase of the sync pipeline (syncing → categorizing → complete / error). Expose via `GET /plaid/sync-status/{item_id}`.
  - Frontend: After Plaid exchange, poll `/plaid/sync-status/{item_id}` every 2 seconds. Show a progress indicator (e.g., "Syncing transactions... Categorizing with AI... Complete!"). Stop polling when status is `complete` or `error`.

### 2.5 Eliminate duplicate API calls between SetupBanner and Dashboard
- **Problem:** `SetupBanner` makes 3 API calls (household, accounts, insurance) that the dashboard itself also makes.
- **Files:**
  - `frontend/components/setup/SetupBanner.tsx`
  - `frontend/app/(app)/dashboard/page.tsx`
- **What:** Pass the already-fetched data from the dashboard to `SetupBanner` as props, or use the SWR cache (from 2.3) so the banner reads from the same cache keys.

### 2.6 Expand ErrorBoundary coverage
- **Problem:** `ErrorBoundary` only wraps `SidebarLayout`. A render-time JS exception in any page component crashes the entire app shell.
- **Files:**
  - `frontend/components/ui/ErrorBoundary.tsx` — add a page-level variant
  - `frontend/app/(app)/layout.tsx` or individual page wrappers
- **What:** Add ErrorBoundary wrappers around each major page section. Consider a higher-order component or layout wrapper that catches per-page errors without destroying the sidebar/navigation.

---

## Phase 3: Entry Flow & Onboarding

First impressions. Clean up the entry flow and make onboarding seamless.

### 3.1 Rename "Test" button to "Get Started"
- **Problem:** The primary way to start building a real profile is labeled "Test" — confusing for real users.
- **Files:** `frontend/components/setup/LoginScreen.tsx`
- **What:**
  - Change button label from "Test" to "Get Started" (or "Use My Data")
  - Change subtitle from "Start fresh — build your financial profile" to something like "Build your personalized financial profile"
  - Update icon from `FlaskConical` to something more appropriate (e.g., `Rocket`, `ArrowRight`, or `UserPlus`)
  - Make this the primary/prominent button (larger, more visual weight)

### 3.2 Fix demo exit dead end
- **Problem:** The "Create Your Account" CTA in the DemoBanner clears localStorage and reloads to the LoginScreen — where "Sign In" is disabled. Dead end.
- **Files:**
  - `frontend/components/SidebarLayout.tsx` — `handleExitDemo()`
  - `frontend/components/ui/DemoBanner.tsx`
- **What:** Two options:
  - **Option A:** Change the DemoBanner CTA from "Create Your Account" to "Start With Your Own Data". On click, switch to local mode and go to the onboarding wizard (not the login screen).
  - **Option B:** Keep the login screen but change the flow so clicking "Create Your Account" from demo takes you directly to "Get Started" (local mode + onboarding), bypassing the login screen.

### 3.3 Fix Tauri demo users seeing login screen on every launch
- **Problem:** Tauri always transitions to `"auth"` after splash, even for returning demo users.
- **Files:** `frontend/components/AppShell.tsx` — `onSplashComplete` callback
- **What:** In `onSplashComplete`, check `DEMO_MODE_KEY` and `FIRST_RUN_KEY` from localStorage. If both are set, skip to `"done"` instead of `"auth"`. Same logic for returning local users.

### 3.4 Add onboarding resume logic (check server-side completion)
- **Problem:** Setup completion relies solely on `localStorage`. If localStorage is cleared, the full onboarding runs again even if the user's database has all their data.
- **Files:**
  - `frontend/components/AppShell.tsx` — phase determination logic
  - `api/routes/setup_status.py` — `GET /setup/status` endpoint
- **What:** On mount, if `FIRST_RUN_KEY` is not set in localStorage, call `GET /setup/status`. If the API reports `complete: true`, set the localStorage flag and skip to `"done"`. This creates a fallback that survives localStorage clearing.

### 3.5 Auto-advance wizard to first incomplete step on re-entry
- **Problem:** Returning users always start at "Household" step regardless of prior progress.
- **Files:** `frontend/components/setup/SetupWizard.tsx`
- **What:** After `loadExistingData()`, compute the first incomplete step:
  - Household: complete if `data.household` exists with income > 0
  - Accounts: complete if `data.accounts.length > 0`
  - Employer: complete if household has employer name
  - Benefits: complete if benefit packages exist
  - Insurance: complete if `data.policies.length > 0`
  - Business: complete if `data.entities.length > 0` (or skipped)
  - Life Events: always optional, count as complete
  - Rules: always optional, count as complete
- Set `step` to the first incomplete step key.

### 3.6 De-emphasize "Skip to finish" in onboarding
- **Problem:** "Skip to finish" link appears at every step, encouraging users to bypass data collection.
- **Files:** `frontend/components/setup/SetupWizard.tsx`
- **What:**
  - Remove "Skip to finish" from the first 3-4 steps (Household, Accounts, Employer, Benefits)
  - Keep it only on optional steps (Insurance, Business, Life Events, Rules)
  - Consider renaming to "Finish later" to better communicate that they can return

### 3.7 Remove or use `SPLASH_SEEN_KEY`
- **Problem:** `SPLASH_SEEN_KEY` is written on splash complete but never read. Dead code.
- **Files:**
  - `frontend/components/AppShell.tsx` — line 92
  - `frontend/lib/storage-keys.ts` — `SPLASH_SEEN_KEY` export
- **What:** Either:
  - **Remove it** (if splash should always play on Tauri launch)
  - **Use it** to skip the splash on subsequent Tauri launches (check in the Tauri init path)

### 3.8 Add FamilyMember data collection to onboarding (or post-onboarding nudge)
- **Problem:** The richer `FamilyMember` model (DOBs, school info, care costs) is never populated during onboarding. Only `HouseholdProfile` is written.
- **Files:**
  - `frontend/components/setup/StepHousehold.tsx` — add optional DOB fields
  - Or create a post-onboarding prompt on `/household` page
- **What:** Collect key family data during onboarding:
  - At minimum: DOB for each spouse (needed for retirement age calculations)
  - Optionally: children's DOBs and names
  - Don't over-collect — keep the step lean. Defer detailed data (school, care costs) to the household page post-onboarding.

### 3.9 Surface AI categorization progress during onboarding
- **Problem:** After connecting Plaid in Step 2, the user reaches Step 8 (Rules & AI Learning) but transactions may not have synced yet. The step shows "No transactions to analyze yet."
- **Files:**
  - `frontend/components/setup/StepRulesLearning.tsx`
  - `frontend/components/setup/StepAccounts.tsx`
- **What:** Two improvements:
  1. In `StepAccounts`, after Plaid success, show sync progress (from task 2.4) so the user knows data is loading.
  2. In `StepRulesLearning`, if accounts are connected but transactions haven't arrived yet, show a message like "Your transactions are still syncing. AI categorization will run automatically when they arrive." with an option to check again.

---

## Phase 4: Backend Architecture & Performance

Code quality, performance, and architectural consistency.

### 4.1 Fix N+1 query in chat `_tool_get_budget_status`
- **Problem:** One `SELECT SUM(amount)` per budget category in a loop. 15 categories = 15 queries.
- **Files:** `pipeline/ai/chat.py` — `_tool_get_budget_status` method
- **What:** Replace the per-category loop with a single grouped query:
  ```python
  select(
      Transaction.effective_category,
      func.sum(func.abs(Transaction.amount))
  ).where(
      Transaction.period_year == year,
      Transaction.period_month == month,
      Transaction.amount < 0,
      Transaction.is_excluded == False
  ).group_by(Transaction.effective_category)
  ```
  Then join results to the budget list in Python.

### 4.2 Cache `_build_system_prompt` results
- **Problem:** 5 sequential DB queries on every chat message to build the system prompt. Same data is re-fetched every turn.
- **Files:** `pipeline/ai/chat.py` — `_build_system_prompt` method
- **What:** Add a simple in-memory cache with a 60-second TTL, keyed on household_id (or a hash of the profile's `updated_at`). The prompt context doesn't change between chat turns. Invalidate on explicit data updates (e.g., household profile save).

### 4.3 Add missing database indexes
- **Problem:** Several frequently-filtered columns lack indexes.
- **Files:** `pipeline/db/migrations.py` — append new migration
- **What:** Add these indexes:
  ```sql
  CREATE INDEX IF NOT EXISTS ix_transaction_date ON transactions(date);
  CREATE INDEX IF NOT EXISTS ix_transaction_account_id ON transactions(account_id);
  CREATE INDEX IF NOT EXISTS ix_transaction_excluded ON transactions(is_excluded);
  CREATE INDEX IF NOT EXISTS ix_recurring_status ON recurring_transactions(status);
  ```

### 4.4 Extract business logic from `scenarios_calc.py` to pipeline
- **Problem:** 384-line route file with inline financial calculations and magic numbers (3% income growth, 7% returns, 2% inflation).
- **Files:**
  - `api/routes/scenarios_calc.py` — slim down to thin orchestrator
  - Create `pipeline/planning/scenario_projection.py` — new module
  - `pipeline/planning/__init__.py` — export new module
- **What:**
  - Move `compose_scenarios` logic → `ScenarioEngine.compose()`
  - Move `multi_year_projection` logic → `ScenarioEngine.project_multi_year()`
  - Move `retirement_impact` logic → `ScenarioEngine.retirement_impact()`
  - Extract magic numbers to named constants:
    ```python
    DEFAULT_INCOME_GROWTH_RATE = 0.03
    DEFAULT_INVESTMENT_RETURN_RATE = 0.07
    DEFAULT_INFLATION_RATE = 0.02
    AFFORDABILITY_THRESHOLDS = {"comfortable": 50, "manageable": 55, "stretched": 70}
    ```

### 4.5 Extract portfolio summary logic from `portfolio_analytics.py` to pipeline
- **Problem:** 445-line route file with aggregation logic, sector mapping, and price refresh orchestration.
- **Files:**
  - `api/routes/portfolio_analytics.py` — slim down
  - Create `pipeline/planning/portfolio_summary.py` — new module
- **What:**
  - Move `portfolio_summary` aggregation → `PortfolioSummaryEngine.build_summary()`
  - Move `refresh_prices` orchestration → `PortfolioSummaryEngine.refresh_all_prices()`
  - Move `SUBTYPE_TO_CLASS` mapping → pipeline constants
  - Convert quote cache upsert from N+1 to bulk operation

### 4.6 Extract tax summary fallback logic from `tax_analysis.py` to pipeline
- **Problem:** Tax data-source fallback chain (TaxItem → HouseholdProfile → none) is business logic in a route file.
- **Files:**
  - `api/routes/tax_analysis.py` — lines 43-73
  - Create or extend `pipeline/tax/tax_summary.py`
- **What:** Move the fallback chain into a `get_tax_summary_with_fallback(session, tax_year)` function in the pipeline layer.

### 4.7 Fix `annual_cost` dual source of truth in recurring transactions
- **Problem:** `RecurringTransaction` has a stored `annual_cost` column AND the route recomputes it from `amount * freq_mult`. Two sources that may disagree.
- **Files:**
  - `api/routes/recurring.py` — inline `annual_cost` calculation
  - `pipeline/db/schema.py` — `RecurringTransaction` model
- **What:** Pick one source:
  - **Preferred:** Compute `annual_cost` as a property on the model (or always compute in the query), and remove the stored column if it's only ever derived from `amount` and `frequency`.
  - **Alternative:** Ensure the stored column is always updated when `amount` or `frequency` changes, and use only the stored value in all reads.

### 4.8 Move inline Pydantic models from route files to `schemas.py`
- **Problem:** Several route files define their own Pydantic models instead of putting them in `api/models/schemas.py` per convention.
- **Files:**
  - `api/routes/scenarios_calc.py` — `ScenarioCalcIn`, `ComposeIn`, `MultiYearIn`, etc.
  - `api/routes/household_optimization.py` — `FilingComparisonIn`, `OptimizeIn`, etc.
  - `api/routes/household.py` — `HouseholdProfileIn`, `HouseholdProfileOut`
  - `api/models/schemas.py` — move models here
- **What:** Move all inline Pydantic models to `schemas.py` and import from there. Keeps the API contract in one place.

### 4.9 Move `_fetch_actuals` out of route import chain
- **Problem:** `budget_forecast.py` imports from `budget.py` at call time to avoid circular import.
- **Files:**
  - `api/routes/budget_forecast.py` — line 24-28
  - `api/routes/budget.py` — `_fetch_actuals` function
  - Create or extend a pipeline module
- **What:** Move `_fetch_actuals` to `pipeline/planning/budget.py` (or similar) so both route files can import from the pipeline layer without circular dependencies.

---

## Phase 5: UI/UX Polish

Visual consistency, information density, and design quality.

### 5.1 Add `font-display` to PageHeader
- **Problem:** `PageHeader`'s `h1` renders in Inter instead of Plus Jakarta Sans. The `font-display` class is missing.
- **Files:** `frontend/components/ui/PageHeader.tsx`
- **What:** Add `font-display` class to the `h1` element. This fixes heading typography across every page that uses `PageHeader`.

### 5.2 Consolidate brand color to design tokens
- **Problem:** `bg-[#16A34A]` is hardcoded in 8+ files. The CSS variable `--accent` exists but isn't used.
- **Files:**
  - `frontend/app/globals.css` or Tailwind config — ensure `--accent` is defined
  - All files using `bg-[#16A34A]`, `text-[#16A34A]`, `border-[#16A34A]`
- **What:** Create a Tailwind utility (e.g., `bg-accent`, `text-accent`) mapped to `--accent`. Find-and-replace all hardcoded `#16A34A` references with the token. This makes future brand changes trivial.

### 5.3 Fix sub-12px text in sidebar
- **Problem:** `text-[10px]` and `text-[11px]` appear in sidebar section labels and card sub-labels. These are below the legibility threshold.
- **Files:**
  - `frontend/components/Sidebar.tsx`
  - `frontend/components/setup/SetupWizard.tsx` (step labels)
  - Any other files using `text-[10px]` or `text-[11px]`
- **What:** Replace all instances of `text-[10px]` with `text-xs` (12px minimum). Replace `text-[11px]` with `text-xs`. This is an accessibility and legibility fix.

### 5.4 Reduce dashboard information density
- **Problem:** Dashboard has 15+ sections. Too much information on first load. No clear visual hierarchy.
- **Files:** `frontend/app/(app)/dashboard/page.tsx`
- **What:**
  - Add a **hero section** at the top: one dominant metric (net worth trajectory or monthly savings rate) with a large number, small sparkline, and trend indicator
  - Group remaining widgets into collapsible sections or tabs:
    - "Spending" tab: budget summary, recent transactions, cash flow trend
    - "Wealth" tab: net worth, goals progress, portfolio summary
    - "Actions" tab: insights, upcoming life events, reminders
  - Remove the "Quick Access" grid at the bottom (duplicates sidebar navigation)
  - Target: first-load viewport shows hero + 3-4 key widgets, not 15

### 5.5 Fix retirement page ordering
- **Problem:** Input form appears below results. "What If" scenarios are shown before the user has digested their base scenario.
- **Files:** `frontend/app/(app)/retirement/page.tsx`
- **What:**
  - Move the input form/profile section above the results
  - Move "What If" scenario cards (Lump Sum, Second Income, Monte Carlo) into a collapsible section or secondary tab that appears after the base scenario
  - Ensure the page reads top-to-bottom: inputs → base results → scenarios

### 5.6 Review and tighten spacing across data-heavy pages
- **Files:** All pages in `frontend/app/(app)/` — especially `market/page.tsx`, `portfolio/`, `tax-strategy/`
- **What:** Audit for:
  - Excessive padding between sections (reduce `gap-8` to `gap-6` or `gap-4` where appropriate)
  - Cards that could be combined (e.g., two small stat cards → one card with two columns)
  - Tables with too many columns on mobile — hide less-important columns on small screens
  - Long scrolling pages that could benefit from tabs or collapse sections

### 5.7 Ensure consistent page structure pattern
- **Files:** All page files in `frontend/app/(app)/`
- **What:** Standardize every page to follow this structure:
  1. `<PageHeader>` with title, optional subtitle, and action buttons
  2. Banners (SetupBanner, error banner, success banner) — conditional
  3. Loading state → skeleton (not spinner)
  4. Empty state → `EmptyState` component with CTA
  5. Data state → main content
  - This is mostly followed but inconsistent across some pages

---

## Phase 6: Data Connectivity & Polish (stretch)

These are lower priority but improve the overall experience.

### 6.1 Make scenario calculations read from DB instead of request body
- **Problem:** `/scenarios/calculate` requires the frontend to pass all financial parameters. If household data changed but frontend sends stale values, calculations are wrong.
- **Files:** `api/routes/scenarios_calc.py`
- **What:** Add an option to read baseline financial data from the DB (HouseholdProfile + Accounts) instead of requiring it in the request body. Frontend can still override individual values.

### 6.2 Add per-page ErrorBoundary wrappers
- **Problem:** A crash in any page component takes down the entire app shell.
- **Files:** `frontend/app/(app)/layout.tsx` or individual page wrappers
- **What:** Wrap `{children}` in a page-level `ErrorBoundary` that shows an error card with a "Reload this page" button, while keeping the sidebar/navigation intact.

### 6.3 Add insurance step household dependency enforcement
- **Problem:** `StepInsurance` creates policies with `household_id: null` if Step 1 was skipped.
- **Files:** `frontend/components/setup/StepInsurance.tsx`
- **What:** If `data.household` is null, show a card saying "Complete the Household step first to link your insurance policies." (Same pattern as `StepBenefits`.)

### 6.4 Parallelize read-only chat tool calls
- **Problem:** When Claude requests multiple tool calls in one round, they execute sequentially.
- **Files:** `pipeline/ai/chat.py` — agentic loop
- **What:** For tool calls within a single response that are all read-only (no writes), use `asyncio.gather()` to run them in parallel. Tag each tool as read-only or read-write. Only parallelize reads.

### 6.5 Make Plaid sync initial delay configurable
- **Problem:** Hard-coded `asyncio.sleep(60)` before the first periodic sync.
- **Files:** `api/main.py` — `_periodic_plaid_sync`
- **What:** Read from `PLAID_SYNC_INITIAL_DELAY_SECONDS` env var, default 60.

---

## Execution Order

The phases are designed to be worked through in order, but within each phase, tasks can be parallelized:

```
Phase 1 (Foundation)     →  Must complete first. Blocks nothing else.
Phase 2 (Loading)        →  Can start after 1.2 and 1.3 are done.
Phase 3 (Entry/Onboard)  →  Can start in parallel with Phase 2.
Phase 4 (Backend)        →  Independent of frontend phases.
Phase 5 (UI/UX)          →  Can start any time; no backend dependencies.
Phase 6 (Stretch)        →  After Phases 1-5 are complete.
```

### Suggested sprint breakdown:
- **Sprint 1:** Phase 1 (all 4 items) + Phase 5.1-5.3 (quick UI wins)
- **Sprint 2:** Phase 2.1-2.3 (loading infrastructure) + Phase 3.1-3.3 (entry flow fixes)
- **Sprint 3:** Phase 2.4-2.6 (data experience) + Phase 3.4-3.6 (onboarding resume)
- **Sprint 4:** Phase 4 (backend architecture)
- **Sprint 5:** Phase 5.4-5.7 (UI density + consistency) + Phase 3.7-3.9 (onboarding polish)
- **Sprint 6:** Phase 6 (stretch goals)
