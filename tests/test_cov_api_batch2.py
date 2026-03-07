"""
Comprehensive API route coverage tests — batch 2.

Covers: entities, equity_comp, family_members, goals, goal_suggestions,
        household, household_optimization.
"""
import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipeline.db.schema import (
    Base,
    BusinessEntity,
    VendorEntityRule,
    EquityGrant,
    VestingEvent,
    EquityTaxProjection,
    FamilyMember,
    Goal,
    HouseholdProfile,
    BenefitPackage,
    HouseholdOptimization,
    InsurancePolicy,
    LifeEvent,
    ManualAsset,
    PlaidAccount,
    Account,
    PlaidItem,
)
from api.database import get_session


# ---------------------------------------------------------------------------
# Shared fixtures
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


# ============================================================================
# 1. api/routes/entities.py
# ============================================================================

class TestEntities:

    @pytest_asyncio.fixture
    async def client(self, db_factory):
        from api.routes.entities import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = _override_session(db_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_list_entities_empty(self, client):
        resp = await client.get("/entities")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_entity(self, client):
        resp = await client.post("/entities", json={
            "name": "TestBiz",
            "entity_type": "sole_prop",
            "tax_treatment": "schedule_c",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TestBiz"
        assert data["entity_type"] == "sole_prop"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_entities_with_data(self, client):
        resp = await client.get("/entities")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

    @pytest.mark.asyncio
    async def test_list_entities_include_inactive(self, client):
        resp = await client.get("/entities?include_inactive=true")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_entity(self, client):
        # Create an entity first
        create_resp = await client.post("/entities", json={"name": "GetBiz"})
        eid = create_resp.json()["id"]
        resp = await client.get(f"/entities/{eid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetBiz"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, client):
        resp = await client.get("/entities/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_entity(self, client):
        create_resp = await client.post("/entities", json={"name": "PatchBiz"})
        eid = create_resp.json()["id"]
        resp = await client.patch(f"/entities/{eid}", json={"entity_type": "llc"})
        assert resp.status_code == 200
        assert resp.json()["entity_type"] == "llc"

    @pytest.mark.asyncio
    async def test_update_entity_not_found(self, client):
        resp = await client.patch("/entities/99999", json={"entity_type": "llc"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_entity(self, client):
        create_resp = await client.post("/entities", json={"name": "DeleteBiz"})
        eid = create_resp.json()["id"]
        resp = await client.delete(f"/entities/{eid}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_entity_not_found(self, client):
        resp = await client.delete("/entities/99999")
        assert resp.status_code == 404

    # --- Vendor Entity Rules ---

    @pytest.mark.asyncio
    async def test_list_vendor_rules_empty(self, client):
        resp = await client.get("/entities/rules/vendor")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_vendor_rule(self, client):
        # Create entity first
        ent = await client.post("/entities", json={"name": "RuleBiz"})
        eid = ent.json()["id"]
        resp = await client.post("/entities/rules/vendor", json={
            "vendor_pattern": "ACME*",
            "business_entity_id": eid,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["vendor_pattern"] == "ACME*"
        assert data["business_entity_id"] == eid

    @pytest.mark.asyncio
    async def test_create_vendor_rule_bad_entity(self, client):
        resp = await client.post("/entities/rules/vendor", json={
            "vendor_pattern": "BAD*",
            "business_entity_id": 99999,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_vendor_rules_with_entity_filter(self, client):
        resp = await client.get("/entities/rules/vendor?entity_id=1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_vendor_rule(self, client):
        ent = await client.post("/entities", json={"name": "DelRuleBiz"})
        eid = ent.json()["id"]
        rule = await client.post("/entities/rules/vendor", json={
            "vendor_pattern": "DEL*",
            "business_entity_id": eid,
        })
        rid = rule.json()["id"]
        resp = await client.delete(f"/entities/rules/vendor/{rid}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_vendor_rule_not_found(self, client):
        resp = await client.delete("/entities/rules/vendor/99999")
        assert resp.status_code == 404

    # --- Apply rules / Reassign / Set entity ---

    @pytest.mark.asyncio
    async def test_apply_rules(self, client):
        resp = await client.post("/entities/apply-rules")
        assert resp.status_code == 200
        assert "updated" in resp.json()

    @pytest.mark.asyncio
    async def test_apply_rules_with_params(self, client):
        resp = await client.post("/entities/apply-rules?year=2025&month=1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reassign_entities(self, client):
        resp = await client.post("/entities/reassign", json={
            "from_entity_id": 1,
            "to_entity_id": 2,
        })
        assert resp.status_code == 200
        assert "reassigned" in resp.json()

    @pytest.mark.asyncio
    async def test_set_transaction_entity(self, client):
        resp = await client.patch("/entities/transactions/1/entity?business_entity_id=1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_set_transaction_entity_null(self, client):
        resp = await client.patch("/entities/transactions/1/entity")
        assert resp.status_code == 200

    # --- Expense Reporting ---

    @pytest.mark.asyncio
    async def test_get_entity_reimbursements_success(self, client):
        with patch(
            "pipeline.planning.business_reports.compute_reimbursement_report",
            new_callable=AsyncMock,
            return_value={"entity_id": 1, "total": 500.0, "items": []},
        ):
            ent = await client.post("/entities", json={"name": "ReimbBiz"})
            eid = ent.json()["id"]
            resp = await client.get(f"/entities/{eid}/reimbursements")
            assert resp.status_code == 200
            assert resp.json()["total"] == 500.0

    @pytest.mark.asyncio
    async def test_get_entity_reimbursements_error(self, client):
        with patch(
            "pipeline.planning.business_reports.compute_reimbursement_report",
            new_callable=AsyncMock,
            return_value={"error": "Entity not found"},
        ):
            resp = await client.get("/entities/1/reimbursements")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_entity_expenses_success(self, client):
        with patch(
            "pipeline.planning.business_reports.compute_entity_expense_report",
            new_callable=AsyncMock,
            return_value={
                "entity_id": 1,
                "entity_name": "TestBiz",
                "year": 2025,
                "monthly_totals": [],
                "category_breakdown": [],
                "year_total_expenses": 1000.0,
                "prior_year_total_expenses": None,
                "year_over_year_change_pct": None,
            },
        ):
            ent = await client.post("/entities", json={"name": "ExpBiz"})
            eid = ent.json()["id"]
            resp = await client.get(f"/entities/{eid}/expenses?year=2025")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_entity_expenses_error(self, client):
        with patch(
            "pipeline.planning.business_reports.compute_entity_expense_report",
            new_callable=AsyncMock,
            return_value={"error": "Entity not found"},
        ):
            resp = await client.get("/entities/1/expenses?year=2025")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_entity_transactions_success(self, client):
        with patch(
            "pipeline.planning.business_reports.get_entity_transactions",
            new_callable=AsyncMock,
            return_value=[],
        ):
            ent = await client.post("/entities", json={"name": "TxListBiz"})
            eid = ent.json()["id"]
            resp = await client.get(f"/entities/{eid}/expenses/transactions?year=2025")
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_entity_transactions_not_found(self, client):
        resp = await client.get("/entities/99999/expenses/transactions?year=2025")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_csv_success(self, client):
        tx_data = [
            {
                "date": "2025-01-15",
                "description": "Office Supplies",
                "amount": 50.0,
                "category": "Supplies",
                "tax_category": "Office Expense",
                "account": "Checking",
                "segment": "business",
                "notes": "",
            }
        ]
        with patch(
            "pipeline.planning.business_reports.get_entity_transactions",
            new_callable=AsyncMock,
            return_value=tx_data,
        ):
            ent = await client.post("/entities", json={"name": "CSVBiz"})
            eid = ent.json()["id"]
            resp = await client.get(f"/entities/{eid}/expenses/csv?year=2025")
            assert resp.status_code == 200
            assert "text/csv" in resp.headers["content-type"]
            assert "CSVBiz" in resp.headers["content-disposition"]

    @pytest.mark.asyncio
    async def test_export_csv_with_month(self, client):
        with patch(
            "pipeline.planning.business_reports.get_entity_transactions",
            new_callable=AsyncMock,
            return_value=[],
        ):
            ent = await client.post("/entities", json={"name": "CSVMonthBiz"})
            eid = ent.json()["id"]
            resp = await client.get(f"/entities/{eid}/expenses/csv?year=2025&month=3")
            assert resp.status_code == 200
            assert "2025-03" in resp.headers["content-disposition"]

    @pytest.mark.asyncio
    async def test_export_csv_not_found(self, client):
        resp = await client.get("/entities/99999/expenses/csv?year=2025")
        assert resp.status_code == 404


# ============================================================================
# 2. api/routes/equity_comp.py
# ============================================================================

class TestEquityComp:

    @pytest_asyncio.fixture
    async def client(self, db_factory):
        from api.routes.equity_comp import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = _override_session(db_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    # --- Grant CRUD ---

    @pytest.mark.asyncio
    async def test_list_grants_empty(self, client):
        resp = await client.get("/equity-comp/grants")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_grant(self, client):
        resp = await client.post("/equity-comp/grants", json={
            "employer_name": "TechCo",
            "grant_type": "rsu",
            "grant_date": "2024-01-15",
            "total_shares": 1000,
            "vested_shares": 0,
            "unvested_shares": 0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["employer_name"] == "TechCo"
        # When both vested and unvested are 0, unvested should be set to total
        assert data["unvested_shares"] == 1000

    @pytest.mark.asyncio
    async def test_create_grant_with_vested(self, client):
        resp = await client.post("/equity-comp/grants", json={
            "employer_name": "TechCo2",
            "grant_type": "iso",
            "grant_date": "2024-06-01",
            "total_shares": 500,
            "vested_shares": 200,
            "unvested_shares": 300,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["vested_shares"] == 200
        assert data["unvested_shares"] == 300

    @pytest.mark.asyncio
    async def test_list_grants_active_only(self, client):
        resp = await client.get("/equity-comp/grants?active_only=true")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

    @pytest.mark.asyncio
    async def test_list_grants_all(self, client):
        resp = await client.get("/equity-comp/grants?active_only=false")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_grant(self, client):
        create = await client.post("/equity-comp/grants", json={
            "employer_name": "PatchCo",
            "grant_type": "nso",
            "grant_date": "2024-01-01",
            "total_shares": 100,
        })
        gid = create.json()["id"]
        resp = await client.patch(f"/equity-comp/grants/{gid}", json={
            "employer_name": "PatchCoUpdated",
            "current_fmv": 50.0,
        })
        assert resp.status_code == 200
        assert resp.json()["employer_name"] == "PatchCoUpdated"
        assert resp.json()["current_fmv"] == 50.0

    @pytest.mark.asyncio
    async def test_update_grant_not_found(self, client):
        resp = await client.patch("/equity-comp/grants/99999", json={"current_fmv": 10.0})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_grant(self, client):
        create = await client.post("/equity-comp/grants", json={
            "employer_name": "DeleteCo",
            "grant_type": "rsu",
            "grant_date": "2024-01-01",
            "total_shares": 50,
        })
        gid = create.json()["id"]
        resp = await client.delete(f"/equity-comp/grants/{gid}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_grant_not_found(self, client):
        resp = await client.delete("/equity-comp/grants/99999")
        assert resp.status_code == 404

    # --- Vesting calendar ---

    @pytest.mark.asyncio
    async def test_get_vesting_calendar_empty(self, client):
        create = await client.post("/equity-comp/grants", json={
            "employer_name": "VestCo",
            "grant_type": "rsu",
            "grant_date": "2024-01-01",
            "total_shares": 400,
        })
        gid = create.json()["id"]
        resp = await client.get(f"/equity-comp/grants/{gid}/vesting")
        assert resp.status_code == 200
        assert resp.json() == []

    # --- All vesting events ---

    @pytest.mark.asyncio
    async def test_all_vesting_events(self, client, db_session):
        # Create grant with vesting events
        grant = EquityGrant(
            employer_name="VestEventsCo",
            grant_type="rsu",
            grant_date=date(2024, 1, 1),
            total_shares=400,
            vested_shares=0,
            unvested_shares=400,
            current_fmv=100.0,
            is_active=True,
            ticker="VEST",
        )
        db_session.add(grant)
        await db_session.flush()

        # Add a future vesting event
        from datetime import timedelta
        future_date = date.today() + timedelta(days=60)
        event = VestingEvent(
            grant_id=grant.id,
            vest_date=future_date,
            shares=100,
            status="upcoming",
        )
        db_session.add(event)
        await db_session.commit()

        resp = await client.get("/equity-comp/vesting-events?months=6")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "months" in data

    # --- Refresh prices ---

    @pytest.mark.asyncio
    async def test_refresh_prices_no_tickers(self, client, db_session):
        """When no active grants have tickers, should return updated=0."""
        # Deactivate all grants with tickers to isolate this test
        result = await db_session.execute(
            select(EquityGrant).where(EquityGrant.ticker.isnot(None), EquityGrant.is_active.is_(True))
        )
        for g in result.scalars():
            g.is_active = False
        # Create grant with no ticker
        grant = EquityGrant(
            employer_name="NoTickerCo",
            grant_type="rsu",
            grant_date=date(2024, 1, 1),
            total_shares=100,
            vested_shares=0,
            unvested_shares=100,
            is_active=True,
            ticker=None,
        )
        db_session.add(grant)
        await db_session.commit()
        resp = await client.post("/equity-comp/refresh-prices")
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0

        # Re-activate grants for other tests
        result = await db_session.execute(select(EquityGrant))
        for g in result.scalars():
            g.is_active = True
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_refresh_prices_with_ticker(self, client, db_session):
        grant = EquityGrant(
            employer_name="TickerCo",
            grant_type="rsu",
            grant_date=date(2024, 1, 1),
            total_shares=100,
            vested_shares=0,
            unvested_shares=100,
            is_active=True,
            ticker="AAPL",
            current_fmv=150.0,
        )
        db_session.add(grant)
        await db_session.commit()

        mock_quotes = {"AAPL": {"price": 200.0}}
        with patch(
            "pipeline.market.yahoo_finance.YahooFinanceService.get_bulk_quotes",
            return_value=mock_quotes,
        ):
            resp = await client.post("/equity-comp/refresh-prices")
            assert resp.status_code == 200
            data = resp.json()
            assert data["updated"] >= 1
            assert "AAPL" in data["tickers"]

    # --- Dashboard ---

    @pytest.mark.asyncio
    async def test_equity_dashboard(self, client, db_session):
        # Create a grant with vesting for dashboard
        grant = EquityGrant(
            employer_name="DashCo",
            grant_type="rsu",
            grant_date=date(2024, 1, 1),
            total_shares=1000,
            vested_shares=500,
            unvested_shares=500,
            current_fmv=50.0,
            is_active=True,
        )
        db_session.add(grant)
        await db_session.flush()

        # Add upcoming vesting event
        from datetime import timedelta
        event = VestingEvent(
            grant_id=grant.id,
            vest_date=date.today() + timedelta(days=90),
            shares=100,
            status="upcoming",
        )
        db_session.add(event)
        await db_session.commit()

        resp = await client.get("/equity-comp/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_equity_value" in data
        assert "upcoming_vest_value_12mo" in data
        assert "grants" in data
        assert data["grants_count"] >= 1

    @pytest.mark.asyncio
    async def test_equity_dashboard_with_options(self, client, db_session):
        """Test dashboard with ISO/NSO grants that use spread calculation."""
        grant = EquityGrant(
            employer_name="ISOCo",
            grant_type="iso",
            grant_date=date(2024, 1, 1),
            total_shares=200,
            vested_shares=100,
            unvested_shares=100,
            current_fmv=100.0,
            strike_price=50.0,
            is_active=True,
        )
        db_session.add(grant)
        await db_session.commit()

        resp = await client.get("/equity-comp/dashboard")
        assert resp.status_code == 200

    # --- Analysis endpoints ---

    @pytest.mark.asyncio
    async def test_withholding_gap(self, client):
        resp = await client.post("/equity-comp/withholding-gap", json={
            "vest_income": 100000,
            "other_income": 200000,
            "filing_status": "mfj",
            "state": "CA",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "withholding_gap" in data

    @pytest.mark.asyncio
    async def test_amt_crossover(self, client):
        resp = await client.post("/equity-comp/amt-crossover", json={
            "iso_shares_available": 5000,
            "strike_price": 10.0,
            "current_fmv": 50.0,
            "other_income": 200000,
            "filing_status": "mfj",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sell_strategy(self, client):
        resp = await client.post("/equity-comp/sell-strategy", json={
            "shares": 500,
            "cost_basis_per_share": 10.0,
            "current_price": 50.0,
            "other_income": 200000,
            "filing_status": "mfj",
            "holding_period_months": 6,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendation" in data

    @pytest.mark.asyncio
    async def test_what_if_leave(self, client):
        resp = await client.post("/equity-comp/what-if-leave", json={
            "leave_date": "2025-06-01",
            "grants": [
                {
                    "grant_type": "rsu",
                    "unvested_shares": 500,
                    "current_fmv": 100.0,
                    "vesting_schedule": [],
                }
            ],
            "other_income": 200000,
            "filing_status": "mfj",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_espp_analysis(self, client):
        resp = await client.post("/equity-comp/espp-analysis", json={
            "purchase_price": 85.0,
            "fmv_at_purchase": 100.0,
            "fmv_at_sale": 120.0,
            "shares": 100,
            "purchase_date": "2024-01-15",
            "sale_date": "2025-06-15",
            "offering_date": "2024-01-01",
            "discount_pct": 15.0,
            "other_income": 200000,
            "filing_status": "mfj",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_concentration_risk(self, client):
        resp = await client.post("/equity-comp/concentration-risk", json={
            "employer_stock_value": 500000,
            "total_net_worth": 1000000,
        })
        assert resp.status_code == 200


# ============================================================================
# 3. api/routes/family_members.py
# ============================================================================

class TestFamilyMembers:

    @pytest_asyncio.fixture
    async def client(self, db_factory):
        from api.routes.family_members import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = _override_session(db_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    @pytest_asyncio.fixture
    async def household(self, db_session):
        hp = HouseholdProfile(
            name="Test Family",
            filing_status="mfj",
            state="CA",
            spouse_a_income=150000,
            spouse_b_income=100000,
            combined_income=250000,
            is_primary=True,
        )
        db_session.add(hp)
        await db_session.commit()
        await db_session.refresh(hp)
        return hp

    @pytest.mark.asyncio
    async def test_list_family_members_empty(self, client):
        resp = await client.get("/family-members/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_create_family_member(self, mock_sync, client, household):
        resp = await client.post("/family-members/", json={
            "household_id": household.id,
            "name": "John Doe",
            "relationship": "self",
            "is_earner": True,
            "income": 150000,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "John Doe"
        assert data["relationship"] == "self"
        mock_sync.assert_called()

    @pytest.mark.asyncio
    async def test_create_family_member_no_household(self, client):
        resp = await client.post("/family-members/", json={
            "household_id": 99999,
            "name": "Orphan",
            "relationship": "self",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_create_duplicate_self(self, mock_sync, client, household):
        # Create first "self"
        await client.post("/family-members/", json={
            "household_id": household.id,
            "name": "Alice",
            "relationship": "self",
        })
        # Try to create another "self"
        resp = await client.post("/family-members/", json={
            "household_id": household.id,
            "name": "Bob",
            "relationship": "self",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_create_child(self, mock_sync, client, household):
        """Non-self/spouse relationship should work without conflict checks."""
        resp = await client.post("/family-members/", json={
            "household_id": household.id,
            "name": "Kid",
            "relationship": "child",
            "date_of_birth": "2020-05-01",
            "care_cost_annual": 15000,
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Kid"

    @pytest.mark.asyncio
    async def test_list_family_members_with_household_filter(self, client, household):
        resp = await client.get(f"/family-members/?household_id={household.id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_family_member(self, client, db_session, household):
        member = FamilyMember(
            household_id=household.id,
            name="GetMe",
            relationship="other",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        resp = await client.get(f"/family-members/{member.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetMe"

    @pytest.mark.asyncio
    async def test_get_family_member_not_found(self, client):
        resp = await client.get("/family-members/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_update_family_member(self, mock_sync, client, db_session, household):
        member = FamilyMember(
            household_id=household.id,
            name="PatchMe",
            relationship="other",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        resp = await client.patch(f"/family-members/{member.id}", json={
            "name": "PatchedName",
            "income": 50000,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "PatchedName"
        mock_sync.assert_called()

    @pytest.mark.asyncio
    async def test_update_family_member_not_found(self, client):
        resp = await client.patch("/family-members/99999", json={"name": "Nope"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("api.routes.family_members.sync_household_from_members", new_callable=AsyncMock)
    async def test_delete_family_member(self, mock_sync, client, db_session, household):
        member = FamilyMember(
            household_id=household.id,
            name="DeleteMe",
            relationship="other",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        resp = await client.delete(f"/family-members/{member.id}")
        assert resp.status_code == 204
        mock_sync.assert_called()

    @pytest.mark.asyncio
    async def test_delete_family_member_not_found(self, client):
        resp = await client.delete("/family-members/99999")
        assert resp.status_code == 404

    # --- Milestones ---

    @pytest.mark.asyncio
    @patch("api.routes.family_members.compute_milestones", return_value=[{"milestone": "College", "year": 2038}])
    async def test_get_milestones(self, mock_milestones, client, db_session, household):
        member = FamilyMember(
            household_id=household.id,
            name="MilestoneKid",
            relationship="child",
            date_of_birth=date(2020, 6, 1),
        )
        db_session.add(member)
        await db_session.commit()

        resp = await client.get(f"/family-members/milestones/by-household?household_id={household.id}")
        assert resp.status_code == 200
        mock_milestones.assert_called_once()


# ============================================================================
# 4. api/routes/goals.py
# ============================================================================

class TestGoals:

    @pytest_asyncio.fixture
    async def client(self, db_factory):
        from api.routes.goals import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = _override_session(db_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_list_goals_empty(self, client):
        resp = await client.get("/goals")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_goal_basic(self, client):
        resp = await client.post("/goals", json={
            "name": "Emergency Fund",
            "goal_type": "emergency_fund",
            "target_amount": 50000,
            "current_amount": 10000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Emergency Fund"
        assert data["progress_pct"] == 20.0

    @pytest.mark.asyncio
    async def test_create_goal_with_target_date(self, client):
        resp = await client.post("/goals", json={
            "name": "House Down Payment",
            "goal_type": "purchase",
            "target_amount": 100000,
            "current_amount": 20000,
            "target_date": "2028-06-15T00:00:00",
            "monthly_contribution": 3000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["months_remaining"] is not None
        assert data["on_track"] is not None

    @pytest.mark.asyncio
    async def test_create_goal_no_target_date(self, client):
        resp = await client.post("/goals", json={
            "name": "Fun Money",
            "goal_type": "savings",
            "target_amount": 5000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["on_track"] is None
        assert data["months_remaining"] is None

    @pytest.mark.asyncio
    async def test_list_goals_with_account_linked(self, client, db_session):
        """Test auto-update of current_amount for account-linked goals."""
        # Create an account and PlaidAccount
        acct = Account(
            name="Savings",
            account_type="depository",
            currency="USD",
            is_active=True,
        )
        db_session.add(acct)
        await db_session.flush()

        plaid_item = PlaidItem(
            item_id="plaid_item_test_123",
            institution_name="TestBank",
            institution_id="ins_test",
            access_token="test-token",
            status="active",
        )
        db_session.add(plaid_item)
        await db_session.flush()

        plaid_acct = PlaidAccount(
            plaid_item_id=plaid_item.id,
            account_id=acct.id,
            plaid_account_id="plaid_acct_123",
            name="Savings Account",
            type="depository",
            current_balance=25000.0,
        )
        db_session.add(plaid_acct)
        await db_session.flush()

        goal = Goal(
            name="Linked Goal",
            goal_type="savings",
            target_amount=50000,
            current_amount=0,
            status="active",
            account_id=plaid_acct.id,
        )
        db_session.add(goal)
        await db_session.commit()

        resp = await client.get("/goals")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_goals_with_manual_asset_link(self, client, db_session):
        """Test auto-update from ManualAsset when PlaidAccount not found.

        This exercises the fallback path: lines 69-74 of goals.py where
        a goal's account_id doesn't match any PlaidAccount, but DOES
        match a ManualAsset.
        """
        from sqlalchemy import delete as sa_delete

        # Remove all PlaidAccounts to ensure no PlaidAccount match
        await db_session.execute(sa_delete(PlaidAccount))
        await db_session.flush()

        asset = ManualAsset(
            name="Investment Account For Goal",
            asset_type="investment",
            current_value=75000.0,
            is_active=True,
        )
        db_session.add(asset)
        await db_session.flush()

        goal = Goal(
            name="Asset Linked Goal Unique",
            goal_type="investment",
            target_amount=100000,
            current_amount=0,
            status="active",
            account_id=asset.id,
        )
        db_session.add(goal)
        await db_session.commit()

        resp = await client.get("/goals")
        assert resp.status_code == 200
        goals = resp.json()
        our_goal = next((g for g in goals if g["name"] == "Asset Linked Goal Unique"), None)
        assert our_goal is not None
        # The current_amount should have been updated from ManualAsset
        assert our_goal["current_amount"] == 75000.0

    @pytest.mark.asyncio
    async def test_update_goal(self, client):
        create = await client.post("/goals", json={
            "name": "Update Goal",
            "goal_type": "savings",
            "target_amount": 10000,
        })
        gid = create.json()["id"]
        resp = await client.patch(f"/goals/{gid}", json={
            "current_amount": 5000,
            "name": "Updated Goal",
        })
        assert resp.status_code == 200
        assert resp.json()["current_amount"] == 5000
        assert resp.json()["name"] == "Updated Goal"

    @pytest.mark.asyncio
    async def test_update_goal_completed(self, client):
        create = await client.post("/goals", json={
            "name": "Complete Me",
            "goal_type": "savings",
            "target_amount": 1000,
        })
        gid = create.json()["id"]
        resp = await client.patch(f"/goals/{gid}", json={
            "status": "completed",
            "current_amount": 1000,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_goal_with_target_date(self, client):
        create = await client.post("/goals", json={
            "name": "Date Goal",
            "goal_type": "savings",
            "target_amount": 5000,
        })
        gid = create.json()["id"]
        resp = await client.patch(f"/goals/{gid}", json={
            "target_date": "2030-12-31T00:00:00",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_goal_not_found(self, client):
        resp = await client.patch("/goals/99999", json={"name": "Nope"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_goal(self, client):
        create = await client.post("/goals", json={
            "name": "Delete Goal",
            "goal_type": "savings",
            "target_amount": 1000,
        })
        gid = create.json()["id"]
        resp = await client.delete(f"/goals/{gid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == gid

    @pytest.mark.asyncio
    async def test_goal_zero_target(self, client):
        """Goal with zero target_amount should not divide by zero."""
        resp = await client.post("/goals", json={
            "name": "Zero Target",
            "goal_type": "savings",
            "target_amount": 0,
            "current_amount": 100,
        })
        assert resp.status_code == 200
        assert resp.json()["progress_pct"] == 0.0


# ============================================================================
# 5. api/routes/goal_suggestions.py
# ============================================================================

class TestGoalSuggestions:

    @pytest_asyncio.fixture
    async def client(self, db_factory):
        from api.routes.goal_suggestions import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = _override_session(db_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_suggestions_returns_all_types(self, client, db_session):
        """Should return all suggestion types when no existing goals."""
        from sqlalchemy import delete as sa_delete
        # Clear all existing goals so every suggestion type is generated
        await db_session.execute(sa_delete(Goal))
        # Clear existing equity grants so RSU suggestion is not generated
        await db_session.execute(sa_delete(VestingEvent))
        await db_session.execute(sa_delete(EquityGrant))
        # Clear ManualAssets to avoid student loan suggestions
        await db_session.execute(sa_delete(ManualAsset))
        await db_session.commit()

        resp = await client.get("/goals/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert "annual_income" in data
        types = [s["goal_type"] for s in data["suggestions"]]
        # Without existing goals, we should get emergency_fund, debt_payoff, purchase, tax, investment
        assert "emergency_fund" in types
        assert "debt_payoff" in types
        assert "purchase" in types
        assert "tax" in types
        assert "investment" in types

    @pytest.mark.asyncio
    async def test_suggestions_with_household(self, client, db_session):
        """With household profile, income-based amounts should adjust."""
        # Clear existing primary profiles
        result = await db_session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary == True)
        )
        for hp in result.scalars():
            hp.is_primary = False
        await db_session.flush()

        hp = HouseholdProfile(
            name="SuggestHH",
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            spouse_b_income=150000,
            combined_income=350000,
            is_primary=True,
        )
        db_session.add(hp)
        await db_session.commit()

        resp = await client.get("/goals/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["annual_income"] == 350000

    @pytest.mark.asyncio
    async def test_suggestions_with_student_loans(self, client, db_session):
        """Should suggest student loan payoff when student liabilities exist."""
        asset = ManualAsset(
            name="Student Loan - Federal",
            asset_type="other",
            is_liability=True,
            current_value=80000,
            is_active=True,
        )
        db_session.add(asset)
        await db_session.commit()

        resp = await client.get("/goals/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        types = [s["goal_type"] for s in data["suggestions"]]
        assert "debt_payoff" in types

    @pytest.mark.asyncio
    async def test_suggestions_with_rsu_grants(self, client, db_session):
        """Should suggest RSU tax withholding reserve when RSU grants exist."""
        grant = EquityGrant(
            employer_name="SuggestionCo",
            grant_type="rsu",
            grant_date=date(2024, 1, 1),
            total_shares=2000,
            vested_shares=500,
            unvested_shares=1500,
            current_fmv=100.0,
            is_active=True,
        )
        db_session.add(grant)
        await db_session.commit()

        resp = await client.get("/goals/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        # There should be a "tax" type suggestion for RSU reserve
        tax_suggestions = [s for s in data["suggestions"] if s["goal_type"] == "tax"]
        assert len(tax_suggestions) >= 1

    @pytest.mark.asyncio
    async def test_suggestions_with_existing_goals(self, client, db_session):
        """Existing goal types should suppress duplicate suggestions."""
        goal = Goal(
            name="Existing EF",
            goal_type="emergency_fund",
            target_amount=30000,
            current_amount=15000,
            status="active",
        )
        db_session.add(goal)
        await db_session.commit()

        resp = await client.get("/goals/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        types = [s["goal_type"] for s in data["suggestions"]]
        assert "emergency_fund" not in types

    @pytest.mark.asyncio
    async def test_suggestions_sorted_by_priority(self, client):
        resp = await client.get("/goals/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        priorities = [s["priority"] for s in data["suggestions"]]
        assert priorities == sorted(priorities)


# ============================================================================
# 6. api/routes/household.py
# ============================================================================

class TestHousehold:

    @pytest_asyncio.fixture
    async def client(self, db_factory):
        from api.routes.household import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = _override_session(db_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    # --- Profile CRUD ---

    @pytest.mark.asyncio
    async def test_list_profiles_empty(self, client):
        resp = await client.get("/household/profiles")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_profile(self, client):
        """Profile creation should compute combined_income."""
        resp = await client.post("/household/profiles", json={
            "name": "First HH",
            "filing_status": "mfj",
            "state": "CA",
            "spouse_a_income": 200000,
            "spouse_b_income": 150000,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "First HH"
        assert data["combined_income"] == 350000

    @pytest.mark.asyncio
    async def test_create_profile_auto_primary_when_first(self, client, db_session):
        """When no profiles exist, first one auto-becomes primary."""
        from sqlalchemy import delete as sa_delete
        # Clear all household profiles to simulate empty state
        await db_session.execute(sa_delete(BenefitPackage))
        await db_session.execute(sa_delete(HouseholdOptimization))
        await db_session.execute(sa_delete(InsurancePolicy))
        await db_session.execute(sa_delete(LifeEvent))
        await db_session.execute(sa_delete(FamilyMember))
        await db_session.execute(sa_delete(HouseholdProfile))
        await db_session.commit()

        resp = await client.post("/household/profiles", json={
            "name": "Sole HH",
            "filing_status": "mfj",
            "spouse_a_income": 100000,
        })
        assert resp.status_code == 201
        assert resp.json()["is_primary"] is True

    @pytest.mark.asyncio
    async def test_create_profile_second_as_primary(self, client):
        """Second profile marked as primary should clear existing primary."""
        resp = await client.post("/household/profiles", json={
            "name": "Second HH",
            "filing_status": "single",
            "spouse_a_income": 180000,
            "is_primary": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_primary"] is True

    @pytest.mark.asyncio
    async def test_create_profile_non_primary(self, client):
        """Profile without is_primary should default to non-primary."""
        resp = await client.post("/household/profiles", json={
            "name": "Third HH",
            "filing_status": "mfs",
            "spouse_a_income": 120000,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_update_profile(self, client):
        create = await client.post("/household/profiles", json={
            "name": "Patch HH",
            "filing_status": "mfj",
            "spouse_a_income": 100000,
        })
        pid = create.json()["id"]
        resp = await client.patch(f"/household/profiles/{pid}", json={
            "spouse_a_income": 200000,
            "spouse_b_income": 100000,
            "state": "NY",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["combined_income"] == 300000
        assert data["state"] == "NY"

    @pytest.mark.asyncio
    async def test_update_profile_set_primary(self, client):
        """Setting is_primary should clear others."""
        create = await client.post("/household/profiles", json={
            "name": "Primary Swap",
            "filing_status": "mfj",
            "spouse_a_income": 100000,
        })
        pid = create.json()["id"]
        resp = await client.patch(f"/household/profiles/{pid}", json={
            "is_primary": True,
        })
        assert resp.status_code == 200
        assert resp.json()["is_primary"] is True

    @pytest.mark.asyncio
    async def test_update_profile_not_found(self, client):
        resp = await client.patch("/household/profiles/99999", json={"state": "TX"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_profile(self, client, db_session):
        create = await client.post("/household/profiles", json={
            "name": "Delete HH",
            "filing_status": "single",
            "spouse_a_income": 100000,
        })
        pid = create.json()["id"]

        # Add related records to test cascade
        ins = InsurancePolicy(
            household_id=pid,
            policy_type="life",
            is_active=True,
        )
        le = LifeEvent(
            household_id=pid,
            event_type="marriage",
            title="Wedding",
        )
        db_session.add_all([ins, le])
        await db_session.commit()

        resp = await client.delete(f"/household/profiles/{pid}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_profile_not_found(self, client):
        resp = await client.delete("/household/profiles/99999")
        assert resp.status_code == 404

    # --- Benefits ---

    @pytest.mark.asyncio
    async def test_get_benefits_empty(self, client):
        create = await client.post("/household/profiles", json={
            "name": "Benefits HH",
            "filing_status": "mfj",
            "spouse_a_income": 100000,
        })
        pid = create.json()["id"]
        resp = await client.get(f"/household/profiles/{pid}/benefits")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_upsert_benefits_create(self, client):
        create = await client.post("/household/profiles", json={
            "name": "Benefits Create HH",
            "filing_status": "mfj",
            "spouse_a_income": 100000,
        })
        pid = create.json()["id"]
        resp = await client.post(f"/household/profiles/{pid}/benefits", json={
            "spouse": "a",
            "has_401k": True,
            "employer_match_pct": 6.0,
            "has_hsa": True,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    @pytest.mark.asyncio
    async def test_upsert_benefits_update(self, client):
        """Second POST with same spouse should update."""
        create = await client.post("/household/profiles", json={
            "name": "Benefits Update HH",
            "filing_status": "mfj",
            "spouse_a_income": 100000,
        })
        pid = create.json()["id"]
        await client.post(f"/household/profiles/{pid}/benefits", json={
            "spouse": "a",
            "has_401k": True,
        })
        resp = await client.post(f"/household/profiles/{pid}/benefits", json={
            "spouse": "a",
            "has_401k": False,
            "has_hsa": True,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    # --- Tax Strategy Profile ---

    @pytest.mark.asyncio
    async def test_get_tax_strategy_profile_no_primary(self, client, db_session):
        """When no primary household exists, return null profile."""
        # Clear all primary flags first
        result = await db_session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary == True)
        )
        for hp in result.scalars():
            hp.is_primary = False
        await db_session.commit()

        resp = await client.get("/household/tax-strategy-profile")
        assert resp.status_code == 200
        assert resp.json()["profile"] is None

    @pytest.mark.asyncio
    async def test_save_tax_strategy_profile(self, client, db_session):
        # Ensure a primary household exists
        hp = HouseholdProfile(
            name="Tax Strategy HH",
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            combined_income=200000,
            is_primary=True,
        )
        db_session.add(hp)
        await db_session.commit()

        resp = await client.put("/household/tax-strategy-profile", json={
            "has_rental_properties": True,
            "has_business_income": False,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"

    @pytest.mark.asyncio
    async def test_get_tax_strategy_profile_with_data(self, client, db_session):
        """After saving, should be able to retrieve tax strategy profile."""
        hp = HouseholdProfile(
            name="Tax Strategy Read HH",
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            combined_income=200000,
            is_primary=True,
            tax_strategy_profile_json='{"has_rental_properties": true}',
        )
        db_session.add(hp)
        await db_session.commit()

        resp = await client.get("/household/tax-strategy-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"] is not None

    @pytest.mark.asyncio
    async def test_get_tax_strategy_profile_with_bad_json(self, client, db_session):
        """Invalid JSON in tax_strategy_profile_json should not crash."""
        # First clear all primary flags
        result = await db_session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary == True)
        )
        for existing in result.scalars():
            existing.is_primary = False
        await db_session.flush()

        hp = HouseholdProfile(
            name="Bad JSON HH",
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            combined_income=200000,
            is_primary=True,
            tax_strategy_profile_json="not valid json{{{",
        )
        db_session.add(hp)
        await db_session.commit()

        resp = await client.get("/household/tax-strategy-profile")
        assert resp.status_code == 200
        # Bad JSON should result in null profile (not a crash)
        assert resp.json()["profile"] is None

    @pytest.mark.asyncio
    async def test_save_tax_strategy_profile_no_primary(self, client, db_session):
        """Should 404 when no primary household."""
        # Clear all primary flags
        result = await db_session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary == True)
        )
        for hp in result.scalars():
            hp.is_primary = False
        await db_session.commit()

        resp = await client.put("/household/tax-strategy-profile", json={
            "test_key": "test_value",
        })
        assert resp.status_code == 404


# ============================================================================
# 7. api/routes/household_optimization.py
# ============================================================================

class TestHouseholdOptimization:

    @pytest_asyncio.fixture
    async def client(self, db_factory):
        from api.routes.household import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = _override_session(db_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_optimize(self, client, db_session):
        """Full optimization endpoint."""
        hp = HouseholdProfile(
            name="Optimize HH",
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            spouse_b_income=150000,
            combined_income=350000,
            is_primary=True,
        )
        db_session.add(hp)
        await db_session.flush()

        # Add benefits
        benefit_a = BenefitPackage(
            household_id=hp.id,
            spouse="a",
            has_401k=True,
            employer_match_pct=6.0,
        )
        benefit_b = BenefitPackage(
            household_id=hp.id,
            spouse="b",
            has_401k=True,
            employer_match_pct=4.0,
        )
        db_session.add_all([benefit_a, benefit_b])
        await db_session.commit()

        with patch(
            "api.routes.household_optimization.HouseholdEngine.full_optimization",
            return_value={
                "filing": {
                    "recommendation": "mfj",
                    "mfj_tax": 80000,
                    "mfs_tax": 95000,
                    "filing_savings": 15000,
                },
                "retirement": {"401k_max_strategy": "both_max"},
                "insurance": {"health_plan": "hdhp"},
                "childcare": {"dcfsa": True},
                "total_annual_savings": 20000,
                "recommendations": ["Max both 401k"],
            },
        ):
            resp = await client.post("/household/optimize", json={
                "household_id": hp.id,
                "tax_year": 2025,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["optimal_filing_status"] == "mfj"
            assert data["total_annual_savings"] == 20000

    @pytest.mark.asyncio
    async def test_optimize_no_tax_year(self, client, db_session):
        """Optimize without specifying tax_year should use current year."""
        hp = HouseholdProfile(
            name="Optimize NoYear",
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            combined_income=200000,
            is_primary=True,
        )
        db_session.add(hp)
        await db_session.commit()

        with patch(
            "api.routes.household_optimization.HouseholdEngine.full_optimization",
            return_value={
                "filing": {
                    "recommendation": "mfj",
                    "mfj_tax": 60000,
                    "mfs_tax": 70000,
                    "filing_savings": 10000,
                },
                "retirement": {},
                "insurance": {},
                "childcare": {},
                "total_annual_savings": 10000,
                "recommendations": [],
            },
        ):
            resp = await client.post("/household/optimize", json={
                "household_id": hp.id,
            })
            assert resp.status_code == 200
            assert resp.json()["tax_year"] == datetime.now(timezone.utc).year

    @pytest.mark.asyncio
    async def test_optimize_not_found(self, client):
        resp = await client.post("/household/optimize", json={
            "household_id": 99999,
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_optimization_success(self, client, db_session):
        hp = HouseholdProfile(
            name="GetOpt HH",
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            combined_income=200000,
            is_primary=False,
        )
        db_session.add(hp)
        await db_session.flush()

        opt = HouseholdOptimization(
            household_id=hp.id,
            tax_year=2025,
            optimal_filing_status="mfj",
            mfj_tax=80000,
            mfs_tax=95000,
            filing_savings=15000,
            optimal_retirement_strategy_json='{"strategy": "max"}',
            optimal_insurance_selection='{"plan": "hdhp"}',
            childcare_strategy_json='{"dcfsa": true}',
            total_annual_savings=20000,
            recommendations_json='["Max 401k"]',
        )
        db_session.add(opt)
        await db_session.commit()

        resp = await client.get(f"/household/profiles/{hp.id}/optimization")
        assert resp.status_code == 200
        data = resp.json()
        assert data["optimal_filing_status"] == "mfj"
        assert data["total_annual_savings"] == 20000
        assert data["retirement_strategy"]["strategy"] == "max"

    @pytest.mark.asyncio
    async def test_get_optimization_not_found(self, client):
        resp = await client.get("/household/profiles/99999/optimization")
        assert resp.status_code == 404

    # --- Filing comparison ---

    @pytest.mark.asyncio
    async def test_filing_comparison(self, client):
        with patch(
            "api.routes.household_optimization.HouseholdEngine.optimize_filing_status",
            return_value={
                "recommendation": "mfj",
                "mfj_tax": 80000,
                "mfs_tax": 95000,
                "filing_savings": 15000,
            },
        ):
            resp = await client.post("/household/filing-comparison", json={
                "spouse_a_income": 200000,
                "spouse_b_income": 150000,
                "dependents": 2,
                "state": "CA",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["recommendation"] == "mfj"

    # --- W-4 Optimization ---

    @pytest.mark.asyncio
    async def test_w4_optimization(self, client):
        with patch(
            "api.routes.household_optimization.compute_w4_recommendations",
            return_value={
                "spouse_a_extra_withholding": 500,
                "spouse_b_extra_withholding": 300,
                "total_extra": 800,
            },
        ):
            resp = await client.post("/household/w4-optimization", json={
                "spouse_a_income": 200000,
                "spouse_b_income": 150000,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "spouse_a_extra_withholding" in data

    # --- Tax Thresholds ---

    @pytest.mark.asyncio
    async def test_tax_thresholds(self, client):
        with patch(
            "api.routes.household_optimization.compute_tax_thresholds",
            return_value={
                "irmaa_distance": 50000,
                "niit_distance": -20000,
                "amt_risk": "low",
            },
        ):
            resp = await client.post("/household/tax-thresholds", json={
                "spouse_a_income": 200000,
                "spouse_b_income": 150000,
                "capital_gains": 10000,
                "qualified_dividends": 5000,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "irmaa_distance" in data
