"""Tests for transaction mutation API endpoints (POST, PATCH) and import pipeline.

Covers:
- POST /transactions (create manual transaction)
- PATCH /transactions/{id} (update category, segment, notes, exclusion)
- GET /transactions (list with filters)
- GET /transactions/{id} (single transaction retrieval)
- GET /transactions/audit (categorization audit)
- POST /import/categorize (trigger categorization pipeline)
- Error handling (404s, invalid inputs)
- Partial updates and persistence verification
"""

import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Account, Base, Transaction


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
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def test_app(test_session_factory):
    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)

    from api.routes import transactions, accounts, import_routes

    app.include_router(transactions.router)
    app.include_router(accounts.router)
    app.include_router(import_routes.router)

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
async def seed_account(test_session_factory) -> int:
    """Create a test account via ORM and return its ID."""
    async with test_session_factory() as session:
        acct = Account(
            name="Test Checking",
            account_type="depository",
            subtype="checking",
            institution="Test Bank",
            currency="USD",
            is_active=True,
            data_source="manual",
        )
        session.add(acct)
        await session.flush()
        acct_id = acct.id
        await session.commit()
    return acct_id


@pytest_asyncio.fixture
async def seed_account_business(test_session_factory) -> int:
    """Create a business account via ORM and return its ID."""
    async with test_session_factory() as session:
        acct = Account(
            name="Business Credit Card",
            account_type="credit_card",
            subtype="credit_card",
            institution="Chase",
            currency="USD",
            is_active=True,
            data_source="manual",
            default_segment="business",
        )
        session.add(acct)
        await session.flush()
        acct_id = acct.id
        await session.commit()
    return acct_id


@pytest_asyncio.fixture
async def seed_transactions(test_session_factory, seed_account) -> list[int]:
    """Seed 5 transactions across different months/categories and return their IDs."""
    now = datetime.now(timezone.utc)
    txns = [
        Transaction(
            account_id=seed_account,
            date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            description="Grocery Store Purchase",
            amount=-85.50,
            currency="USD",
            segment="personal",
            effective_segment="personal",
            category="Groceries",
            effective_category="Groceries",
            period_month=1,
            period_year=2025,
            is_excluded=False,
            data_source="csv",
        ),
        Transaction(
            account_id=seed_account,
            date=datetime(2025, 1, 20, tzinfo=timezone.utc),
            description="Electric Company Payment",
            amount=-120.00,
            currency="USD",
            segment="personal",
            effective_segment="personal",
            category="Utilities",
            effective_category="Utilities",
            period_month=1,
            period_year=2025,
            is_excluded=False,
            data_source="csv",
        ),
        Transaction(
            account_id=seed_account,
            date=datetime(2025, 2, 5, tzinfo=timezone.utc),
            description="Coffee Shop",
            amount=-5.75,
            currency="USD",
            segment="personal",
            effective_segment="personal",
            category="Dining",
            effective_category="Dining",
            period_month=2,
            period_year=2025,
            is_excluded=False,
            data_source="csv",
        ),
        Transaction(
            account_id=seed_account,
            date=datetime(2025, 2, 10, tzinfo=timezone.utc),
            description="Paycheck Direct Deposit",
            amount=3500.00,
            currency="USD",
            segment="personal",
            effective_segment="personal",
            category="Income",
            effective_category="Income",
            period_month=2,
            period_year=2025,
            is_excluded=False,
            data_source="csv",
        ),
        Transaction(
            account_id=seed_account,
            date=datetime(2025, 3, 1, tzinfo=timezone.utc),
            description="Uncategorized Transaction",
            amount=-42.00,
            currency="USD",
            segment="personal",
            effective_segment="personal",
            period_month=3,
            period_year=2025,
            is_excluded=False,
            data_source="csv",
        ),
    ]
    async with test_session_factory() as session:
        session.add_all(txns)
        await session.flush()
        ids = [t.id for t in txns]
        await session.commit()
    return ids


# ---------------------------------------------------------------------------
# POST /transactions — Create manual transaction
# ---------------------------------------------------------------------------


class TestCreateTransaction:
    """Tests for POST /transactions to create manual transactions."""

    async def test_create_manual_transaction(self, client, seed_account):
        resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-06-15T00:00:00",
                "description": "Office Supplies from Staples",
                "amount": -49.99,
                "currency": "USD",
                "segment": "business",
                "category": "Office Supplies",
                "notes": "Printer paper and toner",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Office Supplies from Staples"
        assert data["amount"] == -49.99
        assert data["segment"] == "business"
        assert data["effective_segment"] == "business"
        assert data["effective_category"] == "Office Supplies"
        assert data["notes"] == "Printer paper and toner"
        assert data["data_source"] == "manual"
        assert data["period_month"] == 6
        assert data["period_year"] == 2025
        assert data["is_excluded"] is False
        assert data["id"] is not None

    async def test_create_transaction_minimal_fields(self, client, seed_account):
        """Create a transaction with only the required fields."""
        resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-04-01T00:00:00",
                "description": "Misc expense",
                "amount": -10.00,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Misc expense"
        assert data["amount"] == -10.00
        assert data["segment"] == "personal"  # default
        assert data["currency"] == "USD"  # default

    async def test_create_transaction_with_tax_category(self, client, seed_account):
        resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-07-01T00:00:00",
                "description": "Consulting Payment",
                "amount": 5000.00,
                "segment": "business",
                "category": "Revenue",
                "tax_category": "Schedule C Line 1 - Gross Receipts",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["effective_tax_category"] == "Schedule C Line 1 - Gross Receipts"

    async def test_create_transaction_nonexistent_account(self, client):
        """POST with a non-existent account_id should return 404."""
        resp = await client.post(
            "/transactions",
            json={
                "account_id": 99999,
                "date": "2025-01-01T00:00:00",
                "description": "Ghost transaction",
                "amount": -100.00,
            },
        )
        assert resp.status_code == 404

    async def test_create_transaction_persists(self, client, seed_account):
        """Verify the created transaction can be fetched back via GET."""
        create_resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-08-20T00:00:00",
                "description": "Persisted manual entry",
                "amount": -33.33,
            },
        )
        assert create_resp.status_code == 201
        tx_id = create_resp.json()["id"]

        get_resp = await client.get(f"/transactions/{tx_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["description"] == "Persisted manual entry"
        assert get_resp.json()["amount"] == -33.33

    async def test_create_income_transaction(self, client, seed_account):
        """Create a positive-amount (income) transaction."""
        resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-09-01T00:00:00",
                "description": "Freelance payment received",
                "amount": 2500.00,
                "category": "Freelance Income",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 2500.00
        assert data["effective_category"] == "Freelance Income"


# ---------------------------------------------------------------------------
# PATCH /transactions/{id} — Update transaction
# ---------------------------------------------------------------------------


class TestUpdateTransaction:
    """Tests for PATCH /transactions/{id} to modify existing transactions."""

    async def test_update_category_override(self, client, seed_transactions):
        tx_id = seed_transactions[0]  # Grocery Store Purchase
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"category_override": "Food & Drink"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category_override"] == "Food & Drink"
        assert data["effective_category"] == "Food & Drink"
        assert data["is_manually_reviewed"] is True

    async def test_update_segment_override(self, client, seed_transactions):
        """Change a personal transaction to business segment."""
        tx_id = seed_transactions[0]
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"segment_override": "business"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment_override"] == "business"
        assert data["effective_segment"] == "business"
        assert data["is_manually_reviewed"] is True

    async def test_update_tax_category_override(self, client, seed_transactions):
        tx_id = seed_transactions[1]  # Electric Company
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"tax_category_override": "Schedule A - Home Office Utilities"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tax_category_override"] == "Schedule A - Home Office Utilities"
        assert data["effective_tax_category"] == "Schedule A - Home Office Utilities"

    async def test_mark_as_excluded(self, client, seed_transactions):
        tx_id = seed_transactions[2]  # Coffee Shop
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"is_excluded": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_excluded"] is True

    async def test_update_notes(self, client, seed_transactions):
        tx_id = seed_transactions[3]  # Paycheck
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"notes": "January bi-weekly paycheck from employer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "January bi-weekly paycheck from employer"

    async def test_update_nonexistent_transaction(self, client):
        """PATCH on a nonexistent ID should return 404."""
        resp = await client.patch(
            "/transactions/99999",
            json={"notes": "This should fail"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_partial_update_preserves_other_fields(self, client, seed_transactions):
        """Update only notes — verify category, amount, description are unchanged."""
        tx_id = seed_transactions[0]

        # Get original state
        original = (await client.get(f"/transactions/{tx_id}")).json()

        # Update only notes
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"notes": "Added a note"},
        )
        assert resp.status_code == 200
        updated = resp.json()

        # Core fields should be unchanged
        assert updated["description"] == original["description"]
        assert updated["amount"] == original["amount"]
        assert updated["account_id"] == original["account_id"]
        assert updated["effective_category"] == original["effective_category"]
        assert updated["segment"] == original["segment"]
        assert updated["notes"] == "Added a note"

    async def test_update_persists_on_reread(self, client, seed_transactions):
        """PATCH, then GET to verify the update actually persisted."""
        tx_id = seed_transactions[1]

        await client.patch(
            f"/transactions/{tx_id}",
            json={"category_override": "Bills & Payments"},
        )

        # Re-fetch to confirm persistence
        resp = await client.get(f"/transactions/{tx_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["effective_category"] == "Bills & Payments"
        assert data["is_manually_reviewed"] is True

    async def test_multiple_overrides_at_once(self, client, seed_transactions):
        """Send category, segment, and notes in a single PATCH."""
        tx_id = seed_transactions[2]
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={
                "category_override": "Business Meals",
                "segment_override": "business",
                "notes": "Client lunch meeting",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["effective_category"] == "Business Meals"
        assert data["effective_segment"] == "business"
        assert data["notes"] == "Client lunch meeting"
        assert data["is_manually_reviewed"] is True

    async def test_exclude_then_unexclude(self, client, seed_transactions):
        """Exclude a transaction, then un-exclude it."""
        tx_id = seed_transactions[4]

        # Exclude
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"is_excluded": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_excluded"] is True

        # Un-exclude
        resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"is_excluded": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_excluded"] is False

    async def test_empty_patch_body(self, client, seed_transactions):
        """Sending an empty JSON body should be a no-op (200, no changes)."""
        tx_id = seed_transactions[0]
        original = (await client.get(f"/transactions/{tx_id}")).json()

        resp = await client.patch(f"/transactions/{tx_id}", json={})
        assert resp.status_code == 200
        updated = resp.json()

        assert updated["description"] == original["description"]
        assert updated["amount"] == original["amount"]
        assert updated["effective_category"] == original["effective_category"]


# ---------------------------------------------------------------------------
# GET /transactions — List and filter
# ---------------------------------------------------------------------------


class TestListTransactions:
    """Tests for GET /transactions with various filters."""

    async def test_list_all(self, client, seed_transactions):
        resp = await client.get("/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    async def test_filter_by_year(self, client, seed_transactions):
        resp = await client.get("/transactions", params={"year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5  # All transactions are 2025

    async def test_filter_by_year_and_month(self, client, seed_transactions):
        resp = await client.get("/transactions", params={"year": 2025, "month": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # Jan 2025 has 2 transactions

    async def test_filter_by_account_id(self, client, seed_transactions, seed_account):
        resp = await client.get(
            "/transactions", params={"account_id": seed_account}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    async def test_filter_by_category(self, client, seed_transactions):
        resp = await client.get(
            "/transactions", params={"category": "Groceries"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["effective_category"] == "Groceries"

    async def test_filter_by_segment(self, client, seed_transactions):
        resp = await client.get(
            "/transactions", params={"segment": "personal"}
        )
        assert resp.status_code == 200
        # All seed transactions are personal
        assert resp.json()["total"] == 5

    async def test_filter_excluded(self, client, seed_transactions):
        """By default is_excluded=False, so excluded transactions are hidden."""
        tx_id = seed_transactions[4]

        # Exclude one transaction
        await client.patch(f"/transactions/{tx_id}", json={"is_excluded": True})

        # Default listing should show 4
        resp = await client.get("/transactions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

        # Explicitly listing excluded shows 1
        resp = await client.get("/transactions", params={"is_excluded": True})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_search_by_description(self, client, seed_transactions):
        resp = await client.get(
            "/transactions", params={"search": "Coffee"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "Coffee" in data["items"][0]["description"]

    async def test_search_by_category(self, client, seed_transactions):
        resp = await client.get(
            "/transactions", params={"search": "Utilities"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_pagination_limit_offset(self, client, seed_transactions):
        # Get first 2
        resp = await client.get("/transactions", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5  # Total count unaffected by pagination

        # Get next 2
        resp2 = await client.get("/transactions", params={"limit": 2, "offset": 2})
        data2 = resp2.json()
        assert len(data2["items"]) == 2

        # Verify no overlap
        ids_page1 = {item["id"] for item in data["items"]}
        ids_page2 = {item["id"] for item in data2["items"]}
        assert ids_page1.isdisjoint(ids_page2)

    async def test_filter_nonexistent_account(self, client, seed_transactions):
        """Filtering by a non-existent account should return zero results."""
        resp = await client.get(
            "/transactions", params={"account_id": 99999}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_empty_database(self, client):
        """No seed data — listing should return empty."""
        resp = await client.get("/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# ---------------------------------------------------------------------------
# GET /transactions/{id} — Single transaction
# ---------------------------------------------------------------------------


class TestGetSingleTransaction:
    """Tests for GET /transactions/{id}."""

    async def test_get_existing(self, client, seed_transactions):
        tx_id = seed_transactions[0]
        resp = await client.get(f"/transactions/{tx_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tx_id
        assert data["description"] == "Grocery Store Purchase"
        assert data["amount"] == -85.50

    async def test_get_nonexistent(self, client):
        resp = await client.get("/transactions/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /transactions/audit — Categorization audit
# ---------------------------------------------------------------------------


class TestTransactionAudit:
    """Tests for GET /transactions/audit."""

    async def test_audit_with_categorized_transactions(self, client, seed_transactions):
        resp = await client.get("/transactions/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_transactions"] == 5
        # 4 are categorized (Groceries, Utilities, Dining, Income), 1 uncategorized
        assert data["categorized"] == 4
        assert data["uncategorized"] == 1
        assert data["categorization_rate"] == 80.0
        assert data["quality"] == "needs_attention"
        assert len(data["top_categories"]) > 0
        assert len(data["uncategorized_sample"]) == 1

    async def test_audit_filter_by_year(self, client, seed_transactions):
        resp = await client.get("/transactions/audit", params={"year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_transactions"] == 5

    async def test_audit_empty_database(self, client):
        resp = await client.get("/transactions/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_transactions"] == 0
        assert data["categorization_rate"] == 0
        assert data["quality"] == "poor"


# ---------------------------------------------------------------------------
# Integration: Create then update flow
# ---------------------------------------------------------------------------


class TestCreateThenUpdateFlow:
    """End-to-end flows combining POST and PATCH operations."""

    async def test_create_then_recategorize(self, client, seed_account):
        """Create a transaction, then update its category via PATCH."""
        create_resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-05-15T00:00:00",
                "description": "Amazon Purchase",
                "amount": -199.99,
                "category": "Shopping",
            },
        )
        assert create_resp.status_code == 201
        tx_id = create_resp.json()["id"]

        # Re-categorize
        patch_resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"category_override": "Electronics"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["effective_category"] == "Electronics"

        # Verify via GET
        get_resp = await client.get(f"/transactions/{tx_id}")
        assert get_resp.json()["effective_category"] == "Electronics"
        assert get_resp.json()["category"] == "Shopping"  # Original preserved

    async def test_create_then_exclude(self, client, seed_account):
        """Create a transaction, then exclude it."""
        create_resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-05-20T00:00:00",
                "description": "Duplicate charge",
                "amount": -50.00,
            },
        )
        assert create_resp.status_code == 201
        tx_id = create_resp.json()["id"]

        # Exclude
        patch_resp = await client.patch(
            f"/transactions/{tx_id}",
            json={"is_excluded": True},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["is_excluded"] is True

        # Should not appear in default listing
        list_resp = await client.get("/transactions")
        ids_in_list = [t["id"] for t in list_resp.json()["items"]]
        assert tx_id not in ids_in_list

    async def test_create_then_move_to_business(self, client, seed_account):
        """Create a personal transaction, then reclassify to business."""
        create_resp = await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-06-01T00:00:00",
                "description": "Uber ride to client meeting",
                "amount": -35.00,
                "segment": "personal",
            },
        )
        assert create_resp.status_code == 201
        tx_id = create_resp.json()["id"]
        assert create_resp.json()["effective_segment"] == "personal"

        # Move to business
        patch_resp = await client.patch(
            f"/transactions/{tx_id}",
            json={
                "segment_override": "business",
                "category_override": "Transportation",
                "tax_category_override": "Schedule C Line 24a - Travel",
            },
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["effective_segment"] == "business"
        assert data["effective_category"] == "Transportation"
        assert data["effective_tax_category"] == "Schedule C Line 24a - Travel"

    async def test_create_multiple_then_filter(self, client, seed_account):
        """Create transactions in different segments and filter by segment."""
        await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-10-01T00:00:00",
                "description": "Personal gym membership",
                "amount": -99.00,
                "segment": "personal",
                "category": "Health & Fitness",
            },
        )
        await client.post(
            "/transactions",
            json={
                "account_id": seed_account,
                "date": "2025-10-02T00:00:00",
                "description": "Business SaaS subscription",
                "amount": -49.00,
                "segment": "business",
                "category": "Software",
            },
        )

        # Filter personal
        personal_resp = await client.get(
            "/transactions", params={"segment": "personal"}
        )
        assert personal_resp.status_code == 200
        personal_descs = [t["description"] for t in personal_resp.json()["items"]]
        assert "Personal gym membership" in personal_descs
        assert "Business SaaS subscription" not in personal_descs

        # Filter business
        biz_resp = await client.get(
            "/transactions", params={"segment": "business"}
        )
        assert biz_resp.status_code == 200
        biz_descs = [t["description"] for t in biz_resp.json()["items"]]
        assert "Business SaaS subscription" in biz_descs


# ---------------------------------------------------------------------------
# Account creation via API (for coverage)
# ---------------------------------------------------------------------------


class TestAccountCreation:
    """Verify the accounts API that transactions depend on."""

    async def test_create_account_then_transaction(self, client):
        """Create account via API, then attach a manual transaction to it."""
        acct_resp = await client.post(
            "/accounts",
            json={
                "name": "API-Created Checking",
                "account_type": "depository",
                "institution": "Wells Fargo",
            },
        )
        assert acct_resp.status_code == 201
        acct_id = acct_resp.json()["id"]

        tx_resp = await client.post(
            "/transactions",
            json={
                "account_id": acct_id,
                "date": "2025-11-01T00:00:00",
                "description": "Wire transfer",
                "amount": 10000.00,
            },
        )
        assert tx_resp.status_code == 201
        assert tx_resp.json()["account_id"] == acct_id


# ---------------------------------------------------------------------------
# POST /import/categorize — Trigger categorization
# ---------------------------------------------------------------------------


class TestImportCategorize:
    """Tests for POST /import/categorize endpoint (without file uploads)."""

    async def test_categorize_no_transactions(self, client):
        """Categorize on an empty database should succeed with zero counts."""
        resp = await client.post("/import/categorize")
        assert resp.status_code == 200
        data = resp.json()
        assert "entity_rules_applied" in data
        assert "category_rules_applied" in data

    async def test_categorize_with_seeded_data(self, client, seed_transactions):
        """Run categorization on seeded transactions. Should not crash."""
        resp = await client.post("/import/categorize")
        assert resp.status_code == 200
        data = resp.json()
        # Entity rules and category rules should at least return counts
        assert isinstance(data["entity_rules_applied"], int)
        assert isinstance(data["category_rules_applied"], int)

    async def test_categorize_with_year_filter(self, client, seed_transactions):
        resp = await client.post("/import/categorize", params={"year": 2025})
        assert resp.status_code == 200
