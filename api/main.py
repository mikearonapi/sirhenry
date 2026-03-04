"""
FastAPI application entry point.
Run with: uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import engine
from api.routes import (
    account_links, accounts, assets, benchmarks, budget, budget_forecast, chat,
    documents, entities,
    equity_comp, family_members, goal_suggestions, goals,
    household, household_optimization,
    import_routes, insights, insurance,
    life_events, market, plaid, privacy,
    portfolio, portfolio_analytics, portfolio_crypto,
    recurring, reminders, reports, retirement, retirement_scenarios,
    scenarios, scenarios_calc, setup_status, tax, tax_analysis, tax_strategies,
    tax_modeling, transactions,
)
from pipeline.db import init_db  # importing pipeline.db also registers all extended models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Install PII redaction filter on all loggers (before any data is loaded)
from pipeline.security.logging import install_pii_filter
install_pii_filter()


async def _seed_all_reminders() -> None:
    """Seed all reminder categories at startup: tax, Amazon, financial, Plaid."""
    from api.database import AsyncSessionLocal
    from api.routes.reminders import seed_all_reminders

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await seed_all_reminders(session)
    total = sum(result.values())
    if total:
        logger.info(f"Auto-seeded {total} reminders: {result}")
    else:
        logger.info("All reminders already seeded.")


async def _periodic_plaid_sync(interval_seconds: float) -> None:
    """Background loop: syncs Plaid items on a fixed interval.
    Runs AI categorization + Amazon order matching after each sync."""
    await asyncio.sleep(60)  # initial delay to let startup finish
    while True:
        try:
            from api.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    from pipeline.plaid.sync import sync_all_items
                    result = await sync_all_items(session, run_categorize=True)
                    logger.info(f"Periodic Plaid sync: {result}")
        except Exception as e:
            logger.warning(f"Periodic Plaid sync failed: {e}")
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register field-level encryption events before any DB operations
    from pipeline.db.field_encryption import register_encryption_events
    register_encryption_events()

    logger.info("Initializing database...")
    await init_db(engine)
    logger.info("Database ready.")

    # Run tracked schema migrations (idempotent, applied at most once)
    try:
        from api.database import AsyncSessionLocal
        from pipeline.db.migrations import run_migrations
        async with AsyncSessionLocal() as session:
            await run_migrations(session)
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        raise

    # Load known PII names into the logging redaction filter
    try:
        from pipeline.security.logging import load_known_names_from_db, update_known_names
        async with AsyncSessionLocal() as session:
            names = await load_known_names_from_db(session)
            if names:
                update_known_names(names)
    except Exception as e:
        logger.warning(f"PII name loading failed (non-fatal): {e}")

    # Clean up stale import files older than 7 days
    try:
        from pipeline.security.file_cleanup import cleanup_old_files
        for import_dir in ["data/imports/credit-cards", "data/imports/tax-documents",
                           "data/imports/investments", "data/imports/amazon",
                           "data/processed/tax-documents"]:
            cleanup_old_files(import_dir, max_age_days=7)
    except Exception as e:
        logger.warning(f"Import file cleanup failed (non-fatal): {e}")

    # Auto-recompute financial period summaries for recent years
    try:
        from api.database import AsyncSessionLocal
        from pipeline.ai.report_gen import recompute_all_periods
        from datetime import datetime, timezone
        current_year = datetime.now(timezone.utc).year
        async with AsyncSessionLocal() as session:
            from sqlalchemy import func, select as sa_select
            from pipeline.db.schema import Transaction
            result = await session.execute(
                sa_select(func.distinct(Transaction.period_year)).where(Transaction.period_year.isnot(None))
            )
            years_with_data = sorted([r[0] for r in result if r[0]])
            if not years_with_data:
                years_with_data = [current_year]
            for yr in years_with_data:
                await recompute_all_periods(session, yr)
            await session.commit()
        logger.info(f"Auto-recomputed period summaries for years: {years_with_data}")
    except Exception as e:
        logger.warning(f"Period auto-recompute failed (non-fatal): {e}")

    # Validate Plaid environment and encryption key
    plaid_env = os.environ.get("PLAID_ENV", "sandbox")
    encryption_key = os.environ.get("PLAID_ENCRYPTION_KEY", "")
    if plaid_env == "sandbox":
        logger.warning(
            "PLAID_ENV=sandbox — using test data only. "
            "Set PLAID_ENV=development in .env and update PLAID_SECRET "
            "for real bank connections (free, 100 items)."
        )
    else:
        logger.info(f"Plaid environment: {plaid_env}")

    if plaid_env == "production" and not encryption_key.strip():
        logger.error(
            "CRITICAL: PLAID_ENCRYPTION_KEY is not set but PLAID_ENV=production. "
            "Access tokens will be stored in PLAINTEXT. "
            "Generate a key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        raise RuntimeError(
            "Refusing to start: PLAID_ENCRYPTION_KEY must be set when PLAID_ENV=production"
        )
    elif encryption_key.strip():
        try:
            from cryptography.fernet import Fernet
            Fernet(encryption_key.encode())
            logger.info("Plaid encryption key: valid ✓")
        except Exception:
            logger.error("PLAID_ENCRYPTION_KEY is set but is not a valid Fernet key")
            raise RuntimeError(
                "Invalid PLAID_ENCRYPTION_KEY — must be a base64 Fernet key (44 chars). "
                "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

    # Seed all reminders (tax, Amazon, financial reviews, Plaid health, etc.)
    try:
        await _seed_all_reminders()
    except Exception as e:
        logger.warning(f"Reminder seeding failed (non-fatal): {e}")

    # Start periodic Plaid sync (configurable via PLAID_SYNC_INTERVAL_HOURS, 0 = disabled)
    sync_interval_hours = float(os.environ.get("PLAID_SYNC_INTERVAL_HOURS", "6"))
    sync_task = None
    if sync_interval_hours > 0:
        sync_task = asyncio.create_task(_periodic_plaid_sync(sync_interval_hours * 3600))
        logger.info(f"Plaid auto-sync scheduled every {sync_interval_hours:.1f}h")
    else:
        logger.info("Plaid auto-sync disabled (PLAID_SYNC_INTERVAL_HOURS=0)")

    yield

    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()


app = FastAPI(
    title="Sir Henry API",
    description="AI-powered financial planning API for HENRYs",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
# Auto-detect LAN IPs so the frontend can reach the API from any local machine
try:
    import socket
    hostname = socket.gethostname()
    for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
        ip = info[4][0]
        if ip != "127.0.0.1":
            cors_origins.append(f"http://{ip}:3000")
            cors_origins.append(f"http://{ip}:3001")
except Exception:
    pass
extra = os.environ.get("CORS_ORIGINS", "")
if extra:
    cors_origins.extend(o.strip() for o in extra.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(account_links.router)
app.include_router(accounts.router)
app.include_router(assets.router)
app.include_router(transactions.router)
app.include_router(documents.router)
app.include_router(entities.router)
app.include_router(import_routes.router)
app.include_router(reports.router)
app.include_router(insights.router)
app.include_router(tax.router)
app.include_router(tax_analysis.router, prefix="/tax")
app.include_router(tax_strategies.router, prefix="/tax")
app.include_router(plaid.router)
app.include_router(budget.router)
app.include_router(budget_forecast.router, prefix="/budget")
app.include_router(recurring.router)
app.include_router(goal_suggestions.router)
app.include_router(goals.router)
app.include_router(reminders.router)
app.include_router(chat.router)
app.include_router(portfolio.router)
app.include_router(portfolio_analytics.router, prefix="/portfolio")
app.include_router(portfolio_crypto.router, prefix="/portfolio")
app.include_router(market.router)
app.include_router(retirement.router)
app.include_router(retirement_scenarios.router, prefix="/retirement")
app.include_router(scenarios.router)
app.include_router(scenarios_calc.router, prefix="/scenarios")
app.include_router(equity_comp.router)
app.include_router(household.router)
app.include_router(household_optimization.router, prefix="/household")
app.include_router(family_members.router)
app.include_router(life_events.router)
app.include_router(insurance.router)
app.include_router(privacy.router)
app.include_router(setup_status.router)
app.include_router(tax_modeling.router)
app.include_router(benchmarks.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sirhenry-api"}
