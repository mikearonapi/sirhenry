"""Shared fixtures for SIT integration tests.

Module-scoped fixtures seed demo data ONCE and reuse across all tests in a module.
Function-scoped ``fresh_*`` fixtures create independent databases for mutation tests.
"""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from pipeline.db.schema import Base


# ---------------------------------------------------------------------------
# Module-scoped fixtures — seed demo data ONCE for the entire module
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def demo_engine():
    """In-memory SQLite async engine with all ORM tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def demo_session_factory(demo_engine):
    """Session factory bound to the shared demo engine."""
    return async_sessionmaker(
        demo_engine, class_=AsyncSession, expire_on_commit=False,
    )


@pytest_asyncio.fixture(scope="module")
async def demo_seed(demo_session_factory):
    """Run migrations and seed demo data once for the entire test module."""
    from pipeline.db.migrations import run_migrations
    from pipeline.demo.seeder import seed_demo_data

    async with demo_session_factory() as session:
        await run_migrations(session)

    async with demo_session_factory() as session:
        counts = await seed_demo_data(session)
        await session.commit()

    return counts


@pytest_asyncio.fixture(scope="module")
async def demo_app(demo_session_factory, demo_seed):
    """FastAPI app with all routers, using the demo database."""
    from api.database import get_session
    from api.routes import (
        account_links, accounts, assets, auth_routes, benchmarks, budget,
        chat, demo, documents, entities, error_reports,
        equity_comp, family_members, goal_suggestions, goals,
        household,
        import_routes, income, insights, insurance,
        life_events, market, plaid, privacy,
        portfolio,
        recurring, reminders, reports, retirement, rules,
        scenarios, setup_status, smart_defaults, tax,
        tax_modeling, transactions, user_context, valuations,
    )

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)

    # Register routers (mirrors api/main.py:269-312)
    for router_module in [
        account_links, accounts, assets, transactions, documents, entities,
        import_routes, reports, insights, tax, plaid, budget, recurring,
        goal_suggestions, goals, reminders, chat, portfolio, market,
        retirement, scenarios, equity_comp, household, family_members,
        life_events, insurance, privacy, setup_status, tax_modeling,
        benchmarks, smart_defaults, income, rules, user_context, valuations,
        auth_routes, demo, error_reports,
    ]:
        app.include_router(router_module.router)

    async def override_get_session():
        async with demo_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest_asyncio.fixture(scope="module")
async def client(demo_app):
    """HTTP client for the demo app."""
    async with AsyncClient(
        transport=ASGITransport(app=demo_app),
        base_url="http://test",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def demo_session(demo_session_factory, demo_seed):
    """Function-scoped session for direct DB queries in assertions."""
    async with demo_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Function-scoped fixtures — fresh DB per test (for mutation tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def fresh_engine():
    """Per-test in-memory engine for tests that mutate data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def fresh_session_factory(fresh_engine):
    return async_sessionmaker(
        fresh_engine, class_=AsyncSession, expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def fresh_seed(fresh_session_factory):
    """Seed a fresh DB for mutation tests."""
    from pipeline.db.migrations import run_migrations
    from pipeline.demo.seeder import seed_demo_data

    async with fresh_session_factory() as session:
        await run_migrations(session)

    async with fresh_session_factory() as session:
        counts = await seed_demo_data(session)
        await session.commit()

    return counts


@pytest_asyncio.fixture
async def fresh_app(fresh_session_factory, fresh_seed):
    """Per-test FastAPI app for mutation tests."""
    from api.database import get_session
    from api.routes import (
        account_links, accounts, assets, auth_routes, benchmarks, budget,
        chat, demo, documents, entities, error_reports,
        equity_comp, family_members, goal_suggestions, goals,
        household,
        import_routes, income, insights, insurance,
        life_events, market, plaid, privacy,
        portfolio,
        recurring, reminders, reports, retirement, rules,
        scenarios, setup_status, smart_defaults, tax,
        tax_modeling, transactions, user_context, valuations,
    )

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)
    for router_module in [
        account_links, accounts, assets, transactions, documents, entities,
        import_routes, reports, insights, tax, plaid, budget, recurring,
        goal_suggestions, goals, reminders, chat, portfolio, market,
        retirement, scenarios, equity_comp, household, family_members,
        life_events, insurance, privacy, setup_status, tax_modeling,
        benchmarks, smart_defaults, income, rules, user_context, valuations,
        auth_routes, demo, error_reports,
    ]:
        app.include_router(router_module.router)

    async def override_get_session():
        async with fresh_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest_asyncio.fixture
async def fresh_client(fresh_app):
    """Per-test HTTP client for mutation tests."""
    async with AsyncClient(
        transport=ASGITransport(app=fresh_app),
        base_url="http://test",
    ) as c:
        yield c
