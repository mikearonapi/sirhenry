"""
Async SQLAlchemy engine + session factory for FastAPI dependency injection.

Supports runtime database switching (local vs demo) for the desktop app.
"""
import logging
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipeline.utils import DATABASE_URL

logger = logging.getLogger(__name__)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Primary engine (user's local data)
engine = create_async_engine(DATABASE_URL, echo=False, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Active session factory — can be swapped at runtime
_active_session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal
_active_mode: str = "local"


def _demo_db_url() -> str:
    """Path to the demo database, next to the primary database."""
    # SQLite URL format: sqlite+aiosqlite:///path (3 slashes + path)
    # Path can be relative (./data/db/x.db) or absolute (/Users/x/.sirhenry/data/x.db)
    prefix = "sqlite+aiosqlite:///"
    if DATABASE_URL.startswith(prefix):
        raw_path = DATABASE_URL[len(prefix):]  # e.g. "./data/db/financials.db"
        primary_path = os.path.abspath(raw_path)
        data_dir = os.path.dirname(primary_path)
        demo_path = os.path.join(data_dir, "demo.db")
        return f"{prefix}{demo_path}"
    return DATABASE_URL.replace("financials.db", "demo.db")


async def switch_to_mode(mode: str) -> str:
    """
    Switch the active database. Returns the mode that was set.

    - "local": user's real financial data (financials.db)
    - "demo": synthetic demo data (demo.db, auto-initialized if missing)
    """
    global _active_session_factory, _active_mode

    if mode == _active_mode:
        return mode

    if mode == "local":
        _active_session_factory = AsyncSessionLocal
        _active_mode = "local"
        logger.info("Switched to local database")
        return "local"

    if mode == "demo":
        # Back up user's local database before switching to demo mode
        from pipeline.db.backup import backup_database
        backup_database(DATABASE_URL, reason="pre-demo-switch")

        demo_url = _demo_db_url()
        demo_engine = create_async_engine(
            demo_url, echo=False,
            connect_args={"check_same_thread": False},
        )

        # Initialize schema + seed if the demo DB is empty/new
        from pipeline.db import init_db
        await init_db(demo_engine)

        # Run migrations on demo DB
        demo_sf = async_sessionmaker(demo_engine, expire_on_commit=False)
        async with demo_sf() as session:
            from pipeline.db.migrations import run_migrations
            await run_migrations(session)

        # Seed demo data if not already seeded
        async with demo_sf() as session:
            async with session.begin():
                from pipeline.demo.seeder import get_demo_status, seed_demo_data
                status = await get_demo_status(session)
                if not status["active"]:
                    try:
                        await seed_demo_data(session)
                        logger.info("Demo database seeded")
                    except ValueError:
                        pass  # Already has data

        _active_session_factory = demo_sf
        _active_mode = "demo"
        logger.info(f"Switched to demo database: {demo_url}")
        return "demo"

    raise ValueError(f"Unknown mode: {mode}")


def get_active_mode() -> str:
    """Return the current database mode."""
    return _active_mode


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _active_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
