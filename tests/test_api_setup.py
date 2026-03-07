"""API integration tests for setup/onboarding and auth mode endpoints."""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base, HouseholdProfile, Account, AppSettings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def test_app(test_session_factory):
    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)

    from api.routes import setup_status
    app.include_router(setup_status.router)

    from api.database import get_session

    async def override_get_session():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest_asyncio.fixture
async def client(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /setup/status
# ---------------------------------------------------------------------------

class TestSetupStatus:
    async def test_empty_db(self, client):
        """Fresh database should report nothing complete."""
        resp = await client.get("/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["household"] is False
        assert data["income"] is False
        assert data["accounts"] is False
        assert data["complete"] is False
        assert data["setup_completed_at"] is None

    async def test_with_household_no_income(self, client, test_session_factory):
        """Household exists but no income → income=False."""
        async with test_session_factory() as session:
            session.add(HouseholdProfile(
                filing_status="single",
                state="CA",
                spouse_a_income=0,
                spouse_b_income=0,
                combined_income=0,
            ))
            await session.commit()

        resp = await client.get("/setup/status")
        data = resp.json()
        assert data["household"] is True
        assert data["income"] is False

    async def test_with_household_and_income(self, client, test_session_factory):
        """Household with income → household=True, income=True."""
        async with test_session_factory() as session:
            session.add(HouseholdProfile(
                filing_status="mfj",
                state="NY",
                spouse_a_income=200000,
                spouse_b_income=100000,
                combined_income=300000,
            ))
            await session.commit()

        resp = await client.get("/setup/status")
        data = resp.json()
        assert data["household"] is True
        assert data["income"] is True

    async def test_with_accounts(self, client, test_session_factory):
        """Account present → accounts=True."""
        async with test_session_factory() as session:
            session.add(HouseholdProfile(
                filing_status="single",
                state="CA",
                spouse_a_income=150000,
                spouse_b_income=0,
                combined_income=150000,
            ))
            session.add(Account(
                name="Chase Checking",
                institution="Chase",
                account_type="depository",
            ))
            await session.commit()

        resp = await client.get("/setup/status")
        data = resp.json()
        assert data["accounts"] is True
        assert data["complete"] is True  # household + income + accounts


# ---------------------------------------------------------------------------
# POST /setup/complete
# ---------------------------------------------------------------------------

class TestMarkComplete:
    async def test_marks_complete(self, client):
        resp = await client.post("/setup/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert "setup_completed_at" in data
        assert data["setup_completed_at"] is not None

    async def test_idempotent(self, client):
        """Calling twice should return the same timestamp."""
        r1 = await client.post("/setup/complete")
        r2 = await client.post("/setup/complete")
        assert r1.json()["setup_completed_at"] == r2.json()["setup_completed_at"]

    async def test_setup_completed_at_in_status(self, client):
        """After marking complete, status endpoint should reflect it."""
        await client.post("/setup/complete")
        resp = await client.get("/setup/status")
        data = resp.json()
        assert data["setup_completed_at"] is not None
