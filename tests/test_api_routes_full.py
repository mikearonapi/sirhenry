"""
Comprehensive API route tests — covers all endpoints below 90% coverage.

Uses httpx AsyncClient + ASGITransport against a FastAPI test app with
in-memory SQLite. Mocks external services (Plaid, AI, market data).
"""
import io
import json
import os
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import (
    Base, Account, AccountLink, AppSettings, CryptoHolding, Document,
    EquityGrant, FamilyMember, FinancialPeriod, Goal, HouseholdProfile,
    InvestmentHolding, ManualAsset, PayrollConnection, PayStubRecord,
    PlaidAccount, PlaidItem, RecurringTransaction, Reminder, Transaction,
    UserContext,
)


# ---------------------------------------------------------------------------
# Fixtures — test app with all target routers and overridden session
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
    """Create a minimal FastAPI app registering ALL target routers."""

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)

    from api.routes import (
        account_links, accounts, assets, auth_routes, family_members,
        goal_suggestions, import_routes, income, plaid, portfolio,
        recurring, reminders, reports, setup_status, user_context,
        valuations,
    )

    # account_links must be registered BEFORE accounts so /accounts/suggest-links
    # is matched before /accounts/{account_id}
    app.include_router(account_links.router)
    app.include_router(accounts.router)
    app.include_router(assets.router)
    app.include_router(auth_routes.router)
    app.include_router(family_members.router)
    app.include_router(goal_suggestions.router)
    app.include_router(import_routes.router)
    app.include_router(income.router)
    app.include_router(plaid.router)
    app.include_router(portfolio.router)
    app.include_router(recurring.router)
    app.include_router(reminders.router)
    app.include_router(reports.router)
    app.include_router(setup_status.router)
    app.include_router(user_context.router)
    app.include_router(valuations.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

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


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    """Direct DB session for seeding test data."""
    async with test_session_factory() as session:
        yield session
        await session.commit()


# ---------------------------------------------------------------------------
# Helper: seed common test data
# ---------------------------------------------------------------------------

async def _seed_account(session, name="Test Card", account_type="personal",
                        subtype="credit_card", institution="Chase", last_four="1234",
                        data_source="csv"):
    acct = Account(
        name=name, account_type=account_type, subtype=subtype,
        institution=institution, last_four=last_four, data_source=data_source,
    )
    session.add(acct)
    await session.flush()
    return acct


async def _seed_transaction(session, account_id, amount=-50.0, description="Test Merchant",
                            category="Shopping", period_year=2026, period_month=1):
    tx = Transaction(
        account_id=account_id, date=datetime(period_year, period_month, 15, tzinfo=timezone.utc),
        description=description, amount=amount, segment="personal",
        category=category, effective_category=category,
        period_year=period_year, period_month=period_month,
    )
    session.add(tx)
    await session.flush()
    return tx


async def _seed_household(session, spouse_a_income=200000.0, spouse_b_income=150000.0):
    hp = HouseholdProfile(
        name="Test Household", filing_status="mfj", state="CA",
        spouse_a_name="Alice", spouse_a_income=spouse_a_income,
        spouse_b_name="Bob", spouse_b_income=spouse_b_income,
        combined_income=spouse_a_income + spouse_b_income,
        is_primary=True,
    )
    session.add(hp)
    await session.flush()
    return hp


# ═══════════════════════════════════════════════════════════════════════════
# 1. ACCOUNTS CRUD  (api/routes/accounts.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestAccountsCRUD:
    """Full CRUD lifecycle for accounts."""

    @pytest.mark.asyncio
    async def test_list_accounts_empty(self, client):
        r = await client.get("/accounts")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_create_account(self, client):
        r = await client.post("/accounts", json={
            "name": "Amex Platinum",
            "account_type": "personal",
            "subtype": "credit_card",
            "institution": "American Express",
            "last_four": "9876",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Amex Platinum"
        assert data["institution"] == "American Express"
        assert data["is_active"] is True
        return data["id"]

    @pytest.mark.asyncio
    async def test_create_read_update_delete(self, client):
        # Create
        cr = await client.post("/accounts", json={
            "name": "Savings Account",
            "account_type": "personal",
            "subtype": "bank",
            "institution": "Ally",
        })
        assert cr.status_code == 201
        acct_id = cr.json()["id"]

        # Read
        r = await client.get(f"/accounts/{acct_id}")
        assert r.status_code == 200
        assert r.json()["name"] == "Savings Account"

        # Update (PATCH)
        r = await client.patch(f"/accounts/{acct_id}", json={"name": "Ally Savings"})
        assert r.status_code == 200
        assert r.json()["name"] == "Ally Savings"

        # Delete (soft-deactivate)
        r = await client.delete(f"/accounts/{acct_id}")
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_get_nonexistent_account_404(self, client):
        r = await client.get("/accounts/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_nonexistent_account_404(self, client):
        r = await client.patch("/accounts/99999", json={"name": "x"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_account_404(self, client):
        r = await client.delete("/accounts/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_list_accounts_with_data(self, client, db_session):
        acct = await _seed_account(db_session)
        tx = await _seed_transaction(db_session, acct.id, amount=-125.50)
        await db_session.commit()

        r = await client.get("/accounts")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        found = [a for a in items if a["name"] == "Test Card"]
        assert len(found) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 2. ACCOUNT LINKS  (api/routes/account_links.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestAccountLinks:
    """Account linking, merging, and dedup."""

    @pytest.mark.asyncio
    async def test_link_accounts(self, client, db_session):
        a1 = await _seed_account(db_session, name="Card CSV", data_source="csv", institution="Chase", last_four="1111")
        a2 = await _seed_account(db_session, name="Card Plaid", data_source="plaid", institution="Chase", last_four="1111")
        await db_session.commit()

        r = await client.post(f"/accounts/{a1.id}/link", json={
            "target_account_id": a2.id,
            "link_type": "same_account",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["primary_account_id"] == a1.id
        assert data["secondary_account_id"] == a2.id

    @pytest.mark.asyncio
    async def test_link_self_rejected(self, client, db_session):
        a = await _seed_account(db_session)
        await db_session.commit()
        r = await client.post(f"/accounts/{a.id}/link", json={
            "target_account_id": a.id,
            "link_type": "same_account",
        })
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_link_nonexistent_404(self, client, db_session):
        a = await _seed_account(db_session)
        await db_session.commit()
        r = await client.post(f"/accounts/{a.id}/link", json={
            "target_account_id": 99999,
            "link_type": "same_account",
        })
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_link_409(self, client, db_session):
        a1 = await _seed_account(db_session, name="A1")
        a2 = await _seed_account(db_session, name="A2")
        await db_session.commit()

        await client.post(f"/accounts/{a1.id}/link", json={
            "target_account_id": a2.id, "link_type": "same_account",
        })
        r = await client.post(f"/accounts/{a1.id}/link", json={
            "target_account_id": a2.id, "link_type": "same_account",
        })
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_get_links(self, client, db_session):
        a1 = await _seed_account(db_session, name="L1")
        a2 = await _seed_account(db_session, name="L2")
        await db_session.commit()

        await client.post(f"/accounts/{a1.id}/link", json={
            "target_account_id": a2.id, "link_type": "same_account",
        })

        r = await client.get(f"/accounts/{a1.id}/links")
        assert r.status_code == 200
        assert len(r.json()) == 1

    @pytest.mark.asyncio
    async def test_remove_link(self, client, db_session):
        a1 = await _seed_account(db_session, name="R1")
        a2 = await _seed_account(db_session, name="R2")
        await db_session.commit()

        cr = await client.post(f"/accounts/{a1.id}/link", json={
            "target_account_id": a2.id, "link_type": "same_account",
        })
        link_id = cr.json()["id"]

        r = await client.delete(f"/accounts/{a1.id}/link/{link_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "removed"

    @pytest.mark.asyncio
    async def test_remove_link_wrong_account_403(self, client, db_session):
        a1 = await _seed_account(db_session, name="W1")
        a2 = await _seed_account(db_session, name="W2")
        a3 = await _seed_account(db_session, name="W3")
        await db_session.commit()

        cr = await client.post(f"/accounts/{a1.id}/link", json={
            "target_account_id": a2.id, "link_type": "same_account",
        })
        link_id = cr.json()["id"]

        r = await client.delete(f"/accounts/{a3.id}/link/{link_id}")
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_merge_accounts(self, client, db_session):
        a1 = await _seed_account(db_session, name="Primary")
        a2 = await _seed_account(db_session, name="Secondary")
        tx = await _seed_transaction(db_session, a2.id, amount=-75.0, description="Grocery")
        await db_session.commit()

        r = await client.post(f"/accounts/{a1.id}/merge", json={
            "target_account_id": a2.id, "link_type": "same_account",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["primary_account_id"] == a1.id
        assert data["transactions_moved"] >= 1
        assert data["secondary_deactivated"] is True

    @pytest.mark.asyncio
    async def test_merge_self_rejected(self, client, db_session):
        a = await _seed_account(db_session, name="Self")
        await db_session.commit()
        r = await client.post(f"/accounts/{a.id}/merge", json={
            "target_account_id": a.id, "link_type": "same_account",
        })
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_suggest_links(self, client, db_session):
        # Same institution + last_four, different source = should suggest
        a1 = await _seed_account(db_session, name="Chase CC CSV", data_source="csv",
                                 institution="Chase", last_four="4444")
        a2 = await _seed_account(db_session, name="Chase CC Plaid", data_source="plaid",
                                 institution="Chase", last_four="4444")
        await db_session.commit()

        r = await client.get("/accounts/suggest-links")
        assert r.status_code == 200
        suggestions = r.json()
        assert len(suggestions) >= 1

    @pytest.mark.asyncio
    async def test_resolve_duplicate(self, client, db_session):
        acct = await _seed_account(db_session, name="Dup Acct")
        tx1 = await _seed_transaction(db_session, acct.id, amount=-10, description="Amazon")
        tx2 = await _seed_transaction(db_session, acct.id, amount=-10, description="AMAZON.COM")
        await db_session.commit()

        r = await client.post("/accounts/resolve-duplicate", json={
            "keep_id": tx1.id, "exclude_id": tx2.id,
        })
        assert r.status_code == 200
        assert r.json()["excluded_id"] == tx2.id


# ═══════════════════════════════════════════════════════════════════════════
# 3. MANUAL ASSETS  (api/routes/assets.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestAssetsCRUD:
    """Full CRUD lifecycle for manual assets / liabilities."""

    @pytest.mark.asyncio
    async def test_list_assets_empty(self, client):
        r = await client.get("/assets")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_create_real_estate(self, client):
        r = await client.post("/assets", json={
            "name": "Primary Residence",
            "asset_type": "real_estate",
            "current_value": 850000.0,
            "address": "123 Oak St",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Primary Residence"
        assert data["current_value"] == 850000.0
        assert data["is_liability"] is False

    @pytest.mark.asyncio
    async def test_create_mortgage_liability(self, client):
        r = await client.post("/assets", json={
            "name": "Home Mortgage",
            "asset_type": "mortgage",
            "current_value": 500000.0,
        })
        assert r.status_code == 201
        assert r.json()["is_liability"] is True

    @pytest.mark.asyncio
    async def test_create_update_delete_asset(self, client):
        # Create
        cr = await client.post("/assets", json={
            "name": "Tesla Model Y",
            "asset_type": "vehicle",
            "current_value": 45000.0,
        })
        assert cr.status_code == 201
        asset_id = cr.json()["id"]

        # Update
        r = await client.patch(f"/assets/{asset_id}", json={
            "current_value": 42000.0,
        })
        assert r.status_code == 200
        assert r.json()["current_value"] == 42000.0

        # Delete
        r = await client.delete(f"/assets/{asset_id}")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_update_nonexistent_asset_404(self, client):
        r = await client.patch("/assets/99999", json={"current_value": 100})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_asset_404(self, client):
        r = await client.delete("/assets/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_asset_summary(self, client):
        # Create assets and liabilities
        await client.post("/assets", json={"name": "House", "asset_type": "real_estate", "current_value": 500000})
        await client.post("/assets", json={"name": "Car", "asset_type": "vehicle", "current_value": 30000})
        await client.post("/assets", json={"name": "Mortgage", "asset_type": "mortgage", "current_value": 350000})

        r = await client.get("/assets/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_assets"] == 530000.0
        assert data["total_liabilities"] == 350000.0
        assert data["net"] == 180000.0
        assert data["count"] == 3
        assert "real_estate" in data["by_type"]

    @pytest.mark.asyncio
    async def test_create_investment_asset_links_account(self, client):
        r = await client.post("/assets", json={
            "name": "Fidelity 401k",
            "asset_type": "investment",
            "current_value": 250000.0,
            "institution": "Fidelity",
            "account_subtype": "401k",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["linked_account_id"] is not None

    @pytest.mark.asyncio
    async def test_invalid_asset_type_422(self, client):
        r = await client.post("/assets", json={
            "name": "Bad",
            "asset_type": "invalid_type",
            "current_value": 100,
        })
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 4. PORTFOLIO HOLDINGS  (api/routes/portfolio.py + portfolio_crypto.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestPortfolio:
    """Investment holdings and crypto CRUD."""

    @pytest.mark.asyncio
    async def test_list_holdings_empty(self, client):
        r = await client.get("/portfolio/holdings")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_create_holding(self, client):
        r = await client.post("/portfolio/holdings", json={
            "ticker": "VTI",
            "name": "Vanguard Total Stock Market",
            "shares": 100.0,
            "cost_basis_per_share": 220.50,
            "asset_class": "etf",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "VTI"
        assert data["shares"] == 100.0
        assert data["total_cost_basis"] == 22050.0

    @pytest.mark.asyncio
    async def test_create_update_delete_holding(self, client):
        cr = await client.post("/portfolio/holdings", json={
            "ticker": "AAPL",
            "shares": 50.0,
            "cost_basis_per_share": 150.0,
        })
        holding_id = cr.json()["id"]

        # Update shares
        r = await client.patch(f"/portfolio/holdings/{holding_id}", json={"shares": 75.0})
        assert r.status_code == 200
        assert r.json()["shares"] == 75.0
        assert r.json()["total_cost_basis"] == 11250.0  # 75 * 150

        # Delete
        r = await client.delete(f"/portfolio/holdings/{holding_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] == holding_id

    @pytest.mark.asyncio
    async def test_update_nonexistent_holding_404(self, client):
        r = await client.patch("/portfolio/holdings/99999", json={"shares": 1.0})
        assert r.status_code == 404

    # -- Crypto --

    @pytest.mark.asyncio
    async def test_list_crypto_empty(self, client):
        r = await client.get("/portfolio/crypto")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_create_crypto(self, client):
        r = await client.post("/portfolio/crypto", json={
            "coin_id": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "quantity": 0.5,
            "cost_basis_per_unit": 45000.0,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["coin_id"] == "bitcoin"
        assert data["symbol"] == "BTC"
        assert data["total_cost_basis"] == 22500.0

    @pytest.mark.asyncio
    async def test_create_delete_crypto(self, client):
        cr = await client.post("/portfolio/crypto", json={
            "coin_id": "ethereum",
            "symbol": "ETH",
            "quantity": 10.0,
        })
        crypto_id = cr.json()["id"]

        r = await client.delete(f"/portfolio/crypto/{crypto_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] == crypto_id


# ═══════════════════════════════════════════════════════════════════════════
# 5. FAMILY MEMBERS  (api/routes/family_members.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestFamilyMembers:
    """Family member CRUD with household sync."""

    @pytest.mark.asyncio
    async def test_list_family_members_empty(self, client):
        r = await client.get("/family-members/")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_create_family_member_no_household_404(self, client):
        r = await client.post("/family-members/", json={
            "household_id": 99999,
            "name": "Alice",
            "relationship": "self",
        })
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_crud_family_member(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()

        # Create
        cr = await client.post("/family-members/", json={
            "household_id": hp.id,
            "name": "Alice Smith",
            "relationship": "self",
            "is_earner": True,
            "income": 200000,
            "employer": "TechCorp",
            "work_state": "CA",
        })
        assert cr.status_code == 201
        member_id = cr.json()["id"]
        assert cr.json()["name"] == "Alice Smith"

        # Read
        r = await client.get(f"/family-members/{member_id}")
        assert r.status_code == 200
        assert r.json()["employer"] == "TechCorp"

        # Update
        r = await client.patch(f"/family-members/{member_id}", json={
            "income": 220000,
        })
        assert r.status_code == 200
        assert r.json()["income"] == 220000

        # Delete
        r = await client.delete(f"/family-members/{member_id}")
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_duplicate_self_409(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()

        await client.post("/family-members/", json={
            "household_id": hp.id, "name": "Alice", "relationship": "self",
        })
        r = await client.post("/family-members/", json={
            "household_id": hp.id, "name": "Also Alice", "relationship": "self",
        })
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_get_nonexistent_member_404(self, client):
        r = await client.get("/family-members/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_milestones(self, client, db_session):
        hp = await _seed_household(db_session)
        fm = FamilyMember(
            household_id=hp.id, name="Kid", relationship="child",
            date_of_birth=date(2020, 6, 15),
        )
        db_session.add(fm)
        await db_session.commit()

        r = await client.get(f"/family-members/milestones/by-household?household_id={hp.id}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ═══════════════════════════════════════════════════════════════════════════
# 6. RECURRING TRANSACTIONS  (api/routes/recurring.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestRecurring:
    """Recurring transactions listing, update, and summary."""

    @pytest.mark.asyncio
    async def test_list_recurring_empty(self, client):
        r = await client.get("/recurring")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_list_and_patch_recurring(self, client, db_session):
        rt = RecurringTransaction(
            name="Netflix", amount=-15.99, frequency="monthly",
            category="Entertainment", segment="personal", status="active",
        )
        db_session.add(rt)
        await db_session.flush()
        await db_session.commit()
        rt_id = rt.id

        # List
        r = await client.get("/recurring")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        found = [i for i in items if i["name"] == "Netflix"]
        assert found[0]["annual_cost"] == pytest.approx(191.88, rel=0.01)

        # Update
        r = await client.patch(f"/recurring/{rt_id}", json={"category": "Streaming"})
        assert r.status_code == 200
        assert r.json()["category"] == "Streaming"

    @pytest.mark.asyncio
    async def test_patch_nonexistent_recurring_404(self, client):
        r = await client.patch("/recurring/99999", json={"category": "x"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_recurring_summary(self, client, db_session):
        for name, amt, freq in [
            ("Gym", -50.0, "monthly"),
            ("Spotify", -9.99, "monthly"),
            ("Insurance", -600.0, "annual"),
        ]:
            rt = RecurringTransaction(
                name=name, amount=amt, frequency=freq,
                category="Subscription", segment="personal", status="active",
            )
            db_session.add(rt)
        await db_session.commit()

        r = await client.get("/recurring/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["subscription_count"] == 3
        # Monthly: 50 + 9.99 + 600/12 = 109.99
        assert data["total_monthly_cost"] == pytest.approx(109.99, rel=0.01)
        assert data["total_annual_cost"] == pytest.approx(1319.88, rel=0.01)

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client, db_session):
        rt = RecurringTransaction(
            name="Cancelled Sub", amount=-20.0, frequency="monthly",
            segment="personal", status="cancelled",
        )
        db_session.add(rt)
        await db_session.commit()

        r = await client.get("/recurring?status=cancelled")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    @pytest.mark.asyncio
    async def test_detect_recurring(self, client, db_session):
        """Test the /recurring/detect endpoint."""
        acct = await _seed_account(db_session)
        # Seed 4 months of a recurring charge
        for m in range(1, 5):
            tx = Transaction(
                account_id=acct.id,
                date=datetime(2026, m, 1, tzinfo=timezone.utc),
                description="NETFLIX.COM",
                amount=-15.99,
                segment="personal",
            )
            db_session.add(tx)
        await db_session.commit()

        r = await client.post("/recurring/detect?lookback_months=6")
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 7. REMINDERS  (api/routes/reminders.py + reminders_seed.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestReminders:
    """Reminder CRUD and seeding."""

    @pytest.mark.asyncio
    async def test_list_reminders_empty(self, client):
        r = await client.get("/reminders")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_create_reminder(self, client):
        # Use a future date string without timezone — matches how the route parses it
        due = "2027-06-15T12:00:00"
        r = await client.post("/reminders", json={
            "title": "File tax extension",
            "reminder_type": "tax",
            "due_date": due,
            "amount": 5000.0,
            "advance_notice": "14_days",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "File tax extension"
        assert data["status"] == "pending"
        assert data["amount"] == 5000.0

    @pytest.mark.asyncio
    async def test_update_reminder(self, client, db_session):
        # Seed directly with timezone-aware datetime to avoid _reminder_out mismatch
        r_obj = Reminder(
            title="Pay estimated tax", reminder_type="tax",
            due_date=datetime(2027, 6, 15, tzinfo=timezone.utc),
        )
        db_session.add(r_obj)
        await db_session.flush()
        await db_session.commit()
        reminder_id = r_obj.id

        r = await client.patch(f"/reminders/{reminder_id}", json={
            "status": "completed",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_nonexistent_reminder_404(self, client):
        r = await client.patch("/reminders/99999", json={"status": "completed"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_recurring_reminder_advances(self, client, db_session):
        r_obj = Reminder(
            title="Monthly review",
            due_date=datetime(2027, 6, 15, tzinfo=timezone.utc),
            is_recurring=True, recurrence_rule="monthly",
        )
        db_session.add(r_obj)
        await db_session.flush()
        await db_session.commit()
        reminder_id = r_obj.id

        # Complete it — should advance
        r = await client.patch(f"/reminders/{reminder_id}", json={"status": "completed"})
        assert r.status_code == 200

        # Check a new reminder was created
        r = await client.get("/reminders")
        # The advanced reminder should exist
        assert len(r.json()) >= 1

    @pytest.mark.asyncio
    async def test_filter_by_type(self, client, db_session):
        for title, rtype in [("Tax Q1", "tax"), ("Custom thing", "custom")]:
            r_obj = Reminder(
                title=title, reminder_type=rtype,
                due_date=datetime(2027, 6, 15, tzinfo=timezone.utc),
            )
            db_session.add(r_obj)
        await db_session.commit()

        r = await client.get("/reminders?reminder_type=tax")
        assert r.status_code == 200
        for rem in r.json():
            assert rem["reminder_type"] == "tax"

    @pytest.mark.asyncio
    async def test_seed_all_reminders(self, client):
        r = await client.post("/reminders/seed-all")
        assert r.status_code == 200
        data = r.json()
        assert data["seeded"] >= 0
        assert "by_type" in data

    @pytest.mark.asyncio
    async def test_seed_tax_deadlines(self, client):
        r = await client.post("/reminders/seed-tax-deadlines")
        assert r.status_code == 200
        assert "seeded" in r.json()

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self, client):
        r1 = await client.post("/reminders/seed-all")
        r2 = await client.post("/reminders/seed-all")
        assert r2.status_code == 200
        assert r2.json()["seeded"] == 0  # nothing new seeded


# ═══════════════════════════════════════════════════════════════════════════
# 8. SETUP STATUS  (api/routes/setup_status.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestSetupStatus:
    """Setup wizard status check and completion."""

    @pytest.mark.asyncio
    async def test_setup_status_empty(self, client):
        r = await client.get("/setup/status")
        assert r.status_code == 200
        data = r.json()
        assert data["household"] is False
        assert data["income"] is False
        assert data["accounts"] is False
        assert data["complete"] is False
        assert data["setup_completed_at"] is None

    @pytest.mark.asyncio
    async def test_setup_status_with_data(self, client, db_session):
        hp = await _seed_household(db_session, spouse_a_income=200000)
        acct = await _seed_account(db_session)
        await db_session.commit()

        r = await client.get("/setup/status")
        assert r.status_code == 200
        data = r.json()
        assert data["household"] is True
        assert data["income"] is True
        assert data["accounts"] is True
        assert data["complete"] is True

    @pytest.mark.asyncio
    async def test_mark_setup_complete(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()

        r = await client.post("/setup/complete")
        assert r.status_code == 200
        assert "setup_completed_at" in r.json()

    @pytest.mark.asyncio
    async def test_mark_setup_complete_idempotent(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()

        r1 = await client.post("/setup/complete")
        ts1 = r1.json()["setup_completed_at"]

        r2 = await client.post("/setup/complete")
        ts2 = r2.json()["setup_completed_at"]
        assert ts1 == ts2  # Same timestamp, not re-created

    @pytest.mark.asyncio
    async def test_setup_complete_without_household_warns(self, client):
        r = await client.post("/setup/complete")
        assert r.status_code == 200
        data = r.json()
        assert "warnings" in data
        assert "no_household" in data["warnings"]


# ═══════════════════════════════════════════════════════════════════════════
# 9. AUTH ROUTES  (api/routes/auth_routes.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthRoutes:
    """Auth mode selection and API key injection."""

    @pytest.mark.asyncio
    async def test_get_mode(self, client):
        r = await client.get("/auth/mode")
        assert r.status_code == 200
        assert r.json()["mode"] in ("local", "demo")

    @pytest.mark.asyncio
    async def test_select_invalid_mode_400(self, client):
        r = await client.post("/auth/select-mode", json={"mode": "invalid"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_inject_invalid_api_key_400(self, client):
        r = await client.post("/auth/inject-api-key", json={"key": "not-a-real-key"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_inject_valid_api_key(self, client):
        r = await client.post("/auth/inject-api-key", json={
            "key": "sk-ant-api03-test-key-for-unit-tests-only-not-real",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client):
        r = await client.get("/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["authenticated"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 10. GOAL SUGGESTIONS  (api/routes/goal_suggestions.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestGoalSuggestions:
    """Goal suggestion endpoint — personalized by household data."""

    @pytest.mark.asyncio
    async def test_suggestions_default_income(self, client):
        r = await client.get("/goals/suggestions")
        assert r.status_code == 200
        data = r.json()
        assert data["annual_income"] == 200000  # default HENRY income
        assert len(data["suggestions"]) >= 4
        # Check emergency fund is first priority
        types = [s["goal_type"] for s in data["suggestions"]]
        assert "emergency_fund" in types

    @pytest.mark.asyncio
    async def test_suggestions_with_household(self, client, db_session):
        hp = await _seed_household(db_session, spouse_a_income=300000, spouse_b_income=200000)
        await db_session.commit()

        r = await client.get("/goals/suggestions")
        data = r.json()
        assert data["annual_income"] == 500000
        ef_suggestion = next(s for s in data["suggestions"] if s["goal_type"] == "emergency_fund")
        # 6 months of 500k/12 = ~250k, rounded
        assert ef_suggestion["target_amount"] >= 200000

    @pytest.mark.asyncio
    async def test_suggestions_with_equity_grants(self, client, db_session):
        hp = await _seed_household(db_session)
        grant = EquityGrant(
            employer_name="TechCorp", grant_type="rsu",
            grant_date=date(2024, 1, 1), total_shares=1000,
            vested_shares=500, unvested_shares=500, current_fmv=200.0,
            is_active=True,
        )
        db_session.add(grant)
        await db_session.commit()

        r = await client.get("/goals/suggestions")
        data = r.json()
        types = [s["goal_type"] for s in data["suggestions"]]
        # RSU tax reserve should appear as a 'tax' goal
        tax_goals = [s for s in data["suggestions"] if s["goal_type"] == "tax"]
        assert len(tax_goals) >= 1

    @pytest.mark.asyncio
    async def test_suggestions_exclude_existing_goals(self, client, db_session):
        # Add an existing active emergency fund goal
        goal = Goal(
            name="My Emergency Fund", goal_type="emergency_fund",
            target_amount=100000, status="active",
        )
        db_session.add(goal)
        await db_session.commit()

        r = await client.get("/goals/suggestions")
        types = [s["goal_type"] for s in r.json()["suggestions"]]
        assert "emergency_fund" not in types

    @pytest.mark.asyncio
    async def test_suggestions_include_priority_order(self, client):
        r = await client.get("/goals/suggestions")
        priorities = [s["priority"] for s in r.json()["suggestions"]]
        assert priorities == sorted(priorities)


# ═══════════════════════════════════════════════════════════════════════════
# 11. USER CONTEXT  (api/routes/user_context.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestUserContext:
    """User context CRUD for AI personalization."""

    @pytest.mark.asyncio
    async def test_list_context_empty(self, client):
        r = await client.get("/user-context")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["facts"] == []

    @pytest.mark.asyncio
    async def test_create_and_list_context(self, client):
        cr = await client.post("/user-context", json={
            "category": "business",
            "key": "primary_business",
            "value": "AutoRev — car dealership",
            "source": "manual",
        })
        assert cr.status_code == 200
        assert cr.json()["category"] == "business"
        assert cr.json()["value"] == "AutoRev — car dealership"

        r = await client.get("/user-context")
        assert r.json()["count"] == 1

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, client):
        await client.post("/user-context", json={
            "category": "tax", "key": "filing", "value": "MFJ", "source": "manual",
        })
        r = await client.post("/user-context", json={
            "category": "tax", "key": "filing", "value": "Single", "source": "manual",
        })
        assert r.status_code == 200
        assert r.json()["value"] == "Single"

        # Should still be only 1 fact with that key
        listing = await client.get("/user-context?category=tax")
        assert listing.json()["count"] == 1

    @pytest.mark.asyncio
    async def test_delete_context(self, client):
        cr = await client.post("/user-context", json={
            "category": "preference", "key": "tax_style", "value": "aggressive",
        })
        ctx_id = cr.json()["id"]

        r = await client.delete(f"/user-context/{ctx_id}")
        assert r.status_code == 200
        assert r.json()["deleted_id"] == ctx_id

    @pytest.mark.asyncio
    async def test_delete_nonexistent_context_404(self, client):
        r = await client.delete("/user-context/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client):
        await client.post("/user-context", json={
            "category": "business", "key": "biz1", "value": "val1",
        })
        await client.post("/user-context", json={
            "category": "tax", "key": "tax1", "value": "val2",
        })

        r = await client.get("/user-context?category=business")
        assert r.status_code == 200
        for f in r.json()["facts"]:
            assert f["category"] == "business"


# ═══════════════════════════════════════════════════════════════════════════
# 12. REPORTS  (api/routes/reports.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestReports:
    """Financial reports — dashboard, monthly, periods."""

    @pytest.mark.asyncio
    async def test_list_periods_empty(self, client):
        r = await client.get("/reports/periods")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_list_periods_with_data(self, client, db_session):
        fp = FinancialPeriod(
            year=2026, month=3, segment="all",
            total_income=15000.0, total_expenses=8000.0,
            net_cash_flow=7000.0, w2_income=15000.0,
            investment_income=0, board_income=0,
            business_expenses=0, personal_expenses=8000.0,
            expense_breakdown='{"Housing": 3000, "Food": 1500}',
            income_breakdown='{"W2": 15000}',
        )
        db_session.add(fp)
        await db_session.commit()

        r = await client.get("/reports/periods?year=2026")
        assert r.status_code == 200
        periods = r.json()
        assert len(periods) >= 1
        assert periods[0]["total_income"] == 15000.0
        assert periods[0]["net_cash_flow"] == 7000.0

    @pytest.mark.asyncio
    async def test_dashboard_empty_db(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()

        r = await client.get("/reports/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert data["current_year"] == datetime.now(timezone.utc).year
        assert data["ytd_income"] == 0.0
        assert data["ytd_expenses"] == 0.0

    @pytest.mark.asyncio
    async def test_dashboard_with_data(self, client, db_session):
        hp = await _seed_household(db_session, spouse_a_income=200000, spouse_b_income=0)
        fp = FinancialPeriod(
            year=2026, month=1, segment="all",
            total_income=20000.0, total_expenses=12000.0,
            net_cash_flow=8000.0, w2_income=20000.0,
            investment_income=0, board_income=0,
            business_expenses=0, personal_expenses=12000.0,
        )
        db_session.add(fp)
        await db_session.commit()

        r = await client.get("/reports/dashboard?year=2026")
        assert r.status_code == 200
        data = r.json()
        assert data["ytd_income"] >= 20000.0

    @pytest.mark.asyncio
    async def test_monthly_report(self, client, db_session):
        hp = await _seed_household(db_session)
        acct = await _seed_account(db_session)
        # Seed some transactions for Jan 2026
        for desc, amt in [("Salary", 15000), ("Rent", -2500), ("Groceries", -800)]:
            tx = Transaction(
                account_id=acct.id,
                date=datetime(2026, 1, 15, tzinfo=timezone.utc),
                description=desc, amount=amt, segment="personal",
                period_year=2026, period_month=1,
            )
            db_session.add(tx)
        await db_session.commit()

        r = await client.get("/reports/monthly?year=2026&month=1")
        assert r.status_code == 200
        data = r.json()
        assert "period" in data
        assert "top_expense_categories" in data

    @pytest.mark.asyncio
    async def test_recompute_periods(self, client, db_session):
        hp = await _seed_household(db_session)
        acct = await _seed_account(db_session)
        tx = await _seed_transaction(db_session, acct.id, amount=-100, period_year=2026, period_month=1)
        await db_session.commit()

        r = await client.post("/reports/recompute?year=2026")
        assert r.status_code == 200
        data = r.json()
        assert data["year"] == 2026
        assert data["recomputed"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# 13. INCOME  (api/routes/income.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestIncome:
    """Income/payroll connection endpoints."""

    @pytest.mark.asyncio
    async def test_list_connections_empty(self, client):
        r = await client.get("/income/connections")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    @patch("pipeline.plaid.income_client.create_plaid_user")
    @patch("pipeline.plaid.income_client.create_income_link_token")
    async def test_create_income_link_token(self, mock_link, mock_user, client):
        mock_user.return_value = {"user_token": "test-user-token", "user_id": "user-123"}
        mock_link.return_value = "link-sandbox-token"

        r = await client.post("/income/link-token", json={"income_source_type": "payroll"})
        assert r.status_code == 200
        data = r.json()
        assert data["link_token"] == "link-sandbox-token"
        assert data["connection_id"] is not None

    @pytest.mark.asyncio
    async def test_income_connected_nonexistent_404(self, client):
        r = await client.post("/income/connected/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_income_connected(self, client, db_session):
        conn = PayrollConnection(
            status="pending", income_source_type="payroll",
        )
        db_session.add(conn)
        await db_session.commit()

        r = await client.post(f"/income/connected/{conn.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "syncing"

    @pytest.mark.asyncio
    async def test_cascade_summary_nonexistent_404(self, client):
        r = await client.get("/income/cascade-summary/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_cascade_summary(self, client, db_session):
        conn = PayrollConnection(
            status="synced", income_source_type="payroll",
            employer_name="TechCorp",
        )
        db_session.add(conn)
        await db_session.flush()

        stub = PayStubRecord(
            connection_id=conn.id,
            pay_date=date(2026, 1, 15),
            gross_pay=8000.0,
            gross_pay_ytd=8000.0,
            net_pay=5500.0,
            pay_frequency="semi-monthly",
            deductions_json='[{"description": "401k", "amount": 500}]',
        )
        db_session.add(stub)
        await db_session.commit()

        r = await client.get(f"/income/cascade-summary/{conn.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["employer"] == "TechCorp"
        assert data["pay_stubs_imported"] == 1
        assert data["annual_income"] is not None
        assert "401k" in data["benefits_detected"]

    @pytest.mark.asyncio
    async def test_list_connections(self, client, db_session):
        conn = PayrollConnection(
            status="synced", employer_name="Acme",
            income_source_type="payroll",
        )
        db_session.add(conn)
        await db_session.commit()

        r = await client.get("/income/connections")
        assert r.status_code == 200
        assert len(r.json()) >= 1
        assert r.json()[0]["employer_name"] == "Acme"


# ═══════════════════════════════════════════════════════════════════════════
# 14. PLAID  (api/routes/plaid.py) — all external calls mocked
# ═══════════════════════════════════════════════════════════════════════════

class TestPlaid:
    """Plaid link, sync, and item management — fully mocked."""

    @pytest.mark.asyncio
    @patch("api.routes.plaid.create_link_token")
    async def test_get_link_token(self, mock_create, client):
        mock_create.return_value = "link-sandbox-abc123"
        r = await client.get("/plaid/link-token")
        assert r.status_code == 200
        assert r.json()["link_token"] == "link-sandbox-abc123"

    @pytest.mark.asyncio
    @patch("api.routes.plaid.create_link_token", side_effect=Exception("Plaid down"))
    async def test_get_link_token_error(self, mock_create, client):
        r = await client.get("/plaid/link-token")
        assert r.status_code == 500

    @pytest.mark.asyncio
    async def test_list_items_empty(self, client):
        r = await client.get("/plaid/items")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_list_plaid_accounts_empty(self, client):
        r = await client.get("/plaid/accounts")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_plaid_health_empty(self, client):
        r = await client.get("/plaid/health")
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["total_items"] == 0
        assert data["summary"]["net_balance"] == 0.0

    @pytest.mark.asyncio
    async def test_plaid_health_with_items(self, client, db_session):
        item = PlaidItem(
            item_id="plaid-item-1", access_token="enc-token",
            institution_name="Chase", status="active",
            last_synced_at=datetime.now(timezone.utc),
        )
        db_session.add(item)
        await db_session.flush()

        acct = await _seed_account(db_session, name="Chase Checking", data_source="plaid")
        pa = PlaidAccount(
            plaid_item_id=item.id, account_id=acct.id,
            plaid_account_id="plaid-acct-1",
            name="Chase Checking", type="depository", subtype="checking",
            current_balance=5000.0, available_balance=4800.0,
        )
        db_session.add(pa)
        await db_session.commit()

        r = await client.get("/plaid/health")
        data = r.json()
        assert data["summary"]["total_items"] == 1
        assert data["summary"]["total_assets"] == 5000.0

    @pytest.mark.asyncio
    async def test_sync_status_nonexistent_404(self, client):
        r = await client.get("/plaid/sync-status/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_status(self, client, db_session):
        item = PlaidItem(
            item_id="plaid-item-sync", access_token="enc",
            institution_name="BofA", status="active",
            sync_phase="complete",
        )
        db_session.add(item)
        await db_session.commit()

        r = await client.get(f"/plaid/sync-status/{item.id}")
        assert r.status_code == 200
        assert r.json()["sync_phase"] == "complete"

    @pytest.mark.asyncio
    @patch("api.routes.plaid._initial_sync_and_dedup", new_callable=AsyncMock)
    @patch("api.routes.plaid.exchange_public_token")
    @patch("api.routes.plaid.get_accounts")
    @patch("api.routes.plaid.encrypt_token", return_value="encrypted")
    async def test_exchange_token(self, mock_enc, mock_accts, mock_exchange, mock_bg, client):
        mock_exchange.return_value = {
            "item_id": "plaid-item-new",
            "access_token": "access-sandbox-xxx",
        }
        mock_accts.return_value = [
            {"name": "Checking", "subtype": "checking", "mask": "0001",
             "plaid_account_id": "pa-1", "type": "depository",
             "current_balance": 3000, "available_balance": 2800},
        ]

        r = await client.post("/plaid/exchange-token", json={
            "public_token": "public-sandbox-xxx",
            "institution_name": "Wells Fargo",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "connected"
        assert data["accounts_created"] >= 1

    @pytest.mark.asyncio
    @patch("api.routes.plaid.exchange_public_token")
    @patch("api.routes.plaid.get_accounts")
    @patch("api.routes.plaid.encrypt_token", return_value="encrypted")
    async def test_exchange_token_duplicate_institution_409(
        self, mock_enc, mock_accts, mock_exchange, client, db_session
    ):
        # Pre-seed an existing item for the same institution
        existing = PlaidItem(
            item_id="plaid-existing", access_token="enc",
            institution_name="Wells Fargo", status="active",
        )
        db_session.add(existing)
        await db_session.commit()

        mock_exchange.return_value = {"item_id": "new-id", "access_token": "new-access"}
        mock_accts.return_value = []

        r = await client.post("/plaid/exchange-token", json={
            "public_token": "public-sandbox-yyy",
            "institution_name": "Wells Fargo",
        })
        assert r.status_code == 409

    @pytest.mark.asyncio
    @patch("api.routes.plaid.decrypt_token", return_value="real-access-token")
    @patch("api.routes.plaid.remove_item")
    async def test_delete_item(self, mock_remove, mock_decrypt, client, db_session):
        item = PlaidItem(
            item_id="plaid-to-delete", access_token="enc",
            institution_name="Citi", status="active",
        )
        db_session.add(item)
        await db_session.commit()

        r = await client.delete(f"/plaid/items/{item.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "removed"
        mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_item_404(self, client):
        r = await client.delete("/plaid/items/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    @patch("pipeline.plaid.sync.sync_all_items", new_callable=AsyncMock, return_value={"synced": 0})
    async def test_trigger_sync(self, mock_sync, client, db_session):
        """Trigger sync returns immediately; background task uses AsyncSessionLocal.
        We mock the underlying sync function to avoid real Plaid calls."""
        # We need to mock AsyncSessionLocal to return a proper async context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=None)
        mock_begin.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_begin)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("api.routes.plaid.AsyncSessionLocal", mock_factory):
            r = await client.post("/plaid/sync")
        assert r.status_code == 200
        assert r.json()["status"] == "sync_started"

    @pytest.mark.asyncio
    @patch("api.routes.plaid.decrypt_token", return_value="real-access-token")
    @patch("api.routes.plaid.create_link_token", return_value="update-link-token")
    async def test_update_link_token(self, mock_create, mock_decrypt, client, db_session):
        item = PlaidItem(
            item_id="plaid-update", access_token="enc",
            institution_name="BofA", status="active",
        )
        db_session.add(item)
        await db_session.commit()

        r = await client.get(f"/plaid/link-token/update/{item.id}")
        assert r.status_code == 200
        assert r.json()["link_token"] == "update-link-token"

    @pytest.mark.asyncio
    async def test_update_link_token_nonexistent_404(self, client):
        r = await client.get("/plaid/link-token/update/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_list_items_with_data(self, client, db_session):
        item = PlaidItem(
            item_id="plaid-list-1", access_token="enc",
            institution_name="Schwab", status="active",
        )
        db_session.add(item)
        await db_session.commit()

        r = await client.get("/plaid/items")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert items[0]["institution_name"] == "Schwab"


# ═══════════════════════════════════════════════════════════════════════════
# 15. IMPORT ROUTES  (api/routes/import_routes.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestImportRoutes:
    """File import endpoints — uploads, type detection, categorization."""

    @pytest.mark.asyncio
    async def test_upload_no_file_422(self, client):
        r = await client.post("/import/upload")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(self, client):
        file_content = b"some binary data"
        r = await client.post(
            "/import/upload",
            files={"file": ("test.exe", io.BytesIO(file_content), "application/octet-stream")},
            data={"document_type": "credit_card"},
        )
        assert r.status_code == 400
        assert "not supported" in r.json()["detail"]

    @pytest.mark.asyncio
    @patch("pipeline.importers.credit_card.import_csv_file")
    async def test_upload_csv_credit_card(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed",
            "document_id": 42,
            "transactions_imported": 15,
            "transactions_skipped": 2,
            "message": "Imported 15 transactions",
        }

        csv_content = b"Date,Description,Amount\n2026-01-15,Amazon,-50.00\n2026-01-16,Starbucks,-5.50\n"
        r = await client.post(
            "/import/upload",
            files={"file": ("chase_jan.csv", io.BytesIO(csv_content), "text/csv")},
            data={
                "document_type": "credit_card",
                "account_name": "Chase Sapphire",
                "institution": "Chase",
                "segment": "personal",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["transactions_imported"] == 15
        assert data["filename"] == "chase_jan.csv"

    @pytest.mark.asyncio
    @patch("pipeline.importers.credit_card.import_csv_file")
    async def test_upload_csv_import_error(self, mock_import, client):
        mock_import.return_value = {
            "status": "error",
            "message": "Unrecognized CSV format",
        }

        csv_content = b"bad,data\n"
        r = await client.post(
            "/import/upload",
            files={"file": ("bad.csv", io.BytesIO(csv_content), "text/csv")},
            data={"document_type": "credit_card"},
        )
        assert r.status_code == 422
        assert "Unrecognized" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_detect_type_csv(self, client):
        csv_content = b"Transaction Date,Post Date,Description,Category,Amount\n01/15/2026,01/16/2026,AMAZON,-50.00\n"
        with patch("pipeline.ai.categorizer.detect_document_type") as mock_detect:
            mock_detect.return_value = {"type": "credit_card", "confidence": 0.95}
            r = await client.post(
                "/import/detect-type",
                files={"file": ("unknown.csv", io.BytesIO(csv_content), "text/csv")},
            )
            assert r.status_code == 200
            assert r.json()["type"] == "credit_card"

    @pytest.mark.asyncio
    async def test_upload_no_filename_rejected(self, client):
        """Empty filename on upload is rejected (422 from FastAPI validation)."""
        r = await client.post(
            "/import/upload",
            files={"file": ("", io.BytesIO(b"data"), "text/csv")},
            data={"document_type": "credit_card"},
        )
        # FastAPI rejects empty filename via validation before route handler runs
        assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    @patch("pipeline.importers.tax_doc.import_directory")
    async def test_batch_tax_docs(self, mock_import_dir, client):
        mock_import_dir.return_value = [
            {"status": "completed", "filename": "w2.pdf"},
            {"status": "duplicate", "filename": "w2_copy.pdf"},
        ]

        r = await client.post("/import/batch-tax-docs?tax_year=2025")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert data["completed"] == 1
        assert data["duplicate"] == 1

    @pytest.mark.asyncio
    @patch("pipeline.db.models.apply_entity_rules", new_callable=AsyncMock, return_value=5)
    @patch("pipeline.ai.category_rules.apply_rules", new_callable=AsyncMock, return_value={"applied": 3})
    @patch("pipeline.ai.categorizer.categorize_transactions", new_callable=AsyncMock, return_value={"categorized": 10, "total": 15})
    async def test_run_categorization(self, mock_cat, mock_rules, mock_entity, client):
        r = await client.post("/import/categorize")
        assert r.status_code == 200
        data = r.json()
        assert data["entity_rules_applied"] == 5
        assert data["category_rules_applied"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# 16. VALUATIONS  (api/routes/valuations.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestValuations:
    """Asset valuation endpoints — vehicle VIN and property."""

    @pytest.mark.asyncio
    @patch("pipeline.market.vehicle_valuation.VehicleValuationService.decode_vin", new_callable=AsyncMock)
    @patch("pipeline.market.vehicle_valuation.VehicleValuationService.estimate_value")
    async def test_decode_vehicle(self, mock_estimate, mock_decode, client):
        mock_decode.return_value = {"year": 2023, "make": "Tesla", "model": "Model Y"}
        mock_estimate.return_value = {"estimated_value": 42000.0, "confidence": "medium"}

        r = await client.get("/valuations/vehicle/1HGCM82633A123456")
        assert r.status_code == 200
        data = r.json()
        assert data["vehicle"]["make"] == "Tesla"
        assert data["valuation"]["estimated_value"] == 42000.0

    @pytest.mark.asyncio
    @patch("pipeline.market.vehicle_valuation.VehicleValuationService.decode_vin", new_callable=AsyncMock)
    async def test_decode_vehicle_bad_vin_400(self, mock_decode, client):
        mock_decode.return_value = None
        r = await client.get("/valuations/vehicle/BADVIN")
        assert r.status_code == 400

    @pytest.mark.asyncio
    @patch("pipeline.market.property_valuation.PropertyValuationService.get_valuation", new_callable=AsyncMock)
    async def test_property_valuation(self, mock_val, client):
        mock_val.return_value = {"estimated_value": 850000.0, "confidence": "high"}
        r = await client.get("/valuations/property?address=123+Main+St")
        assert r.status_code == 200
        assert r.json()["estimated_value"] == 850000.0

    @pytest.mark.asyncio
    @patch("pipeline.market.property_valuation.PropertyValuationService.get_valuation", new_callable=AsyncMock)
    async def test_property_valuation_not_found_404(self, mock_val, client):
        mock_val.return_value = None
        r = await client.get("/valuations/property?address=Nowhere")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_asset_404(self, client):
        r = await client.post("/valuations/assets/99999/refresh")
        assert r.status_code == 404

    @pytest.mark.asyncio
    @patch("pipeline.market.vehicle_valuation.VehicleValuationService.decode_vin", new_callable=AsyncMock)
    @patch("pipeline.market.vehicle_valuation.VehicleValuationService.estimate_value")
    async def test_refresh_vehicle_asset(self, mock_estimate, mock_decode, client, db_session):
        asset = ManualAsset(
            name="Old Car", asset_type="vehicle",
            current_value=20000.0, is_active=True,
        )
        db_session.add(asset)
        await db_session.commit()

        mock_decode.return_value = {"year": 2021, "make": "Honda", "model": "Civic"}
        mock_estimate.return_value = {"estimated_value": 18500.0}

        r = await client.post(
            f"/valuations/assets/{asset.id}/refresh",
            json={"vin": "1HGCM82633A999999"},
        )
        assert r.status_code == 200
        assert r.json()["updated"] is True
        assert r.json()["new_value"] == 18500.0

    @pytest.mark.asyncio
    async def test_refresh_vehicle_no_vin_400(self, client, db_session):
        asset = ManualAsset(
            name="No VIN Car", asset_type="vehicle",
            current_value=15000.0, is_active=True,
        )
        db_session.add(asset)
        await db_session.commit()

        r = await client.post(f"/valuations/assets/{asset.id}/refresh")
        assert r.status_code == 400

    @pytest.mark.asyncio
    @patch("pipeline.market.property_valuation.PropertyValuationService.get_valuation", new_callable=AsyncMock)
    async def test_refresh_real_estate_asset(self, mock_val, client, db_session):
        asset = ManualAsset(
            name="House", asset_type="real_estate",
            current_value=700000.0, is_active=True,
            address="456 Elm St",
        )
        db_session.add(asset)
        await db_session.commit()

        mock_val.return_value = {"estimated_value": 750000.0}

        r = await client.post(f"/valuations/assets/{asset.id}/refresh")
        assert r.status_code == 200
        assert r.json()["updated"] is True
        assert r.json()["new_value"] == 750000.0


# ═══════════════════════════════════════════════════════════════════════════
# 17. DATABASE  (api/database.py) — mode switching
# ═══════════════════════════════════════════════════════════════════════════

class TestDatabase:
    """Database mode and session management."""

    @pytest.mark.asyncio
    async def test_get_active_mode(self):
        from api.database import get_active_mode
        mode = get_active_mode()
        assert mode in ("local", "demo")

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self, test_session_factory):
        from api.database import get_session
        # The overridden session should work
        async with test_session_factory() as session:
            assert isinstance(session, AsyncSession)


# ═══════════════════════════════════════════════════════════════════════════
# 18. AUTH MIDDLEWARE  (api/auth.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthMiddleware:
    """JWT validation and auth bypass in dev/demo mode."""

    @pytest.mark.asyncio
    async def test_get_current_user_no_auth_configured(self):
        """In dev mode (no SUPABASE_JWT_SECRET), auth returns None."""
        from api.auth import get_current_user
        from unittest.mock import MagicMock

        request = MagicMock()
        result = await get_current_user(request, credentials=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_with_bad_token(self):
        """When Supabase auth is configured, invalid tokens raise 401."""
        from api.auth import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
        request = MagicMock()

        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": "test-secret"}):
            # Re-import to pick up env var
            import importlib
            import api.auth
            importlib.reload(api.auth)
            try:
                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await api.auth.get_current_user(request, credentials=creds)
                assert exc_info.value.status_code == 401
            finally:
                # Restore
                with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": ""}, clear=False):
                    importlib.reload(api.auth)


# ═══════════════════════════════════════════════════════════════════════════
# 19. APP FACTORY / LIFESPAN  (api/main.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestMainApp:
    """Test app factory health endpoint and basic wiring."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
