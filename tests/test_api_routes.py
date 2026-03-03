"""API integration tests using httpx.AsyncClient with FastAPI test client."""
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base, Account, Transaction, Budget


# ---------------------------------------------------------------------------
# Build a minimal test app that skips the heavyweight lifespan (Plaid sync,
# AI report generation, etc.) but still registers all routers.
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
    """Create a minimal FastAPI app with routes but no heavy lifespan."""

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)

    # Import and register routers
    from api.routes import accounts, transactions, budget

    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(budget.router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sirhenry-api"}

    # Override the session dependency
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
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "sirhenry-api"


# ---------------------------------------------------------------------------
# Account CRUD
# ---------------------------------------------------------------------------


class TestAccountEndpoints:
    @pytest.mark.asyncio
    async def test_create_account(self, client):
        resp = await client.post("/accounts", json={
            "name": "Chase Sapphire",
            "account_type": "personal",
            "subtype": "credit_card",
            "institution": "Chase",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Chase Sapphire"
        assert data["account_type"] == "personal"
        assert data["is_active"] is True
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_and_get_account(self, client):
        # Create
        create_resp = await client.post("/accounts", json={
            "name": "Fidelity Brokerage",
            "account_type": "investment",
            "subtype": "brokerage",
            "institution": "Fidelity",
        })
        account_id = create_resp.json()["id"]

        # Get by ID
        get_resp = await client.get(f"/accounts/{account_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == account_id
        assert data["name"] == "Fidelity Brokerage"

    @pytest.mark.asyncio
    async def test_list_accounts(self, client):
        # Create two accounts
        await client.post("/accounts", json={
            "name": "Account A",
            "account_type": "personal",
        })
        await client.post("/accounts", json={
            "name": "Account B",
            "account_type": "personal",
        })

        resp = await client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_update_account(self, client):
        create_resp = await client.post("/accounts", json={
            "name": "Old Name",
            "account_type": "personal",
        })
        account_id = create_resp.json()["id"]

        patch_resp = await client.patch(f"/accounts/{account_id}", json={
            "name": "New Name",
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_deactivate_account(self, client):
        create_resp = await client.post("/accounts", json={
            "name": "To Deactivate",
            "account_type": "personal",
        })
        account_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/accounts/{account_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_get_nonexistent_account_404(self, client):
        resp = await client.get("/accounts/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_account_missing_required_field_422(self, client):
        resp = await client.post("/accounts", json={
            # Missing "name" and "account_type"
            "institution": "Chase",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Transaction endpoints
# ---------------------------------------------------------------------------


class TestTransactionEndpoints:
    @pytest.mark.asyncio
    async def test_list_transactions_empty(self, client):
        resp = await client.get("/transactions", params={"limit": 10, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_nonexistent_transaction_404(self, client):
        resp = await client.get("/transactions/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_transactions_with_pagination(self, client, test_session_factory):
        """Insert transactions directly and verify pagination."""
        # Create account and transactions directly via DB
        async with test_session_factory() as session:
            acct = Account(
                name="Test Account",
                account_type="personal",
                subtype="credit_card",
            )
            session.add(acct)
            await session.flush()

            from datetime import datetime
            for i in range(5):
                txn = Transaction(
                    account_id=acct.id,
                    date=datetime(2025, 1, i + 1),
                    description=f"Transaction {i}",
                    amount=-10.0 * (i + 1),
                    currency="USD",
                    segment="personal",
                    period_month=1,
                    period_year=2025,
                    is_excluded=False,
                    is_manually_reviewed=False,
                )
                session.add(txn)
            await session.commit()

        # Now query via API
        resp = await client.get("/transactions", params={"limit": 3, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3

        # Page 2
        resp2 = await client.get("/transactions", params={"limit": 3, "offset": 3})
        data2 = resp2.json()
        assert len(data2["items"]) == 2


# ---------------------------------------------------------------------------
# Budget endpoints
# ---------------------------------------------------------------------------


class TestBudgetEndpoints:
    @pytest.mark.asyncio
    async def test_create_budget(self, client):
        resp = await client.post("/budget", json={
            "year": 2025,
            "month": 3,
            "category": "Groceries",
            "segment": "personal",
            "budget_amount": 600.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "Groceries"
        assert data["budget_amount"] == 600.0

    @pytest.mark.asyncio
    async def test_list_budgets(self, client):
        # Create a budget
        await client.post("/budget", json={
            "year": 2025,
            "month": 6,
            "category": "Dining",
            "budget_amount": 400.0,
        })
        resp = await client.get("/budget", params={"year": 2025, "month": 6})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["category"] == "Dining"

    @pytest.mark.asyncio
    async def test_update_budget(self, client):
        create_resp = await client.post("/budget", json={
            "year": 2025,
            "month": 7,
            "category": "Travel",
            "budget_amount": 1000.0,
        })
        budget_id = create_resp.json()["id"]

        patch_resp = await client.patch(f"/budget/{budget_id}", json={
            "budget_amount": 1500.0,
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["budget_amount"] == 1500.0

    @pytest.mark.asyncio
    async def test_delete_budget(self, client):
        create_resp = await client.post("/budget", json={
            "year": 2025,
            "month": 8,
            "category": "Entertainment",
            "budget_amount": 200.0,
        })
        budget_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/budget/{budget_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] == budget_id

    @pytest.mark.asyncio
    async def test_update_nonexistent_budget_404(self, client):
        resp = await client.patch("/budget/99999", json={"budget_amount": 100.0})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_upsert_existing_budget(self, client):
        """Creating a budget with the same year/month/category/segment should update it."""
        await client.post("/budget", json={
            "year": 2025,
            "month": 9,
            "category": "Groceries",
            "segment": "personal",
            "budget_amount": 500.0,
        })
        resp2 = await client.post("/budget", json={
            "year": 2025,
            "month": 9,
            "category": "Groceries",
            "segment": "personal",
            "budget_amount": 700.0,
        })
        assert resp2.status_code == 200
        assert resp2.json()["budget_amount"] == 700.0

    @pytest.mark.asyncio
    async def test_budget_missing_required_params_422(self, client):
        # year and month are required query params for list
        resp = await client.get("/budget")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Error response format
# ---------------------------------------------------------------------------


class TestErrorResponses:
    @pytest.mark.asyncio
    async def test_422_has_detail(self, client):
        resp = await client.post("/accounts", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_404_has_detail(self, client):
        resp = await client.get("/accounts/99999")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
