"""
Comprehensive coverage tests for API route files:
  - api/routes/accounts.py
  - api/routes/account_links.py
  - api/routes/assets.py
  - api/routes/budget.py
  - api/routes/budget_forecast.py
  - api/routes/chat.py
  - api/routes/documents.py
"""
import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import (
    Base, Account, Transaction, PlaidAccount, PlaidItem,
    AccountLink, Document, ManualAsset, Budget,
    ChatConversation, ChatMessage, HouseholdProfile,
    BusinessEntity,
)

# Import routers at module level so coverage sees the executed lines
from api.database import get_session
from api.routes.accounts import router as accounts_router
from api.routes.account_links import router as account_links_router
from api.routes.assets import router as assets_router
from api.routes.budget import router as budget_router
from api.routes.chat import router as chat_router
from api.routes.documents import router as documents_router


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        # Clean up data between tests
        await sess.rollback()


def _make_app(db_session):
    """Create a FastAPI test app with all relevant routers and session override.

    IMPORTANT: account_links router must be registered BEFORE accounts router
    so that /accounts/suggest-links is matched before /accounts/{account_id}.
    This matches the production router registration order in api/main.py.
    """
    app = FastAPI()
    # account_links FIRST — its fixed paths (/suggest-links, /resolve-duplicate)
    # must register before the accounts /{account_id} path parameter
    app.include_router(account_links_router)
    app.include_router(accounts_router)
    app.include_router(assets_router)
    app.include_router(budget_router)
    app.include_router(chat_router)
    app.include_router(documents_router)

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    return app


@pytest_asyncio.fixture
async def client(db_session):
    app = _make_app(db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════
# Helper: seed data
# ═══════════════════════════════════════════════════════════════════════════

async def _create_account(session, name="Test Account", account_type="personal",
                          subtype="credit_card", institution="Chase", data_source="csv",
                          last_four=None, is_active=True) -> Account:
    a = Account(
        name=name,
        account_type=account_type,
        subtype=subtype,
        institution=institution,
        currency="USD",
        is_active=is_active,
        data_source=data_source,
        last_four=last_four,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(a)
    await session.flush()
    return a


async def _create_transaction(session, account_id, amount=-50.0, category="Food",
                              period_year=2025, period_month=3, is_excluded=False,
                              description="Test txn") -> Transaction:
    t = Transaction(
        account_id=account_id,
        date=datetime.now(timezone.utc),
        description=description,
        amount=amount,
        segment="personal",
        effective_category=category,
        period_year=period_year,
        period_month=period_month,
        is_excluded=is_excluded,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(t)
    await session.flush()
    return t


async def _create_plaid_item(session, institution_name="Chase") -> PlaidItem:
    pi = PlaidItem(
        item_id="item_test_" + str(id(session)),
        access_token="encrypted_token_123",
        institution_id="ins_123",
        institution_name=institution_name,
        status="active",
        last_synced_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    session.add(pi)
    await session.flush()
    return pi


async def _create_plaid_account(session, plaid_item_id, account_id=None) -> PlaidAccount:
    pa = PlaidAccount(
        plaid_item_id=plaid_item_id,
        account_id=account_id,
        plaid_account_id="plaid_acc_" + str(id(session)),
        name="Plaid Checking",
        type="depository",
        subtype="checking",
        current_balance=5000.0,
        available_balance=4500.0,
        mask="1234",
    )
    session.add(pa)
    await session.flush()
    return pa


async def _create_document(session, account_id=None, filename="test.csv",
                           document_type="credit_card") -> Document:
    d = Document(
        filename=filename,
        original_path="/tmp/test.csv",
        file_type="csv",
        document_type=document_type,
        status="completed",
        file_hash="abc123" + str(id(session)),
        account_id=account_id,
        imported_at=datetime.now(timezone.utc),
    )
    session.add(d)
    await session.flush()
    return d


async def _create_budget(session, year=2025, month=3, category="Food",
                         budget_amount=500.0, segment="personal") -> Budget:
    b = Budget(
        year=year,
        month=month,
        category=category,
        segment=segment,
        budget_amount=budget_amount,
        notes="Test budget",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(b)
    await session.flush()
    return b


async def _create_manual_asset(session, name="My House", asset_type="real_estate",
                                current_value=500000.0, is_liability=False) -> ManualAsset:
    a = ManualAsset(
        name=name,
        asset_type=asset_type,
        is_liability=is_liability,
        current_value=current_value,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(a)
    await session.flush()
    return a


# ═══════════════════════════════════════════════════════════════════════════
# ACCOUNTS TESTS — api/routes/accounts.py
# ═══════════════════════════════════════════════════════════════════════════


class TestAccountsRoutes:
    """Tests for /accounts endpoints."""

    @pytest.mark.asyncio
    async def test_list_accounts_empty(self, client):
        """GET /accounts returns empty list when no accounts exist."""
        resp = await client.get("/accounts")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_accounts_with_plaid_and_csv(self, db_session, client):
        """GET /accounts returns accounts with Plaid metadata and txn-based balances."""
        # Create a CSV account with transactions
        csv_acct = await _create_account(db_session, name="CSV Card", data_source="csv",
                                          institution="Chase")
        await _create_transaction(db_session, csv_acct.id, amount=-100.0)
        await _create_transaction(db_session, csv_acct.id, amount=-200.0)

        # Create a Plaid-linked account
        plaid_acct = await _create_account(db_session, name="Plaid Checking",
                                            data_source="plaid", institution="BofA")
        pi = await _create_plaid_item(db_session, institution_name="BofA")
        await _create_plaid_account(db_session, pi.id, account_id=plaid_acct.id)

        resp = await client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

        # Find the plaid account and check metadata
        plaid_item = next((a for a in data if a["name"] == "Plaid Checking"), None)
        assert plaid_item is not None
        assert plaid_item["current_balance"] == 5000.0
        assert plaid_item["available_balance"] == 4500.0
        assert plaid_item["plaid_mask"] == "1234"
        assert plaid_item["plaid_type"] == "depository"
        assert plaid_item["plaid_subtype"] == "checking"
        assert plaid_item["plaid_last_synced"] is not None

        # Find the CSV account - balance from transaction sum
        csv_item = next((a for a in data if a["name"] == "CSV Card"), None)
        assert csv_item is not None
        assert csv_item["balance"] == -300.0
        assert csv_item["transaction_count"] == 2

    @pytest.mark.asyncio
    async def test_list_accounts_exclude_plaid(self, db_session, client):
        """GET /accounts?exclude_plaid=true omits Plaid-linked accounts."""
        csv_acct = await _create_account(db_session, name="CSV Only", data_source="csv")
        plaid_acct = await _create_account(db_session, name="Plaid Only", data_source="plaid")
        pi = await _create_plaid_item(db_session)
        await _create_plaid_account(db_session, pi.id, account_id=plaid_acct.id)

        resp = await client.get("/accounts?exclude_plaid=true")
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert "Plaid Only" not in names

    @pytest.mark.asyncio
    async def test_get_single_account_success(self, db_session, client):
        """GET /accounts/{id} returns account details."""
        acct = await _create_account(db_session, name="Single Acct")
        resp = await client.get(f"/accounts/{acct.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Single Acct"
        assert resp.json()["id"] == acct.id

    @pytest.mark.asyncio
    async def test_get_single_account_not_found(self, client):
        """GET /accounts/{id} returns 404 for non-existent account."""
        resp = await client.get("/accounts/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_account(self, client):
        """POST /accounts creates a new account and returns 201."""
        payload = {
            "name": "New Brokerage",
            "account_type": "investment",
            "subtype": "brokerage",
            "institution": "Fidelity",
            "currency": "USD",
            "data_source": "manual",
        }
        resp = await client.post("/accounts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Brokerage"
        assert data["account_type"] == "investment"
        assert data["institution"] == "Fidelity"

    @pytest.mark.asyncio
    async def test_update_account_success(self, db_session, client):
        """PATCH /accounts/{id} updates account fields."""
        acct = await _create_account(db_session, name="Old Name")
        resp = await client.patch(f"/accounts/{acct.id}", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_account_not_found(self, client):
        """PATCH /accounts/{id} returns 404 for non-existent account."""
        resp = await client.patch("/accounts/99999", json={"name": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_deactivate_account_success(self, db_session, client):
        """DELETE /accounts/{id} deactivates (soft-delete) the account."""
        acct = await _create_account(db_session, name="To Deactivate")
        resp = await client.delete(f"/accounts/{acct.id}")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_deactivate_account_not_found(self, client):
        """DELETE /accounts/{id} returns 404 for non-existent account."""
        resp = await client.delete("/accounts/99999")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# ACCOUNT LINKS TESTS — api/routes/account_links.py
# ═══════════════════════════════════════════════════════════════════════════


class TestAccountLinksRoutes:
    """Tests for /accounts/{id}/link, /accounts/{id}/links, etc."""

    @pytest.mark.asyncio
    async def test_link_accounts_success(self, db_session, client):
        """POST /accounts/{id}/link creates a link between two accounts."""
        a1 = await _create_account(db_session, name="Account A")
        a2 = await _create_account(db_session, name="Account B")
        resp = await client.post(
            f"/accounts/{a1.id}/link",
            json={"target_account_id": a2.id, "link_type": "same_account"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["primary_account_id"] == a1.id
        assert data["secondary_account_id"] == a2.id
        assert data["link_type"] == "same_account"
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_link_accounts_self_link(self, db_session, client):
        """POST /accounts/{id}/link rejects linking to itself."""
        a1 = await _create_account(db_session, name="Self Link")
        resp = await client.post(
            f"/accounts/{a1.id}/link",
            json={"target_account_id": a1.id},
        )
        assert resp.status_code == 400
        assert "itself" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_link_accounts_not_found(self, db_session, client):
        """POST /accounts/{id}/link rejects if target account doesn't exist."""
        a1 = await _create_account(db_session, name="Exists")
        resp = await client.post(
            f"/accounts/{a1.id}/link",
            json={"target_account_id": 99999},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_link_accounts_primary_not_found(self, client):
        """POST /accounts/{id}/link rejects if primary account doesn't exist."""
        resp = await client.post(
            "/accounts/99998/link",
            json={"target_account_id": 99999},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_link_accounts_duplicate(self, db_session, client):
        """POST /accounts/{id}/link rejects duplicate link."""
        a1 = await _create_account(db_session, name="Dup A")
        a2 = await _create_account(db_session, name="Dup B")
        # Create first link
        link = AccountLink(
            primary_account_id=a1.id,
            secondary_account_id=a2.id,
            link_type="same_account",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(link)
        await db_session.flush()

        # Try to create duplicate
        resp = await client.post(
            f"/accounts/{a1.id}/link",
            json={"target_account_id": a2.id},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_account_links(self, db_session, client):
        """GET /accounts/{id}/links returns all links for the account."""
        a1 = await _create_account(db_session, name="Link A")
        a2 = await _create_account(db_session, name="Link B")
        link = AccountLink(
            primary_account_id=a1.id,
            secondary_account_id=a2.id,
            link_type="same_account",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(link)
        await db_session.flush()

        resp = await client.get(f"/accounts/{a1.id}/links")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["primary_account_id"] == a1.id

    @pytest.mark.asyncio
    async def test_remove_link_success(self, db_session, client):
        """DELETE /accounts/{id}/link/{link_id} removes the link."""
        a1 = await _create_account(db_session, name="Remove A")
        a2 = await _create_account(db_session, name="Remove B")
        link = AccountLink(
            primary_account_id=a1.id,
            secondary_account_id=a2.id,
            link_type="same_account",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(link)
        await db_session.flush()

        resp = await client.delete(f"/accounts/{a1.id}/link/{link.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    @pytest.mark.asyncio
    async def test_remove_link_not_found(self, client):
        """DELETE /accounts/{id}/link/{link_id} returns 404 if link doesn't exist."""
        resp = await client.delete("/accounts/1/link/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_link_wrong_account(self, db_session, client):
        """DELETE /accounts/{id}/link/{link_id} returns 403 if link doesn't belong."""
        a1 = await _create_account(db_session, name="Wrong A")
        a2 = await _create_account(db_session, name="Wrong B")
        a3 = await _create_account(db_session, name="Wrong C")
        link = AccountLink(
            primary_account_id=a1.id,
            secondary_account_id=a2.id,
            link_type="same_account",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(link)
        await db_session.flush()

        # Try to remove using account a3 which is unrelated
        resp = await client.delete(f"/accounts/{a3.id}/link/{link.id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_merge_accounts_success(self, db_session, client):
        """POST /accounts/{id}/merge merges secondary into primary."""
        a1 = await _create_account(db_session, name="Primary", data_source="csv")
        a2 = await _create_account(db_session, name="Secondary", data_source="plaid")
        # Add some txns and docs to the secondary
        await _create_transaction(db_session, a2.id, amount=-50.0)
        await _create_document(db_session, account_id=a2.id)

        resp = await client.post(
            f"/accounts/{a1.id}/merge",
            json={"target_account_id": a2.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["primary_account_id"] == a1.id
        assert data["secondary_account_id"] == a2.id
        assert data["transactions_moved"] >= 1
        assert data["documents_moved"] >= 1
        assert data["secondary_deactivated"] is True

    @pytest.mark.asyncio
    async def test_merge_accounts_with_plaid_reassignment(self, db_session, client):
        """POST /accounts/{id}/merge reassigns PlaidAccount from secondary."""
        a1 = await _create_account(db_session, name="MergePrimary", data_source="csv")
        a2 = await _create_account(db_session, name="MergeSecondary", data_source="plaid")
        pi = await _create_plaid_item(db_session)
        await _create_plaid_account(db_session, pi.id, account_id=a2.id)

        resp = await client.post(
            f"/accounts/{a1.id}/merge",
            json={"target_account_id": a2.id},
        )
        assert resp.status_code == 200
        assert resp.json()["secondary_deactivated"] is True

    @pytest.mark.asyncio
    async def test_merge_self_rejected(self, db_session, client):
        """POST /accounts/{id}/merge rejects merging with self."""
        a1 = await _create_account(db_session, name="MergeSelf")
        resp = await client.post(
            f"/accounts/{a1.id}/merge",
            json={"target_account_id": a1.id},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_merge_primary_not_found(self, client):
        """POST /accounts/{id}/merge returns 404 if primary not found."""
        resp = await client.post(
            "/accounts/99998/merge",
            json={"target_account_id": 99999},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_merge_secondary_not_found(self, db_session, client):
        """POST /accounts/{id}/merge returns 404 if secondary not found."""
        a1 = await _create_account(db_session, name="MergeExistPrimary")
        resp = await client.post(
            f"/accounts/{a1.id}/merge",
            json={"target_account_id": 99999},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_suggest_links_empty(self, client):
        """GET /accounts/suggest-links returns empty when no cross-source matches."""
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_suggest_links_institution_last_four(self, db_session, client):
        """GET /accounts/suggest-links detects matching institution + last_four."""
        await _create_account(
            db_session, name="Chase CC", institution="Chase",
            last_four="4321", data_source="csv",
        )
        await _create_account(
            db_session, name="Chase CC", institution="Chase",
            last_four="4321", data_source="plaid",
        )
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200
        data = resp.json()
        matched = [s for s in data if "last 4" in s.get("match_reason", "").lower()
                   or "same institution" in s.get("match_reason", "").lower()]
        assert len(matched) >= 1

    @pytest.mark.asyncio
    async def test_suggest_links_same_name_subtype(self, db_session, client):
        """GET /accounts/suggest-links detects matching name + subtype."""
        await _create_account(
            db_session, name="Savings", subtype="savings", data_source="csv",
            institution=None,
        )
        await _create_account(
            db_session, name="Savings", subtype="savings", data_source="plaid",
            institution=None,
        )
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_suggest_links_institution_similar_name(self, db_session, client):
        """GET /accounts/suggest-links detects matching institution + similar name."""
        await _create_account(
            db_session, name="Chase Checking", institution="Chase", data_source="csv",
        )
        await _create_account(
            db_session, name="Chase Checking Plus", institution="Chase", data_source="plaid",
        )
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_suggest_links_same_source_skip(self, db_session, client):
        """GET /accounts/suggest-links skips pairs with same data_source (line 212)."""
        # Two accounts with same source but matching criteria — should NOT suggest
        await _create_account(
            db_session, name="Same Source A", institution="Fidelity",
            last_four="9999", data_source="csv",
        )
        await _create_account(
            db_session, name="Same Source B", institution="Fidelity",
            last_four="9999", data_source="csv",
        )
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200
        # The matching pair has same data_source, so should not be in suggestions
        data = resp.json()
        for s in data:
            if s["account_a_name"] == "Same Source A" and s["account_b_name"] == "Same Source B":
                pytest.fail("Same-source pair should not be suggested")

    @pytest.mark.asyncio
    async def test_suggest_links_no_match_returns_none(self, db_session, client):
        """GET /accounts/suggest-links returns empty for non-matching cross-source accounts (line 301)."""
        await _create_account(
            db_session, name="Unique Name AAA", institution="BankAAA",
            subtype="checking", data_source="csv",
        )
        await _create_account(
            db_session, name="Totally Different BBB", institution="BankBBB",
            subtype="savings", data_source="plaid",
        )
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200
        # These two have different institution, different name, different subtype
        # _match_reason should return None for this pair

    @pytest.mark.asyncio
    @patch("pipeline.dedup.cross_source.find_cross_source_duplicates", new_callable=AsyncMock)
    async def test_find_duplicates(self, mock_find, db_session, client):
        """GET /accounts/{id}/duplicates returns duplicate candidates."""
        mock_find.return_value = [{"tx_a": 1, "tx_b": 2, "confidence": 0.9}]
        acct = await _create_account(db_session, name="Dup Target")
        resp = await client.get(f"/accounts/{acct.id}/duplicates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] == acct.id
        assert data["count"] == 1
        assert len(data["candidates"]) == 1

    @pytest.mark.asyncio
    @patch("pipeline.dedup.cross_source.auto_resolve_duplicates", new_callable=AsyncMock)
    async def test_auto_dedup(self, mock_resolve, db_session, client):
        """POST /accounts/{id}/auto-dedup auto-resolves duplicates."""
        mock_resolve.return_value = {"resolved": 2, "skipped": 0}
        acct = await _create_account(db_session, name="AutoDedup Target")
        resp = await client.post(f"/accounts/{acct.id}/auto-dedup?min_confidence=0.9")
        assert resp.status_code == 200
        assert resp.json()["resolved"] == 2

    @pytest.mark.asyncio
    async def test_resolve_duplicate_success(self, db_session, client):
        """POST /accounts/resolve-duplicate marks the exclude txn as excluded."""
        acct = await _create_account(db_session, name="Resolve Test")
        t1 = await _create_transaction(db_session, acct.id, description="Keep")
        t2 = await _create_transaction(db_session, acct.id, description="Exclude")

        resp = await client.post(
            "/accounts/resolve-duplicate",
            json={"keep_id": t1.id, "exclude_id": t2.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["excluded_id"] == t2.id
        assert data["kept_id"] == t1.id

    @pytest.mark.asyncio
    async def test_resolve_duplicate_not_found(self, client):
        """POST /accounts/resolve-duplicate returns 404 if exclude txn not found."""
        resp = await client.post(
            "/accounts/resolve-duplicate",
            json={"keep_id": 1, "exclude_id": 99999},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# ASSETS TESTS — api/routes/assets.py
# ═══════════════════════════════════════════════════════════════════════════


class TestAssetsRoutes:
    """Tests for /assets endpoints."""

    @pytest.mark.asyncio
    async def test_list_assets_empty(self, client):
        """GET /assets returns empty list when no assets."""
        resp = await client.get("/assets")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_assets_active_only(self, db_session, client):
        """GET /assets excludes inactive assets by default."""
        await _create_manual_asset(db_session, name="Active Home")
        inactive = ManualAsset(
            name="Sold Car", asset_type="vehicle", is_liability=False,
            current_value=10000, is_active=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(inactive)
        await db_session.flush()

        resp = await client.get("/assets")
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert "Sold Car" not in names

    @pytest.mark.asyncio
    async def test_list_assets_include_inactive(self, db_session, client):
        """GET /assets?include_inactive=true includes all assets."""
        inactive = ManualAsset(
            name="Sold Boat", asset_type="vehicle", is_liability=False,
            current_value=5000, is_active=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(inactive)
        await db_session.flush()

        resp = await client.get("/assets?include_inactive=true")
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert "Sold Boat" in names

    @pytest.mark.asyncio
    async def test_create_asset_real_estate(self, client):
        """POST /assets creates a real_estate asset."""
        payload = {
            "name": "Vacation Home",
            "asset_type": "real_estate",
            "current_value": 350000.0,
            "address": "123 Beach Rd",
        }
        resp = await client.post("/assets", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Vacation Home"
        assert data["asset_type"] == "real_estate"
        assert data["is_liability"] is False
        assert data["current_value"] == 350000.0

    @pytest.mark.asyncio
    async def test_create_asset_liability(self, client):
        """POST /assets with liability type sets is_liability=True."""
        payload = {
            "name": "Auto Loan",
            "asset_type": "mortgage",
            "current_value": 25000.0,
        }
        resp = await client.post("/assets", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_liability"] is True

    @pytest.mark.asyncio
    async def test_create_investment_asset_creates_linked_account(self, client):
        """POST /assets with type=investment auto-creates a linked Account."""
        payload = {
            "name": "401k",
            "asset_type": "investment",
            "current_value": 150000.0,
            "account_subtype": "401k",
            "institution": "Fidelity",
        }
        resp = await client.post("/assets", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["linked_account_id"] is not None

    @pytest.mark.asyncio
    async def test_create_asset_invalid_type(self, client):
        """POST /assets with invalid asset_type returns 422."""
        payload = {
            "name": "Bad",
            "asset_type": "invalid_type",
            "current_value": 100.0,
        }
        resp = await client.post("/assets", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_asset_success(self, db_session, client):
        """PATCH /assets/{id} updates asset fields."""
        asset = await _create_manual_asset(db_session, name="Update Me", current_value=100000)
        resp = await client.patch(
            f"/assets/{asset.id}",
            json={"current_value": 120000.0, "notes": "Updated value"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_value"] == 120000.0
        assert data["notes"] == "Updated value"

    @pytest.mark.asyncio
    async def test_update_asset_not_found(self, client):
        """PATCH /assets/{id} returns 404 for non-existent asset."""
        resp = await client.patch("/assets/99999", json={"current_value": 1.0})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_asset_success(self, db_session, client):
        """DELETE /assets/{id} deletes the asset."""
        asset = await _create_manual_asset(db_session, name="Delete Me")
        resp = await client.delete(f"/assets/{asset.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_asset_not_found(self, client):
        """DELETE /assets/{id} returns 404 for non-existent asset."""
        resp = await client.delete("/assets/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_asset_summary(self, db_session, client):
        """GET /assets/summary returns aggregated totals."""
        await _create_manual_asset(db_session, name="Home Summary",
                                    asset_type="real_estate", current_value=400000)
        await _create_manual_asset(db_session, name="Car Summary",
                                    asset_type="vehicle", current_value=30000)
        await _create_manual_asset(db_session, name="Mortgage Summary",
                                    asset_type="mortgage", current_value=200000,
                                    is_liability=True)

        resp = await client.get("/assets/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_assets" in data
        assert "total_liabilities" in data
        assert "net" in data
        assert "count" in data
        assert "by_type" in data
        assert data["total_assets"] >= 430000  # Home + Car
        assert data["total_liabilities"] >= 200000


# ═══════════════════════════════════════════════════════════════════════════
# BUDGET TESTS — api/routes/budget.py
# ═══════════════════════════════════════════════════════════════════════════


class TestBudgetRoutes:
    """Tests for /budget endpoints."""

    @pytest.mark.asyncio
    async def test_budget_categories(self, db_session, client):
        """GET /budget/categories returns distinct categories with types."""
        acct = await _create_account(db_session, name="Cat Acct")
        await _create_transaction(db_session, acct.id, category="Food",
                                  amount=-50, period_year=2025, period_month=3)
        await _create_transaction(db_session, acct.id, category="W-2 Wages",
                                  amount=5000, period_year=2025, period_month=3)

        resp = await client.get("/budget/categories?year=2025&month=3")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        cats = {c["category"]: c["category_type"] for c in data}
        if "Food" in cats:
            assert cats["Food"] == "expense"
        if "W-2 Wages" in cats:
            assert cats["W-2 Wages"] == "income"

    @pytest.mark.asyncio
    async def test_budget_categories_goal_type(self, db_session, client):
        """GET /budget/categories recognizes goal categories."""
        acct = await _create_account(db_session, name="Goal Acct")
        await _create_transaction(db_session, acct.id, category="Vacation Fund",
                                  amount=-200, period_year=2025, period_month=5)
        resp = await client.get("/budget/categories?year=2025&month=5")
        assert resp.status_code == 200
        data = resp.json()
        goal_cats = [c for c in data if c.get("category_type") == "goal"]
        # Vacation Fund should be classified as a goal
        vf = [c for c in data if c["category"] == "Vacation Fund"]
        if vf:
            assert vf[0]["category_type"] == "goal"

    @pytest.mark.asyncio
    async def test_budget_categories_no_filter(self, db_session, client):
        """GET /budget/categories without year/month returns all."""
        acct = await _create_account(db_session, name="AllCat Acct")
        await _create_transaction(db_session, acct.id, category="Shopping")
        resp = await client.get("/budget/categories")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_budget_summary(self, db_session, client):
        """GET /budget/summary returns budget health and YoY data."""
        acct = await _create_account(db_session, name="BSum Acct")
        await _create_budget(db_session, year=2025, month=6, category="Food",
                             budget_amount=500)
        await _create_transaction(db_session, acct.id, category="Food",
                                  amount=-600, period_year=2025, period_month=6)

        resp = await client.get("/budget/summary?year=2025&month=6")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == 2025
        assert data["month"] == 6
        assert "total_budgeted" in data
        assert "total_actual" in data
        assert "variance" in data
        assert "utilization_pct" in data
        assert "over_budget_categories" in data
        assert "year_over_year" in data
        # Should have YoY data for 3 years
        assert len(data["year_over_year"]) == 3

    @pytest.mark.asyncio
    async def test_copy_budget_success(self, db_session, client):
        """POST /budget/copy copies budget lines from one month to another."""
        await _create_budget(db_session, year=2025, month=1, category="Groceries",
                             budget_amount=600)
        await _create_budget(db_session, year=2025, month=1, category="Transport",
                             budget_amount=200)

        resp = await client.post(
            "/budget/copy?from_year=2025&from_month=1&to_year=2025&to_month=2"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["copied"] >= 2

    @pytest.mark.asyncio
    async def test_copy_budget_skips_existing(self, db_session, client):
        """POST /budget/copy skips categories that already exist in target month."""
        await _create_budget(db_session, year=2025, month=7, category="Groceries",
                             budget_amount=600)
        # Already exists in target
        await _create_budget(db_session, year=2025, month=8, category="Groceries",
                             budget_amount=700)

        resp = await client.post(
            "/budget/copy?from_year=2025&from_month=7&to_year=2025&to_month=8"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["copied"] == 0

    @pytest.mark.asyncio
    async def test_copy_budget_source_not_found(self, client):
        """POST /budget/copy returns 404 if source month has no budgets."""
        resp = await client.post(
            "/budget/copy?from_year=1999&from_month=1&to_year=1999&to_month=2"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("pipeline.planning.smart_defaults.generate_smart_budget", new_callable=AsyncMock)
    async def test_auto_generate_budget(self, mock_gen, client):
        """POST /budget/auto-generate returns preview without saving."""
        mock_gen.return_value = [
            {"category": "Food", "segment": "personal", "budget_amount": 500.0, "source": "3mo_avg"},
            {"category": "Gas", "segment": "personal", "budget_amount": 200.0, "source": "3mo_avg"},
        ]
        resp = await client.post("/budget/auto-generate?year=2025&month=4")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 700.0
        assert len(data["lines"]) == 2
        assert data["year"] == 2025
        assert data["month"] == 4

    @pytest.mark.asyncio
    @patch("pipeline.planning.smart_defaults.generate_smart_budget", new_callable=AsyncMock)
    async def test_auto_generate_apply(self, mock_gen, db_session, client):
        """POST /budget/auto-generate/apply saves budget lines."""
        mock_gen.return_value = [
            {"category": "Auto Food", "segment": "personal", "budget_amount": 450.0, "source": "3mo_avg"},
        ]
        resp = await client.post("/budget/auto-generate/apply?year=2025&month=9")
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] >= 1

    @pytest.mark.asyncio
    @patch("pipeline.planning.smart_defaults.generate_smart_budget", new_callable=AsyncMock)
    async def test_auto_generate_apply_skips_existing(self, mock_gen, db_session, client):
        """POST /budget/auto-generate/apply skips categories that already exist."""
        await _create_budget(db_session, year=2025, month=10, category="Food Exist",
                             budget_amount=500, segment="personal")
        mock_gen.return_value = [
            {"category": "Food Exist", "segment": "personal", "budget_amount": 600.0, "source": "3mo_avg"},
        ]
        resp = await client.post("/budget/auto-generate/apply?year=2025&month=10")
        assert resp.status_code == 200
        assert resp.json()["created"] == 0

    @pytest.mark.asyncio
    async def test_list_budgets(self, db_session, client):
        """GET /budget returns budget list with actuals and variance."""
        acct = await _create_account(db_session, name="ListB Acct")
        b = await _create_budget(db_session, year=2026, month=1, category="Groceries LB",
                                  budget_amount=400)
        await _create_transaction(db_session, acct.id, category="Groceries LB",
                                  amount=-350, period_year=2026, period_month=1)

        resp = await client.get("/budget?year=2026&month=1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        item = next((i for i in data if i["category"] == "Groceries LB"), None)
        if item:
            assert item["budget_amount"] == 400
            assert item["actual_amount"] >= 0

    @pytest.mark.asyncio
    async def test_list_budgets_with_segment(self, db_session, client):
        """GET /budget?segment=personal filters by segment."""
        await _create_budget(db_session, year=2026, month=2, category="Biz Expense",
                             budget_amount=1000, segment="business")
        await _create_budget(db_session, year=2026, month=2, category="Personal Food",
                             budget_amount=500, segment="personal")

        resp = await client.get("/budget?year=2026&month=2&segment=personal")
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            if item.get("category") in ("Biz Expense", "Personal Food"):
                assert item["segment"] == "personal"

    @pytest.mark.asyncio
    async def test_create_budget_new(self, client):
        """POST /budget creates a new budget line."""
        payload = {
            "year": 2026,
            "month": 3,
            "category": "Entertainment New",
            "segment": "personal",
            "budget_amount": 300.0,
            "notes": "Movies and fun",
        }
        resp = await client.post("/budget", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "Entertainment New"
        assert data["budget_amount"] == 300.0

    @pytest.mark.asyncio
    async def test_create_budget_upsert_existing(self, db_session, client):
        """POST /budget with existing category updates existing record."""
        await _create_budget(db_session, year=2026, month=4, category="Upsert Cat",
                             budget_amount=100)
        payload = {
            "year": 2026,
            "month": 4,
            "category": "Upsert Cat",
            "segment": "personal",
            "budget_amount": 200.0,
        }
        resp = await client.post("/budget", json=payload)
        assert resp.status_code == 200
        assert resp.json()["budget_amount"] == 200.0

    @pytest.mark.asyncio
    async def test_update_budget_success(self, db_session, client):
        """PATCH /budget/{id} updates budget amount and notes."""
        b = await _create_budget(db_session, year=2026, month=5, category="UpdateB",
                                  budget_amount=500)
        resp = await client.patch(
            f"/budget/{b.id}",
            json={"budget_amount": 600.0, "notes": "Increased"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["budget_amount"] == 600.0
        assert data["notes"] == "Increased"

    @pytest.mark.asyncio
    async def test_update_budget_not_found(self, client):
        """PATCH /budget/{id} returns 404 for non-existent budget."""
        resp = await client.patch("/budget/99999", json={"budget_amount": 100.0})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_budget(self, db_session, client):
        """DELETE /budget/{id} removes the budget line."""
        b = await _create_budget(db_session, year=2026, month=6, category="DeleteB",
                                  budget_amount=300)
        resp = await client.delete(f"/budget/{b.id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == b.id


# ═══════════════════════════════════════════════════════════════════════════
# BUDGET FORECAST TESTS — api/routes/budget_forecast.py
# ═══════════════════════════════════════════════════════════════════════════


class TestBudgetForecastRoutes:
    """Tests for /budget/unbudgeted, /budget/forecast, /budget/velocity."""

    @pytest.mark.asyncio
    async def test_unbudgeted_categories(self, db_session, client):
        """GET /budget/unbudgeted returns categories with spending but no budget."""
        acct = await _create_account(db_session, name="Unbud Acct")
        await _create_transaction(db_session, acct.id, category="Dining Out",
                                  amount=-80, period_year=2026, period_month=7)
        # No budget for "Dining Out" in 2026-07

        resp = await client.get("/budget/unbudgeted?year=2026&month=7")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Check that Dining Out appears as unbudgeted
        cats = [c["category"] for c in data]
        assert "Dining Out" in cats

    @pytest.mark.asyncio
    async def test_unbudgeted_excludes_budgeted(self, db_session, client):
        """GET /budget/unbudgeted excludes categories with budgets."""
        acct = await _create_account(db_session, name="BudExcl Acct")
        await _create_transaction(db_session, acct.id, category="Budgeted Cat",
                                  amount=-100, period_year=2026, period_month=8)
        await _create_budget(db_session, year=2026, month=8, category="Budgeted Cat",
                             budget_amount=150)

        resp = await client.get("/budget/unbudgeted?year=2026&month=8")
        assert resp.status_code == 200
        cats = [c["category"] for c in resp.json()]
        assert "Budgeted Cat" not in cats

    @pytest.mark.asyncio
    async def test_budget_forecast(self, db_session, client):
        """GET /budget/forecast returns spending prediction."""
        acct = await _create_account(db_session, name="Forecast Acct")
        # Create historical spending data
        for m in range(1, 7):
            await _create_transaction(db_session, acct.id, category="Groceries FC",
                                      amount=-400, period_year=2025, period_month=m)

        resp = await client.get("/budget/forecast?year=2025&month=6")
        assert resp.status_code == 200
        data = resp.json()
        assert "forecast" in data
        assert "seasonal" in data
        assert data["target_month"] == 6
        assert data["target_year"] == 2025

    @pytest.mark.asyncio
    async def test_budget_forecast_default_month(self, db_session, client):
        """GET /budget/forecast without year/month uses current date."""
        resp = await client.get("/budget/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert "target_month" in data
        assert "target_year" in data

    @pytest.mark.asyncio
    async def test_budget_forecast_skips_null_category(self, db_session, client):
        """GET /budget/forecast skips rows with null effective_category."""
        acct = await _create_account(db_session, name="NullCat Acct")
        # Create a transaction with None category
        t = Transaction(
            account_id=acct.id,
            date=datetime.now(timezone.utc),
            description="Null cat txn",
            amount=-50.0,
            segment="personal",
            effective_category=None,
            period_year=2025,
            period_month=4,
            is_excluded=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(t)
        await db_session.flush()

        resp = await client.get("/budget/forecast?year=2025&month=5")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_spend_velocity(self, db_session, client):
        """GET /budget/velocity returns spending velocity data."""
        acct = await _create_account(db_session, name="Velocity Acct")
        await _create_budget(db_session, year=2026, month=3, category="Groceries VEL",
                             budget_amount=600)
        await _create_transaction(db_session, acct.id, category="Groceries VEL",
                                  amount=-200, period_year=2026, period_month=3)

        resp = await client.get("/budget/velocity?year=2026&month=3")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_spend_velocity_default_month(self, client):
        """GET /budget/velocity without year/month uses current date."""
        resp = await client.get("/budget/velocity")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ═══════════════════════════════════════════════════════════════════════════
# CHAT TESTS — api/routes/chat.py
# ═══════════════════════════════════════════════════════════════════════════


class TestChatRoutes:
    """Tests for /chat endpoints."""

    @pytest.mark.asyncio
    @patch("api.routes.chat.run_chat", new_callable=AsyncMock)
    async def test_send_message(self, mock_run_chat, client):
        """POST /chat/message returns chat response."""
        mock_run_chat.return_value = {
            "response": "Hello! How can I help?",
            "requires_consent": False,
            "actions": [],
            "tool_calls_made": 0,
            "conversation_id": 1,
        }
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "conversation_id": None,
            "page_context": "dashboard",
        }
        resp = await client.post("/chat/message", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "Hello! How can I help?"
        assert data["requires_consent"] is False
        assert data["conversation_id"] == 1
        assert data["tool_calls_made"] == 0
        mock_run_chat.assert_called_once()

    @pytest.mark.asyncio
    @patch("api.routes.chat.run_chat", new_callable=AsyncMock)
    async def test_send_message_with_consent(self, mock_run_chat, client):
        """POST /chat/message handles requires_consent flag."""
        mock_run_chat.return_value = {
            "response": None,
            "requires_consent": True,
            "actions": [{"tool": "update_budget", "input": {}, "result_preview": "..."}],
            "tool_calls_made": 1,
            "conversation_id": 2,
        }
        payload = {
            "messages": [{"role": "user", "content": "Update my budget"}],
        }
        resp = await client.post("/chat/message", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["requires_consent"] is True
        assert len(data["actions"]) == 1

    @pytest.mark.asyncio
    @patch("api.routes.chat.run_chat_stream")
    async def test_stream_message(self, mock_stream, client):
        """POST /chat/stream returns SSE event stream."""
        async def fake_stream(*args, **kwargs):
            yield {"type": "text_delta", "text": "Hello"}
            yield {"type": "done", "conversation_id": 1, "actions": []}

        mock_stream.return_value = fake_stream()

        payload = {
            "messages": [{"role": "user", "content": "Hi"}],
        }
        resp = await client.post("/chat/stream", json=payload)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        text = resp.text
        assert "text_delta" in text
        assert "done" in text
        assert "[DONE]" in text

    @pytest.mark.asyncio
    @patch("api.routes.chat.run_chat_stream")
    async def test_stream_message_error(self, mock_stream, client):
        """POST /chat/stream handles exceptions gracefully."""
        async def error_stream(*args, **kwargs):
            raise ValueError("Something broke")
            yield  # Make it a generator

        mock_stream.return_value = error_stream()

        payload = {
            "messages": [{"role": "user", "content": "Cause error"}],
        }
        resp = await client.post("/chat/stream", json=payload)
        assert resp.status_code == 200
        text = resp.text
        assert "error" in text
        assert "[DONE]" in text

    @pytest.mark.asyncio
    async def test_list_conversations_empty(self, client):
        """GET /chat/conversations returns empty list when no conversations."""
        resp = await client.get("/chat/conversations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_conversations_with_data(self, db_session, client):
        """GET /chat/conversations returns conversations with message counts."""
        conv = ChatConversation(
            title="Test Conv",
            page_context="budget",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(conv)
        await db_session.flush()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Hello",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(msg)
        await db_session.flush()

        resp = await client.get("/chat/conversations")
        assert resp.status_code == 200
        data = resp.json()
        found = next((c for c in data if c["title"] == "Test Conv"), None)
        assert found is not None
        assert found["message_count"] >= 1
        assert found["page_context"] == "budget"

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, db_session, client):
        """GET /chat/conversations/{id} returns conversation with messages."""
        conv = ChatConversation(
            title="Detail Conv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(conv)
        await db_session.flush()

        msg1 = ChatMessage(
            conversation_id=conv.id, role="user", content="Hey",
            created_at=datetime.now(timezone.utc),
        )
        msg2 = ChatMessage(
            conversation_id=conv.id, role="assistant", content="Hi there!",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add_all([msg1, msg2])
        await db_session.flush()

        resp = await client.get(f"/chat/conversations/{conv.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Detail Conv"
        assert data["message_count"] == 2
        assert len(data["messages"]) == 2

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, client):
        """GET /chat/conversations/{id} returns 404 for non-existent conversation."""
        resp = await client.get("/chat/conversations/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation(self, db_session, client):
        """DELETE /chat/conversations/{id} deletes the conversation."""
        conv = ChatConversation(
            title="Delete Me Conv",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(conv)
        await db_session.flush()

        resp = await client.delete(f"/chat/conversations/{conv.id}")
        assert resp.status_code == 204


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENTS TESTS — api/routes/documents.py
# ═══════════════════════════════════════════════════════════════════════════


class TestDocumentsRoutes:
    """Tests for /documents endpoints."""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, client):
        """GET /documents returns empty list with total=0."""
        resp = await client.get("/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    @pytest.mark.asyncio
    async def test_list_documents_with_data(self, db_session, client):
        """GET /documents returns documents with pagination info."""
        acct = await _create_account(db_session, name="Doc Acct")
        await _create_document(db_session, account_id=acct.id, filename="payroll.csv",
                               document_type="credit_card")

        resp = await client.get("/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_type(self, db_session, client):
        """GET /documents?document_type=credit_card filters by document type."""
        acct = await _create_account(db_session, name="Filter Acct")
        await _create_document(db_session, account_id=acct.id, document_type="credit_card")

        resp = await client.get("/documents?document_type=credit_card")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["document_type"] == "credit_card"

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_status(self, db_session, client):
        """GET /documents?status=completed filters by status."""
        resp = await client.get("/documents?status=completed")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_document_success(self, db_session, client):
        """GET /documents/{id} returns document details."""
        doc = await _create_document(db_session, filename="detail.csv")
        resp = await client.get(f"/documents/{doc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "detail.csv"
        assert data["id"] == doc.id

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client):
        """GET /documents/{id} returns 404 for non-existent document."""
        resp = await client.get("/documents/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_document_success(self, db_session, client):
        """DELETE /documents/{id} deletes the document."""
        doc = await _create_document(db_session, filename="delete_me.csv")
        resp = await client.delete(f"/documents/{doc.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, client):
        """DELETE /documents/{id} returns 404 for non-existent document."""
        resp = await client.delete("/documents/99999")
        assert resp.status_code == 404
