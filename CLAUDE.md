# SirHENRY — Claude Code Project Guide

## What This Is
AI-powered financial advisor for HENRYs (High Earners, Not Rich Yet). Local-first SaaS — user financial data stays in a per-user SQLite database, never centralized.

## Tech Stack
- **Frontend:** Next.js 16 + React 19 + Tailwind v4 + TypeScript (`frontend/`)
- **API:** FastAPI + Python 3.12 + SQLAlchemy async + aiosqlite (`api/`)
- **Database:** SQLite per-user (`data/db/financials.db`)
- **AI:** Anthropic Claude via `pipeline/ai/`
- **Bank Sync:** Plaid (`pipeline/plaid/`)
- **Market Data:** yfinance (`pipeline/market/`)

## Directory Structure
```
api/                    # FastAPI backend
  main.py               # App entry, lifespan, CORS, router registration
  database.py           # AsyncSession factory (get_session dependency)
  models/schemas.py     # Shared Pydantic schemas (API contract)
  routes/               # 27 route modules (one per domain)
pipeline/               # Business logic (NOT in routes)
  ai/                   # Claude integrations (chat, categorizer, tax_analyzer, report_gen)
  db/                   # ORM schema, migrations, encryption, DAL
    schema.py           # *** SINGLE SOURCE OF TRUTH for all ORM models ***
    models.py           # Data access layer functions
    migrations.py       # Startup migrations (append-only)
    encryption.py       # Fernet encryption for Plaid tokens
  importers/            # CSV, Amazon, credit card, investment, tax doc parsers
  market/               # Yahoo Finance, crypto, economic data
  plaid/                # Plaid client and sync logic
  planning/             # Retirement, portfolio, tax, equity, scenarios engines
  tax/                  # Tax calculator and constants (federal brackets, limits)
frontend/               # Next.js app
  app/page.tsx          # Public landing page (waitlist)
  app/(app)/            # Internal app pages (25+ routes, gated by AppShell)
  components/           # React components (ui/, accounts/, household/, insights/)
  hooks/                # Custom React hooks (useTabState, useInsights, etc.)
  lib/                  # API client functions (api-{domain}.ts → api.ts barrel)
  types/                # TypeScript type definitions ({domain}.ts → api.ts barrel)
scripts/                # Utility scripts (data audit, migration, import helpers)
data/                   # GITIGNORED — personal financial data, SQLite DB
docs/                   # Architecture, features, design, brand docs
research/               # Market research, audience analysis
tests/                  # pytest test suite
```

## Key Conventions

### Backend (Python)
- Routes are thin orchestrators: validate → call pipeline → return response
- Business logic lives in `pipeline/`, never in route files
- All routes use `Depends(get_session)` — do NOT call `session.commit()` manually (the dependency auto-commits)
- Use `await session.flush()` if you need generated IDs before the auto-commit
- ORM models: ONLY in `pipeline/db/schema.py` (the shim files schema_extended/henry/household are re-exports)
- Route files target <400 lines; pipeline modules target <300 lines
- Tax constants (brackets, limits, deductions) live in `pipeline/tax/constants.py` — import from there

### Frontend (TypeScript/React)
- Pages (`app/*/page.tsx`) should be thin: fetch data, compose components — target <400 lines
- Domain components in `components/{domain}/`, reusable UI in `components/ui/`
- Types in `types/{domain}.ts`, exported through `types/api.ts` barrel
- API functions in `lib/api-{domain}.ts`, exported through `lib/api.ts` barrel
- All API calls use `request()` from `lib/api-client.ts` (centralized fetch wrapper)
- NO `any` type — use `unknown` then narrow
- Financial numbers: `font-mono` (JetBrains Mono); Headings: `font-display` (Plus Jakarta Sans)
- Brand colors: Henry Green (#16A34A) for CTAs, Warm Gold for milestones only
- **Tabbed pages**: Use `TabBar` (`components/ui/TabBar.tsx`) + `useTabState` (`hooks/useTabState.ts`) for pages with multiple content sections. Tab constants go in `components/{domain}/constants.ts`. Variants: "underline" (default) or "pill". URL hash persistence via `#tab=<id>`.
- **Route gating**: `AppShell` handles client-side phase-based route gating (splash → auth → welcome → goals → setup → done). No server middleware needed for route blocking.

### Database
- `pipeline/db/schema.py` = single source of truth for all models
- Never create model classes outside this file
- Migrations in `migrations.py` are append-only, run at startup
- Use `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN` patterns
- Never use destructive migrations without explicit approval

## Development

### Run locally
```bash
# Both API + Frontend (recommended)
./dev.sh
# → API: http://localhost:8000, Frontend: http://localhost:3000

# Or separately:
.venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

### Run tests
```bash
pytest                    # all tests
pytest tests/test_retirement.py  # specific test
```

### Key environment variables
Copy `.env.example` to `.env` and fill in:
- `ANTHROPIC_API_KEY` — required for AI features
- `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` — required for bank sync
- `PLAID_ENCRYPTION_KEY` — REQUIRED in production (Fernet key for token encryption)

## Security Rules — NEVER Violate
- NEVER commit `.env`, `data/`, `*.db`, or `scripts/*.json` — all gitignored
- NEVER log PII (names, account numbers, SSNs, balances, transaction descriptions)
- NEVER store plaintext Plaid access tokens — always encrypt with Fernet
- NEVER hardcode API keys — they live only in `.env`
- NEVER include financial data in error messages
- NEVER send user data to external services except Plaid (sync) and Claude (AI features)
- Plaid tokens must be encrypted via `pipeline/db/encryption.py` before DB storage

## Pre-Launch State
The app is in pre-launch mode. `AppShell` handles client-side route gating — unauthenticated users see the landing page. Internal pages are accessible in "Get Started" (test with own data) and "Demo" (pre-populated demo data) modes.

## Authoritative Docs (priority order)
1. This file (CLAUDE.md) — project guide for AI coding assistants
2. `docs/ARCHITECTURE.md` — detailed project structure
3. `docs/FEATURES.md` — feature requirements and data models
4. `docs/DESIGN.md` — UX flows and layout
5. `docs/BRAND.md` — brand guidelines
6. `.cursor/rules/` — additional coding conventions (also applies to Claude Code)
