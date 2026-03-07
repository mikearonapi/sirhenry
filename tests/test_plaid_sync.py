"""Tests for pipeline/plaid/sync.py — bank sync logic with mocked Plaid calls.

Tests the core sync functions: account balance updates, new transaction processing,
modified transaction updates, removed transaction handling, cross-source dedup,
and net worth snapshots. All Plaid API calls are mocked.
"""
import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from pipeline.db.schema import (
    Account,
    ManualAsset,
    NetWorthSnapshot,
    PlaidAccount,
    PlaidItem,
    Transaction,
)
from pipeline.plaid.sync import (
    _map_plaid_type,
    _process_new_transactions,
    _remove_transactions,
    _update_account_balances,
    _update_modified_transactions,
    snapshot_net_worth,
    sync_item,
)


# ---------------------------------------------------------------------------
# Helper — build a PlaidItem with associated account/plaid_account
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def plaid_item(session):
    """Create a PlaidItem with one linked account and PlaidAccount."""
    item = PlaidItem(
        item_id="test-item-001",
        access_token="encrypted-token-123",
        institution_name="Chase",
        status="active",
    )
    session.add(item)
    await session.flush()

    acct = Account(name="Chase Checking", institution="Chase", account_type="personal")
    session.add(acct)
    await session.flush()

    pa = PlaidAccount(
        plaid_item_id=item.id,
        account_id=acct.id,
        plaid_account_id="plaid-acct-001",
        name="Chase Checking",
        type="depository",
        subtype="checking",
        current_balance=5000.0,
    )
    session.add(pa)
    await session.flush()

    return item, acct, pa


# ---------------------------------------------------------------------------
# _map_plaid_type
# ---------------------------------------------------------------------------

class TestMapPlaidType:
    def test_depository(self):
        assert _map_plaid_type("depository") == "personal"

    def test_credit(self):
        assert _map_plaid_type("credit") == "personal"

    def test_investment(self):
        assert _map_plaid_type("investment") == "investment"

    def test_loan(self):
        assert _map_plaid_type("loan") == "personal"

    def test_mortgage(self):
        assert _map_plaid_type("mortgage") == "personal"

    def test_unknown_defaults_personal(self):
        assert _map_plaid_type("other") == "personal"

    def test_case_insensitive(self):
        assert _map_plaid_type("DEPOSITORY") == "personal"
        assert _map_plaid_type("Investment") == "investment"


# ---------------------------------------------------------------------------
# _update_account_balances
# ---------------------------------------------------------------------------

class TestUpdateAccountBalances:
    async def test_updates_existing_balance(self, session, plaid_item):
        item, acct, pa = plaid_item
        accounts_data = [{
            "plaid_account_id": "plaid-acct-001",
            "name": "Chase Checking",
            "type": "depository",
            "subtype": "checking",
            "current_balance": 7500.0,
            "available_balance": 7200.0,
            "limit_balance": None,
        }]
        updated = await _update_account_balances(session, item, accounts_data)
        assert updated == 1

        result = await session.execute(
            select(PlaidAccount).where(PlaidAccount.plaid_account_id == "plaid-acct-001")
        )
        refreshed = result.scalar_one()
        assert refreshed.current_balance == 7500.0
        assert refreshed.available_balance == 7200.0

    async def test_creates_new_account_on_unknown_plaid_id(self, session, plaid_item):
        item, _, _ = plaid_item
        accounts_data = [{
            "plaid_account_id": "plaid-acct-new",
            "name": "Chase Savings",
            "type": "depository",
            "subtype": "savings",
            "current_balance": 20000.0,
            "available_balance": 20000.0,
            "limit_balance": None,
        }]
        updated = await _update_account_balances(session, item, accounts_data)
        assert updated == 1

        result = await session.execute(
            select(PlaidAccount).where(PlaidAccount.plaid_account_id == "plaid-acct-new")
        )
        new_pa = result.scalar_one()
        assert new_pa.name == "Chase Savings"
        assert new_pa.current_balance == 20000.0

    async def test_empty_accounts_data(self, session, plaid_item):
        item, _, _ = plaid_item
        updated = await _update_account_balances(session, item, [])
        assert updated == 0


# ---------------------------------------------------------------------------
# _process_new_transactions
# ---------------------------------------------------------------------------

class TestProcessNewTransactions:
    async def test_inserts_new_transactions(self, session, plaid_item):
        item, acct, pa = plaid_item
        added = [{
            "plaid_account_id": "plaid-acct-001",
            "date": datetime(2025, 1, 15, tzinfo=timezone.utc),
            "description": "Starbucks Coffee",
            "merchant_name": "Starbucks",
            "amount": -5.75,
            "currency": "USD",
            "period_month": 1,
            "period_year": 2025,
            "transaction_hash": hashlib.sha256(b"tx-001").hexdigest(),
            "pending": False,
        }]
        count = await _process_new_transactions(session, item, added)
        assert count == 1

        result = await session.execute(select(Transaction).where(Transaction.account_id == acct.id))
        txns = list(result.scalars().all())
        assert len(txns) == 1
        assert txns[0].description == "Starbucks Coffee"
        assert txns[0].amount == -5.75

    async def test_skips_pending_transactions(self, session, plaid_item):
        item, _, _ = plaid_item
        added = [{
            "plaid_account_id": "plaid-acct-001",
            "date": datetime(2025, 1, 15, tzinfo=timezone.utc),
            "description": "Pending Charge",
            "amount": -50.0,
            "period_month": 1,
            "period_year": 2025,
            "transaction_hash": hashlib.sha256(b"pending-001").hexdigest(),
            "pending": True,
        }]
        count = await _process_new_transactions(session, item, added)
        assert count == 0

    async def test_skips_unknown_plaid_account(self, session, plaid_item):
        item, _, _ = plaid_item
        added = [{
            "plaid_account_id": "plaid-acct-UNKNOWN",
            "date": datetime(2025, 1, 15, tzinfo=timezone.utc),
            "description": "Mystery",
            "amount": -10.0,
            "period_month": 1,
            "period_year": 2025,
            "transaction_hash": hashlib.sha256(b"unknown-001").hexdigest(),
            "pending": False,
        }]
        count = await _process_new_transactions(session, item, added)
        assert count == 0

    async def test_empty_added_list(self, session, plaid_item):
        item, _, _ = plaid_item
        count = await _process_new_transactions(session, item, [])
        assert count == 0

    async def test_cross_source_dedup_skips_csv_matches(self, session, plaid_item):
        """If a CSV transaction already exists with same account/date/amount, skip it."""
        item, acct, pa = plaid_item
        # Pre-existing CSV transaction
        session.add(Transaction(
            account_id=acct.id,
            date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            description="Starbucks (CSV)",
            amount=-5.75,
            period_year=2025,
            period_month=1,
            is_excluded=False,
            data_source="csv",
        ))
        await session.flush()

        # Plaid tries to add same date/amount
        added = [{
            "plaid_account_id": "plaid-acct-001",
            "date": datetime(2025, 1, 15, tzinfo=timezone.utc),
            "description": "Starbucks Coffee",
            "amount": -5.75,
            "period_month": 1,
            "period_year": 2025,
            "transaction_hash": hashlib.sha256(b"plaid-dup").hexdigest(),
            "pending": False,
        }]
        count = await _process_new_transactions(session, item, added)
        assert count == 0  # Skipped due to cross-source dedup

    async def test_multiple_transactions_batch(self, session, plaid_item):
        item, acct, pa = plaid_item
        added = [
            {
                "plaid_account_id": "plaid-acct-001",
                "date": datetime(2025, 1, i, tzinfo=timezone.utc),
                "description": f"Purchase {i}",
                "amount": -10.0 * i,
                "period_month": 1,
                "period_year": 2025,
                "transaction_hash": hashlib.sha256(f"batch-{i}".encode()).hexdigest(),
                "pending": False,
            }
            for i in range(1, 6)
        ]
        count = await _process_new_transactions(session, item, added)
        assert count == 5


# ---------------------------------------------------------------------------
# _update_modified_transactions
# ---------------------------------------------------------------------------

class TestUpdateModifiedTransactions:
    async def test_updates_amount(self, session, plaid_item):
        item, acct, _ = plaid_item
        tx_hash = hashlib.sha256(b"mod-tx-001").hexdigest()
        session.add(Transaction(
            account_id=acct.id,
            date=datetime(2025, 2, 1, tzinfo=timezone.utc),
            description="Amazon",
            amount=-50.0,
            period_year=2025,
            period_month=2,
            is_excluded=False,
            transaction_hash=tx_hash,
        ))
        await session.flush()

        modified = [{
            "transaction_hash": tx_hash,
            "amount": -55.0,
            "date": datetime(2025, 2, 1, tzinfo=timezone.utc),
            "description": "Amazon",
            "pending": False,
        }]
        updated = await _update_modified_transactions(session, item, modified)
        assert updated == 1

        result = await session.execute(
            select(Transaction).where(Transaction.transaction_hash == tx_hash)
        )
        tx = result.scalar_one()
        assert tx.amount == -55.0

    async def test_skips_pending(self, session, plaid_item):
        item, _, _ = plaid_item
        modified = [{
            "transaction_hash": "some-hash",
            "amount": -100.0,
            "pending": True,
        }]
        updated = await _update_modified_transactions(session, item, modified)
        assert updated == 0

    async def test_skips_nonexistent_hash(self, session, plaid_item):
        item, _, _ = plaid_item
        modified = [{
            "transaction_hash": hashlib.sha256(b"nonexistent").hexdigest(),
            "amount": -999.0,
            "pending": False,
        }]
        updated = await _update_modified_transactions(session, item, modified)
        assert updated == 0

    async def test_empty_modified_list(self, session, plaid_item):
        item, _, _ = plaid_item
        updated = await _update_modified_transactions(session, item, [])
        assert updated == 0

    async def test_fallback_to_plaid_transaction_id(self, session, plaid_item):
        """When transaction_hash is missing, compute from plaid_transaction_id."""
        item, acct, _ = plaid_item
        plaid_id = "plaid-tx-fallback"
        expected_hash = hashlib.sha256(plaid_id.encode()).hexdigest()
        session.add(Transaction(
            account_id=acct.id,
            date=datetime(2025, 3, 1, tzinfo=timezone.utc),
            description="Target",
            amount=-30.0,
            period_year=2025,
            period_month=3,
            is_excluded=False,
            transaction_hash=expected_hash,
        ))
        await session.flush()

        modified = [{
            "plaid_transaction_id": plaid_id,
            "amount": -35.0,
            "pending": False,
        }]
        updated = await _update_modified_transactions(session, item, modified)
        assert updated == 1


# ---------------------------------------------------------------------------
# _remove_transactions
# ---------------------------------------------------------------------------

class TestRemoveTransactions:
    async def test_marks_as_excluded(self, session):
        plaid_id = "plaid-remove-001"
        tx_hash = hashlib.sha256(plaid_id.encode()).hexdigest()

        acct = Account(name="Test", institution="Test", account_type="personal")
        session.add(acct)
        await session.flush()

        session.add(Transaction(
            account_id=acct.id,
            date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            description="To be removed",
            amount=-20.0,
            period_year=2025,
            period_month=1,
            is_excluded=False,
            transaction_hash=tx_hash,
        ))
        await session.flush()

        await _remove_transactions(session, [plaid_id])

        result = await session.execute(
            select(Transaction).where(Transaction.transaction_hash == tx_hash)
        )
        tx = result.scalar_one()
        assert tx.is_excluded is True
        assert "[removed by Plaid]" in tx.notes

    async def test_empty_removed_list(self, session):
        await _remove_transactions(session, [])
        # Should not raise

    async def test_nonexistent_id_no_error(self, session):
        await _remove_transactions(session, ["nonexistent-plaid-id"])
        # Should not raise — no matching transaction to update


# ---------------------------------------------------------------------------
# sync_item (integration — mocked Plaid calls)
# ---------------------------------------------------------------------------

class TestSyncItem:
    @patch("pipeline.plaid.sync.decrypt_token", return_value="raw-token")
    @patch("pipeline.plaid.sync.get_accounts")
    @patch("pipeline.plaid.sync.sync_transactions")
    async def test_full_sync_flow(self, mock_sync_txns, mock_get_accts, mock_decrypt, session, plaid_item):
        item, acct, pa = plaid_item

        mock_get_accts.return_value = [{
            "plaid_account_id": "plaid-acct-001",
            "name": "Chase Checking",
            "type": "depository",
            "subtype": "checking",
            "current_balance": 8000.0,
            "available_balance": 7500.0,
            "limit_balance": None,
        }]
        mock_sync_txns.return_value = {
            "added": [{
                "plaid_account_id": "plaid-acct-001",
                "date": datetime(2025, 3, 1, tzinfo=timezone.utc),
                "description": "Grocery Store",
                "amount": -80.0,
                "period_month": 3,
                "period_year": 2025,
                "transaction_hash": hashlib.sha256(b"sync-tx-1").hexdigest(),
                "pending": False,
            }],
            "modified": [],
            "removed": [],
            "next_cursor": "cursor-v2",
        }

        added, updated = await sync_item(session, item)
        assert added == 1
        assert updated == 1
        assert item.plaid_cursor == "cursor-v2"

    @patch("pipeline.plaid.sync.decrypt_token")
    @patch("pipeline.plaid.sync.get_accounts")
    @patch("pipeline.plaid.sync.sync_transactions")
    async def test_sync_no_access_token(self, mock_sync, mock_accts, mock_decrypt, session):
        item = PlaidItem(
            item_id="no-token",
            access_token="",
            institution_name="NoToken Bank",
            status="active",
        )
        session.add(item)
        await session.flush()

        added, updated = await sync_item(session, item)
        assert added == 0
        assert updated == 0
        mock_decrypt.assert_not_called()

    @patch("pipeline.plaid.sync.decrypt_token", return_value="raw-token")
    @patch("pipeline.plaid.sync.get_accounts", return_value=[])
    @patch("pipeline.plaid.sync.sync_transactions")
    async def test_sync_with_removals(self, mock_sync, mock_accts, mock_decrypt, session, plaid_item):
        item, acct, _ = plaid_item
        remove_id = "plaid-to-remove"
        tx_hash = hashlib.sha256(remove_id.encode()).hexdigest()
        session.add(Transaction(
            account_id=acct.id,
            date=datetime(2025, 1, 10, tzinfo=timezone.utc),
            description="Old charge",
            amount=-15.0,
            period_year=2025,
            period_month=1,
            is_excluded=False,
            transaction_hash=tx_hash,
        ))
        await session.flush()

        mock_sync.return_value = {
            "added": [],
            "modified": [],
            "removed": [remove_id],
        }

        added, updated = await sync_item(session, item)
        assert added == 0

        result = await session.execute(
            select(Transaction).where(Transaction.transaction_hash == tx_hash)
        )
        tx = result.scalar_one()
        assert tx.is_excluded is True


# ---------------------------------------------------------------------------
# snapshot_net_worth
# ---------------------------------------------------------------------------

class TestSnapshotNetWorth:
    async def test_creates_snapshot_from_plaid_accounts(self, session):
        item = PlaidItem(
            item_id="nw-item", access_token="tok", institution_name="Bank", status="active",
        )
        session.add(item)
        await session.flush()

        # Depository account
        session.add(PlaidAccount(
            plaid_item_id=item.id, plaid_account_id="pa-check",
            name="Checking", type="depository", current_balance=10000.0,
        ))
        # Credit card
        session.add(PlaidAccount(
            plaid_item_id=item.id, plaid_account_id="pa-cc",
            name="Visa", type="credit", current_balance=-2000.0,
        ))
        # Investment
        session.add(PlaidAccount(
            plaid_item_id=item.id, plaid_account_id="pa-invest",
            name="Brokerage", type="investment", current_balance=50000.0,
        ))
        await session.flush()

        await snapshot_net_worth(session)

        result = await session.execute(select(NetWorthSnapshot))
        snap = result.scalar_one()
        assert snap.checking_savings == 10000.0
        assert snap.credit_card_debt == 2000.0
        assert snap.investment_value == 50000.0
        assert snap.total_assets == 60000.0  # checking + investment
        assert snap.total_liabilities == 2000.0
        assert snap.net_worth == 58000.0

    async def test_includes_manual_assets(self, session):
        session.add(ManualAsset(
            name="Home", asset_type="real_estate", current_value=500000.0,
            is_liability=False, is_active=True,
        ))
        session.add(ManualAsset(
            name="Mortgage", asset_type="mortgage", current_value=350000.0,
            is_liability=True, is_active=True,
        ))
        await session.flush()

        await snapshot_net_worth(session)

        result = await session.execute(select(NetWorthSnapshot))
        snap = result.scalar_one()
        assert snap.real_estate_value == 500000.0
        assert snap.mortgage_balance == 350000.0
        assert snap.net_worth == 150000.0

    async def test_upserts_same_month(self, session):
        """Running snapshot twice in same month should update, not create duplicate."""
        await snapshot_net_worth(session)
        await snapshot_net_worth(session)

        result = await session.execute(select(NetWorthSnapshot))
        snapshots = list(result.scalars().all())
        assert len(snapshots) == 1  # Upserted, not duplicated

    async def test_empty_db_creates_zero_snapshot(self, session):
        await snapshot_net_worth(session)

        result = await session.execute(select(NetWorthSnapshot))
        snap = result.scalar_one()
        assert snap.net_worth == 0.0
        assert snap.total_assets == 0.0
        assert snap.total_liabilities == 0.0

    async def test_inactive_manual_assets_excluded(self, session):
        session.add(ManualAsset(
            name="Sold Car", asset_type="vehicle", current_value=25000.0,
            is_liability=False, is_active=False,
        ))
        await session.flush()

        await snapshot_net_worth(session)

        result = await session.execute(select(NetWorthSnapshot))
        snap = result.scalar_one()
        assert snap.vehicle_value == 0.0
