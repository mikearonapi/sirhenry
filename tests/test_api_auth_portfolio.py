"""API integration tests for auth and portfolio analytics endpoints."""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch, AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base, TargetAllocation


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

    from api.routes import auth_routes, portfolio_analytics
    app.include_router(auth_routes.router)
    app.include_router(portfolio_analytics.router)

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
# Auth Tests
# ---------------------------------------------------------------------------

class TestGetMode:
    async def test_returns_current_mode(self, client):
        """GET /auth/mode returns the current mode from get_active_mode."""
        with patch("api.routes.auth_routes.get_active_mode", return_value="local"):
            resp = await client.get("/auth/mode")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "local"

    async def test_returns_demo_mode(self, client):
        """GET /auth/mode returns 'demo' when active mode is demo."""
        with patch("api.routes.auth_routes.get_active_mode", return_value="demo"):
            resp = await client.get("/auth/mode")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "demo"


class TestSelectMode:
    async def test_select_local_mode(self, client):
        """POST /auth/select-mode with mode 'local' succeeds."""
        with patch(
            "api.routes.auth_routes.switch_to_mode",
            new_callable=AsyncMock,
            return_value="local",
        ):
            resp = await client.post("/auth/select-mode", json={"mode": "local"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["mode"] == "local"

    async def test_select_demo_mode(self, client):
        """POST /auth/select-mode with mode 'demo' succeeds."""
        with patch(
            "api.routes.auth_routes.switch_to_mode",
            new_callable=AsyncMock,
            return_value="demo",
        ):
            resp = await client.post("/auth/select-mode", json={"mode": "demo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["mode"] == "demo"

    async def test_invalid_mode_returns_400(self, client):
        """POST /auth/select-mode with an unrecognised mode returns 400."""
        resp = await client.post("/auth/select-mode", json={"mode": "unknown"})
        assert resp.status_code == 400

    async def test_missing_mode_field_returns_422(self, client):
        """POST /auth/select-mode with no body returns 422 (validation error)."""
        resp = await client.post("/auth/select-mode", json={})
        assert resp.status_code == 422


class TestInjectApiKey:
    async def test_valid_key_succeeds(self, client):
        """POST /auth/inject-api-key with a valid 'sk-ant-' key returns ok."""
        resp = await client.post(
            "/auth/inject-api-key",
            json={"key": "sk-ant-api01-testkey12345"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    async def test_invalid_key_returns_400(self, client):
        """POST /auth/inject-api-key with a key not starting with 'sk-ant-' returns 400."""
        resp = await client.post(
            "/auth/inject-api-key",
            json={"key": "not-a-valid-key-format"},
        )
        assert resp.status_code == 400

    async def test_empty_key_returns_422(self, client):
        """POST /auth/inject-api-key with a key that is too short returns 422."""
        resp = await client.post(
            "/auth/inject-api-key",
            json={"key": "short"},
        )
        assert resp.status_code == 422

    async def test_missing_key_field_returns_422(self, client):
        """POST /auth/inject-api-key with no key field returns 422."""
        resp = await client.post("/auth/inject-api-key", json={})
        assert resp.status_code == 422


class TestGetMe:
    async def test_no_auth_returns_unauthenticated(self, client):
        """GET /auth/me without any Authorization header returns unauthenticated."""
        with patch("api.routes.auth_routes.get_active_mode", return_value="local"):
            resp = await client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is False

    async def test_demo_mode_returns_unauthenticated(self, client):
        """GET /auth/me in demo mode returns unauthenticated (no JWT required)."""
        with patch("api.routes.auth_routes.get_active_mode", return_value="demo"):
            resp = await client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is False
        assert data["demo_mode"] is True


# ---------------------------------------------------------------------------
# Portfolio Tests
# ---------------------------------------------------------------------------

class TestTargetAllocationPresets:
    async def test_returns_three_presets(self, client):
        """GET /target-allocation/presets returns exactly 3 HENRY presets."""
        resp = await client.get("/target-allocation/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        presets = data["presets"]
        assert len(presets) == 3
        assert "aggressive" in presets
        assert "balanced" in presets
        assert "conservative" in presets

    async def test_presets_have_name_and_allocation(self, client):
        """Each preset has 'name' and 'allocation' keys."""
        resp = await client.get("/target-allocation/presets")
        data = resp.json()
        for key, preset in data["presets"].items():
            assert "name" in preset, f"Preset '{key}' missing 'name'"
            assert "allocation" in preset, f"Preset '{key}' missing 'allocation'"

    async def test_presets_allocations_sum_to_100(self, client):
        """Each preset allocation sums to 100%."""
        resp = await client.get("/target-allocation/presets")
        data = resp.json()
        for key, preset in data["presets"].items():
            total = sum(preset["allocation"].values())
            assert abs(total - 100) <= 1, (
                f"Preset '{key}' allocation sums to {total}, expected ~100"
            )


class TestGetTargetAllocation:
    async def test_returns_default_when_none_set(self, client):
        """GET /target-allocation returns the default balanced preset when DB is empty."""
        resp = await client.get("/target-allocation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is None
        assert "allocation" in data
        assert "name" in data

    async def test_default_is_balanced(self, client):
        """The default allocation returned when nothing is set is the balanced preset."""
        resp = await client.get("/target-allocation")
        data = resp.json()
        # The route hardcodes the balanced preset as default
        assert data["name"] == "Balanced Growth"
        allocation = data["allocation"]
        assert "stock" in allocation
        assert "bond" in allocation


class TestPutTargetAllocation:
    async def test_creates_new_allocation(self, client):
        """PUT /target-allocation persists a new allocation and returns it."""
        payload = {
            "name": "My Custom Allocation",
            "allocation": {"stock": 50, "bond": 30, "etf": 20},
        }
        resp = await client.put("/target-allocation", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Custom Allocation"
        assert data["allocation"] == {"stock": 50.0, "bond": 30.0, "etf": 20.0}
        assert data["id"] is not None

    async def test_saved_allocation_returned_on_get(self, client):
        """After PUT, GET /target-allocation returns the saved allocation."""
        payload = {
            "name": "Saved Allocation",
            "allocation": {"stock": 60, "bond": 25, "etf": 15},
        }
        await client.put("/target-allocation", json=payload)

        resp = await client.get("/target-allocation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Saved Allocation"
        assert data["allocation"] == {"stock": 60.0, "bond": 25.0, "etf": 15.0}
        assert data["id"] is not None

    async def test_allocation_not_summing_to_100_returns_400(self, client):
        """PUT /target-allocation with percentages not summing to ~100 returns 400."""
        payload = {
            "name": "Bad Allocation",
            "allocation": {"stock": 50, "bond": 20},  # sums to 70
        }
        resp = await client.put("/target-allocation", json=payload)
        assert resp.status_code == 400

    async def test_allocation_exactly_100_is_accepted(self, client):
        """PUT /target-allocation with exactly 100% is accepted."""
        payload = {
            "name": "Exact Allocation",
            "allocation": {"stock": 40, "bond": 40, "etf": 20},
        }
        resp = await client.put("/target-allocation", json=payload)
        assert resp.status_code == 200

    async def test_allocation_within_tolerance_is_accepted(self, client):
        """PUT /target-allocation within ±1% of 100 is accepted."""
        payload = {
            "name": "Near-100 Allocation",
            "allocation": {"stock": 50, "bond": 30, "etf": 20.5},  # sums to 100.5
        }
        resp = await client.put("/target-allocation", json=payload)
        assert resp.status_code == 200

    async def test_second_put_deactivates_first(self, client):
        """A second PUT deactivates the previous allocation and activates the new one."""
        first = {
            "name": "First Allocation",
            "allocation": {"stock": 70, "bond": 20, "etf": 10},
        }
        second = {
            "name": "Second Allocation",
            "allocation": {"stock": 50, "bond": 30, "etf": 20},
        }
        await client.put("/target-allocation", json=first)
        await client.put("/target-allocation", json=second)

        resp = await client.get("/target-allocation")
        data = resp.json()
        assert data["name"] == "Second Allocation"

    async def test_missing_allocation_field_returns_422(self, client):
        """PUT /target-allocation with no allocation dict returns 422."""
        resp = await client.put("/target-allocation", json={"name": "no-alloc"})
        assert resp.status_code == 422


class TestPortfolioSummary:
    async def test_empty_portfolio_returns_valid_structure(self, client):
        """GET /summary with an empty DB returns a valid zero-value summary."""
        resp = await client.get("/summary")
        assert resp.status_code == 200
        data = resp.json()

        # Required top-level keys
        assert "total_value" in data
        assert "holdings_count" in data
        assert "top_holdings" in data
        assert "asset_class_allocation" in data
        assert "sector_allocation" in data

    async def test_empty_portfolio_total_is_zero(self, client):
        """GET /summary on an empty DB has zero total value and no holdings."""
        resp = await client.get("/summary")
        data = resp.json()
        assert data["total_value"] == 0.0
        assert data["holdings_count"] == 0
        assert data["top_holdings"] == []

    async def test_summary_has_cost_basis_fields(self, client):
        """GET /summary response includes cost basis and gain/loss fields."""
        resp = await client.get("/summary")
        data = resp.json()
        assert "total_cost_basis" in data
        assert "total_gain_loss" in data
        assert "total_gain_loss_pct" in data
        assert "has_cost_basis" in data
