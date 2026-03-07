"""
End-to-end integration tests against the full demo database.

Seeds the complete Michael & Jessica Chen demo household (13 accounts,
2400+ transactions, budgets, retirement, insurance, equity, goals, etc.)
into an in-memory SQLite database and verifies every major API endpoint
returns populated data.
"""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base


# ---------------------------------------------------------------------------
# Module-scoped fixtures — seed demo data ONCE for all tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def demo_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def demo_session_factory(demo_engine):
    return async_sessionmaker(demo_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="module")
async def demo_seed(demo_session_factory):
    """Run migrations and seed demo data once for the entire module."""
    from pipeline.db.migrations import run_migrations
    from pipeline.demo.seeder import seed_demo_data

    # run_migrations manages its own commits internally
    async with demo_session_factory() as session:
        await run_migrations(session)

    # seed_demo_data manages its own flushes; we commit at the end
    async with demo_session_factory() as session:
        counts = await seed_demo_data(session)
        await session.commit()

    return counts


@pytest_asyncio.fixture(scope="module")
async def demo_app(demo_session_factory, demo_seed):
    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)

    # Register all routers (mirroring api/main.py:269-311)
    from api.routes import (
        account_links, accounts, assets, auth_routes, benchmarks, budget,
        chat, demo, documents, entities,
        equity_comp, family_members, goal_suggestions, goals,
        household,
        import_routes, income, insights, insurance,
        life_events, market, plaid, privacy,
        portfolio,
        recurring, reminders, reports, retirement, rules,
        scenarios, setup_status, smart_defaults, tax,
        tax_modeling, transactions, user_context, valuations,
    )

    app.include_router(account_links.router)
    app.include_router(accounts.router)
    app.include_router(assets.router)
    app.include_router(transactions.router)
    app.include_router(documents.router)
    app.include_router(entities.router)
    app.include_router(import_routes.router)
    app.include_router(reports.router)
    app.include_router(insights.router)
    app.include_router(tax.router)
    app.include_router(plaid.router)
    app.include_router(budget.router)
    app.include_router(recurring.router)
    app.include_router(goal_suggestions.router)
    app.include_router(goals.router)
    app.include_router(reminders.router)
    app.include_router(chat.router)
    app.include_router(portfolio.router)
    app.include_router(market.router)
    app.include_router(retirement.router)
    app.include_router(scenarios.router)
    app.include_router(equity_comp.router)
    app.include_router(household.router)
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
    app.include_router(auth_routes.router)
    app.include_router(demo.router)

    from api.database import get_session

    async def override_get_session():
        async with demo_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest_asyncio.fixture(scope="module")
async def client(demo_app):
    async with AsyncClient(
        transport=ASGITransport(app=demo_app),
        base_url="http://test",
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Seed verification
# ---------------------------------------------------------------------------

class TestDemoSeed:
    async def test_seed_returned_counts(self, demo_seed):
        counts = demo_seed
        assert counts.get("households", 0) >= 1
        assert counts.get("accounts", 0) >= 10
        assert counts.get("transactions", 0) >= 100


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

class TestDemoAccounts:
    async def test_list_accounts(self, client):
        resp = await client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 10
        names = [a["name"] for a in data]
        assert any("Chase" in n for n in names)

    async def test_account_has_required_fields(self, client):
        resp = await client.get("/accounts")
        acct = resp.json()[0]
        assert "id" in acct
        assert "name" in acct
        assert "institution" in acct
        assert "account_type" in acct


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TestDemoTransactions:
    async def test_list_transactions(self, client):
        resp = await client.get("/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    async def test_transactions_have_categories(self, client):
        resp = await client.get("/transactions")
        data = resp.json()
        # Response is TransactionListOut with .items list
        txns = data.get("items", data) if isinstance(data, dict) else data
        categorized = [t for t in txns if t.get("effective_category")]
        assert len(categorized) > 0


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

class TestDemoBudget:
    async def test_list_budgets(self, client):
        resp = await client.get("/budget", params={"year": 2026, "month": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_budget_categories(self, client):
        resp = await client.get("/budget/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    async def test_budget_summary(self, client):
        resp = await client.get("/budget/summary", params={"year": 2026, "month": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Household & Family
# ---------------------------------------------------------------------------

class TestDemoHousehold:
    async def test_list_profiles(self, client):
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 1
        p = profiles[0]
        assert p["filing_status"] == "mfj"
        assert p["state"] == "NY"
        assert p["combined_income"] >= 400000

    async def test_family_members(self, client):
        resp = await client.get("/family-members/")
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) >= 3
        names = [m["name"] for m in members]
        assert any("Michael" in n for n in names)
        assert any("Jessica" in n for n in names)


# ---------------------------------------------------------------------------
# Setup Status
# ---------------------------------------------------------------------------

class TestDemoSetup:
    async def test_setup_status_complete(self, client):
        resp = await client.get("/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["household"] is True
        assert data["income"] is True
        assert data["accounts"] is True
        assert data["complete"] is True


# ---------------------------------------------------------------------------
# Insurance
# ---------------------------------------------------------------------------

class TestDemoInsurance:
    async def test_list_policies(self, client):
        resp = await client.get("/insurance/")
        assert resp.status_code == 200
        policies = resp.json()
        assert len(policies) >= 3
        types = {p["policy_type"] for p in policies}
        # Demo household should have multiple policy types
        assert len(types) >= 2


# ---------------------------------------------------------------------------
# Recurring
# ---------------------------------------------------------------------------

class TestDemoRecurring:
    async def test_list_recurring(self, client):
        resp = await client.get("/recurring")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 10

    async def test_recurring_summary(self, client):
        resp = await client.get("/recurring/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_monthly_cost"] > 0
        assert data["total_annual_cost"] > 0


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

class TestDemoGoals:
    async def test_list_goals(self, client):
        resp = await client.get("/goals")
        assert resp.status_code == 200
        goals = resp.json()
        assert len(goals) >= 3


# ---------------------------------------------------------------------------
# Equity Compensation
# ---------------------------------------------------------------------------

class TestDemoEquityComp:
    async def test_list_grants(self, client):
        resp = await client.get("/equity-comp/grants")
        assert resp.status_code == 200
        grants = resp.json()
        assert len(grants) >= 1

    async def test_dashboard(self, client):
        resp = await client.get("/equity-comp/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class TestDemoPortfolio:
    async def test_portfolio_summary(self, client):
        resp = await client.get("/portfolio/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] > 0
        assert data["holdings_count"] > 0

    async def test_target_allocation(self, client):
        resp = await client.get("/portfolio/target-allocation")
        assert resp.status_code == 200
        data = resp.json()
        assert "allocation" in data

    async def test_net_worth_trend(self, client):
        resp = await client.get("/portfolio/net-worth-trend")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data or "data" in data or isinstance(data, dict)

    async def test_allocation_presets(self, client):
        resp = await client.get("/portfolio/target-allocation/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert len(data["presets"]) == 3


# ---------------------------------------------------------------------------
# Tax
# ---------------------------------------------------------------------------

class TestDemoTax:
    async def test_tax_summary(self, client):
        resp = await client.get("/tax/summary", params={"tax_year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_tax_checklist(self, client):
        resp = await client.get("/tax/checklist", params={"tax_year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) > 0


# ---------------------------------------------------------------------------
# Retirement
# ---------------------------------------------------------------------------

class TestDemoRetirement:
    async def test_list_profiles(self, client):
        resp = await client.get("/retirement/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 1


# ---------------------------------------------------------------------------
# Life Events
# ---------------------------------------------------------------------------

class TestDemoLifeEvents:
    async def test_list_events(self, client):
        resp = await client.get("/life-events/")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

class TestDemoBenchmarks:
    async def test_snapshot(self, client):
        resp = await client.get("/benchmarks/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_order_of_operations(self, client):
        resp = await client.get("/benchmarks/order-of-operations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, list):
            assert len(data) > 0


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

class TestDemoScenarios:
    async def test_templates(self, client):
        resp = await client.get("/scenarios/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class TestDemoRules:
    async def test_rules_summary(self, client):
        resp = await client.get("/rules/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_category_rules(self, client):
        resp = await client.get("/rules/category")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert isinstance(data["rules"], list)
