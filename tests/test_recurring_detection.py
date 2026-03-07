"""Tests for pipeline/db/recurring_detection.py — recurring transaction detection."""
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from pipeline.db.recurring_detection import (
    _normalize_description,
    _detect_frequency,
    detect_recurring_transactions,
)
from pipeline.db.schema import Account, Transaction, RecurringTransaction


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestNormalizeDescription:
    def test_lowercase(self):
        assert _normalize_description("NETFLIX") == "netflix"

    def test_collapses_digits(self):
        assert _normalize_description("STARBUCKS 12345") == "starbucks #"

    def test_truncates_at_40(self):
        long = "A" * 60
        assert len(_normalize_description(long)) <= 40

    def test_whitespace(self):
        assert _normalize_description("  SPOTIFY  ") == "spotify"


class TestDetectFrequency:
    def test_monthly(self):
        assert _detect_frequency([30, 31, 29]) == "monthly"

    def test_quarterly(self):
        assert _detect_frequency([90, 91, 89]) == "quarterly"

    def test_annual(self):
        assert _detect_frequency([365, 366]) == "annual"

    def test_weekly(self):
        assert _detect_frequency([7, 7, 7]) == "weekly"

    def test_irregular(self):
        assert _detect_frequency([10, 50, 120]) is None

    def test_empty(self):
        assert _detect_frequency([]) is None

    def test_boundary_monthly_low(self):
        assert _detect_frequency([25]) == "monthly"

    def test_boundary_monthly_high(self):
        assert _detect_frequency([35]) == "monthly"

    def test_below_monthly_range(self):
        assert _detect_frequency([24]) is None

    def test_above_monthly_range(self):
        assert _detect_frequency([36]) is None


# ---------------------------------------------------------------------------
# Full detection (DB-dependent)
# ---------------------------------------------------------------------------

class TestDetectRecurring:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_transactions(self, session):
        """Create an account and transactions with monthly recurring pattern."""
        acct = Account(name="Test Checking", institution="Test Bank", account_type="depository")
        session.add(acct)
        await session.flush()
        self.account_id = acct.id

        base_date = datetime(2025, 1, 15, tzinfo=timezone.utc)
        for i in range(4):
            txn = Transaction(
                account_id=acct.id,
                date=base_date + timedelta(days=30 * i),
                description="NETFLIX SUBSCRIPTION",
                amount=-15.99,
                period_year=2025,
                period_month=1 + i,
            )
            session.add(txn)
        await session.flush()

    async def test_detects_monthly(self, session):
        txns = (await session.execute(
            __import__("sqlalchemy").select(Transaction)
        )).scalars().all()
        result = await detect_recurring_transactions(session, txns)
        assert result["detected"] >= 1

    async def test_skips_single_transaction(self, session):
        """A single transaction should not be detected as recurring."""
        # Clear all transactions and add just one
        for t in (await session.execute(
            __import__("sqlalchemy").select(Transaction)
        )).scalars():
            await session.delete(t)
        await session.flush()

        session.add(Transaction(
            account_id=self.account_id,
            date=datetime(2025, 3, 1, tzinfo=timezone.utc),
            description="ONE TIME CHARGE",
            amount=-50.0,
            period_year=2025,
            period_month=3,
        ))
        await session.flush()

        txns = (await session.execute(
            __import__("sqlalchemy").select(Transaction)
        )).scalars().all()
        result = await detect_recurring_transactions(session, txns)
        assert result["detected"] == 0

    async def test_skips_high_variance(self, session):
        """Transactions with high amount variance should not match."""
        for t in (await session.execute(
            __import__("sqlalchemy").select(Transaction)
        )).scalars():
            await session.delete(t)
        await session.flush()

        base_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        amounts = [-10.0, -50.0, -100.0]  # Very high variance
        for i, amount in enumerate(amounts):
            session.add(Transaction(
                account_id=self.account_id,
                date=base_date + timedelta(days=30 * i),
                description="VARIABLE CHARGE",
                amount=amount,
                period_year=2025,
                period_month=1 + i,
            ))
        await session.flush()

        txns = (await session.execute(
            __import__("sqlalchemy").select(Transaction)
        )).scalars().all()
        result = await detect_recurring_transactions(session, txns)
        assert result["detected"] == 0

    async def test_does_not_duplicate(self, session):
        """Running detection twice should not create duplicate records."""
        txns = (await session.execute(
            __import__("sqlalchemy").select(Transaction)
        )).scalars().all()
        r1 = await detect_recurring_transactions(session, txns)
        await session.flush()

        # Re-query transactions and run again
        txns2 = (await session.execute(
            __import__("sqlalchemy").select(Transaction)
        )).scalars().all()
        r2 = await detect_recurring_transactions(session, txns2)
        assert r2["detected"] == 0  # Already exists
