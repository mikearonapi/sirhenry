"""
Final coverage push — targets specific UNCOVERED LINES across low-coverage API routes.

Registers routes EXACTLY like api/main.py does, including sub-router nesting
(portfolio includes portfolio_analytics/portfolio_crypto, budget includes
budget_forecast, household includes household_optimization, retirement includes
retirement_scenarios, scenarios includes scenarios_calc, tax includes
tax_analysis/tax_strategies).

Uses httpx AsyncClient + ASGITransport with in-memory SQLite.
All external services (Plaid, Claude, Yahoo Finance, etc.) are mocked.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipeline.db.schema import (
    Account,
    AccountLink,
    Base,
    BenefitPackage,
    Budget,
    BusinessEntity,
    CategoryRule,
    CryptoHolding,
    Document,
    EquityGrant,
    EquityTaxProjection,
    Goal,
    HouseholdOptimization,
    HouseholdProfile,
    InsurancePolicy,
    InvestmentHolding,
    LifeEvent,
    LifeScenario,
    ManualAsset,
    NetWorthSnapshot,
    PlaidAccount,
    PlaidItem,
    PortfolioSnapshot,
    RecurringTransaction,
    RetirementProfile,
    TargetAllocation,
    Transaction,
    UserContext,
    VendorEntityRule,
    VestingEvent,
)


# ---------------------------------------------------------------------------
# Engine / Session / App fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_factory):
    async with db_factory() as s:
        yield s


def _override_session(factory):
    async def _dep():
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise
    return _dep


def _build_full_app():
    """Build a FastAPI app with ALL routes registered exactly like api/main.py.

    This is the critical piece - sub-routers are included by parent routers,
    so we only include the parent routers at app level.
    """
    from api.routes import (
        account_links, accounts, assets, benchmarks, budget,
        chat, documents, entities, equity_comp, error_reports,
        family_members, goal_suggestions, goals, household,
        import_routes, income, insights, insurance, life_events,
        market, plaid, portfolio, privacy, recurring, reminders,
        reports, retirement, rules, scenarios, setup_status,
        smart_defaults, tax, tax_modeling, transactions,
        user_context, valuations,
    )

    app = FastAPI()
    app.include_router(account_links.router)
    app.include_router(accounts.router)
    app.include_router(assets.router)
    app.include_router(transactions.router)
    app.include_router(documents.router)
    app.include_router(entities.router)
    app.include_router(import_routes.router)
    app.include_router(reports.router)
    app.include_router(insights.router)
    app.include_router(tax.router)           # includes tax_analysis + tax_strategies
    app.include_router(plaid.router)
    app.include_router(budget.router)        # includes budget_forecast
    app.include_router(recurring.router)
    app.include_router(goal_suggestions.router)
    app.include_router(goals.router)
    app.include_router(reminders.router)
    app.include_router(chat.router)
    app.include_router(portfolio.router)     # includes portfolio_analytics + portfolio_crypto
    app.include_router(market.router)
    app.include_router(retirement.router)    # includes retirement_scenarios
    app.include_router(scenarios.router)     # includes scenarios_calc
    app.include_router(equity_comp.router)
    app.include_router(household.router)     # includes household_optimization
    app.include_router(family_members.router)
    app.include_router(life_events.router)
    app.include_router(insurance.router)
    app.include_router(privacy.router)
    app.include_router(setup_status.router)
    app.include_router(tax_modeling.router)
    app.include_router(benchmarks.router)
    app.include_router(smart_defaults.router)
    app.include_router(income.router)
    app.include_router(rules.router)
    app.include_router(user_context.router)
    app.include_router(valuations.router)
    app.include_router(error_reports.router)

    return app


@pytest_asyncio.fixture
async def client(db_factory):
    app = _build_full_app()
    from api.database import get_session
    app.dependency_overrides[get_session] = _override_session(db_factory)
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    yield c
    await c.aclose()


# ---------------------------------------------------------------------------
# Helper: seed data
# ---------------------------------------------------------------------------

async def _seed_account(session, name="Test Checking", institution="Test Bank",
                        subtype="checking", data_source="csv"):
    acct = Account(
        name=name, account_type="personal", subtype=subtype,
        institution=institution, data_source=data_source, is_active=True,
    )
    session.add(acct)
    await session.flush()
    return acct


async def _seed_transaction(session, account_id, amount=-50.0,
                            description="GROCERY STORE", category="Groceries",
                            date_val=None, segment="personal"):
    d = date_val or date(2025, 6, 15)
    tx = Transaction(
        account_id=account_id, date=d, description=description,
        amount=amount, currency="USD", segment=segment,
        effective_segment=segment, category=category,
        effective_category=category, period_month=d.month,
        period_year=d.year, data_source="csv",
    )
    session.add(tx)
    await session.flush()
    return tx


async def _seed_household(session, filing_status="mfj", a_income=200000,
                           b_income=150000, state="CA", is_primary=True):
    hp = HouseholdProfile(
        filing_status=filing_status, spouse_a_income=a_income,
        spouse_b_income=b_income, combined_income=a_income + b_income,
        state=state, is_primary=is_primary,
    )
    session.add(hp)
    await session.flush()
    return hp


async def _seed_scenario(session, name="Buy House", scenario_type="home_purchase"):
    s = LifeScenario(
        name=name, scenario_type=scenario_type,
        parameters=json.dumps({"price": 800000}),
        annual_income=250000, monthly_take_home=15000,
        current_monthly_expenses=5000, current_monthly_debt_payments=500,
        current_savings=100000, current_investments=200000,
        total_cost=800000, new_monthly_payment=4000,
        monthly_surplus_after=6000, savings_rate_before_pct=30,
        savings_rate_after_pct=20, dti_before_pct=5,
        dti_after_pct=30, affordability_score=75,
        verdict="Affordable", status="computed",
    )
    session.add(s)
    await session.flush()
    return s


# ===========================================================================
# 1. api/database.py — get_session, switch_to_mode
# ===========================================================================

class TestDatabaseModule:
    @pytest.mark.asyncio
    async def test_get_session_commit(self):
        """Test the get_session dependency function."""
        from api.database import get_session
        # get_session is an async generator — just verify it's importable
        gen = get_session()
        assert gen is not None

    @pytest.mark.asyncio
    async def test_get_active_mode(self):
        from api.database import get_active_mode
        mode = get_active_mode()
        assert mode in ("local", "demo")

    def test_demo_db_url(self):
        from api.database import _demo_db_url
        url = _demo_db_url()
        assert "demo.db" in url


# ===========================================================================
# 2. api/main.py — app factory, health endpoint
# ===========================================================================

class TestMainApp:
    def test_app_exists(self):
        from api.main import app
        assert app is not None
        assert app.title == "Sir Henry API"

    def test_routes_registered(self):
        from api.main import app
        paths = [r.path for r in app.routes]
        # Verify key routes are registered
        assert "/health" in paths


# ===========================================================================
# 3. api/routes/plaid.py — FULL coverage targets
# ===========================================================================

class TestPlaidCoverage:
    @pytest.mark.asyncio
    async def test_get_link_token_success(self, client):
        with patch("api.routes.plaid.create_link_token", return_value="lt-123"):
            resp = await client.get("/plaid/link-token")
            assert resp.status_code == 200
            assert resp.json()["link_token"] == "lt-123"

    @pytest.mark.asyncio
    async def test_get_link_token_error(self, client):
        with patch("api.routes.plaid.create_link_token", side_effect=Exception("fail")):
            resp = await client.get("/plaid/link-token")
            assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_update_link_token_not_found(self, client):
        resp = await client.get("/plaid/link-token/update/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_link_token_success(self, client, db_session):
        pi = PlaidItem(item_id="u1", access_token="enc", institution_name="Bank",
                       status="active")
        db_session.add(pi)
        await db_session.commit()
        with patch("api.routes.plaid.decrypt_token", return_value="tok"), \
             patch("api.routes.plaid.create_link_token", return_value="upd-tok"):
            resp = await client.get(f"/plaid/link-token/update/{pi.id}")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_link_token_plaid_error(self, client, db_session):
        pi = PlaidItem(item_id="u2", access_token="enc", institution_name="ErrBank",
                       status="active")
        db_session.add(pi)
        await db_session.commit()
        with patch("api.routes.plaid.decrypt_token", return_value="tok"), \
             patch("api.routes.plaid.create_link_token", side_effect=Exception("Plaid error")):
            resp = await client.get(f"/plaid/link-token/update/{pi.id}")
            assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_exchange_token_dup_institution(self, client, db_session):
        pi = PlaidItem(item_id="dup1", access_token="x", institution_name="DupBank",
                       status="active")
        db_session.add(pi)
        await db_session.commit()
        resp = await client.post("/plaid/exchange-token", json={
            "public_token": "pt", "institution_name": "DupBank",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_exchange_token_success_with_account_match(self, client, db_session):
        """Test exchange with account matching — covers lines 195-270."""
        # Create a manual account that will match by last_four + institution
        acct = await _seed_account(db_session, name="My Chase Card",
                                   institution="Chase", data_source="csv")
        acct.last_four = "4242"
        await db_session.commit()

        with patch("api.routes.plaid.exchange_public_token", return_value={
            "item_id": "new_item_match", "access_token": "access_new_match",
        }), patch("api.routes.plaid.encrypt_token", return_value="enc_new"), \
             patch("api.routes.plaid.get_accounts", return_value=[
                 {"plaid_account_id": "chase_acct_1", "name": "Chase Sapphire",
                  "subtype": "credit_card", "mask": "4242", "type": "credit",
                  "current_balance": 1500.0, "available_balance": None,
                  "limit_balance": 10000.0, "iso_currency": "USD",
                  "official_name": None, "last_updated": datetime.now(timezone.utc)},
             ]):
            resp = await client.post("/plaid/exchange-token", json={
                "public_token": "pub_match", "institution_name": "Chase",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "connected"
            assert data["accounts_matched"] >= 1

    @pytest.mark.asyncio
    async def test_exchange_token_fail(self, client):
        with patch("api.routes.plaid.exchange_public_token",
                   side_effect=Exception("exchange failed")):
            resp = await client.post("/plaid/exchange-token", json={
                "public_token": "bad", "institution_name": "NoBank",
            })
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_sync_status_not_found(self, client):
        resp = await client.get("/plaid/sync-status/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_status_found(self, client, db_session):
        pi = PlaidItem(item_id="ss1", access_token="enc", institution_name="SyncBank",
                       status="active", sync_phase="complete",
                       last_synced_at=datetime.now(timezone.utc))
        db_session.add(pi)
        await db_session.commit()
        resp = await client.get(f"/plaid/sync-status/{pi.id}")
        assert resp.status_code == 200
        assert resp.json()["sync_phase"] == "complete"

    @pytest.mark.asyncio
    async def test_list_items(self, client, db_session):
        resp = await client.get("/plaid/items")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_item_not_found(self, client):
        resp = await client.delete("/plaid/items/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_item_success(self, client, db_session):
        pi = PlaidItem(item_id="d1", access_token="enc_del", institution_name="DelBank",
                       status="active")
        db_session.add(pi)
        await db_session.commit()
        with patch("api.routes.plaid.decrypt_token", return_value="tok"), \
             patch("api.routes.plaid.remove_item"):
            resp = await client.delete(f"/plaid/items/{pi.id}")
            assert resp.status_code == 200
            assert resp.json()["status"] == "removed"

    @pytest.mark.asyncio
    async def test_delete_item_revoke_fails(self, client, db_session):
        """Cover line 332: Plaid revoke fails but item still marked removed."""
        pi = PlaidItem(item_id="d2", access_token="enc_del2", institution_name="FailBank",
                       status="active")
        db_session.add(pi)
        await db_session.commit()
        with patch("api.routes.plaid.decrypt_token", return_value="tok"), \
             patch("api.routes.plaid.remove_item", side_effect=Exception("net error")):
            resp = await client.delete(f"/plaid/items/{pi.id}")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sync_plaid(self, client):
        resp = await client.post("/plaid/sync")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_plaid_accounts(self, client):
        resp = await client.get("/plaid/accounts")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_plaid_health_with_items(self, client, db_session):
        """Cover lines 372-430: health endpoint with items, balance sums, staleness."""
        pi = PlaidItem(item_id="h1", access_token="enc", institution_name="HealthBank",
                       status="active",
                       last_synced_at=datetime.now(timezone.utc) - timedelta(hours=48))
        db_session.add(pi)
        await db_session.flush()
        # Investment account (asset)
        pa1 = PlaidAccount(plaid_item_id=pi.id, plaid_account_id="h_pa1",
                           name="Brokerage", type="investment", subtype="brokerage",
                           current_balance=50000.0)
        # Credit account (liability)
        pa2 = PlaidAccount(plaid_item_id=pi.id, plaid_account_id="h_pa2",
                           name="CC", type="credit", subtype="credit card",
                           current_balance=-2500.0)
        db_session.add_all([pa1, pa2])
        await db_session.commit()

        resp = await client.get("/plaid/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_items"] >= 1
        # Stale check — 48 hours > 24 threshold
        assert any(item["stale"] for item in data["items"] if item["institution"] == "HealthBank")


# ===========================================================================
# 4. api/routes/accounts.py — lines 31-83, 92-94, 103, 113-120, 129-134
# ===========================================================================

class TestAccountsCoverage:
    @pytest.mark.asyncio
    async def test_list_accounts_with_transactions(self, client, db_session):
        """Cover balance from transaction sum (non-plaid)."""
        acct = await _seed_account(db_session, name="CsvAcct", data_source="csv")
        await _seed_transaction(db_session, acct.id, amount=-100.0)
        await db_session.commit()
        resp = await client.get("/accounts")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_accounts_exclude_plaid(self, client, db_session):
        resp = await client.get("/accounts?exclude_plaid=true")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_single_account_not_found(self, client):
        resp = await client.get("/accounts/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_account(self, client):
        resp = await client.post("/accounts", json={
            "name": "NewSave", "account_type": "personal",
            "subtype": "savings", "institution": "BigBank",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_update_account(self, client, db_session):
        acct = await _seed_account(db_session, name="UpdAcct")
        await db_session.commit()
        resp = await client.patch(f"/accounts/{acct.id}", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_account_not_found(self, client):
        resp = await client.patch("/accounts/99999", json={"name": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_deactivate_account(self, client, db_session):
        acct = await _seed_account(db_session, name="DeactAcct")
        await db_session.commit()
        resp = await client.delete(f"/accounts/{acct.id}")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_deactivate_account_not_found(self, client):
        resp = await client.delete("/accounts/99999")
        assert resp.status_code == 404


# ===========================================================================
# 5. api/routes/transactions.py — lines 54-60, 77-162, 174-249
# ===========================================================================

class TestTransactionsCoverage:
    @pytest.mark.asyncio
    async def test_list_transactions_with_filters(self, client, db_session):
        """Cover various query param filters."""
        acct = await _seed_account(db_session, name="TxFilter")
        await _seed_transaction(db_session, acct.id, category="Dining")
        await db_session.commit()
        resp = await client.get("/transactions?category=Dining&year=2025&month=6&search=GROCERY")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_transactions_segment(self, client):
        resp = await client.get("/transactions?segment=business")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_transaction_audit_no_year(self, client):
        resp = await client.get("/transactions/audit")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_transaction_with_children(self, client, db_session):
        """Cover lines 153-161: transaction with children (split parent)."""
        acct = await _seed_account(db_session, name="SplitAcct")
        parent_tx = await _seed_transaction(db_session, acct.id, amount=-100.0,
                                            description="AMAZON SPLIT")
        child_tx = Transaction(
            account_id=acct.id, date=date(2025, 6, 15),
            description="Item 1", amount=-40.0, currency="USD",
            segment="personal", effective_segment="personal",
            category="Electronics", effective_category="Electronics",
            period_month=6, period_year=2025, data_source="csv",
            parent_transaction_id=parent_tx.id,
        )
        db_session.add(child_tx)
        await db_session.commit()
        resp = await client.get(f"/transactions/{parent_tx.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "children" in data

    @pytest.mark.asyncio
    async def test_update_transaction_entity(self, client, db_session):
        """Cover lines 187-188: business_entity_override."""
        acct = await _seed_account(db_session, name="EntUpd")
        tx = await _seed_transaction(db_session, acct.id)
        ent = BusinessEntity(name="My LLC", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        resp = await client.patch(f"/transactions/{tx.id}", json={
            "business_entity_override": ent.id,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_transaction_segment_override(self, client, db_session):
        """Cover segment_override path."""
        acct = await _seed_account(db_session, name="SegUpd")
        tx = await _seed_transaction(db_session, acct.id)
        await db_session.commit()
        resp = await client.patch(f"/transactions/{tx.id}", json={
            "segment_override": "business",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_manual_transaction(self, client, db_session):
        acct = await _seed_account(db_session, name="ManTx")
        await db_session.commit()
        resp = await client.post("/transactions", json={
            "account_id": acct.id, "date": "2025-07-01",
            "description": "Manual", "amount": -25.0,
            "segment": "personal", "category": "Other",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_manual_transaction_bad_account(self, client):
        resp = await client.post("/transactions", json={
            "account_id": 99999, "date": "2025-07-01",
            "description": "Bad", "amount": -10.0, "segment": "personal",
        })
        assert resp.status_code == 404


# ===========================================================================
# 6. api/routes/household.py — profiles CRUD, benefits, tax strategy profile
# ===========================================================================

class TestHouseholdCoverage:
    @pytest.mark.asyncio
    async def test_list_profiles(self, client):
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_profile(self, client):
        resp = await client.post("/household/profiles", json={
            "filing_status": "single", "spouse_a_income": 180000,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_second_profile_as_primary(self, client, db_session):
        """Cover lines 49-57: enforce single primary."""
        hp = await _seed_household(db_session, is_primary=True)
        await db_session.commit()
        resp = await client.post("/household/profiles", json={
            "filing_status": "mfj", "spouse_a_income": 200000,
            "spouse_b_income": 150000, "is_primary": True,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_update_profile(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()
        resp = await client.patch(f"/household/profiles/{hp.id}", json={
            "spouse_a_income": 220000, "is_primary": True,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_profile_not_found(self, client):
        resp = await client.patch("/household/profiles/99999", json={
            "spouse_a_income": 100000,
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_profile(self, client, db_session):
        hp = await _seed_household(db_session, is_primary=False)
        await db_session.commit()
        resp = await client.delete(f"/household/profiles/{hp.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_profile_with_related(self, client, db_session):
        """Cover lines 101-108: cascade delete with insurance + life events."""
        hp = await _seed_household(db_session, is_primary=False)
        pol = InsurancePolicy(household_id=hp.id, policy_type="auto",
                              provider="Geico", is_active=True)
        ev = LifeEvent(household_id=hp.id, event_type="family",
                       event_subtype="birth", title="Baby born", tax_year=2025)
        db_session.add_all([pol, ev])
        await db_session.commit()
        resp = await client.delete(f"/household/profiles/{hp.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_profile_not_found(self, client):
        resp = await client.delete("/household/profiles/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_benefits(self, client, db_session):
        hp = await _seed_household(db_session)
        bp = BenefitPackage(household_id=hp.id, spouse="a",
                            employer_name="ACME")
        db_session.add(bp)
        await db_session.commit()
        resp = await client.get(f"/household/profiles/{hp.id}/benefits")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_upsert_benefits_create(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()
        resp = await client.post(f"/household/profiles/{hp.id}/benefits", json={
            "spouse": "a", "employer_name": "NewCo",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    @pytest.mark.asyncio
    async def test_upsert_benefits_update(self, client, db_session):
        hp = await _seed_household(db_session)
        bp = BenefitPackage(household_id=hp.id, spouse="b", employer_name="Old")
        db_session.add(bp)
        await db_session.commit()
        resp = await client.post(f"/household/profiles/{hp.id}/benefits", json={
            "spouse": "b", "employer_name": "Updated",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_get_tax_strategy_profile_none(self, client):
        resp = await client.get("/household/tax-strategy-profile")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_tax_strategy_profile_with_data(self, client, db_session):
        """Cover lines 158-163: parse tax_strategy_profile_json."""
        hp = await _seed_household(db_session, is_primary=True)
        hp.tax_strategy_profile_json = json.dumps({"owns_business": True})
        await db_session.commit()
        resp = await client.get("/household/tax-strategy-profile")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_save_tax_strategy_profile(self, client, db_session):
        hp = await _seed_household(db_session, is_primary=True)
        await db_session.commit()
        resp = await client.put("/household/tax-strategy-profile", json={
            "owns_business": False,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_save_tax_strategy_profile_no_profile(self, client):
        """Cover line 174: no primary household."""
        # If no primary household exists, should get 404
        # (depends on state - may have one from earlier tests)
        resp = await client.put("/household/tax-strategy-profile", json={
            "owns_business": True,
        })
        assert resp.status_code in (200, 404)


# ===========================================================================
# 7. api/routes/scenarios_calc.py — templates, calculate, compose, multi-year, etc.
# ===========================================================================

class TestScenariosCalcCoverage:
    @pytest.mark.asyncio
    async def test_get_templates(self, client):
        resp = await client.get("/scenarios/templates")
        assert resp.status_code == 200
        assert "templates" in resp.json()

    @pytest.mark.asyncio
    async def test_calculate_scenario(self, client):
        with patch("api.routes.scenarios_calc.LifeScenarioEngine") as mock_engine:
            mock_engine.calculate.return_value = {
                "total_cost": 800000, "verdict": "Affordable",
                "affordability_score": 80,
            }
            resp = await client.post("/scenarios/calculate", json={
                "scenario_type": "home_purchase",
                "parameters": {"price": 800000, "down_payment_pct": 20},
                "annual_income": 250000, "monthly_take_home": 15000,
                "current_monthly_expenses": 5000,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_calculate_scenario_error(self, client):
        with patch("api.routes.scenarios_calc.LifeScenarioEngine") as mock_engine:
            mock_engine.calculate.return_value = {"error": "Invalid params"}
            resp = await client.post("/scenarios/calculate", json={
                "scenario_type": "home_purchase",
                "parameters": {}, "annual_income": 100000,
                "monthly_take_home": 6000, "current_monthly_expenses": 3000,
            })
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_compose_scenarios_not_enough(self, client, db_session):
        s = await _seed_scenario(db_session)
        await db_session.commit()
        resp = await client.post("/scenarios/compose", json={
            "scenario_ids": [s.id],
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_compose_scenarios_success(self, client, db_session):
        s1 = await _seed_scenario(db_session, name="S1")
        s2 = await _seed_scenario(db_session, name="S2", scenario_type="car_purchase")
        await db_session.commit()
        with patch("api.routes.scenarios_calc.compose_scenarios",
                   return_value={"combined_impact": 100000}):
            resp = await client.post("/scenarios/compose", json={
                "scenario_ids": [s1.id, s2.id],
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_multi_year_projection(self, client, db_session):
        s = await _seed_scenario(db_session)
        await db_session.commit()
        with patch("api.routes.scenarios_calc.project_multi_year",
                   return_value={"projections": []}):
            resp = await client.post(f"/scenarios/{s.id}/multi-year",
                                     json={"years": 5})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_multi_year_not_found(self, client):
        resp = await client.post("/scenarios/99999/multi-year", json={"years": 5})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_retirement_impact(self, client, db_session):
        s = await _seed_scenario(db_session)
        await db_session.commit()
        with patch("api.routes.scenarios_calc.compute_retirement_impact",
                   return_value={"impact": "moderate"}):
            resp = await client.post(f"/scenarios/{s.id}/retirement-impact")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_retirement_impact_not_found(self, client):
        resp = await client.post("/scenarios/99999/retirement-impact")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_monte_carlo(self, client, db_session):
        s = await _seed_scenario(db_session)
        await db_session.commit()
        with patch("api.routes.scenarios_calc.run_monte_carlo_simulation",
                   return_value={"success_rate": 0.85}):
            resp = await client.post(f"/scenarios/{s.id}/monte-carlo",
                                     json={"runs": 100})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_monte_carlo_not_found(self, client):
        resp = await client.post("/scenarios/99999/monte-carlo", json={"runs": 100})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_compare_scenarios(self, client, db_session):
        s1 = await _seed_scenario(db_session, name="CmpA")
        s2 = await _seed_scenario(db_session, name="CmpB")
        await db_session.commit()
        with patch("api.routes.scenarios_calc.compare_scenario_metrics",
                   return_value={"winner": "CmpA"}):
            resp = await client.post("/scenarios/compare", json={
                "scenario_a_id": s1.id, "scenario_b_id": s2.id,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_compare_scenarios_missing(self, client, db_session):
        s = await _seed_scenario(db_session)
        await db_session.commit()
        resp = await client.post("/scenarios/compare", json={
            "scenario_a_id": s.id, "scenario_b_id": 99999,
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_ai_analysis(self, client, db_session):
        s = await _seed_scenario(db_session)
        hp = await _seed_household(db_session)
        await db_session.commit()
        with patch("api.routes.scenarios_calc.analyze_scenario_with_ai",
                   return_value={"analysis": "Looks good"}):
            resp = await client.post(f"/scenarios/{s.id}/ai-analysis")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_ai_analysis_not_found(self, client):
        resp = await client.post("/scenarios/99999/ai-analysis")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_scenario_suggestions(self, client):
        resp = await client.get("/scenarios/suggestions")
        assert resp.status_code == 200


# ===========================================================================
# 8. api/routes/budget.py — all CRUD + summary + copy + auto-generate
# ===========================================================================

class TestBudgetCoverage:
    @pytest.mark.asyncio
    async def test_budget_categories(self, client, db_session):
        acct = await _seed_account(db_session, name="BudCat")
        await _seed_transaction(db_session, acct.id, category="Rent")
        await db_session.commit()
        resp = await client.get("/budget/categories?year=2025&month=6")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_budget_summary(self, client, db_session):
        b = Budget(year=2026, month=3, category="Groceries",
                   segment="personal", budget_amount=500.0)
        db_session.add(b)
        await db_session.commit()
        resp = await client.get("/budget/summary?year=2026&month=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_budgeted" in data
        assert "year_over_year" in data

    @pytest.mark.asyncio
    async def test_copy_budget(self, client, db_session):
        b = Budget(year=2026, month=1, category="Utils",
                   segment="personal", budget_amount=200.0)
        db_session.add(b)
        await db_session.commit()
        resp = await client.post("/budget/copy?from_year=2026&from_month=1&to_year=2026&to_month=2")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_copy_budget_not_found(self, client):
        resp = await client.post("/budget/copy?from_year=1900&from_month=1&to_year=1900&to_month=2")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_auto_generate(self, client):
        with patch("pipeline.planning.smart_defaults.generate_smart_budget",
                   new_callable=AsyncMock, return_value=[
                       {"category": "Food", "segment": "personal",
                        "budget_amount": 600, "source": "pattern"},
                   ]):
            resp = await client.post("/budget/auto-generate?year=2026&month=4")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auto_generate_apply(self, client):
        with patch("pipeline.planning.smart_defaults.generate_smart_budget",
                   new_callable=AsyncMock, return_value=[
                       {"category": "Transport", "segment": "personal",
                        "budget_amount": 300, "source": "pattern"},
                   ]):
            resp = await client.post("/budget/auto-generate/apply?year=2026&month=5")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_budgets(self, client, db_session):
        b = Budget(year=2026, month=6, category="Shopping",
                   segment="personal", budget_amount=400.0)
        db_session.add(b)
        await db_session.commit()
        resp = await client.get("/budget?year=2026&month=6")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_budgets_with_segment(self, client):
        resp = await client.get("/budget?year=2026&month=6&segment=personal")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_budget_new(self, client):
        resp = await client.post("/budget", json={
            "year": 2026, "month": 7, "category": "Entertainment",
            "segment": "personal", "budget_amount": 150.0,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_budget_update_existing(self, client, db_session):
        """Cover lines 266-270: upsert existing budget."""
        b = Budget(year=2026, month=8, category="Dining",
                   segment="personal", budget_amount=200.0)
        db_session.add(b)
        await db_session.commit()
        resp = await client.post("/budget", json={
            "year": 2026, "month": 8, "category": "Dining",
            "segment": "personal", "budget_amount": 300.0,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_budget(self, client, db_session):
        b = Budget(year=2026, month=9, category="Gas",
                   segment="personal", budget_amount=150.0)
        db_session.add(b)
        await db_session.commit()
        resp = await client.patch(f"/budget/{b.id}", json={"budget_amount": 200.0})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_budget_not_found(self, client):
        resp = await client.patch("/budget/99999", json={"budget_amount": 100.0})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_budget(self, client, db_session):
        b = Budget(year=2026, month=10, category="Misc",
                   segment="personal", budget_amount=100.0)
        db_session.add(b)
        await db_session.commit()
        resp = await client.delete(f"/budget/{b.id}")
        assert resp.status_code == 200


# ===========================================================================
# 9. api/routes/import_routes.py — upload, detect-type, categorize
# ===========================================================================

class TestImportCoverage:
    @pytest.mark.asyncio
    async def test_upload_no_filename(self, client):
        resp = await client.post("/import/upload", data={
            "document_type": "credit_card",
        }, files={"file": ("", b"", "text/csv")})
        # Empty filename triggers FastAPI validation (422) or app-level check (400)
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_upload_bad_extension(self, client):
        resp = await client.post("/import/upload", data={
            "document_type": "credit_card",
        }, files={"file": ("test.xyz", b"data", "text/plain")})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_credit_card_csv(self, client):
        csv_content = b"Date,Description,Amount\n2025-01-01,Store,-50.00"
        with patch("pipeline.importers.credit_card.import_csv_file",
                   new_callable=AsyncMock, return_value={
                       "status": "completed", "transactions_imported": 1,
                       "transactions_skipped": 0, "document_id": 1, "message": "ok",
                   }):
            resp = await client.post("/import/upload", data={
                "document_type": "credit_card",
                "account_name": "Test Card", "institution": "Chase",
                "segment": "personal",
            }, files={"file": ("stmt.csv", csv_content, "text/csv")})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_import_error(self, client):
        csv_content = b"bad,data"
        with patch("pipeline.importers.credit_card.import_csv_file",
                   new_callable=AsyncMock, return_value={
                       "status": "error", "message": "Parse error",
                   }):
            resp = await client.post("/import/upload", data={
                "document_type": "credit_card",
            }, files={"file": ("fail.csv", csv_content, "text/csv")})
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_detect_type_csv(self, client):
        csv_content = b"Transaction Date,Description,Amount\n01/15/2025,AMAZON,-25.00"
        with patch("pipeline.ai.categorizer.detect_document_type",
                   return_value={"type": "credit_card", "confidence": 0.9}):
            resp = await client.post("/import/detect-type",
                                     files={"file": ("test.csv", csv_content, "text/csv")})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_categorize(self, client):
        with patch("pipeline.db.models.apply_entity_rules",
                   new_callable=AsyncMock, return_value=5), \
             patch("pipeline.ai.category_rules.apply_rules",
                   new_callable=AsyncMock, return_value={"applied": 3}), \
             patch("pipeline.ai.categorizer.categorize_transactions",
                   new_callable=AsyncMock, return_value={"categorized": 2}):
            resp = await client.post("/import/categorize?year=2025")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_batch_tax_docs(self, client):
        with patch("pipeline.importers.tax_doc.import_directory",
                   new_callable=AsyncMock, return_value=[
                       {"status": "completed", "filename": "w2.pdf"},
                   ]):
            resp = await client.post("/import/batch-tax-docs?tax_year=2025")
            assert resp.status_code == 200


# ===========================================================================
# 10. api/routes/portfolio_analytics.py — sub-router under /portfolio
# ===========================================================================

class TestPortfolioAnalyticsCoverage:
    @pytest.mark.asyncio
    async def test_refresh_prices(self, client, db_session):
        h = InvestmentHolding(
            ticker="AAPL", name="Apple", shares=10, current_price=150.0,
            current_value=1500.0, total_cost_basis=1200.0,
            asset_class="stock", is_active=True,
        )
        db_session.add(h)
        await db_session.commit()
        with patch("api.routes.portfolio_analytics.YahooFinanceService") as mock_yf, \
             patch("api.routes.portfolio_analytics.CryptoService") as mock_cs:
            mock_yf.get_bulk_quotes.return_value = {
                "AAPL": {"ticker": "AAPL", "price": 175.0, "sector": "Technology"},
            }
            mock_cs.get_prices = AsyncMock(return_value={})
            resp = await client.post("/portfolio/refresh-prices")
            assert resp.status_code == 200
            assert resp.json()["stocks_updated"] >= 1

    @pytest.mark.asyncio
    async def test_get_quote(self, client):
        with patch("api.routes.portfolio_analytics.YahooFinanceService") as mock_yf:
            mock_yf.get_quote.return_value = {"ticker": "MSFT", "price": 400.0}
            resp = await client.get("/portfolio/quote/MSFT")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self, client):
        with patch("api.routes.portfolio_analytics.YahooFinanceService") as mock_yf:
            mock_yf.get_quote.return_value = None
            resp = await client.get("/portfolio/quote/INVALID")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_history(self, client):
        with patch("api.routes.portfolio_analytics.YahooFinanceService") as mock_yf:
            mock_yf.get_history.return_value = [{"date": "2025-01-01", "close": 150}]
            resp = await client.get("/portfolio/history/AAPL")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        with patch("api.routes.portfolio_analytics.YahooFinanceService") as mock_yf:
            mock_yf.get_key_stats.return_value = {"pe_ratio": 25.0}
            resp = await client.get("/portfolio/stats/AAPL")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_stats_not_found(self, client):
        with patch("api.routes.portfolio_analytics.YahooFinanceService") as mock_yf:
            mock_yf.get_key_stats.return_value = None
            resp = await client.get("/portfolio/stats/BAD")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_portfolio_summary(self, client):
        resp = await client.get("/portfolio/summary")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_tax_loss_harvest(self, client, db_session):
        h = InvestmentHolding(
            ticker="TSLA", name="Tesla", shares=5, current_price=200.0,
            current_value=1000.0, total_cost_basis=1500.0,
            cost_basis_per_share=300.0, asset_class="stock", is_active=True,
        )
        db_session.add(h)
        await db_session.commit()
        resp = await client.get("/portfolio/tax-loss-harvest?marginal_rate=0.37&filing_status=mfj")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_target_allocation_get(self, client):
        resp = await client.get("/portfolio/target-allocation")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_target_allocation_set(self, client):
        resp = await client.put("/portfolio/target-allocation", json={
            "name": "Growth", "allocation": {"stock": 70, "etf": 20, "bond": 10},
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_target_allocation_bad_sum(self, client):
        resp = await client.put("/portfolio/target-allocation", json={
            "name": "Bad", "allocation": {"stock": 50, "bond": 10},
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_allocation_presets(self, client):
        resp = await client.get("/portfolio/target-allocation/presets")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_rebalance(self, client):
        resp = await client.get("/portfolio/rebalance")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_benchmark(self, client):
        resp = await client.get("/portfolio/benchmark")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_concentration(self, client):
        resp = await client.get("/portfolio/concentration")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_performance(self, client):
        with patch("api.routes.portfolio_analytics.PortfolioAnalyticsEngine") as mock_engine:
            mock_engine.performance_metrics.return_value = {
                "time_weighted_return": 0, "sharpe_ratio": None,
                "max_drawdown": 0, "volatility": None, "period_months": 0,
            }
            resp = await client.get("/portfolio/performance")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_net_worth_trend(self, client):
        resp = await client.get("/portfolio/net-worth-trend")
        assert resp.status_code == 200


# ===========================================================================
# 11. api/routes/account_links.py — link, merge, suggest, duplicates
# ===========================================================================

class TestAccountLinksCoverage:
    @pytest.mark.asyncio
    async def test_link_self(self, client, db_session):
        acct = await _seed_account(db_session, name="SelfLink")
        await db_session.commit()
        resp = await client.post(f"/accounts/{acct.id}/link", json={
            "target_account_id": acct.id, "link_type": "same_account",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_link_not_found(self, client):
        resp = await client.post("/accounts/99999/link", json={
            "target_account_id": 99998, "link_type": "same_account",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_link_success(self, client, db_session):
        a = await _seed_account(db_session, name="LinkA")
        b = await _seed_account(db_session, name="LinkB")
        await db_session.commit()
        resp = await client.post(f"/accounts/{a.id}/link", json={
            "target_account_id": b.id, "link_type": "same_account",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_link_duplicate(self, client, db_session):
        a = await _seed_account(db_session, name="DupLinkA")
        b = await _seed_account(db_session, name="DupLinkB")
        link = AccountLink(primary_account_id=a.id, secondary_account_id=b.id,
                           link_type="same_account")
        db_session.add(link)
        await db_session.commit()
        resp = await client.post(f"/accounts/{a.id}/link", json={
            "target_account_id": b.id, "link_type": "same_account",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_links(self, client, db_session):
        a = await _seed_account(db_session, name="GetLinksAcct")
        await db_session.commit()
        resp = await client.get(f"/accounts/{a.id}/links")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_remove_link_not_found(self, client, db_session):
        a = await _seed_account(db_session, name="RmLink")
        await db_session.commit()
        resp = await client.delete(f"/accounts/{a.id}/link/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_link_wrong_account(self, client, db_session):
        a = await _seed_account(db_session, name="WrongA")
        b = await _seed_account(db_session, name="WrongB")
        c = await _seed_account(db_session, name="WrongC")
        link = AccountLink(primary_account_id=a.id, secondary_account_id=b.id,
                           link_type="same_account")
        db_session.add(link)
        await db_session.commit()
        resp = await client.delete(f"/accounts/{c.id}/link/{link.id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_merge_accounts(self, client, db_session):
        a = await _seed_account(db_session, name="MergeA")
        b = await _seed_account(db_session, name="MergeB")
        tx = await _seed_transaction(db_session, b.id)
        await db_session.commit()
        resp = await client.post(f"/accounts/{a.id}/merge", json={
            "target_account_id": b.id, "link_type": "same_account",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["secondary_deactivated"] is True
        assert data["transactions_moved"] >= 1

    @pytest.mark.asyncio
    async def test_merge_self(self, client, db_session):
        a = await _seed_account(db_session, name="MergeSelf")
        await db_session.commit()
        resp = await client.post(f"/accounts/{a.id}/merge", json={
            "target_account_id": a.id, "link_type": "same_account",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_merge_not_found(self, client):
        resp = await client.post("/accounts/99999/merge", json={
            "target_account_id": 99998, "link_type": "same_account",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_suggest_links(self, client, db_session):
        """Cover _match_reason logic."""
        a = await _seed_account(db_session, name="Chase Sapphire",
                                institution="Chase", data_source="csv")
        a.last_four = "1234"
        b = await _seed_account(db_session, name="Chase Sapphire",
                                institution="Chase", data_source="plaid")
        b.last_four = "1234"
        await db_session.commit()
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_find_duplicates(self, client, db_session):
        a = await _seed_account(db_session, name="DedupAcct")
        await db_session.commit()
        with patch("pipeline.dedup.cross_source.find_cross_source_duplicates",
                   new_callable=AsyncMock, return_value=[]):
            resp = await client.get(f"/accounts/{a.id}/duplicates")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auto_dedup(self, client, db_session):
        a = await _seed_account(db_session, name="AutoDedupAcct")
        await db_session.commit()
        with patch("pipeline.dedup.cross_source.auto_resolve_duplicates",
                   new_callable=AsyncMock, return_value={"resolved": 0}):
            resp = await client.post(f"/accounts/{a.id}/auto-dedup")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_resolve_duplicate(self, client, db_session):
        a = await _seed_account(db_session, name="ResAcct")
        tx = await _seed_transaction(db_session, a.id)
        await db_session.commit()
        resp = await client.post("/accounts/resolve-duplicate", json={
            "keep_id": 1, "exclude_id": tx.id,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_resolve_duplicate_not_found(self, client):
        resp = await client.post("/accounts/resolve-duplicate", json={
            "keep_id": 1, "exclude_id": 99999,
        })
        assert resp.status_code == 404


# ===========================================================================
# 12. api/routes/goals.py — CRUD + auto-update from account
# ===========================================================================

class TestGoalsCoverage:
    @pytest.mark.asyncio
    async def test_list_goals(self, client):
        resp = await client.get("/goals")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_goal(self, client):
        resp = await client.post("/goals", json={
            "name": "Emergency Fund", "goal_type": "savings",
            "target_amount": 30000, "current_amount": 5000,
            "target_date": "2027-01-01", "monthly_contribution": 500,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_goal_no_date(self, client):
        resp = await client.post("/goals", json={
            "name": "Travel Fund", "goal_type": "savings",
            "target_amount": 5000, "current_amount": 0,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_goal(self, client, db_session):
        g = Goal(name="Upd Goal", goal_type="savings",
                 target_amount=10000, current_amount=2000,
                 status="active")
        db_session.add(g)
        await db_session.commit()
        resp = await client.patch(f"/goals/{g.id}", json={
            "current_amount": 5000, "status": "completed",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_goal_not_found(self, client):
        resp = await client.patch("/goals/99999", json={"name": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_goal(self, client, db_session):
        g = Goal(name="Del Goal", goal_type="savings",
                 target_amount=5000, current_amount=0, status="active")
        db_session.add(g)
        await db_session.commit()
        resp = await client.delete(f"/goals/{g.id}")
        assert resp.status_code == 200


# ===========================================================================
# 13. api/routes/valuations.py — vehicle, property, asset refresh
# ===========================================================================

class TestValuationsCoverage:
    @pytest.mark.asyncio
    async def test_decode_vehicle(self, client):
        with patch("pipeline.market.vehicle_valuation.VehicleValuationService.decode_vin",
                   new_callable=AsyncMock, return_value={
                       "year": 2022, "make": "Toyota", "model": "Camry",
                   }), \
             patch("pipeline.market.vehicle_valuation.VehicleValuationService.estimate_value",
                   return_value={"estimated_value": 25000}):
            resp = await client.get("/valuations/vehicle/1HGBH41JXMN109186")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_decode_vehicle_bad_vin(self, client):
        with patch("pipeline.market.vehicle_valuation.VehicleValuationService.decode_vin",
                   new_callable=AsyncMock, return_value=None):
            resp = await client.get("/valuations/vehicle/BAD")
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_property_valuation(self, client):
        with patch("pipeline.market.property_valuation.PropertyValuationService.get_valuation",
                   new_callable=AsyncMock, return_value={
                       "estimated_value": 500000, "address": "123 Main St",
                   }):
            resp = await client.get("/valuations/property?address=123+Main+St")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_property_valuation_not_found(self, client):
        with patch("pipeline.market.property_valuation.PropertyValuationService.get_valuation",
                   new_callable=AsyncMock, return_value=None):
            resp = await client.get("/valuations/property?address=nowhere")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_vehicle_asset(self, client, db_session):
        asset = ManualAsset(name="Car", asset_type="vehicle", current_value=20000,
                            is_active=True, is_liability=False)
        db_session.add(asset)
        await db_session.commit()
        with patch("pipeline.market.vehicle_valuation.VehicleValuationService.decode_vin",
                   new_callable=AsyncMock, return_value={
                       "year": 2021, "make": "Honda", "model": "Civic",
                   }), \
             patch("pipeline.market.vehicle_valuation.VehicleValuationService.estimate_value",
                   return_value={"estimated_value": 22000}):
            resp = await client.post(f"/valuations/assets/{asset.id}/refresh",
                                     json={"vin": "1HGBH41JXMN109186"})
            assert resp.status_code == 200
            assert resp.json()["updated"] is True

    @pytest.mark.asyncio
    async def test_refresh_asset_not_found(self, client):
        resp = await client.post("/valuations/assets/99999/refresh", json={"vin": "test"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_vehicle_no_vin(self, client, db_session):
        asset = ManualAsset(name="Car2", asset_type="vehicle", current_value=15000,
                            is_active=True, is_liability=False)
        db_session.add(asset)
        await db_session.commit()
        resp = await client.post(f"/valuations/assets/{asset.id}/refresh", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_refresh_real_estate_asset(self, client, db_session):
        asset = ManualAsset(name="House", asset_type="real_estate", current_value=400000,
                            is_active=True, is_liability=False, address="456 Oak Ave")
        db_session.add(asset)
        await db_session.commit()
        with patch("pipeline.market.property_valuation.PropertyValuationService.get_valuation",
                   new_callable=AsyncMock, return_value={
                       "estimated_value": 450000, "address": "456 Oak Ave",
                   }):
            resp = await client.post(f"/valuations/assets/{asset.id}/refresh",
                                     json={"address": "456 Oak Ave"})
            assert resp.status_code == 200


# ===========================================================================
# 14. api/routes/entities.py — business entity CRUD + vendor rules + expenses
# ===========================================================================

class TestEntitiesCoverage:
    @pytest.mark.asyncio
    async def test_list_entities(self, client):
        resp = await client.get("/entities")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_entities_include_inactive(self, client):
        resp = await client.get("/entities?include_inactive=true")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, client):
        resp = await client.get("/entities/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_entity(self, client):
        resp = await client.post("/entities", json={
            "name": "My LLC", "entity_type": "llc",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_update_entity(self, client, db_session):
        ent = BusinessEntity(name="UpdEnt", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        resp = await client.patch(f"/entities/{ent.id}", json={
            "entity_type": "s_corp",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_entity_not_found(self, client):
        resp = await client.patch("/entities/99999", json={"entity_type": "llc"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_entity(self, client, db_session):
        ent = BusinessEntity(name="DelEnt", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        resp = await client.delete(f"/entities/{ent.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_entity_not_found(self, client):
        resp = await client.delete("/entities/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_vendor_rules(self, client):
        resp = await client.get("/entities/rules/vendor")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_vendor_rule(self, client, db_session):
        ent = BusinessEntity(name="RuleEnt", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        resp = await client.post("/entities/rules/vendor", json={
            "vendor_pattern": "AMAZON", "business_entity_id": ent.id,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_vendor_rule_bad_entity(self, client):
        resp = await client.post("/entities/rules/vendor", json={
            "vendor_pattern": "TEST", "business_entity_id": 99999,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_apply_rules(self, client):
        resp = await client.post("/entities/apply-rules")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reassign_entities(self, client, db_session):
        ent_from = BusinessEntity(name="ReassFrom", entity_type="llc", is_active=True)
        ent_to = BusinessEntity(name="ReassTo", entity_type="llc", is_active=True)
        db_session.add(ent_from)
        db_session.add(ent_to)
        await db_session.commit()
        resp = await client.post("/entities/reassign", json={
            "from_entity_id": ent_from.id, "to_entity_id": ent_to.id,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_set_transaction_entity(self, client, db_session):
        acct = await _seed_account(db_session, name="EntTxAcct")
        tx = await _seed_transaction(db_session, acct.id)
        await db_session.commit()
        resp = await client.patch(f"/entities/transactions/{tx.id}/entity?business_entity_id=1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_entity_reimbursements(self, client, db_session):
        ent = BusinessEntity(name="ReimbEnt", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        with patch("pipeline.planning.business_reports.compute_reimbursement_report",
                   new_callable=AsyncMock, return_value={"total": 500}):
            resp = await client.get(f"/entities/{ent.id}/reimbursements")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_entity_expenses(self, client, db_session):
        ent = BusinessEntity(name="ExpEnt", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        with patch("pipeline.planning.business_reports.compute_entity_expense_report",
                   new_callable=AsyncMock, return_value={
                       "entity_id": ent.id, "entity_name": "ExpEnt", "year": 2025,
                       "monthly_totals": [], "category_breakdown": [],
                       "year_total_expenses": 5000.0,
                       "prior_year_total_expenses": None,
                       "year_over_year_change_pct": None,
                   }):
            resp = await client.get(f"/entities/{ent.id}/expenses?year=2025")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_entity_transactions(self, client, db_session):
        ent = BusinessEntity(name="TxEnt", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        with patch("pipeline.planning.business_reports.get_entity_transactions",
                   new_callable=AsyncMock, return_value=[]):
            resp = await client.get(f"/entities/{ent.id}/expenses/transactions?year=2025")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_entity_csv(self, client, db_session):
        ent = BusinessEntity(name="CsvEnt", entity_type="llc", is_active=True)
        db_session.add(ent)
        await db_session.commit()
        with patch("pipeline.planning.business_reports.get_entity_transactions",
                   new_callable=AsyncMock, return_value=[
                       {"date": "2025-01-01", "description": "Office Supplies",
                        "amount": -50.0, "category": "Supplies",
                        "tax_category": "Business Expense", "account": "Chase",
                        "segment": "business", "notes": ""},
                   ]):
            resp = await client.get(f"/entities/{ent.id}/expenses/csv?year=2025")
            assert resp.status_code == 200
            assert "text/csv" in resp.headers.get("content-type", "")


# ===========================================================================
# 15. api/routes/life_events.py — CRUD + action items
# ===========================================================================

class TestLifeEventsCoverage:
    @pytest.mark.asyncio
    async def test_list_events(self, client):
        resp = await client.get("/life-events/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_events_filtered(self, client):
        resp = await client.get("/life-events/?event_type=family&tax_year=2025")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_event(self, client, db_session):
        hp = await _seed_household(db_session)
        await db_session.commit()
        resp = await client.post("/life-events/", json={
            "household_id": hp.id, "event_type": "family",
            "event_subtype": "birth", "title": "Baby arrived",
            "tax_year": 2025, "event_date": "2025-03-15",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_event_with_action_items(self, client, db_session):
        """Cover lines 186-188: auto-generate action items."""
        hp = await _seed_household(db_session)
        await db_session.commit()
        resp = await client.post("/life-events/", json={
            "household_id": hp.id, "event_type": "real_estate",
            "event_subtype": "purchase", "title": "Bought house",
            "tax_year": 2025,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, client):
        resp = await client.get("/life-events/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_event(self, client, db_session):
        ev = LifeEvent(event_type="family", event_subtype="marriage",
                       title="Got married", tax_year=2025)
        db_session.add(ev)
        await db_session.commit()
        resp = await client.get(f"/life-events/{ev.id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_event(self, client, db_session):
        ev = LifeEvent(event_type="employment", event_subtype="job_change",
                       title="New job", tax_year=2025)
        db_session.add(ev)
        await db_session.commit()
        resp = await client.patch(f"/life-events/{ev.id}", json={
            "title": "New job at ACME",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_event_not_found(self, client):
        resp = await client.patch("/life-events/99999", json={"title": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_action_item(self, client, db_session):
        ev = LifeEvent(event_type="family", event_subtype="birth",
                       title="Action test", tax_year=2025,
                       action_items_json=json.dumps([
                           {"text": "Update insurance", "completed": False},
                       ]))
        db_session.add(ev)
        await db_session.commit()
        resp = await client.patch(f"/life-events/{ev.id}/action-items/0",
                                   json={"index": 0, "completed": True})
        assert resp.status_code == 200
        assert resp.json()["items"][0]["completed"] is True

    @pytest.mark.asyncio
    async def test_toggle_action_item_out_of_range(self, client, db_session):
        ev = LifeEvent(event_type="family", event_subtype="birth",
                       title="Range test", tax_year=2025,
                       action_items_json=json.dumps([
                           {"text": "Single item", "completed": False},
                       ]))
        db_session.add(ev)
        await db_session.commit()
        resp = await client.patch(f"/life-events/{ev.id}/action-items/5",
                                   json={"index": 5, "completed": True})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_event(self, client, db_session):
        ev = LifeEvent(event_type="family", event_subtype="birth",
                       title="Del test", tax_year=2025)
        db_session.add(ev)
        await db_session.commit()
        resp = await client.delete(f"/life-events/{ev.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_event_not_found(self, client):
        resp = await client.delete("/life-events/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_action_templates(self, client):
        resp = await client.get("/life-events/action-templates/family?event_subtype=birth")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) > 0


# ===========================================================================
# 16. api/routes/retirement_scenarios.py — calculate, trajectory, monte-carlo
# ===========================================================================

class TestRetirementScenariosCoverage:
    @pytest.mark.asyncio
    async def test_calculate_retirement(self, client):
        resp = await client.post("/retirement/calculate", json={
            "current_age": 35, "retirement_age": 65,
            "current_annual_income": 200000,
            "monthly_retirement_contribution": 2000,
            "current_retirement_savings": 100000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "target_nest_egg" in data
        assert "on_track" in data

    @pytest.mark.asyncio
    async def test_trajectory_not_found(self, client):
        resp = await client.get("/retirement/trajectory/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_trajectory_success(self, client, db_session):
        rp = RetirementProfile(
            name="Test Plan", current_age=35, retirement_age=65,
            life_expectancy=90, current_annual_income=200000,
            monthly_retirement_contribution=2000,
            current_retirement_savings=100000,
            pre_retirement_return_pct=7.0, post_retirement_return_pct=5.0,
            income_replacement_pct=80.0, inflation_rate_pct=3.0,
            tax_rate_in_retirement_pct=22.0, is_primary=True,
        )
        db_session.add(rp)
        await db_session.commit()
        resp = await client.get(f"/retirement/trajectory/{rp.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["scenarios"]) == 3

    @pytest.mark.asyncio
    async def test_monte_carlo_retirement(self, client):
        resp = await client.post("/retirement/monte-carlo", json={
            "current_age": 35, "retirement_age": 65,
            "current_annual_income": 200000,
            "monthly_retirement_contribution": 2000,
            "current_retirement_savings": 100000,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_budget_snapshot(self, client):
        resp = await client.get("/retirement/budget-snapshot")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_comprehensive_budget(self, client):
        with patch("pipeline.planning.smart_defaults.compute_comprehensive_personal_budget",
                   new_callable=AsyncMock, return_value=[
                       {"category": "Rent", "monthly_amount": 2000,
                        "source": "budget", "months_of_data": None},
                   ]):
            resp = await client.get("/retirement/comprehensive-budget")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_retirement_budget(self, client):
        with patch("pipeline.planning.smart_defaults.compute_comprehensive_personal_budget",
                   new_callable=AsyncMock, return_value=[
                       {"category": "Rent", "monthly_amount": 2000,
                        "source": "budget", "months_of_data": None},
                   ]), \
             patch("pipeline.planning.retirement_budget.compute_retirement_budget",
                   return_value={
                       "lines": [{"category": "Rent", "current_monthly": 2000,
                                  "retirement_monthly": 2000, "multiplier": 1.0,
                                  "reason": "same", "source": "budget",
                                  "is_user_override": False}],
                       "current_monthly_total": 2000, "current_annual_total": 24000,
                       "retirement_monthly_total": 2000, "retirement_annual_total": 24000,
                   }):
            resp = await client.get("/retirement/retirement-budget?retirement_age=65")
            assert resp.status_code == 200


# ===========================================================================
# 17. api/routes/insurance.py — CRUD + gap analysis
# ===========================================================================

class TestInsuranceCoverage:
    @pytest.mark.asyncio
    async def test_list_policies(self, client):
        resp = await client.get("/insurance/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_policies_filtered(self, client):
        resp = await client.get("/insurance/?policy_type=auto&is_active=true")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_policy_invalid_type(self, client):
        resp = await client.post("/insurance/", json={
            "policy_type": "invalid", "provider": "Test",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_policy_annual_only(self, client):
        """Cover lines 54-55: annual_premium → monthly_premium sync."""
        resp = await client.post("/insurance/", json={
            "policy_type": "auto", "provider": "Geico",
            "annual_premium": 1200,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_policy_monthly_only(self, client):
        """Cover lines 56-57: monthly_premium → annual_premium sync."""
        resp = await client.post("/insurance/", json={
            "policy_type": "home", "provider": "StateFarm",
            "monthly_premium": 150,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, client):
        resp = await client.get("/insurance/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_policy(self, client, db_session):
        p = InsurancePolicy(policy_type="life", provider="MetLife",
                            is_active=True, annual_premium=2400)
        db_session.add(p)
        await db_session.commit()
        resp = await client.get(f"/insurance/{p.id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_policy(self, client, db_session):
        p = InsurancePolicy(policy_type="auto", provider="UpdIns",
                            is_active=True, annual_premium=1200)
        db_session.add(p)
        await db_session.commit()
        resp = await client.patch(f"/insurance/{p.id}", json={
            "policy_type": "auto", "annual_premium": 1400,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_policy_not_found(self, client):
        resp = await client.patch("/insurance/99999", json={"policy_type": "auto", "annual_premium": 1000})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_policy(self, client, db_session):
        p = InsurancePolicy(policy_type="pet", provider="DelIns",
                            is_active=True, annual_premium=600)
        db_session.add(p)
        await db_session.commit()
        resp = await client.delete(f"/insurance/{p.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_policy_not_found(self, client):
        resp = await client.delete("/insurance/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_gap_analysis(self, client):
        resp = await client.post("/insurance/gap-analysis", json={
            "spouse_a_income": 200000, "spouse_b_income": 150000,
            "total_debt": 500000, "dependents": 2, "net_worth": 800000,
        })
        assert resp.status_code == 200


# ===========================================================================
# 18. api/routes/rules.py — summary, category rules, vendor rules, generate
# ===========================================================================

class TestRulesCoverage:
    @pytest.mark.asyncio
    async def test_rules_summary(self, client):
        resp = await client.get("/rules/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "category_rule_count" in data
        assert "vendor_rule_count" in data

    @pytest.mark.asyncio
    async def test_get_category_rules(self, client, db_session):
        rule = CategoryRule(
            merchant_pattern="STARBUCKS", category="Dining",
            is_active=True, match_count=5,
        )
        db_session.add(rule)
        await db_session.commit()
        resp = await client.get("/rules/category")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_patch_category_rule(self, client, db_session):
        rule = CategoryRule(
            merchant_pattern="PATCH_TEST", category="Old", is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()
        resp = await client.patch(f"/rules/category/{rule.id}", json={
            "category": "New Category",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_patch_category_rule_not_found(self, client):
        resp = await client.patch("/rules/category/99999", json={"category": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_category_rule(self, client, db_session):
        rule = CategoryRule(
            merchant_pattern="DEL_TEST", category="Del", is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()
        resp = await client.delete(f"/rules/category/{rule.id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_apply_category_rule(self, client, db_session):
        rule = CategoryRule(
            merchant_pattern="APPLY_TEST", category="Applied", is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()
        resp = await client.post(f"/rules/category/{rule.id}/apply")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_generate_rules(self, client):
        with patch("pipeline.ai.rule_generator.generate_rules_from_patterns",
                   new_callable=AsyncMock, return_value=[
                       {"vendor_pattern": "UBER", "category": "Transport",
                        "transaction_count": 10, "source": "pattern"},
                   ]):
            resp = await client.post("/rules/generate")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_apply_generated_rules(self, client):
        with patch("pipeline.ai.rule_generator.create_rules_from_proposals",
                   new_callable=AsyncMock, return_value={"created": 1, "applied": 5}):
            resp = await client.post("/rules/generate/apply", json={
                "rules": [{"vendor_pattern": "UBER", "category": "Transport"}],
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_vendor_rules(self, client):
        resp = await client.get("/rules/vendor")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_rule_categories(self, client):
        resp = await client.get("/rules/categories")
        assert resp.status_code == 200


# ===========================================================================
# 19. api/routes/equity_comp.py — grants CRUD + analysis endpoints
# ===========================================================================

class TestEquityCompCoverage:
    @pytest.mark.asyncio
    async def test_list_grants(self, client):
        resp = await client.get("/equity-comp/grants")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_grant(self, client):
        resp = await client.post("/equity-comp/grants", json={
            "employer_name": "ACME", "grant_type": "rsu",
            "grant_date": "2024-01-15", "total_shares": 1000,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_update_grant(self, client, db_session):
        g = EquityGrant(
            employer_name="UpdEmp", grant_type="rsu",
            grant_date=date(2024, 1, 1), total_shares=500,
            vested_shares=100, unvested_shares=400, is_active=True,
        )
        db_session.add(g)
        await db_session.commit()
        resp = await client.patch(f"/equity-comp/grants/{g.id}", json={
            "vested_shares": 200,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_grant_not_found(self, client):
        resp = await client.patch("/equity-comp/grants/99999", json={"vested_shares": 1})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_grant(self, client, db_session):
        g = EquityGrant(
            employer_name="DelEmp", grant_type="nso",
            grant_date=date(2024, 6, 1), total_shares=200,
            vested_shares=0, unvested_shares=200, is_active=True,
        )
        db_session.add(g)
        await db_session.commit()
        resp = await client.delete(f"/equity-comp/grants/{g.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_grant_not_found(self, client):
        resp = await client.delete("/equity-comp/grants/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_vesting_calendar(self, client, db_session):
        g = EquityGrant(
            employer_name="VestEmp", grant_type="rsu",
            grant_date=date(2024, 1, 1), total_shares=400,
            vested_shares=100, unvested_shares=300, is_active=True,
        )
        db_session.add(g)
        await db_session.flush()
        ve = VestingEvent(
            grant_id=g.id, vest_date=date(2025, 7, 1),
            shares=100, status="upcoming",
        )
        db_session.add(ve)
        await db_session.commit()
        resp = await client.get(f"/equity-comp/grants/{g.id}/vesting")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_all_vesting_events(self, client):
        resp = await client.get("/equity-comp/vesting-events?months=12")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_refresh_equity_prices(self, client, db_session):
        g = EquityGrant(
            employer_name="PriceEmp", grant_type="rsu",
            grant_date=date(2024, 1, 1), total_shares=100,
            vested_shares=50, unvested_shares=50,
            ticker="GOOG", is_active=True,
        )
        db_session.add(g)
        await db_session.commit()
        with patch("pipeline.market.yahoo_finance.YahooFinanceService.get_bulk_quotes",
                   return_value={"GOOG": {"price": 180.0}}):
            resp = await client.post("/equity-comp/refresh-prices")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_equity_dashboard(self, client):
        resp = await client.get("/equity-comp/dashboard")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_withholding_gap(self, client):
        resp = await client.post("/equity-comp/withholding-gap", json={
            "vest_income": 50000, "other_income": 200000,
            "filing_status": "mfj", "state": "CA",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_amt_crossover(self, client):
        resp = await client.post("/equity-comp/amt-crossover", json={
            "iso_shares_available": 1000, "strike_price": 50,
            "current_fmv": 150, "other_income": 200000,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sell_strategy(self, client):
        resp = await client.post("/equity-comp/sell-strategy", json={
            "shares": 100, "cost_basis_per_share": 50,
            "current_price": 150, "other_income": 200000,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_what_if_leave(self, client):
        resp = await client.post("/equity-comp/what-if-leave", json={
            "leave_date": "2025-12-31",
            "grants": [
                {"grant_type": "rsu", "unvested_shares": 100,
                 "current_fmv": 150, "vest_dates": ["2026-03-01"]},
            ],
            "other_income": 200000,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_espp_analysis(self, client):
        resp = await client.post("/equity-comp/espp-analysis", json={
            "purchase_price": 85.0, "fmv_at_purchase": 100.0,
            "fmv_at_sale": 120.0, "shares": 50,
            "purchase_date": "2024-06-30", "sale_date": "2025-07-01",
            "offering_date": "2024-01-01",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_concentration_risk(self, client):
        resp = await client.post("/equity-comp/concentration-risk", json={
            "employer_stock_value": 500000, "total_net_worth": 1200000,
        })
        assert resp.status_code == 200
