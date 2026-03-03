# Sir Henry — Architecture

> Source of truth for project structure. Updated 2026-03-02.

---

## Stack

| Layer | Technology | Entry Point |
|-------|-----------|-------------|
| Frontend | Next.js 15 + React 19 + Tailwind v4 | `frontend/` |
| API | FastAPI (Python 3.12) | `api/main.py` |
| Database | SQLite via SQLAlchemy async + aiosqlite | `pipeline/db/schema.py` |
| AI | Anthropic Claude (chat + categorization) | `pipeline/ai/` |
| Market Data | yfinance | `pipeline/market/` |
| Bank Connections | Plaid | `pipeline/plaid/` |

---

## Directory Map

```
.
├── api/                    # FastAPI backend
│   ├── main.py             # App entry, CORS, lifespan, router registration
│   ├── database.py         # Engine + AsyncSessionLocal factory
│   └── routes/             # One file per domain (27 route files)
│       ├── accounts.py
│       ├── budget.py
│       ├── chat.py
│       ├── equity_comp.py
│       ├── household.py
│       ├── insights.py
│       ├── insurance.py
│       ├── life_events.py
│       ├── portfolio.py
│       ├── retirement.py
│       ├── scenarios.py
│       ├── tax.py
│       ├── tax_modeling.py
│       ├── transactions.py
│       └── ... (13 more)
│
├── pipeline/               # Business logic, data processing, AI
│   ├── __init__.py
│   ├── utils.py            # DATABASE_URL, shared constants
│   ├── ai/                 # AI-powered features
│   │   ├── categorizer.py  # Transaction categorization via Claude
│   │   ├── chat.py         # "Ask Sir Henry" conversational AI
│   │   ├── report_gen.py   # Period summary computation
│   │   └── tax_analyzer.py # Tax strategy generation
│   ├── analytics/
│   │   ├── insights.py     # Outlier detection, normalization, YoY
│   │   └── net_worth.py    # Net worth snapshots
│   ├── db/
│   │   ├── schema.py       # *** SINGLE SOURCE OF TRUTH for all ORM models ***
│   │   ├── schema_extended.py  # Re-export shim (backward compat)
│   │   ├── schema_henry.py    # Re-export shim (backward compat)
│   │   ├── schema_household.py # Re-export shim (backward compat)
│   │   ├── models.py       # Data Access Layer (DAL) functions
│   │   ├── migrations.py   # Tracked schema migrations (run on startup)
│   │   └── __init__.py     # Barrel — re-exports all models + DAL functions
│   ├── importers/          # Data ingest (CSV, Amazon, PDF)
│   ├── market/             # Market data fetching (yfinance)
│   ├── parsers/            # File format parsers
│   ├── plaid/              # Plaid bank connection + sync
│   ├── planning/           # Financial planning engines
│   │   ├── retirement.py   # Retirement calculator (deterministic)
│   │   ├── equity_comp.py  # RSU/ISO/ESPP analysis
│   │   ├── life_scenarios.py # "Can I afford X?" engine
│   │   ├── tax_modeling.py # Roth conversion, S-Corp, multi-year
│   │   └── household_optimizer.py
│   └── tax/                # Tax computation utilities
│
├── frontend/               # Next.js app
│   ├── app/                # App Router pages (one dir per route)
│   │   ├── page.tsx        # Dashboard
│   │   ├── layout.tsx      # Root layout (fonts, sidebar)
│   │   ├── globals.css     # Design tokens, brand colors
│   │   ├── household/      # 2501-line page (needs splitting — tracked)
│   │   ├── accounts/       # 1382-line page (needs splitting — tracked)
│   │   └── ... (18 more page dirs)
│   ├── components/
│   │   ├── Sidebar.tsx     # Main navigation
│   │   ├── AiChat.tsx      # "Ask Sir Henry" floating chat
│   │   ├── TrajectoryChart.tsx  # Retirement fan chart
│   │   ├── SidebarLayout.tsx
│   │   ├── insights/       # Insight sub-components
│   │   └── ui/             # Shared UI primitives (Card, Badge, StatCard, etc.)
│   ├── lib/
│   │   ├── api.ts          # Barrel — re-exports all api-*.ts domain files
│   │   ├── api-client.ts   # BASE url + request() fetch wrapper
│   │   ├── api-*.ts        # Domain API functions (25 files)
│   │   └── utils.ts        # formatCurrency, formatDate, cn()
│   ├── types/
│   │   ├── api.ts          # Barrel — re-exports all domain type files
│   │   └── *.ts            # Domain type files (19 files)
│   ├── hooks/
│   └── public/
│       └── henry-brand.png # Brand logo
│
├── scripts/                # Utility / migration / analysis scripts
│   └── README.md           # Documents every script's purpose and category
│
├── tests/                  # Pytest test suite
│   ├── test_retirement.py  # Retirement calculator tests (23 tests)
│   ├── test_migrations.py  # Migration system tests (5 tests)
│   └── conftest.py
│
├── docs/                   # Reference documentation
│   ├── ARCHITECTURE.md     # THIS FILE — project structure source of truth
│   ├── BRAND.md            # Brand guidelines, colors, typography, voice
│   ├── DESIGN.md           # App design principles, UX flows, layout
│   ├── FEATURES.md         # Feature requirements, data models, user flows
│   └── Henry.md            # Product vision, market positioning
│
├── research/               # Market research and opportunity analysis
│
├── data/                   # *** GITIGNORED — personal financial data ***
│
├── .gitignore              # Excludes data/, .env, *.db, scripts artifacts
├── .env                    # API keys (never committed)
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # API + frontend containers
├── Dockerfile              # API container build
├── pytest.ini              # Test configuration
└── README.md
```

---

## Key Design Decisions

### Single Source of Truth for ORM Models
All SQLAlchemy models live in `pipeline/db/schema.py`. The satellite files
(`schema_extended.py`, `schema_henry.py`, `schema_household.py`) are thin
re-export shims for backward compatibility only.

### Pydantic Schemas Live in Route Files
Each API route file defines its own Pydantic request/response models inline.
There is no centralized Pydantic schema file — each route owns its contract.

### Frontend Type System
TypeScript interfaces live in `frontend/types/` split by domain (19 files).
`frontend/types/api.ts` is a barrel that re-exports everything.

### Frontend API Client
API fetch functions live in `frontend/lib/` split by domain (25 files).
`frontend/lib/api.ts` is a barrel that re-exports everything.

### Migration System
Schema migrations are tracked in `pipeline/db/migrations.py` with a
`_schema_migrations` table. Each migration runs at most once. New migrations
are appended to the `MIGRATIONS` list.

### Data Security
The entire `data/` directory, all `*.db` files, `.env`, and `scripts/*.json`
are excluded from version control via `.gitignore`.

---

## Running the App

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Tests
python -m pytest tests/ -v

# Docker
docker compose up --build
```

---

## Known Tech Debt

| Item | File | Status |
|------|------|--------|
| household/page.tsx is 2501 lines | `frontend/app/household/page.tsx` | Tracked for splitting |
| accounts/page.tsx is 1382 lines | `frontend/app/accounts/page.tsx` | Tracked for splitting |
| models.py is a monolithic DAL | `pipeline/db/models.py` (788 lines) | Future split by domain |
