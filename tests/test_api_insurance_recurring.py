"""API integration tests for insurance and recurring transaction endpoints."""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base, InsurancePolicy, RecurringTransaction


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

    from api.routes import insurance, recurring
    app.include_router(insurance.router)
    app.include_router(recurring.router)

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
# Helper: seed helpers
# ---------------------------------------------------------------------------

LIFE_POLICY_BODY = {
    "policy_type": "life",
    "provider": "MetLife",
    "premium_monthly": 50.0,
    "coverage_amount": 500000.0,
    "is_active": True,
}


async def _seed_policy(session_factory, **kwargs) -> InsurancePolicy:
    """Insert an InsurancePolicy row directly and return it."""
    defaults = dict(
        policy_type="life",
        provider="MetLife",
        monthly_premium=50.0,
        annual_premium=600.0,
        coverage_amount=500_000.0,
        is_active=True,
    )
    defaults.update(kwargs)
    async with session_factory() as session:
        policy = InsurancePolicy(**defaults)
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        return policy


async def _seed_recurring(session_factory, **kwargs) -> RecurringTransaction:
    """Insert a RecurringTransaction row directly and return it."""
    defaults = dict(
        name="Netflix",
        amount=-15.99,
        frequency="monthly",
        category="Streaming",
        segment="personal",
        status="active",
        is_auto_detected=True,
    )
    defaults.update(kwargs)
    async with session_factory() as session:
        rec = RecurringTransaction(**defaults)
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec


# ---------------------------------------------------------------------------
# Insurance — POST /insurance/
# ---------------------------------------------------------------------------

class TestCreatePolicy:
    async def test_create_life_policy(self, client):
        """Create a life insurance policy and verify the response shape."""
        body = {
            "policy_type": "life",
            "provider": "MetLife",
            "monthly_premium": 50.0,
            "coverage_amount": 500000.0,
            "is_active": True,
        }
        resp = await client.post("/insurance/", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_type"] == "life"
        assert data["provider"] == "MetLife"
        assert data["coverage_amount"] == 500000.0
        assert data["is_active"] is True
        assert "id" in data
        assert data["id"] > 0

    async def test_create_syncs_annual_from_monthly(self, client):
        """Providing only monthly_premium should compute annual_premium."""
        body = {
            "policy_type": "health",
            "monthly_premium": 100.0,
        }
        resp = await client.post("/insurance/", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["annual_premium"] == pytest.approx(1200.0, rel=1e-6)

    async def test_create_syncs_monthly_from_annual(self, client):
        """Providing only annual_premium should compute monthly_premium."""
        body = {
            "policy_type": "auto",
            "annual_premium": 1200.0,
        }
        resp = await client.post("/insurance/", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["monthly_premium"] == pytest.approx(100.0, rel=1e-6)

    async def test_create_invalid_policy_type_returns_400(self, client):
        """An unrecognised policy_type must return 400."""
        body = {"policy_type": "INVALID_TYPE"}
        resp = await client.post("/insurance/", json=body)
        assert resp.status_code == 400

    async def test_create_all_valid_policy_types(self, client):
        """Every value in POLICY_TYPES should be accepted."""
        valid_types = [
            "health", "life", "disability", "auto", "home",
            "umbrella", "pet", "vision", "dental", "ltc", "other",
        ]
        for pt in valid_types:
            resp = await client.post("/insurance/", json={"policy_type": pt})
            assert resp.status_code == 201, f"Expected 201 for policy_type={pt!r}"


# ---------------------------------------------------------------------------
# Insurance — GET /insurance/
# ---------------------------------------------------------------------------

class TestListPolicies:
    async def test_list_empty(self, client):
        """Fresh database should return an empty list."""
        resp = await client.get("/insurance/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_data(self, client, test_session_factory):
        """After seeding two policies the list should contain both."""
        await _seed_policy(test_session_factory, policy_type="life", provider="MetLife")
        await _seed_policy(test_session_factory, policy_type="auto", provider="GEICO")

        resp = await client.get("/insurance/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        providers = {p["provider"] for p in data}
        assert providers == {"MetLife", "GEICO"}

    async def test_filter_by_policy_type(self, client, test_session_factory):
        """Filtering by policy_type should return only matching policies."""
        await _seed_policy(test_session_factory, policy_type="life")
        await _seed_policy(test_session_factory, policy_type="auto")
        await _seed_policy(test_session_factory, policy_type="auto")

        resp = await client.get("/insurance/", params={"policy_type": "auto"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(p["policy_type"] == "auto" for p in data)

    async def test_filter_by_is_active_true(self, client, test_session_factory):
        """Filtering is_active=true should exclude inactive policies."""
        await _seed_policy(test_session_factory, is_active=True)
        await _seed_policy(test_session_factory, is_active=False)

        resp = await client.get("/insurance/", params={"is_active": "true"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_active"] is True

    async def test_filter_by_is_active_false(self, client, test_session_factory):
        """Filtering is_active=false should return only inactive policies."""
        await _seed_policy(test_session_factory, is_active=True)
        await _seed_policy(test_session_factory, is_active=False, policy_type="auto")

        resp = await client.get("/insurance/", params={"is_active": "false"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["is_active"] is False

    async def test_filter_by_household_id(self, client, test_session_factory):
        """Filtering by household_id should return only matching policies."""
        await _seed_policy(test_session_factory, household_id=1)
        await _seed_policy(test_session_factory, household_id=2)

        resp = await client.get("/insurance/", params={"household_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["household_id"] == 1


# ---------------------------------------------------------------------------
# Insurance — GET /insurance/{policy_id}
# ---------------------------------------------------------------------------

class TestGetPolicy:
    async def test_get_existing_policy(self, client, test_session_factory):
        """Fetching an existing policy by ID should return it."""
        seeded = await _seed_policy(test_session_factory, provider="Prudential")

        resp = await client.get(f"/insurance/{seeded.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == seeded.id
        assert data["provider"] == "Prudential"
        assert data["policy_type"] == "life"

    async def test_get_nonexistent_policy_returns_404(self, client):
        """Requesting a policy that does not exist must return 404."""
        resp = await client.get("/insurance/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Insurance — PATCH /insurance/{policy_id}
# ---------------------------------------------------------------------------

class TestUpdatePolicy:
    async def test_update_premium(self, client, test_session_factory):
        """PATCH should update the monthly_premium and return the updated record."""
        seeded = await _seed_policy(test_session_factory, monthly_premium=50.0, annual_premium=600.0)

        resp = await client.patch(
            f"/insurance/{seeded.id}",
            json={"policy_type": "life", "monthly_premium": 75.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["monthly_premium"] == 75.0
        # annual_premium should be re-computed: 75 * 12 = 900
        assert data["annual_premium"] == pytest.approx(900.0, rel=1e-6)

    async def test_update_provider(self, client, test_session_factory):
        """PATCH should update arbitrary fields such as provider."""
        seeded = await _seed_policy(test_session_factory, provider="OldProvider")

        resp = await client.patch(
            f"/insurance/{seeded.id}",
            json={"policy_type": "life", "provider": "NewProvider"},
        )
        assert resp.status_code == 200
        assert resp.json()["provider"] == "NewProvider"

    async def test_update_nonexistent_policy_returns_404(self, client):
        """PATCH on a missing policy must return 404."""
        resp = await client.patch(
            "/insurance/99999",
            json={"policy_type": "life"},
        )
        assert resp.status_code == 404

    async def test_update_is_active(self, client, test_session_factory):
        """Deactivating a policy via PATCH should persist the change."""
        seeded = await _seed_policy(test_session_factory, is_active=True)

        resp = await client.patch(
            f"/insurance/{seeded.id}",
            json={"policy_type": "life", "is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Insurance — DELETE /insurance/{policy_id}
# ---------------------------------------------------------------------------

class TestDeletePolicy:
    async def test_delete_existing_policy_returns_204(self, client, test_session_factory):
        """Deleting an existing policy should return 204 No Content."""
        seeded = await _seed_policy(test_session_factory)

        resp = await client.delete(f"/insurance/{seeded.id}")
        assert resp.status_code == 204

    async def test_deleted_policy_no_longer_listed(self, client, test_session_factory):
        """After deletion the policy should not appear in the list."""
        seeded = await _seed_policy(test_session_factory)

        await client.delete(f"/insurance/{seeded.id}")
        resp = await client.get("/insurance/")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert seeded.id not in ids

    async def test_delete_nonexistent_policy_returns_404(self, client):
        """Deleting a policy that does not exist must return 404."""
        resp = await client.delete("/insurance/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Recurring — GET /recurring
# ---------------------------------------------------------------------------

class TestListRecurring:
    async def test_list_empty(self, client):
        """Fresh database should return an empty list for recurring."""
        resp = await client.get("/recurring")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_seeded_data(self, client, test_session_factory):
        """Seeded recurring transactions should appear in the list."""
        await _seed_recurring(test_session_factory, name="Netflix", amount=-15.99)
        await _seed_recurring(test_session_factory, name="Spotify", amount=-9.99)

        resp = await client.get("/recurring")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {r["name"] for r in data}
        assert names == {"Netflix", "Spotify"}

    async def test_list_response_shape(self, client, test_session_factory):
        """Each item in the list must have the expected fields."""
        await _seed_recurring(test_session_factory, name="Hulu", amount=-7.99, category="Streaming")

        resp = await client.get("/recurring")
        assert resp.status_code == 200
        item = resp.json()[0]
        for field in ("id", "name", "amount", "frequency", "category", "segment", "status",
                      "last_seen_date", "next_expected_date", "is_auto_detected", "notes", "annual_cost"):
            assert field in item, f"Missing field: {field}"

    async def test_list_computes_annual_cost(self, client, test_session_factory):
        """annual_cost should be |amount| * frequency multiplier."""
        await _seed_recurring(test_session_factory, name="Adobe", amount=-54.99, frequency="monthly")

        resp = await client.get("/recurring")
        item = resp.json()[0]
        # monthly × 12
        assert item["annual_cost"] == pytest.approx(54.99 * 12, rel=1e-4)

    async def test_filter_by_status(self, client, test_session_factory):
        """Passing ?status=active should exclude non-active records."""
        await _seed_recurring(test_session_factory, name="Active Sub", status="active")
        await _seed_recurring(test_session_factory, name="Cancelled Sub", status="cancelled")

        resp = await client.get("/recurring", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Active Sub"


# ---------------------------------------------------------------------------
# Recurring — GET /recurring/summary
# ---------------------------------------------------------------------------

class TestRecurringSummary:
    async def test_summary_empty(self, client):
        """Summary of an empty database should return zeros."""
        resp = await client.get("/recurring/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_monthly_cost"] == 0.0
        assert data["total_annual_cost"] == 0.0
        assert data["subscription_count"] == 0
        assert data["by_category"] == {}

    async def test_summary_with_active_records(self, client, test_session_factory):
        """Summary should aggregate only active recurring transactions."""
        await _seed_recurring(
            test_session_factory, name="Netflix", amount=-15.99,
            frequency="monthly", category="Streaming", status="active",
        )
        await _seed_recurring(
            test_session_factory, name="Gym", amount=-50.0,
            frequency="monthly", category="Health", status="active",
        )
        await _seed_recurring(
            test_session_factory, name="OldSub", amount=-100.0,
            frequency="monthly", category="Other", status="cancelled",
        )

        resp = await client.get("/recurring/summary")
        assert resp.status_code == 200
        data = resp.json()

        # Only 2 active items
        assert data["subscription_count"] == 2
        expected_monthly = 15.99 + 50.0
        assert data["total_monthly_cost"] == pytest.approx(expected_monthly, rel=1e-4)
        assert data["total_annual_cost"] == pytest.approx(expected_monthly * 12, rel=1e-4)

    async def test_summary_by_category_breakdown(self, client, test_session_factory):
        """by_category should list each category's monthly contribution."""
        await _seed_recurring(
            test_session_factory, name="Netflix", amount=-15.99,
            category="Streaming", status="active",
        )
        await _seed_recurring(
            test_session_factory, name="Hulu", amount=-7.99,
            category="Streaming", status="active",
        )
        await _seed_recurring(
            test_session_factory, name="Gym", amount=-50.0,
            category="Health", status="active",
        )

        resp = await client.get("/recurring/summary")
        data = resp.json()
        by_cat = data["by_category"]
        assert "Streaming" in by_cat
        assert "Health" in by_cat
        assert by_cat["Streaming"] == pytest.approx(15.99 + 7.99, rel=1e-4)
        assert by_cat["Health"] == pytest.approx(50.0, rel=1e-4)

    async def test_summary_excludes_inactive(self, client, test_session_factory):
        """Cancelled records must not appear in the summary totals."""
        await _seed_recurring(
            test_session_factory, name="CancelledSub", amount=-200.0,
            status="cancelled",
        )

        resp = await client.get("/recurring/summary")
        data = resp.json()
        assert data["total_monthly_cost"] == 0.0
        assert data["subscription_count"] == 0


# ---------------------------------------------------------------------------
# Recurring — PATCH /recurring/{recurring_id}
# ---------------------------------------------------------------------------

class TestUpdateRecurring:
    async def test_update_status(self, client, test_session_factory):
        """PATCH should allow changing the status of a recurring record."""
        seeded = await _seed_recurring(test_session_factory, status="active")

        resp = await client.patch(
            f"/recurring/{seeded.id}",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_update_category(self, client, test_session_factory):
        """PATCH should allow re-categorising a recurring record."""
        seeded = await _seed_recurring(test_session_factory, category="Streaming")

        resp = await client.patch(
            f"/recurring/{seeded.id}",
            json={"category": "Entertainment"},
        )
        assert resp.status_code == 200
        assert resp.json()["category"] == "Entertainment"

    async def test_update_notes(self, client, test_session_factory):
        """PATCH should allow setting notes on a recurring record."""
        seeded = await _seed_recurring(test_session_factory)

        resp = await client.patch(
            f"/recurring/{seeded.id}",
            json={"notes": "Shared with family plan"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Shared with family plan"

    async def test_update_nonexistent_returns_404(self, client):
        """PATCH on a missing recurring item must return 404."""
        resp = await client.patch(
            "/recurring/99999",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 404

    async def test_update_persists_across_list(self, client, test_session_factory):
        """Changes made via PATCH should be reflected in a subsequent GET /recurring."""
        seeded = await _seed_recurring(test_session_factory, name="OldName", status="active")

        await client.patch(f"/recurring/{seeded.id}", json={"status": "cancelled"})

        resp = await client.get("/recurring")
        items = {r["id"]: r for r in resp.json()}
        assert items[seeded.id]["status"] == "cancelled"
