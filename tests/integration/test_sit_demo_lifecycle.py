"""SIT: Demo mode lifecycle.

Validates seed → explore → reset → re-seed cycle.
Uses function-scoped fixtures for isolation.
"""
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from tests.integration.expected_values import *

from pipeline.db.schema import (
    Base, HouseholdProfile, Account, Transaction, Budget,
    InvestmentHolding, InsurancePolicy, Goal, RetirementProfile,
    EquityGrant, RecurringTransaction, LifeEvent, FamilyMember,
    CategoryRule, CryptoHolding, ManualAsset, TaxItem, TaxStrategy,
    NetWorthSnapshot, AppSettings,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_fresh_db():
    """Create a fresh in-memory DB with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _seed(factory):
    from pipeline.db.migrations import run_migrations
    from pipeline.demo.seeder import seed_demo_data

    async with factory() as session:
        await run_migrations(session)
    async with factory() as session:
        counts = await seed_demo_data(session)
        await session.commit()
    return counts


# ---------------------------------------------------------------------------
# Seed completeness
# ---------------------------------------------------------------------------

class TestSeedCompleteness:
    async def test_seed_populates_all_entities(self):
        engine, factory = await _create_fresh_db()
        counts = await _seed(factory)

        async with factory() as session:
            # Verify each major entity type
            assert (await session.scalar(select(func.count()).select_from(HouseholdProfile))) >= 1
            assert (await session.scalar(select(func.count()).select_from(FamilyMember))) >= 3
            assert (await session.scalar(select(func.count()).select_from(Account))) >= ACCOUNT_COUNT
            assert (await session.scalar(select(func.count()).select_from(Transaction))) >= 100
            assert (await session.scalar(select(func.count()).select_from(Budget))) >= 100
            assert (await session.scalar(select(func.count()).select_from(InvestmentHolding))) >= INVESTMENT_HOLDINGS_COUNT
            assert (await session.scalar(select(func.count()).select_from(CryptoHolding))) >= CRYPTO_HOLDINGS_COUNT
            assert (await session.scalar(select(func.count()).select_from(InsurancePolicy))) >= INSURANCE_POLICY_COUNT
            assert (await session.scalar(select(func.count()).select_from(Goal))) >= GOAL_COUNT
            assert (await session.scalar(select(func.count()).select_from(RetirementProfile))) >= 1
            assert (await session.scalar(select(func.count()).select_from(EquityGrant))) >= 1
            assert (await session.scalar(select(func.count()).select_from(RecurringTransaction))) >= RECURRING_COUNT
            assert (await session.scalar(select(func.count()).select_from(LifeEvent))) >= LIFE_EVENT_COUNT
            assert (await session.scalar(select(func.count()).select_from(CategoryRule))) >= CATEGORY_RULE_COUNT
            assert (await session.scalar(select(func.count()).select_from(ManualAsset))) >= 5
            assert (await session.scalar(select(func.count()).select_from(TaxItem))) >= 2
            assert (await session.scalar(select(func.count()).select_from(TaxStrategy))) >= TAX_STRATEGY_COUNT
            assert (await session.scalar(select(func.count()).select_from(NetWorthSnapshot))) >= NET_WORTH_SNAPSHOT_COUNT

        await engine.dispose()

    async def test_seed_returns_counts(self):
        engine, factory = await _create_fresh_db()
        counts = await _seed(factory)

        assert isinstance(counts, dict)
        expected_keys = [
            "households", "family_members", "accounts", "transactions",
            "budgets", "investment_holdings", "crypto_holdings",
            "insurance_policies", "goals", "retirement_profiles",
        ]
        for key in expected_keys:
            assert key in counts, f"Missing key: {key}"
            assert counts[key] > 0, f"Zero count for: {key}"

        await engine.dispose()


# ---------------------------------------------------------------------------
# Double-seed protection
# ---------------------------------------------------------------------------

class TestDoubleSeedProtection:
    async def test_double_seed_refused(self):
        engine, factory = await _create_fresh_db()
        await _seed(factory)

        # Second seed should raise
        from pipeline.demo.seeder import seed_demo_data
        async with factory() as session:
            with pytest.raises(ValueError, match="already contains data"):
                await seed_demo_data(session)

        await engine.dispose()


# ---------------------------------------------------------------------------
# Demo status
# ---------------------------------------------------------------------------

class TestDemoStatus:
    async def test_demo_status_active_after_seed(self):
        engine, factory = await _create_fresh_db()
        await _seed(factory)

        from pipeline.demo.seeder import get_demo_status
        async with factory() as session:
            status = await get_demo_status(session)
            assert status["active"] is True
            assert status["profile_name"] is not None

        await engine.dispose()

    async def test_demo_status_inactive_before_seed(self):
        engine, factory = await _create_fresh_db()

        from pipeline.demo.seeder import get_demo_status
        from pipeline.db.migrations import run_migrations

        async with factory() as session:
            await run_migrations(session)

        async with factory() as session:
            status = await get_demo_status(session)
            assert status["active"] is False

        await engine.dispose()


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    async def test_seed_explore_reset_reseed(self):
        """Complete lifecycle: seed → verify → reset → verify empty → reseed → verify again."""
        engine, factory = await _create_fresh_db()

        # Step 1: Seed
        counts_1 = await _seed(factory)
        assert counts_1["transactions"] > 100

        # Step 2: Verify data exists
        async with factory() as session:
            acct_count = await session.scalar(
                select(func.count()).select_from(Account)
            )
            assert acct_count >= ACCOUNT_COUNT

            txn_count = await session.scalar(
                select(func.count()).select_from(Transaction)
            )
            assert txn_count > 100

        # Step 3: Reset — manually clear all tables (reset_demo_data checks URL)
        async with factory() as session:
            await session.execute(text("PRAGMA foreign_keys = OFF"))
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(table.delete())
            await session.execute(text("PRAGMA foreign_keys = ON"))
            await session.commit()

        # Step 4: Verify empty
        async with factory() as session:
            assert (await session.scalar(
                select(func.count()).select_from(Account)
            )) == 0
            assert (await session.scalar(
                select(func.count()).select_from(Transaction)
            )) == 0
            assert (await session.scalar(
                select(func.count()).select_from(HouseholdProfile)
            )) == 0

        # Step 5: Re-seed
        from pipeline.demo.seeder import seed_demo_data
        async with factory() as session:
            counts_2 = await seed_demo_data(session)
            await session.commit()

        # Step 6: Verify data restored
        assert counts_2["transactions"] == counts_1["transactions"]
        assert counts_2["accounts"] == counts_1["accounts"]

        async with factory() as session:
            acct_count = await session.scalar(
                select(func.count()).select_from(Account)
            )
            assert acct_count >= ACCOUNT_COUNT

        await engine.dispose()
