"""End-to-end onboarding integration test.

Simulates a user going through the full onboarding flow:
1. Check initial setup status (empty)
2. Create household profile with income
3. Link an account
4. Mark setup complete
5. Verify setup status reflects completion
"""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base


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

    from api.routes import setup_status, household, family_members
    app.include_router(setup_status.router)
    app.include_router(household.router)
    app.include_router(family_members.router)

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
# Full onboarding flow
# ---------------------------------------------------------------------------

class TestOnboardingFlow:
    """Simulate a complete onboarding journey."""

    async def test_full_flow(self, client, test_session_factory):
        # Step 1: Fresh database — nothing complete
        resp = await client.get("/setup/status")
        assert resp.status_code == 200
        status = resp.json()
        assert status["household"] is False
        assert status["income"] is False
        assert status["accounts"] is False
        assert status["complete"] is False
        assert status["setup_completed_at"] is None

        # Step 2: Create household profile with income
        resp = await client.post("/household/profiles", json={
            "filing_status": "mfj",
            "state": "CA",
            "spouse_a_income": 250000,
            "spouse_b_income": 150000,
        })
        assert resp.status_code == 201
        profile = resp.json()
        profile_id = profile["id"]
        assert profile["combined_income"] == 400000
        assert profile["is_primary"] is True

        # Step 3: Verify setup status reflects household + income
        resp = await client.get("/setup/status")
        status = resp.json()
        assert status["household"] is True
        assert status["income"] is True
        assert status["accounts"] is False  # No accounts yet
        assert status["complete"] is False

        # Step 4: Add an account directly via DB (simulating Plaid link)
        from pipeline.db.schema import Account
        async with test_session_factory() as session:
            session.add(Account(
                name="Chase Checking",
                institution="Chase",
                account_type="depository",
            ))
            await session.commit()

        # Step 5: Verify all steps complete
        resp = await client.get("/setup/status")
        status = resp.json()
        assert status["household"] is True
        assert status["income"] is True
        assert status["accounts"] is True
        assert status["complete"] is True

        # Step 6: Mark setup complete
        resp = await client.post("/setup/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_completed_at"] is not None
        # No warnings since household + income exist
        assert "warnings" not in data or len(data.get("warnings", [])) == 0

        # Step 7: Verify idempotent
        resp2 = await client.post("/setup/complete")
        assert resp2.json()["setup_completed_at"] == data["setup_completed_at"]

        # Step 8: Final status reflects completion timestamp
        resp = await client.get("/setup/status")
        final = resp.json()
        assert final["setup_completed_at"] is not None
        assert final["complete"] is True


class TestOnboardingIncompleteCompletion:
    """Mark setup complete without all steps — should warn but not block."""

    async def test_complete_without_household(self, client):
        resp = await client.post("/setup/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert "no_household" in data["warnings"]

    async def test_complete_without_income(self, client, test_session_factory):
        # Create household without income
        await client.post("/household/profiles", json={
            "filing_status": "single",
            "state": "NY",
            "spouse_a_income": 0,
            "spouse_b_income": 0,
        })
        resp = await client.post("/setup/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert "no_income" in data["warnings"]


class TestHouseholdCascade:
    """Verify household operations cascade correctly."""

    async def test_create_and_list(self, client):
        # Create
        resp = await client.post("/household/profiles", json={
            "filing_status": "mfj",
            "state": "TX",
            "spouse_a_income": 180000,
            "spouse_b_income": 120000,
        })
        assert resp.status_code == 201

        # List
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 1
        assert profiles[0]["state"] == "TX"

    async def test_update_income(self, client):
        resp = await client.post("/household/profiles", json={
            "filing_status": "single",
            "state": "WA",
            "spouse_a_income": 100000,
        })
        profile_id = resp.json()["id"]

        resp = await client.patch(f"/household/profiles/{profile_id}", json={
            "spouse_a_income": 150000,
        })
        assert resp.status_code == 200
        assert resp.json()["spouse_a_income"] == 150000
        assert resp.json()["combined_income"] == 150000

    async def test_delete_profile(self, client):
        resp = await client.post("/household/profiles", json={
            "filing_status": "single",
            "state": "FL",
            "spouse_a_income": 90000,
        })
        profile_id = resp.json()["id"]

        resp = await client.delete(f"/household/profiles/{profile_id}")
        assert resp.status_code == 204

        # Confirm deleted — list should be empty
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200
        assert len(resp.json()) == 0
