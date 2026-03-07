"""API integration tests for household and family member endpoints."""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base, HouseholdProfile, InsurancePolicy, LifeEvent


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

    from api.routes import household, family_members
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
# Household Profile CRUD
# ---------------------------------------------------------------------------

class TestHouseholdCRUD:
    async def test_list_empty(self, client):
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_profile(self, client):
        resp = await client.post("/household/profiles", json={
            "filing_status": "mfj",
            "state": "CA",
            "spouse_a_income": 200000,
            "spouse_b_income": 100000,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["filing_status"] == "mfj"
        assert data["combined_income"] == 300000
        assert data["is_primary"] is True  # First profile = auto-primary

    async def test_update_profile(self, client):
        # Create
        create_resp = await client.post("/household/profiles", json={
            "filing_status": "single",
            "state": "NY",
            "spouse_a_income": 150000,
            "spouse_b_income": 0,
        })
        profile_id = create_resp.json()["id"]

        # Update
        resp = await client.patch(f"/household/profiles/{profile_id}", json={
            "filing_status": "mfj",
            "state": "NY",
            "spouse_a_income": 200000,
            "spouse_b_income": 120000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["filing_status"] == "mfj"
        assert data["combined_income"] == 320000

    async def test_update_404(self, client):
        resp = await client.patch("/household/profiles/999", json={
            "filing_status": "single",
            "state": "CA",
            "spouse_a_income": 100000,
            "spouse_b_income": 0,
        })
        assert resp.status_code == 404

    async def test_delete_profile(self, client):
        create_resp = await client.post("/household/profiles", json={
            "filing_status": "single",
            "state": "TX",
            "spouse_a_income": 100000,
            "spouse_b_income": 0,
        })
        profile_id = create_resp.json()["id"]

        resp = await client.delete(f"/household/profiles/{profile_id}")
        assert resp.status_code == 204

        # Verify deleted
        list_resp = await client.get("/household/profiles")
        assert len(list_resp.json()) == 0

    async def test_delete_404(self, client):
        resp = await client.delete("/household/profiles/999")
        assert resp.status_code == 404

    async def test_delete_cascades_insurance(self, client, test_session_factory):
        """Deleting a household should also delete associated insurance policies."""
        # Create household
        create_resp = await client.post("/household/profiles", json={
            "filing_status": "single",
            "state": "CA",
            "spouse_a_income": 150000,
            "spouse_b_income": 0,
        })
        profile_id = create_resp.json()["id"]

        # Add insurance policy directly
        async with test_session_factory() as session:
            session.add(InsurancePolicy(
                household_id=profile_id,
                policy_type="life",
                provider="MetLife",
                coverage_amount=500000,
            ))
            await session.commit()

        # Delete household → should cascade
        resp = await client.delete(f"/household/profiles/{profile_id}")
        assert resp.status_code == 204

        # Verify insurance also deleted
        async with test_session_factory() as session:
            from sqlalchemy import select, func
            count = await session.scalar(
                select(func.count()).select_from(InsurancePolicy)
            )
            assert count == 0


# ---------------------------------------------------------------------------
# Family Members
# ---------------------------------------------------------------------------

class TestFamilyMembers:
    @pytest_asyncio.fixture(autouse=True)
    async def create_household(self, client):
        """Create a household for family member tests."""
        resp = await client.post("/household/profiles", json={
            "filing_status": "mfj",
            "state": "CA",
            "spouse_a_income": 200000,
            "spouse_b_income": 100000,
        })
        self.household_id = resp.json()["id"]

    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_create_member(self, mock_sync, client):
        resp = await client.post("/family-members/", json={
            "household_id": self.household_id,
            "name": "Alice",
            "relationship": "self",
            "is_earner": True,
            "income": 200000,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Alice"
        assert data["relationship"] == "self"

    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_list_members(self, mock_sync, client):
        await client.post("/family-members/", json={
            "household_id": self.household_id,
            "name": "Alice",
            "relationship": "self",
        })

        resp = await client.get(f"/family-members/?household_id={self.household_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_duplicate_self_rejected(self, mock_sync, client):
        """Cannot have two 'self' members in same household."""
        await client.post("/family-members/", json={
            "household_id": self.household_id,
            "name": "Alice",
            "relationship": "self",
        })
        resp = await client.post("/family-members/", json={
            "household_id": self.household_id,
            "name": "Alice Clone",
            "relationship": "self",
        })
        assert resp.status_code == 409

    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_invalid_household(self, mock_sync, client):
        resp = await client.post("/family-members/", json={
            "household_id": 99999,
            "name": "Nobody",
            "relationship": "self",
        })
        assert resp.status_code == 404
