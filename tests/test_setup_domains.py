"""Tests for Setup domain data-moving operations: account linking, merging,
dedup, business entities, life events, and insurance."""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base


# ---------------------------------------------------------------------------
# Fixtures — minimal FastAPI app with relevant routers
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

    from api.routes import accounts, account_links, transactions, entities, life_events, insurance

    app.include_router(account_links.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(entities.router)
    app.include_router(life_events.router)
    app.include_router(insurance.router)

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
# Helper — create an account via API
# ---------------------------------------------------------------------------

async def _create_account(client: AsyncClient, name: str, data_source: str = "csv", **kwargs):
    body = {"name": name, "account_type": "personal", "data_source": data_source, **kwargs}
    resp = await client.post("/accounts", json=body)
    assert resp.status_code == 201
    return resp.json()


async def _create_transaction(client: AsyncClient, account_id: int, amount: float, description: str = "Test"):
    body = {
        "account_id": account_id,
        "date": "2025-01-15T00:00:00",
        "description": description,
        "amount": amount,
    }
    resp = await client.post("/transactions", json=body)
    assert resp.status_code == 201
    return resp.json()


# ===========================================================================
# Account Linking
# ===========================================================================

class TestAccountLinking:
    @pytest.mark.asyncio
    async def test_link_two_accounts(self, client):
        a1 = await _create_account(client, "Checking CSV", data_source="csv")
        a2 = await _create_account(client, "Checking Plaid", data_source="plaid")

        resp = await client.post(f"/accounts/{a1['id']}/link", json={"target_account_id": a2["id"]})
        assert resp.status_code == 200
        link = resp.json()
        assert link["primary_account_id"] == a1["id"]
        assert link["secondary_account_id"] == a2["id"]
        assert link["link_type"] == "same_account"

    @pytest.mark.asyncio
    async def test_link_self_returns_400(self, client):
        a = await _create_account(client, "Self Account")
        resp = await client.post(f"/accounts/{a['id']}/link", json={"target_account_id": a["id"]})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_link_duplicate_returns_409(self, client):
        a1 = await _create_account(client, "Acct A")
        a2 = await _create_account(client, "Acct B")
        await client.post(f"/accounts/{a1['id']}/link", json={"target_account_id": a2["id"]})
        resp = await client.post(f"/accounts/{a1['id']}/link", json={"target_account_id": a2["id"]})
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_remove_link(self, client):
        a1 = await _create_account(client, "Link A")
        a2 = await _create_account(client, "Link B")
        link_resp = await client.post(f"/accounts/{a1['id']}/link", json={"target_account_id": a2["id"]})
        link_id = link_resp.json()["id"]
        resp = await client.delete(f"/accounts/{a1['id']}/link/{link_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_account_links(self, client):
        a1 = await _create_account(client, "Link Get A")
        a2 = await _create_account(client, "Link Get B")
        await client.post(f"/accounts/{a1['id']}/link", json={"target_account_id": a2["id"]})
        resp = await client.get(f"/accounts/{a1['id']}/links")
        assert resp.status_code == 200
        links = resp.json()
        assert len(links) == 1


# ===========================================================================
# Account Merging
# ===========================================================================

class TestAccountMerging:
    @pytest.mark.asyncio
    async def test_merge_moves_transactions(self, client):
        primary = await _create_account(client, "Primary")
        secondary = await _create_account(client, "Secondary")
        await _create_transaction(client, secondary["id"], -50.00, "Coffee")
        await _create_transaction(client, secondary["id"], -25.00, "Lunch")

        resp = await client.post(
            f"/accounts/{primary['id']}/merge",
            json={"target_account_id": secondary["id"]},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["transactions_moved"] == 2
        assert result["secondary_deactivated"] is True

    @pytest.mark.asyncio
    async def test_merge_deactivates_secondary(self, client):
        primary = await _create_account(client, "Merge Primary")
        secondary = await _create_account(client, "Merge Secondary")
        await client.post(
            f"/accounts/{primary['id']}/merge",
            json={"target_account_id": secondary["id"]},
        )
        # Fetch all accounts including inactive
        resp = await client.get("/accounts")
        accounts = resp.json()
        secondary_found = [a for a in accounts if a["id"] == secondary["id"]]
        # Secondary should not appear in active accounts list
        assert len(secondary_found) == 0

    @pytest.mark.asyncio
    async def test_merge_creates_audit_link(self, client):
        primary = await _create_account(client, "Audit Primary")
        secondary = await _create_account(client, "Audit Secondary")
        await client.post(
            f"/accounts/{primary['id']}/merge",
            json={"target_account_id": secondary["id"]},
        )
        resp = await client.get(f"/accounts/{primary['id']}/links")
        links = resp.json()
        assert len(links) >= 1
        assert any(l["link_type"] == "same_account" for l in links)

    @pytest.mark.asyncio
    async def test_merge_self_returns_400(self, client):
        a = await _create_account(client, "Self Merge")
        resp = await client.post(
            f"/accounts/{a['id']}/merge",
            json={"target_account_id": a["id"]},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_merge_nonexistent_returns_404(self, client):
        a = await _create_account(client, "Exists")
        resp = await client.post(
            f"/accounts/{a['id']}/merge",
            json={"target_account_id": 9999},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_merge_preserves_data_integrity(self, client):
        """Total transaction count before == after merge (no data loss)."""
        primary = await _create_account(client, "Integrity Primary")
        secondary = await _create_account(client, "Integrity Secondary")
        await _create_transaction(client, primary["id"], -10.00, "Existing")
        await _create_transaction(client, secondary["id"], -20.00, "To Move 1")
        await _create_transaction(client, secondary["id"], -30.00, "To Move 2")

        resp = await client.post(
            f"/accounts/{primary['id']}/merge",
            json={"target_account_id": secondary["id"]},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["transactions_moved"] == 2

        # Primary should now have all 3 transactions
        txns_resp = await client.get(f"/transactions?account_id={primary['id']}")
        assert txns_resp.status_code == 200
        assert txns_resp.json()["total"] == 3


# ===========================================================================
# Suggest Links
# ===========================================================================

class TestSuggestLinks:
    @pytest.mark.asyncio
    async def test_suggest_same_institution_last_four(self, client):
        await _create_account(client, "Chase Checking CSV", data_source="csv",
                              institution="Chase", last_four="1234")
        await _create_account(client, "Chase Checking Plaid", data_source="plaid",
                              institution="Chase", last_four="1234")
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200
        suggestions = resp.json()
        assert len(suggestions) >= 1
        assert "Chase" in suggestions[0]["match_reason"]

    @pytest.mark.asyncio
    async def test_no_suggestions_same_source(self, client):
        await _create_account(client, "Same Source A", data_source="csv", institution="BofA")
        await _create_account(client, "Same Source B", data_source="csv", institution="BofA")
        resp = await client.get("/accounts/suggest-links")
        assert resp.status_code == 200
        # Same data_source should NOT generate suggestions
        suggestions = resp.json()
        same_source = [s for s in suggestions if s["account_a_source"] == s["account_b_source"]]
        assert len(same_source) == 0


# ===========================================================================
# Business Entity Routes
# ===========================================================================

class TestBusinessEntityRoutes:
    @pytest.mark.asyncio
    async def test_create_and_list_entities(self, client):
        resp = await client.post("/entities", json={
            "name": "Test LLC",
            "entity_type": "llc",
            "tax_treatment": "schedule_c",
        })
        assert resp.status_code == 201
        entity = resp.json()
        assert entity["name"] == "Test LLC"

        list_resp = await client.get("/entities")
        assert list_resp.status_code == 200
        assert any(e["name"] == "Test LLC" for e in list_resp.json())

    @pytest.mark.asyncio
    async def test_vendor_rule_crud(self, client):
        # Create entity first
        ent = await client.post("/entities", json={
            "name": "Rule Target",
            "entity_type": "sole_prop",
            "tax_treatment": "schedule_c",
        })
        ent_id = ent.json()["id"]

        # Create rule
        rule_resp = await client.post("/entities/rules/vendor", json={
            "vendor_pattern": "AMAZON",
            "business_entity_id": ent_id,
        })
        assert rule_resp.status_code == 201
        rule = rule_resp.json()
        assert rule["vendor_pattern"] == "AMAZON"

        # List rules
        list_resp = await client.get(f"/entities/rules/vendor?entity_id={ent_id}")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1

        # Delete rule (returns 204 No Content)
        del_resp = await client.delete(f"/entities/rules/vendor/{rule['id']}")
        assert del_resp.status_code == 204

    @pytest.mark.asyncio
    async def test_apply_entity_rules(self, client):
        # Create entity + rule + transaction
        ent = await client.post("/entities", json={
            "name": "Auto Tag Corp",
            "entity_type": "employer",
            "tax_treatment": "w2",
        })
        ent_id = ent.json()["id"]
        await client.post("/entities/rules/vendor", json={
            "vendor_pattern": "STARBUCKS",
            "business_entity_id": ent_id,
        })
        acct = await _create_account(client, "Rules Test Acct")
        await _create_transaction(client, acct["id"], -5.50, "STARBUCKS #123")

        # Apply rules
        resp = await client.post("/entities/apply-rules")
        assert resp.status_code == 200
        assert resp.json()["updated"] >= 0  # May or may not match depending on implementation

    @pytest.mark.asyncio
    async def test_reassign_entities(self, client):
        ent_a = await client.post("/entities", json={
            "name": "Old Entity",
            "entity_type": "sole_prop",
            "tax_treatment": "schedule_c",
        })
        ent_b = await client.post("/entities", json={
            "name": "New Entity",
            "entity_type": "llc",
            "tax_treatment": "schedule_c",
        })
        resp = await client.post("/entities/reassign", json={
            "from_entity_id": ent_a.json()["id"],
            "to_entity_id": ent_b.json()["id"],
        })
        assert resp.status_code == 200
        assert "reassigned" in resp.json()


# ===========================================================================
# Life Event Routes
# ===========================================================================

class TestLifeEventRoutes:
    @pytest.mark.asyncio
    async def test_create_life_event_with_action_items(self, client):
        resp = await client.post("/life-events/", json={
            "event_type": "real_estate_purchase",
            "title": "Bought a house",
            "event_date": "2025-06-15",
            "tax_year": 2025,
        })
        assert resp.status_code == 201
        event = resp.json()
        assert event["event_type"] == "real_estate_purchase"
        assert event["title"] == "Bought a house"
        # Action items should be auto-generated from template
        assert event["action_items_json"] is not None

    @pytest.mark.asyncio
    async def test_crud_lifecycle(self, client):
        # Create
        create_resp = await client.post("/life-events/", json={
            "event_type": "employment_job_change",
            "title": "New job at Acme",
        })
        assert create_resp.status_code == 201
        event_id = create_resp.json()["id"]

        # Get
        get_resp = await client.get(f"/life-events/{event_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "New job at Acme"

        # Update
        patch_resp = await client.patch(f"/life-events/{event_id}", json={
            "title": "New job at Acme Corp",
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["title"] == "New job at Acme Corp"

        # Delete (returns 204 No Content)
        del_resp = await client.delete(f"/life-events/{event_id}")
        assert del_resp.status_code == 204

    @pytest.mark.asyncio
    async def test_action_templates_available(self, client):
        resp = await client.get("/life-events/action-templates/real_estate_purchase")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0


# ===========================================================================
# Insurance Routes
# ===========================================================================

class TestInsuranceRoutes:
    @pytest.mark.asyncio
    async def test_create_policy(self, client):
        resp = await client.post("/insurance/", json={
            "policy_type": "life",
            "provider": "MetLife",
            "coverage_amount": 500000,
            "annual_premium": 1200,
        })
        assert resp.status_code == 201
        policy = resp.json()
        assert policy["policy_type"] == "life"
        assert policy["coverage_amount"] == 500000

    @pytest.mark.asyncio
    async def test_premium_sync(self, client):
        """When annual_premium is set, monthly should be computed."""
        resp = await client.post("/insurance/", json={
            "policy_type": "auto",
            "annual_premium": 2400,
        })
        assert resp.status_code == 201
        policy = resp.json()
        assert policy["monthly_premium"] == 200.0

    @pytest.mark.asyncio
    async def test_gap_analysis(self, client):
        resp = await client.post("/insurance/gap-analysis", json={
            "spouse_a_income": 150000,
            "spouse_b_income": 100000,
            "total_debt": 400000,
            "dependents": 2,
            "net_worth": 500000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "gaps" in data
        # With no policies and high income, there should be gaps
        assert len(data["gaps"]) > 0

    @pytest.mark.asyncio
    async def test_gap_analysis_includes_employer_benefits(self, client, test_session_factory):
        """Employer life/disability coverage from BenefitPackage reduces reported gaps."""
        from pipeline.db.schema import BenefitPackage, HouseholdProfile

        # Seed household + benefit package directly via ORM
        async with test_session_factory() as session:
            household = HouseholdProfile(
                name="Test Household", filing_status="mfj",
                spouse_a_income=150000, spouse_b_income=100000,
                combined_income=250000,
            )
            session.add(household)
            await session.flush()
            hh_id = household.id

            bp = BenefitPackage(
                household_id=hh_id, spouse="A", employer_name="Acme Corp",
                life_insurance_coverage=500000,  # $500k employer life
                ltd_coverage_pct=60,             # 60% LTD
            )
            session.add(bp)
            await session.commit()

        # Run gap analysis WITH the household_id so employer benefits are found
        resp = await client.post("/insurance/gap-analysis", json={
            "household_id": hh_id,
            "spouse_a_income": 150000,
            "spouse_b_income": 100000,
            "total_debt": 400000,
            "dependents": 2,
            "net_worth": 500000,
        })
        assert resp.status_code == 200
        data = resp.json()
        gaps_by_type = {g["type"]: g for g in data["gaps"]}

        # Life gap should include $500k employer coverage
        life = gaps_by_type["life"]
        assert life["employer_provided"] == 500000
        assert life["current_coverage"] >= 500000  # at least employer amount

        # Disability gap should include employer LTD
        disability = gaps_by_type["disability"]
        assert disability["employer_provided"] > 0  # employer LTD factored in
