"""Tests for the smart defaults engine."""
import json
import pytest
import pytest_asyncio
from datetime import date, datetime, timezone

from pipeline.db.schema import (
    Account,
    BenefitPackage,
    Budget,
    BusinessEntity,
    EquityGrant,
    FamilyMember,
    Goal,
    HouseholdProfile,
    ManualAsset,
    NetWorthSnapshot,
    PlaidAccount,
    PlaidItem,
    RecurringTransaction,
    TaxItem,
    Document,
    Transaction,
)
from pipeline.planning.smart_defaults import (
    compute_smart_defaults,
    detect_household_updates,
    apply_household_updates,
    generate_smart_budget,
    compute_comprehensive_personal_budget,
    get_tax_carry_forward,
    _employer_match,
    _canonicalize,
    _is_excluded,
)


# ---------------------------------------------------------------------------
# Pure function tests (no DB needed)
# ---------------------------------------------------------------------------

class TestEmployerMatch:
    def test_exact_match(self):
        assert _employer_match("Accenture", "Accenture") is True

    def test_case_insensitive(self):
        assert _employer_match("ACCENTURE", "accenture") is True

    def test_suffix_ignored_inc(self):
        assert _employer_match("Accenture Inc", "Accenture") is True

    def test_suffix_ignored_llc(self):
        assert _employer_match("MyCompany LLC", "MyCompany") is True

    def test_substring_match(self):
        assert _employer_match("Google", "Alphabet / Google") is True

    def test_no_match(self):
        assert _employer_match("Apple", "Google") is False

    def test_empty_strings(self):
        assert _employer_match("", "Google") is False
        assert _employer_match("Google", "") is False
        assert _employer_match("", "") is False

    def test_none_values(self):
        assert _employer_match(None, "Google") is False
        assert _employer_match("Google", None) is False


class TestCanonicalize:
    def test_known_mapping(self):
        assert _canonicalize("Groceries & Food") == "Groceries"
        assert _canonicalize("Coffee Shops") == "Coffee & Beverages"
        assert _canonicalize("Hotel & Lodging") == "Travel"

    def test_unknown_passthrough(self):
        assert _canonicalize("Custom Category") == "Custom Category"

    def test_fitness_variants(self):
        assert _canonicalize("Fitness & Gym") == "Fitness"
        assert _canonicalize("Health & Fitness") == "Fitness"
        assert _canonicalize("Sports & Fitness") == "Fitness"


class TestIsExcluded:
    def test_transfer_excluded(self):
        assert _is_excluded("Transfer") is True
        assert _is_excluded("Credit Card Payment") is True
        assert _is_excluded("Savings") is True

    def test_income_excluded(self):
        assert _is_excluded("Other Income") is True
        assert _is_excluded("Dividend Income") is True
        assert _is_excluded("W-2 Wages") is True

    def test_business_prefix_excluded(self):
        assert _is_excluded("Business Expenses") is True

    def test_goal_prefix_excluded(self):
        assert _is_excluded("Goal: Emergency Fund") is True

    def test_tax_excluded(self):
        assert _is_excluded("Tax Payments") is True
        assert _is_excluded("Property Tax") is True

    def test_paycheck_excluded(self):
        assert _is_excluded("Accenture Paycheck") is True

    def test_savings_keywords_excluded(self):
        assert _is_excluded("Emergency Fund") is True
        assert _is_excluded("College 529 Plan") is True

    def test_normal_categories_not_excluded(self):
        assert _is_excluded("Groceries") is False
        assert _is_excluded("Restaurants & Bars") is False
        assert _is_excluded("Auto Maintenance") is False
        assert _is_excluded("Utilities") is False
        assert _is_excluded("Rent") is False


# ---------------------------------------------------------------------------
# DB-backed tests: compute_smart_defaults
# ---------------------------------------------------------------------------

class TestComputeSmartDefaultsEmpty:
    """Empty database should return safe defaults for every key."""

    @pytest.mark.asyncio
    async def test_returns_all_sections(self, session):
        result = await compute_smart_defaults(session)
        expected_sections = {
            "household", "age", "income", "retirement", "expenses",
            "debts", "assets", "net_worth", "recurring", "equity",
            "tax", "benefits", "goals", "businesses", "data_sources",
        }
        assert expected_sections.issubset(result.keys())

    @pytest.mark.asyncio
    async def test_empty_household(self, session):
        result = await compute_smart_defaults(session)
        assert result["household"] == {}

    @pytest.mark.asyncio
    async def test_empty_age(self, session):
        result = await compute_smart_defaults(session)
        assert result["age"]["current_age"] is None

    @pytest.mark.asyncio
    async def test_empty_income(self, session):
        result = await compute_smart_defaults(session)
        assert result["income"]["w2_total"] == 0
        assert result["income"]["combined"] == 0

    @pytest.mark.asyncio
    async def test_empty_data_sources(self, session):
        result = await compute_smart_defaults(session)
        ds = result["data_sources"]
        assert ds["has_w2"] is False
        assert ds["has_plaid"] is False
        assert ds["has_household"] is False


# ---------------------------------------------------------------------------
# DB-backed: with seeded household data
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_session(session):
    """Session pre-populated with typical HENRY household data."""
    # Household profile
    profile = HouseholdProfile(
        name="Aron Household",
        filing_status="mfj",
        state="CA",
        spouse_a_name="Mike",
        spouse_a_income=250_000,
        spouse_a_employer="TechCorp Inc",
        spouse_b_name="Sarah",
        spouse_b_income=150_000,
        spouse_b_employer="Consulting LLC",
        combined_income=400_000,
        other_income_annual=10_000,
        is_primary=True,
    )
    session.add(profile)
    await session.flush()

    # Family member (self) for age computation
    member = FamilyMember(
        household_id=profile.id,
        name="Mike",
        relationship="self",
        date_of_birth=date(1990, 6, 15),
        is_earner=True,
        income=250_000,
        employer="TechCorp Inc",
    )
    session.add(member)

    # Manual assets (retirement accounts)
    session.add(ManualAsset(
        name="401k",
        asset_type="retirement",
        is_liability=False,
        current_value=500_000,
        is_active=True,
        is_retirement_account=True,
        employer_match_pct=50,
        contribution_rate_pct=10,
        employee_contribution_ytd=15_000,
    ))
    session.add(ManualAsset(
        name="Roth IRA",
        asset_type="retirement",
        is_liability=False,
        current_value=100_000,
        is_active=True,
        is_retirement_account=True,
    ))

    # Non-retirement investment
    session.add(ManualAsset(
        name="Brokerage",
        asset_type="investment",
        is_liability=False,
        current_value=200_000,
        is_active=True,
        is_retirement_account=False,
    ))

    # Liability
    session.add(ManualAsset(
        name="Mortgage",
        asset_type="mortgage",
        is_liability=True,
        current_value=400_000,
        is_active=True,
        is_retirement_account=False,
    ))

    # Net worth snapshot
    session.add(NetWorthSnapshot(
        snapshot_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        year=2026,
        month=2,
        total_assets=800_000,
        total_liabilities=400_000,
        net_worth=400_000,
    ))

    # Benefit package
    session.add(BenefitPackage(
        household_id=profile.id,
        spouse="A",
        employer_name="TechCorp Inc",
        has_401k=True,
        employer_match_pct=50,
        employer_match_limit_pct=6,
        has_hsa=True,
        has_espp=True,
        has_mega_backdoor=False,
        health_premium_monthly=500,
    ))

    # Goal
    session.add(Goal(
        name="Emergency Fund",
        target_amount=50_000,
        current_amount=30_000,
        status="active",
        monthly_contribution=500,
    ))

    # Business entity
    session.add(BusinessEntity(
        name="Side Consulting",
        entity_type="sole_prop",
        tax_treatment="schedule_c",
        is_active=True,
    ))

    # Recurring transaction
    session.add(RecurringTransaction(
        name="Netflix",
        amount=-15.99,
        frequency="monthly",
        category="Streaming & Entertainment",
        segment="personal",
        status="active",
    ))

    # Equity grant
    session.add(EquityGrant(
        employer_name="TechCorp Inc",
        grant_type="RSU",
        grant_date=date(2024, 1, 1),
        total_shares=1000,
        vested_shares=250,
        unvested_shares=750,
        current_fmv=150.0,
        is_active=True,
    ))

    # W-2 tax item (need a document first)
    doc = Document(
        filename="w2_2025.pdf",
        original_path="/tmp/w2_2025.pdf",
        file_type="pdf",
        document_type="w2",
        status="completed",
        file_hash="abc123def456",
    )
    session.add(doc)
    await session.flush()

    session.add(TaxItem(
        source_document_id=doc.id,
        tax_year=2025,
        form_type="w2",
        payer_name="TechCorp Inc",
        w2_wages=250_000,
        w2_federal_tax_withheld=50_000,
        w2_state_income_tax=20_000,
    ))

    # Account + transactions for expense computation
    acct = Account(
        name="Chase Sapphire",
        account_type="personal",
        subtype="credit_card",
    )
    session.add(acct)
    await session.flush()

    # Add transactions for the last 3 months
    today = date.today()
    for offset in range(1, 4):
        m = today.month - offset
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        session.add(Transaction(
            account_id=acct.id,
            date=datetime(y, m, 15, tzinfo=timezone.utc),
            description="Whole Foods",
            amount=-500.00,
            segment="personal",
            effective_segment="personal",
            category="Groceries",
            effective_category="Groceries",
            period_month=m,
            period_year=y,
            flow_type="expense",
            is_excluded=False,
        ))
        session.add(Transaction(
            account_id=acct.id,
            date=datetime(y, m, 20, tzinfo=timezone.utc),
            description="Shell Gas Station",
            amount=-80.00,
            segment="personal",
            effective_segment="personal",
            category="Gas",
            effective_category="Gas",
            period_month=m,
            period_year=y,
            flow_type="expense",
            is_excluded=False,
        ))

    await session.flush()
    return session


class TestComputeSmartDefaultsSeeded:
    @pytest.mark.asyncio
    async def test_household_populated(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        h = result["household"]
        assert h["filing_status"] == "mfj"
        assert h["state"] == "CA"
        assert h["combined_income"] == 400_000
        assert h["spouse_a_name"] == "Mike"

    @pytest.mark.asyncio
    async def test_age_computed(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        age = result["age"]["current_age"]
        # Born 1990, test year ~2026 -> age should be 35 or 36
        assert 35 <= age <= 36

    @pytest.mark.asyncio
    async def test_income_from_w2(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        inc = result["income"]
        assert inc["w2_total"] == 250_000
        assert inc["w2_fed_withheld"] == 50_000

    @pytest.mark.asyncio
    async def test_income_combined_uses_household(self, seeded_session):
        """combined should prefer household's combined_income over W-2."""
        result = await compute_smart_defaults(seeded_session)
        # Household combined_income=400k, W-2=250k -> should use 400k
        assert result["income"]["combined"] == 400_000

    @pytest.mark.asyncio
    async def test_retirement_savings(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        ret = result["retirement"]
        assert ret["total_savings"] == 600_000  # 500k + 100k

    @pytest.mark.asyncio
    async def test_assets_breakdown(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        assets = result["assets"]
        assert assets["retirement_total"] == 600_000
        assert assets["investment_total"] == 200_000

    @pytest.mark.asyncio
    async def test_debts_includes_mortgage(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        debts = result["debts"]
        assert isinstance(debts, list)
        mortgage_found = any(d["name"] == "Mortgage" for d in debts)
        assert mortgage_found is True

    @pytest.mark.asyncio
    async def test_net_worth_snapshot(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        nw = result["net_worth"]
        assert nw["net_worth"] == 400_000
        assert nw["as_of"] == "2026-02"

    @pytest.mark.asyncio
    async def test_recurring_found(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        recurring = result["recurring"]
        assert len(recurring) >= 1
        assert recurring[0]["name"] == "Netflix"

    @pytest.mark.asyncio
    async def test_equity_value(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        eq = result["equity"]
        # 250 vested * 150 + 750 unvested * 150 = 37500 + 112500 = 150000
        assert eq["total_value"] == 150_000
        assert eq["vested_value"] == 37_500

    @pytest.mark.asyncio
    async def test_tax_defaults(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        tax = result["tax"]
        assert tax["federal_withholding"] == 50_000
        assert tax["state_withholding"] == 20_000
        assert tax["tax_year"] == 2025

    @pytest.mark.asyncio
    async def test_benefits_populated(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        ben = result["benefits"]
        assert ben["has_401k"] is True
        assert ben["has_hsa"] is True
        assert ben["has_espp"] is True
        assert ben["match_pct"] == 50

    @pytest.mark.asyncio
    async def test_goals_populated(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        goals = result["goals"]
        assert len(goals) == 1
        assert goals[0]["name"] == "Emergency Fund"
        assert goals[0]["progress_pct"] == 60.0  # 30k/50k

    @pytest.mark.asyncio
    async def test_businesses_populated(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        biz = result["businesses"]
        assert len(biz) == 1
        assert biz[0]["name"] == "Side Consulting"

    @pytest.mark.asyncio
    async def test_data_sources_flags(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        ds = result["data_sources"]
        assert ds["has_w2"] is True
        assert ds["has_household"] is True
        assert ds["has_assets"] is True
        assert ds["has_recurring"] is True
        assert ds["has_equity"] is True

    @pytest.mark.asyncio
    async def test_expenses_computed(self, seeded_session):
        result = await compute_smart_defaults(seeded_session)
        exp = result["expenses"]
        assert exp["months_of_data"] >= 1
        assert exp["avg_monthly"] > 0


# ---------------------------------------------------------------------------
# detect_household_updates
# ---------------------------------------------------------------------------

class TestDetectHouseholdUpdates:
    @pytest.mark.asyncio
    async def test_no_profile_returns_empty(self, session):
        suggestions = await detect_household_updates(session)
        assert suggestions == []

    @pytest.mark.asyncio
    async def test_detects_income_mismatch(self, seeded_session):
        """When W-2 wages differ from household income, suggest an update."""
        # The seeded profile has spouse_a_income=250k, W-2 wages=250k
        # They match, so let's change the profile to create a mismatch
        from sqlalchemy import select
        result = await seeded_session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True))
        )
        profile = result.scalar_one()
        profile.spouse_a_income = 200_000  # mismatch with W-2's 250k
        await seeded_session.flush()

        suggestions = await detect_household_updates(seeded_session)
        assert len(suggestions) >= 1
        income_suggestion = next(
            (s for s in suggestions if s["field"] == "spouse_a_income"), None
        )
        assert income_suggestion is not None
        assert income_suggestion["suggested"] == 250_000

    @pytest.mark.asyncio
    async def test_no_w2_returns_empty(self, session):
        """No W-2s -> no suggestions even with a profile."""
        profile = HouseholdProfile(
            name="Test",
            filing_status="single",
            spouse_a_income=100_000,
            spouse_a_employer="SomeCo",
            combined_income=100_000,
            is_primary=True,
        )
        session.add(profile)
        await session.flush()
        suggestions = await detect_household_updates(session)
        assert suggestions == []


# ---------------------------------------------------------------------------
# apply_household_updates
# ---------------------------------------------------------------------------

class TestApplyHouseholdUpdates:
    @pytest.mark.asyncio
    async def test_no_profile_returns_error(self, session):
        result = await apply_household_updates(session, [])
        assert result["error"] == "No household profile found"

    @pytest.mark.asyncio
    async def test_applies_income_update(self, seeded_session):
        updates = [
            {"field": "spouse_a_income", "suggested": 275_000},
        ]
        result = await apply_household_updates(seeded_session, updates)
        assert result["applied"] == 1

        # Verify it was applied
        from sqlalchemy import select
        row = await seeded_session.execute(
            select(HouseholdProfile).where(HouseholdProfile.is_primary.is_(True))
        )
        profile = row.scalar_one()
        assert profile.spouse_a_income == 275_000
        # Combined should be recomputed
        assert profile.combined_income == 275_000 + 150_000

    @pytest.mark.asyncio
    async def test_rejects_disallowed_fields(self, seeded_session):
        updates = [
            {"field": "id", "suggested": 999},
            {"field": "name", "suggested": "Hacked"},
        ]
        result = await apply_household_updates(seeded_session, updates)
        assert result["applied"] == 0


# ---------------------------------------------------------------------------
# generate_smart_budget
# ---------------------------------------------------------------------------

class TestGenerateSmartBudget:
    @pytest.mark.asyncio
    async def test_empty_db_returns_empty(self, session):
        lines = await generate_smart_budget(session, 2026, 3)
        assert lines == []

    @pytest.mark.asyncio
    async def test_recurring_creates_budget_lines(self, session):
        session.add(RecurringTransaction(
            name="Spotify",
            amount=-9.99,
            frequency="monthly",
            category="Streaming",
            segment="personal",
            status="active",
        ))
        session.add(RecurringTransaction(
            name="Annual Insurance",
            amount=-1200,
            frequency="annual",
            category="Insurance",
            segment="personal",
            status="active",
        ))
        await session.flush()

        lines = await generate_smart_budget(session, 2026, 3)
        assert len(lines) >= 2

        streaming_line = next((l for l in lines if l["category"] == "Streaming"), None)
        assert streaming_line is not None
        assert streaming_line["budget_amount"] == pytest.approx(9.99, abs=0.01)
        assert streaming_line["source"] == "recurring"

        insurance_line = next((l for l in lines if l["category"] == "Insurance"), None)
        assert insurance_line is not None
        assert insurance_line["budget_amount"] == pytest.approx(100.0, abs=1)  # 1200/12

    @pytest.mark.asyncio
    async def test_goals_added_to_budget(self, session):
        session.add(Goal(
            name="Vacation Fund",
            target_amount=10_000,
            current_amount=2_000,
            status="active",
            monthly_contribution=500,
        ))
        await session.flush()

        lines = await generate_smart_budget(session, 2026, 3)
        goal_line = next((l for l in lines if "Vacation Fund" in l.get("detail", "")), None)
        assert goal_line is not None
        assert goal_line["budget_amount"] == 500

    @pytest.mark.asyncio
    async def test_recurring_sorted_first(self, session):
        session.add(RecurringTransaction(
            name="Gym",
            amount=-50,
            frequency="monthly",
            category="Fitness",
            segment="personal",
            status="active",
        ))
        session.add(Goal(
            name="House Fund",
            target_amount=100_000,
            current_amount=10_000,
            status="active",
            monthly_contribution=2_000,
        ))
        await session.flush()

        lines = await generate_smart_budget(session, 2026, 3)
        if len(lines) >= 2:
            # Recurring should appear before goals
            sources = [l["source"] for l in lines]
            if "recurring" in sources and "goal" in sources:
                assert sources.index("recurring") < sources.index("goal")


# ---------------------------------------------------------------------------
# get_tax_carry_forward
# ---------------------------------------------------------------------------

class TestTaxCarryForward:
    @pytest.mark.asyncio
    async def test_empty_returns_empty(self, session):
        items = await get_tax_carry_forward(session, 2024, 2025)
        assert items == []

    @pytest.mark.asyncio
    async def test_carry_forward_items(self, seeded_session):
        items = await get_tax_carry_forward(seeded_session, 2025, 2026)
        assert len(items) >= 1
        w2_item = next((i for i in items if i["form_type"] == "w2"), None)
        assert w2_item is not None
        assert w2_item["prior_year_amount"] == 250_000
        assert w2_item["status"] == "expected"  # no 2026 W-2 exists yet
