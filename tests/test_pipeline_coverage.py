"""
Tests to close coverage gaps on pipeline modules below 80%.

Covers: income_sync, field_encryption, plaid/client, plaid/income_client,
seed_entities, chat_tools, chat, amazon importer, tax_analyzer,
error_reporting, file_cleanup, logging, utils, proactive_insights, smart_defaults.
"""
import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pipeline.db.schema import (
    Account,
    BenefitPackage,
    Budget,
    BusinessEntity,
    Document,
    EquityGrant,
    ErrorLog,
    FamilyMember,
    Goal,
    HouseholdProfile,
    InsurancePolicy,
    ManualAsset,
    NetWorthSnapshot,
    PayrollConnection,
    PayStubRecord,
    PlaidAccount,
    PlaidItem,
    RecurringTransaction,
    Reminder,
    TaxItem,
    TaxStrategy,
    Transaction,
    UserContext,
    VestingEvent,
    Base,
)

# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


# ═══════════════════════════════════════════════════════════════════════════
# 1. pipeline/plaid/income_sync.py
# ═══════════════════════════════════════════════════════════════════════════

class TestIncomeSync:
    """Tests for pipeline.plaid.income_sync — 16% → 80%+."""

    @pytest.mark.asyncio
    async def test_estimate_annual_income_from_ytd(self):
        from pipeline.plaid.income_sync import _estimate_annual_income
        stub = {"gross_pay_ytd": 60000, "pay_date": "2025-06-15"}
        result = _estimate_annual_income(stub)
        assert result == round(60000 * 12 / 6, 2)  # 120000.0

    @pytest.mark.asyncio
    async def test_estimate_annual_income_from_frequency(self):
        from pipeline.plaid.income_sync import _estimate_annual_income
        stub = {"gross_pay": 5000, "pay_frequency": "BIWEEKLY"}
        result = _estimate_annual_income(stub)
        assert result == round(5000 * 26, 2)

    @pytest.mark.asyncio
    async def test_estimate_annual_income_fallback(self):
        from pipeline.plaid.income_sync import _estimate_annual_income
        stub = {"gross_pay": 4000, "pay_frequency": "UNKNOWN_FREQ"}
        result = _estimate_annual_income(stub)
        assert result == round(4000 * 24, 2)

    @pytest.mark.asyncio
    async def test_estimate_annual_income_bad_date(self):
        from pipeline.plaid.income_sync import _estimate_annual_income
        stub = {"gross_pay_ytd": 50000, "pay_date": "bad-date"}
        result = _estimate_annual_income(stub)
        # Falls back to gross_pay * multiplier
        assert result == 0.0  # no gross_pay

    def test_normalize_employer(self):
        from pipeline.plaid.income_sync import _normalize_employer
        assert _normalize_employer("Accenture LLC") == "accenture"
        assert _normalize_employer("Apple Inc.") == "apple"
        assert _normalize_employer("  ") == ""
        assert _normalize_employer(None) == ""

    def test_employer_matches(self):
        from pipeline.plaid.income_sync import _employer_matches
        assert _employer_matches("Accenture", "Accenture LLC") is True
        assert _employer_matches("Google", "Meta") is False
        assert _employer_matches("", "Accenture") is False

    def test_match_to_spouse_a_match(self):
        from pipeline.plaid.income_sync import _match_to_spouse
        profile = SimpleNamespace(
            spouse_a_employer="Accenture LLC",
            spouse_b_employer="Google Inc",
            spouse_a_income=200000,
            spouse_b_income=150000,
        )
        assert _match_to_spouse(profile, "Accenture") == "a"

    def test_match_to_spouse_b_match(self):
        from pipeline.plaid.income_sync import _match_to_spouse
        profile = SimpleNamespace(
            spouse_a_employer="Accenture LLC",
            spouse_b_employer="Google Inc",
            spouse_a_income=200000,
            spouse_b_income=150000,
        )
        assert _match_to_spouse(profile, "Google") == "b"

    def test_match_to_spouse_both_match(self):
        from pipeline.plaid.income_sync import _match_to_spouse
        profile = SimpleNamespace(
            spouse_a_employer="Tech Corp",
            spouse_b_employer="Tech Corp West",
            spouse_a_income=100000,
            spouse_b_income=100000,
        )
        assert _match_to_spouse(profile, "Tech Corp") == "a"

    def test_match_to_spouse_empty_slot(self):
        from pipeline.plaid.income_sync import _match_to_spouse
        profile = SimpleNamespace(
            spouse_a_employer="Accenture",
            spouse_b_employer=None,
            spouse_a_income=200000,
            spouse_b_income=0,
        )
        assert _match_to_spouse(profile, "NewCo") == "b"

    def test_match_to_spouse_both_filled(self):
        from pipeline.plaid.income_sync import _match_to_spouse
        profile = SimpleNamespace(
            spouse_a_employer="Co A",
            spouse_b_employer="Co B",
            spouse_a_income=100000,
            spouse_b_income=80000,
        )
        # No match, both slots filled → defaults to "b"
        assert _match_to_spouse(profile, "NewCo") == "b"

    def test_extract_work_state(self):
        from pipeline.plaid.income_sync import _extract_work_state
        assert _extract_work_state(None) is None
        assert _extract_work_state({"region": "CA"}) == "CA"
        assert _extract_work_state({"state": "NY"}) == "NY"
        assert _extract_work_state("some_string") is None

    @pytest.mark.asyncio
    async def test_sync_payroll_to_household(self, session):
        from pipeline.plaid.income_sync import sync_payroll_to_household

        # Create a household profile
        profile = HouseholdProfile(
            name="Test Household",
            is_primary=True,
            spouse_a_income=100000,
            spouse_a_employer="Accenture LLC",
        )
        session.add(profile)
        await session.flush()

        # Create a payroll connection
        conn = PayrollConnection(status="pending")
        session.add(conn)
        await session.flush()

        payroll_data = {
            "pay_stubs": [
                {
                    "pay_date": date(2025, 6, 15),
                    "pay_period_start": date(2025, 6, 1),
                    "pay_period_end": date(2025, 6, 15),
                    "pay_frequency": "SEMI_MONTHLY",
                    "gross_pay": 8333.33,
                    "gross_pay_ytd": 50000,
                    "net_pay": 6000,
                    "net_pay_ytd": 36000,
                    "deductions": [
                        {"description": "401K", "current_amount": 500},
                        {"description": "Health Insurance", "current_amount": 200},
                    ],
                    "employer_name": "Accenture LLC",
                    "employer_ein": "12-3456789",
                    "employer_address": {"region": "CA", "city": "San Francisco"},
                }
            ],
            "w2s": [
                {
                    "tax_year": 2024,
                    "employer_name": "Accenture LLC",
                    "employer_ein": "12-3456789",
                    "wages_tips": 195000,
                    "federal_tax_withheld": 40000,
                    "ss_wages": 168600,
                    "ss_tax_withheld": 10453,
                    "medicare_wages": 195000,
                    "medicare_tax_withheld": 2828,
                }
            ],
        }

        counts = await sync_payroll_to_household(session, conn, payroll_data)
        assert counts["pay_stubs"] == 1
        assert counts["tax_items"] == 1
        assert conn.status == "active"
        assert conn.employer_name == "Accenture LLC"

    @pytest.mark.asyncio
    async def test_create_tax_items_dedup(self, session):
        from pipeline.plaid.income_sync import _create_tax_items

        # Create a source document first (required FK)
        doc = Document(
            filename="plaid_payroll.json",
            original_path="/tmp/plaid_payroll.json",
            file_type="json",
            document_type="plaid_payroll",
            status="completed",
            file_hash="abc123dedup",
        )
        session.add(doc)
        await session.flush()

        # Create an existing TaxItem
        existing = TaxItem(
            source_document_id=doc.id,
            form_type="w2",
            tax_year=2024,
            payer_name="Accenture LLC",
            w2_wages=195000,
        )
        session.add(existing)
        await session.flush()

        data = {
            "w2s": [{
                "tax_year": 2024,
                "employer_name": "Accenture LLC",
                "wages_tips": 195000,
            }]
        }
        count = await _create_tax_items(session, data)
        assert count == 0  # Deduped

    @pytest.mark.asyncio
    async def test_create_tax_items_no_year(self, session):
        from pipeline.plaid.income_sync import _create_tax_items
        data = {"w2s": [{"employer_name": "Foo"}]}  # No tax_year
        count = await _create_tax_items(session, data)
        assert count == 0

    @pytest.mark.asyncio
    async def test_update_benefits_no_stubs(self, session):
        from pipeline.plaid.income_sync import _update_benefits
        data = {"pay_stubs": []}
        result = await _update_benefits(session, data)
        assert result == 0

    @pytest.mark.asyncio
    async def test_update_benefits_no_deductions(self, session):
        from pipeline.plaid.income_sync import _update_benefits
        data = {"pay_stubs": [{"pay_date": "2025-01-15", "deductions": []}]}
        result = await _update_benefits(session, data)
        assert result == 0

    @pytest.mark.asyncio
    async def test_update_benefits_with_deductions(self, session):
        from pipeline.plaid.income_sync import _update_benefits

        profile = HouseholdProfile(
            name="Test", is_primary=True, spouse_a_employer="TechCo"
        )
        session.add(profile)
        await session.flush()

        data = {
            "pay_stubs": [{
                "pay_date": "2025-06-15",
                "pay_frequency": "BIWEEKLY",
                "employer_name": "TechCo",
                "deductions": [
                    {"description": "ROTH 401K", "current_amount": 800},
                    {"description": "HSA", "current_amount": 150},
                    {"description": "FSA", "current_amount": 100},
                    {"description": "Dental", "current_amount": 50},
                    {"description": "Life Insurance", "current_amount": 20},
                ],
            }]
        }
        result = await _update_benefits(session, data)
        assert result >= 4  # Multiple deductions mapped

    @pytest.mark.asyncio
    async def test_update_household_no_profile(self, session):
        from pipeline.plaid.income_sync import _update_household
        data = {"pay_stubs": [{"pay_date": "2025-06-15", "gross_pay_ytd": 50000}]}
        result = await _update_household(session, data)
        assert result == 0

    @pytest.mark.asyncio
    async def test_update_household_spouse_b(self, session):
        from pipeline.plaid.income_sync import _update_household

        profile = HouseholdProfile(
            name="Test",
            is_primary=True,
            spouse_a_employer="CompanyA",
            spouse_a_income=200000,
            spouse_b_employer=None,
            spouse_b_income=0,
        )
        session.add(profile)
        await session.flush()

        data = {
            "pay_stubs": [{
                "pay_date": "2025-06-15",
                "gross_pay_ytd": 75000,
                "employer_name": "NewEmployer",
                "employer_address": {"region": "NY"},
            }]
        }
        result = await _update_household(session, data)
        assert result > 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. pipeline/db/field_encryption.py
# ═══════════════════════════════════════════════════════════════════════════

class TestFieldEncryption:
    """Tests for pipeline.db.field_encryption — 20% → 80%+."""

    def test_encrypted_fields_registry(self):
        from pipeline.db.field_encryption import ENCRYPTED_FIELDS
        assert "HouseholdProfile" in ENCRYPTED_FIELDS
        assert "spouse_a_name" in ENCRYPTED_FIELDS["HouseholdProfile"]
        assert "FamilyMember" in ENCRYPTED_FIELDS
        assert "TaxItem" in ENCRYPTED_FIELDS

    def test_decrypted_marker_constant(self):
        from pipeline.db.field_encryption import _DECRYPTED_MARKER
        assert _DECRYPTED_MARKER == "_field_encryption_decrypted"

    @patch("pipeline.db.field_encryption._registered", False)
    @patch("pipeline.db.field_encryption.event")
    def test_register_encryption_events(self, mock_event):
        import pipeline.db.field_encryption as fe
        fe._registered = False
        fe.register_encryption_events()
        # Should have registered listeners
        assert mock_event.listen.call_count > 0
        fe._registered = False  # Reset for other tests

    @patch("pipeline.db.field_encryption._registered", True)
    def test_register_encryption_events_idempotent(self):
        """Calling register twice should be a no-op."""
        import pipeline.db.field_encryption as fe
        original_registered = fe._registered
        fe._registered = True
        fe.register_encryption_events()
        # Should not re-register
        fe._registered = original_registered


# ═══════════════════════════════════════════════════════════════════════════
# 3. pipeline/plaid/client.py
# ═══════════════════════════════════════════════════════════════════════════

class TestPlaidClient:
    """Tests for pipeline.plaid.client — 23% → 80%+."""

    def test_parse_date_none(self):
        from pipeline.plaid.client import _parse_date
        assert _parse_date(None) is None

    def test_parse_date_date_obj(self):
        from pipeline.plaid.client import _parse_date
        d = date(2025, 1, 15)
        result = _parse_date(d)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo == timezone.utc

    def test_parse_date_string(self):
        from pipeline.plaid.client import _parse_date
        result = _parse_date("2025-03-15")
        assert result.year == 2025
        assert result.month == 3
        assert result.day == 15
        assert result.tzinfo == timezone.utc

    def test_parse_date_invalid(self):
        from pipeline.plaid.client import _parse_date
        assert _parse_date("not-a-date") is None

    def test_normalize_transaction_basic(self):
        from pipeline.plaid.client import _normalize_transaction
        tx = {
            "transaction_id": "tx123",
            "account_id": "acct1",
            "date": "2025-01-15",
            "authorized_date": "2025-01-14",
            "name": "Amazon Prime",
            "merchant_name": "Amazon",
            "amount": 14.99,
            "iso_currency_code": "USD",
            "payment_channel": "online",
            "personal_finance_category": {
                "primary": "SHOPPING",
                "detailed": "GENERAL_MERCHANDISE",
                "confidence_level": "HIGH",
            },
            "location": {"city": "Seattle", "region": "WA"},
            "counterparties": [],
            "category": ["Shopping"],
            "logo_url": "https://logo.com/amzn.png",
            "website": "amazon.com",
            "pending": False,
        }
        result = _normalize_transaction(tx)
        assert result["plaid_transaction_id"] == "tx123"
        assert result["amount"] == -14.99  # Plaid flips sign
        assert result["description"] == "Amazon Prime"
        assert result["merchant_name"] == "Amazon"
        assert result["plaid_pfc_primary"] == "SHOPPING"
        assert result["pending"] is False
        assert result["period_year"] == 2025
        assert result["period_month"] == 1

    def test_normalize_transaction_no_date(self):
        from pipeline.plaid.client import _normalize_transaction
        tx = {
            "transaction_id": "tx_nodate",
            "account_id": "acct1",
            "amount": 10.0,
            "name": "Test",
        }
        result = _normalize_transaction(tx)
        # Falls back to now
        assert result["date"] is not None
        assert result["period_year"] == datetime.now(timezone.utc).year

    def test_normalize_transaction_with_to_dict_objects(self):
        """Test that objects with to_dict() are handled."""
        from pipeline.plaid.client import _normalize_transaction

        class MockPFC:
            def to_dict(self):
                return {"primary": "FOOD", "detailed": "GROCERIES", "confidence_level": "HIGH"}

        class MockLocation:
            def to_dict(self):
                return {"city": "Austin", "region": "TX"}

        class MockCP:
            def to_dict(self):
                return {"name": "Walmart", "type": "merchant", "website": "walmart.com"}

        tx = {
            "transaction_id": "tx_obj",
            "account_id": "acct1",
            "date": "2025-03-01",
            "amount": 50.0,
            "name": "Walmart",
            "personal_finance_category": MockPFC(),
            "location": MockLocation(),
            "counterparties": [MockCP()],
        }
        result = _normalize_transaction(tx)
        assert result["plaid_pfc_primary"] == "FOOD"
        counterparties = json.loads(result["plaid_counterparties_json"])
        assert len(counterparties) == 1
        assert counterparties[0]["name"] == "Walmart"

    @patch("pipeline.plaid.client.get_plaid_client")
    def test_get_accounts(self, mock_get_client):
        from pipeline.plaid.client import get_accounts
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.accounts_get.return_value = {
            "accounts": [
                {
                    "account_id": "acct_001",
                    "name": "Checking",
                    "official_name": "Premium Checking",
                    "type": "depository",
                    "subtype": "checking",
                    "balances": {"current": 5000.0, "available": 4500.0, "iso_currency_code": "USD"},
                    "mask": "1234",
                }
            ]
        }
        accounts = get_accounts("test-access-token")
        assert len(accounts) == 1
        assert accounts[0]["name"] == "Checking"
        assert accounts[0]["current_balance"] == 5000.0
        assert accounts[0]["plaid_account_id"] == "acct_001"

    @patch("pipeline.plaid.client.get_plaid_client")
    def test_exchange_public_token(self, mock_get_client):
        from pipeline.plaid.client import exchange_public_token
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.item_public_token_exchange.return_value = {
            "access_token": "access-token-abc",
            "item_id": "item-id-xyz",
        }
        result = exchange_public_token("public-token-123")
        assert result["access_token"] == "access-token-abc"
        assert result["item_id"] == "item-id-xyz"

    @patch("pipeline.plaid.client.get_plaid_client")
    def test_remove_item(self, mock_get_client):
        from pipeline.plaid.client import remove_item
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.item_remove.return_value = {"removed": True}
        assert remove_item("access-token") is True

    @patch("pipeline.plaid.client.get_plaid_client")
    def test_create_link_token_new(self, mock_get_client):
        from pipeline.plaid.client import create_link_token
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.link_token_create.return_value = {"link_token": "link-token-abc"}
        result = create_link_token(user_id="user1")
        assert result == "link-token-abc"

    @patch("pipeline.plaid.client.get_plaid_client")
    def test_create_link_token_update_mode(self, mock_get_client):
        from pipeline.plaid.client import create_link_token
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.link_token_create.return_value = {"link_token": "link-update-token"}
        result = create_link_token(access_token="existing-access-token")
        assert result == "link-update-token"

    def test_retry_on_transient_success(self):
        from pipeline.plaid.client import _retry_on_transient
        mock_fn = MagicMock(return_value="ok")
        result = _retry_on_transient(mock_fn, "arg1")
        assert result == "ok"
        mock_fn.assert_called_once_with("arg1")

    def test_retry_on_transient_non_retriable(self):
        import plaid
        from pipeline.plaid.client import _retry_on_transient
        exc = plaid.ApiException(status=400, reason="Bad Request")
        exc.body = json.dumps({"error_code": "INVALID_INPUT"})
        mock_fn = MagicMock(side_effect=exc)
        with pytest.raises(plaid.ApiException):
            _retry_on_transient(mock_fn)

    def test_transaction_hash_deterministic(self):
        from pipeline.plaid.client import _normalize_transaction
        tx = {
            "transaction_id": "tx_abc",
            "amount": 10.0,
            "date": "2025-01-01",
        }
        r1 = _normalize_transaction(tx)
        r2 = _normalize_transaction(tx)
        assert r1["transaction_hash"] == r2["transaction_hash"]
        expected = hashlib.sha256(b"tx_abc").hexdigest()
        assert r1["transaction_hash"] == expected


# ═══════════════════════════════════════════════════════════════════════════
# 4. pipeline/plaid/income_client.py
# ═══════════════════════════════════════════════════════════════════════════

class TestIncomeClient:
    """Tests for pipeline.plaid.income_client — 23% → 80%+."""

    def test_plaid_headers(self):
        from pipeline.plaid.income_client import _plaid_headers, PLAID_VERSION
        headers = _plaid_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Plaid-Version"] == PLAID_VERSION

    def test_plaid_auth(self):
        from pipeline.plaid.income_client import _plaid_auth
        auth = _plaid_auth()
        assert "client_id" in auth
        assert "secret" in auth

    def test_plaid_base_url_sandbox(self):
        from pipeline.plaid.income_client import _plaid_base_url
        with patch.dict(os.environ, {"PLAID_ENV": "sandbox"}):
            url = _plaid_base_url()
            assert "sandbox" in url

    def test_plaid_base_url_production(self):
        from pipeline.plaid.income_client import _plaid_base_url
        with patch.dict(os.environ, {"PLAID_ENV": "production"}):
            url = _plaid_base_url()
            assert "production" in url

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_create_plaid_user_with_token(self, mock_post):
        from pipeline.plaid.income_client import create_plaid_user
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"user_token": "ut-123", "user_id": "uid-456"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        result = create_plaid_user("test-user")
        assert result["user_token"] == "ut-123"
        assert result["user_id"] == "uid-456"

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_create_plaid_user_only_user_id(self, mock_post):
        from pipeline.plaid.income_client import create_plaid_user
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"user_id": "uid-789"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        result = create_plaid_user("test-user")
        assert result["user_token"] == ""
        assert result["user_id"] == "uid-789"

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_create_plaid_user_neither(self, mock_post):
        from pipeline.plaid.income_client import create_plaid_user
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        with pytest.raises(ValueError, match="neither user_token nor user_id"):
            create_plaid_user("test-user")

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_create_plaid_user_error_code(self, mock_post):
        from pipeline.plaid.income_client import create_plaid_user
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error_code": "INTERNAL_ERROR", "error_message": "failed"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        with pytest.raises(ValueError, match="INTERNAL_ERROR"):
            create_plaid_user("test-user")

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_create_income_link_token_with_user_token(self, mock_post):
        from pipeline.plaid.income_client import create_income_link_token
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"link_token": "link-income-token"}
        mock_post.return_value = mock_resp
        result = create_income_link_token(user_token="ut-abc")
        assert result == "link-income-token"

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_create_income_link_token_with_user_id(self, mock_post):
        from pipeline.plaid.income_client import create_income_link_token
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"link_token": "link-uid-token"}
        mock_post.return_value = mock_resp
        result = create_income_link_token(user_id="uid-abc")
        assert result == "link-uid-token"

    def test_create_income_link_token_no_credentials(self):
        from pipeline.plaid.income_client import create_income_link_token
        with pytest.raises(ValueError, match="Either user_token or user_id"):
            create_income_link_token()

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_create_income_link_token_failure(self, mock_post):
        from pipeline.plaid.income_client import create_income_link_token
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"error_message": "Invalid user_token"}
        mock_resp.text = "Invalid user_token"
        mock_post.return_value = mock_resp
        with pytest.raises(ValueError, match="Invalid user_token"):
            create_income_link_token(user_token="bad-token")

    def test_normalize_payroll_response_dict(self):
        from pipeline.plaid.income_client import _normalize_payroll_response
        response = {
            "items": [{
                "payroll_income": [{
                    "pay_stubs": [{
                        "employer": {"name": "TechCo", "tax_id": "12-3456789"},
                        "income_breakdown": [
                            {"current_amount": 5000, "ytd_amount": 30000}
                        ],
                        "deductions": {"breakdown": [{"description": "401k", "current_amount": 500}]},
                        "net_pay": {"current_amount": 4000, "ytd_amount": 24000},
                        "pay_date": "2025-06-15",
                        "pay_period_start_date": "2025-06-01",
                        "pay_period_end_date": "2025-06-15",
                        "pay_frequency": "BIWEEKLY",
                    }],
                    "w2s": [{
                        "employer": {"name": "TechCo", "tax_id": "12-3456789"},
                        "tax_year": 2024,
                        "wages_tips_other_comp": 195000,
                        "federal_income_tax_withheld": 40000,
                        "social_security_wages": 168600,
                        "social_security_tax_withheld": 10453,
                        "medicare_wages_and_tips": 195000,
                        "medicare_tax_withheld": 2828,
                    }],
                }],
            }],
        }
        result = _normalize_payroll_response(response)
        assert len(result["pay_stubs"]) == 1
        assert len(result["w2s"]) == 1
        assert result["pay_stubs"][0]["employer_name"] == "TechCo"
        assert result["w2s"][0]["wages_tips"] == 195000
        assert len(result["employers"]) == 1

    def test_normalize_payroll_response_with_to_dict(self):
        from pipeline.plaid.income_client import _normalize_payroll_response

        class MockResp:
            def to_dict(self):
                return {"items": []}

        result = _normalize_payroll_response(MockResp())
        assert result["pay_stubs"] == []
        assert result["w2s"] == []

    def test_get_payroll_income_no_credentials(self):
        from pipeline.plaid.income_client import get_payroll_income
        with pytest.raises(ValueError, match="Either user_token or user_id"):
            get_payroll_income()

    @patch("pipeline.plaid.income_client._retry_httpx_post")
    def test_get_payroll_income_with_user_id(self, mock_post):
        from pipeline.plaid.income_client import get_payroll_income
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": []}
        mock_post.return_value = mock_resp
        result = get_payroll_income(user_id="uid-test")
        assert result["pay_stubs"] == []

    @patch("httpx.post")
    def test_retry_httpx_post_success(self, mock_httpx):
        from pipeline.plaid.income_client import _retry_httpx_post
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.return_value = mock_resp
        result = _retry_httpx_post("https://example.com", timeout=5)
        assert result.status_code == 200
        mock_httpx.assert_called_once_with("https://example.com", timeout=5)


# ═══════════════════════════════════════════════════════════════════════════
# 5. pipeline/seed_entities.py
# ═══════════════════════════════════════════════════════════════════════════

class TestSeedEntities:
    """Tests for pipeline.seed_entities — 34% → 80%+."""

    def test_entities_list_defined(self):
        from pipeline.seed_entities import ENTITIES
        assert len(ENTITIES) >= 4
        names = [e["name"] for e in ENTITIES]
        assert "Accenture" in names

    def test_vendor_rules_defined(self):
        from pipeline.seed_entities import VENDOR_RULES
        assert len(VENDOR_RULES) > 0
        patterns = [r["vendor_pattern"] for r in VENDOR_RULES]
        assert "cursor" in patterns

    def test_entity_structure(self):
        from pipeline.seed_entities import ENTITIES
        for entity in ENTITIES:
            assert "name" in entity
            assert "entity_type" in entity
            assert "tax_treatment" in entity


# ═══════════════════════════════════════════════════════════════════════════
# 10. pipeline/security/error_reporting.py
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorReporting:
    """Tests for pipeline.security.error_reporting — 0% → 80%+."""

    @pytest.mark.asyncio
    async def test_submit_error_report(self, session):
        from pipeline.security.error_reporting import submit_error_report
        entry = await submit_error_report(
            session,
            error_type="frontend_error",
            message="Cannot read property 'foo'",
            stack_trace="Error at line 42\n  at bar()",
            source_url="https://app.sirhenry.ai/dashboard",
            user_agent="Mozilla/5.0",
            user_note="Page crashed when I clicked budget",
            context={"page": "dashboard", "action": "click"},
        )
        assert entry.id is not None
        assert entry.error_type == "frontend_error"
        assert entry.source_url == "https://app.sirhenry.ai/dashboard"
        assert entry.status == "new"
        assert entry.context_json is not None
        parsed = json.loads(entry.context_json)
        assert parsed["page"] == "dashboard"

    @pytest.mark.asyncio
    async def test_submit_error_report_pii_scrubbed(self, session):
        from pipeline.security.error_reporting import submit_error_report
        entry = await submit_error_report(
            session,
            error_type="api_error",
            message="User john@example.com with SSN 123-45-6789 had an error",
        )
        # PII should be scrubbed
        assert "123-45-6789" not in (entry.message or "")
        assert "john@example.com" not in (entry.message or "")

    @pytest.mark.asyncio
    async def test_submit_error_report_truncation(self, session):
        from pipeline.security.error_reporting import submit_error_report, MAX_MESSAGE
        long_msg = "x" * 2000
        entry = await submit_error_report(
            session,
            error_type="test",
            message=long_msg,
        )
        assert len(entry.message) <= MAX_MESSAGE

    @pytest.mark.asyncio
    async def test_submit_error_report_none_fields(self, session):
        from pipeline.security.error_reporting import submit_error_report
        entry = await submit_error_report(
            session,
            error_type="minimal_error",
        )
        assert entry.id is not None
        assert entry.message is None
        assert entry.stack_trace is None

    @pytest.mark.asyncio
    async def test_get_error_reports(self, session):
        from pipeline.security.error_reporting import submit_error_report, get_error_reports
        for i in range(3):
            await submit_error_report(session, error_type=f"error_{i}", message=f"msg {i}")
        reports, total = await get_error_reports(session)
        assert total == 3
        assert len(reports) == 3

    @pytest.mark.asyncio
    async def test_get_error_reports_with_status_filter(self, session):
        from pipeline.security.error_reporting import submit_error_report, get_error_reports
        await submit_error_report(session, error_type="err1")
        reports, total = await get_error_reports(session, status="new")
        assert total >= 1

    @pytest.mark.asyncio
    async def test_get_error_reports_pagination(self, session):
        from pipeline.security.error_reporting import submit_error_report, get_error_reports
        for i in range(5):
            await submit_error_report(session, error_type=f"err_{i}")
        reports, total = await get_error_reports(session, limit=2, offset=0)
        assert len(reports) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_update_error_status(self, session):
        from pipeline.security.error_reporting import submit_error_report, update_error_status
        entry = await submit_error_report(session, error_type="fixable")
        updated = await update_error_status(session, entry.id, "resolved")
        assert updated is not None
        assert updated.status == "resolved"

    @pytest.mark.asyncio
    async def test_update_error_status_not_found(self, session):
        from pipeline.security.error_reporting import update_error_status
        result = await update_error_status(session, 99999, "resolved")
        assert result is None

    def test_truncate_helper(self):
        from pipeline.security.error_reporting import _truncate
        assert _truncate(None, 100) is None
        assert _truncate("", 100) is None
        assert _truncate("hello", 3) == "hel"
        assert _truncate("hello", 10) == "hello"


# ═══════════════════════════════════════════════════════════════════════════
# 11. pipeline/security/file_cleanup.py
# ═══════════════════════════════════════════════════════════════════════════

class TestFileCleanup:
    """Tests for pipeline.security.file_cleanup — 76% → 80%+."""

    def test_secure_delete_nonexistent(self):
        from pipeline.security.file_cleanup import secure_delete_file
        assert secure_delete_file("/nonexistent/file.txt") is False

    def test_secure_delete_real_file(self):
        from pipeline.security.file_cleanup import secure_delete_file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"sensitive data here")
            path = f.name
        assert os.path.exists(path)
        result = secure_delete_file(path)
        assert result is True
        assert not os.path.exists(path)

    def test_cleanup_old_files_nonexistent_dir(self):
        from pipeline.security.file_cleanup import cleanup_old_files
        result = cleanup_old_files("/nonexistent/directory/xyz")
        assert result == 0

    def test_cleanup_old_files_with_files(self):
        from pipeline.security.file_cleanup import cleanup_old_files
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an "old" file
            old_file = Path(tmpdir) / "old.csv"
            old_file.write_text("old data")
            # Make it old (set mtime to 30 days ago)
            old_time = time.time() - (30 * 86400)
            os.utime(old_file, (old_time, old_time))

            # Create a "new" file
            new_file = Path(tmpdir) / "new.csv"
            new_file.write_text("new data")

            result = cleanup_old_files(tmpdir, max_age_days=7)
            assert result == 1
            assert not old_file.exists()
            assert new_file.exists()

    def test_cleanup_old_files_extension_filter(self):
        from pipeline.security.file_cleanup import cleanup_old_files
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = Path(tmpdir) / "data.xyz"
            old_file.write_text("data")
            old_time = time.time() - (30 * 86400)
            os.utime(old_file, (old_time, old_time))

            # .xyz is not in default extensions
            result = cleanup_old_files(tmpdir, max_age_days=7)
            assert result == 0
            assert old_file.exists()

    @pytest.mark.asyncio
    async def test_clear_document_raw_text(self, session):
        from pipeline.security.file_cleanup import clear_document_raw_text
        doc = Document(
            filename="w2.pdf",
            original_path="/tmp/w2.pdf",
            file_type="pdf",
            document_type="tax_form",
            status="completed",
            file_hash="abc123cleanup",
            raw_text="Sensitive W-2 data: SSN 123-45-6789",
        )
        session.add(doc)
        await session.flush()
        assert doc.raw_text is not None

        await clear_document_raw_text(session, doc.id)
        result = await session.execute(
            select(Document).where(Document.id == doc.id)
        )
        updated = result.scalar_one()
        assert updated.raw_text is None


# ═══════════════════════════════════════════════════════════════════════════
# 12. pipeline/security/logging.py
# ═══════════════════════════════════════════════════════════════════════════

class TestPIILogging:
    """Tests for pipeline.security.logging — 66% → 80%+."""

    def test_pii_redaction_filter_ssn(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        assert "[SSN]" in f._redact("SSN is 123-45-6789")

    def test_pii_redaction_filter_ssn_last4(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        assert "[SSN_LAST4]" in f._redact("ssn_last4: 6789")

    def test_pii_redaction_filter_dollar(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        assert "[$***]" in f._redact("Balance is $50,000.00")

    def test_pii_redaction_filter_email(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        assert "[EMAIL]" in f._redact("Email: test@example.com")

    def test_pii_redaction_filter_ein(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        assert "[EIN]" in f._redact("EIN: 12-3456789")

    def test_pii_redaction_known_names(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter(known_names=["Alice Smith", "Bob Jones"])
        result = f._redact("Alice Smith logged in and Bob Jones sent a message")
        assert "Alice Smith" not in result
        assert "Bob Jones" not in result
        assert "[NAME]" in result

    def test_set_known_names_dedup_and_sort(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        f.set_known_names(["Al", "Alice", "Al", "", "Bob Smith", "  "])
        # Deduped, short names filtered, sorted longest first
        assert f._known_names[0] == "Bob Smith"

    def test_filter_record_string_msg(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "SSN: 123-45-6789", None, None
        )
        f.filter(record)
        assert "123-45-6789" not in record.msg

    def test_filter_record_dict_args(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test %s", None, None
        )
        record.args = {"key": "Email: foo@bar.com"}
        f.filter(record)
        assert "foo@bar.com" not in record.args["key"]

    def test_filter_record_tuple_args(self):
        from pipeline.security.logging import PIIRedactionFilter
        f = PIIRedactionFilter()
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test %s %s", ("hello@test.com", 42), None
        )
        f.filter(record)
        assert "hello@test.com" not in record.args[0]
        assert record.args[1] == 42  # Non-string untouched

    def test_scrub_pii_standalone(self):
        from pipeline.security.logging import scrub_pii
        result = scrub_pii("SSN 123-45-6789 and $10,000")
        assert "123-45-6789" not in result
        assert "$10,000" not in result

    def test_install_pii_filter(self):
        import pipeline.security.logging as pii_mod
        old = pii_mod._filter_instance
        pii_mod._filter_instance = None
        try:
            f = pii_mod.install_pii_filter(known_names=["Test User"])
            assert f is not None
            # Second call returns same instance
            f2 = pii_mod.install_pii_filter()
            assert f2 is f
        finally:
            # Cleanup
            logging.getLogger().removeFilter(f)
            pii_mod._filter_instance = old

    def test_update_known_names_no_filter(self):
        import pipeline.security.logging as pii_mod
        old = pii_mod._filter_instance
        pii_mod._filter_instance = None
        pii_mod.update_known_names(["Test"])  # Should not crash
        pii_mod._filter_instance = old


# ═══════════════════════════════════════════════════════════════════════════
# 13. pipeline/utils.py
# ═══════════════════════════════════════════════════════════════════════════

class TestUtils:
    """Tests for pipeline.utils — 73% → 80%+."""

    def test_file_hash(self):
        from pipeline.utils import file_hash
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello world")
            path = f.name
        try:
            h = file_hash(path)
            expected = hashlib.sha256(b"hello world").hexdigest()
            assert h == expected
        finally:
            os.unlink(path)

    def test_to_float_normal(self):
        from pipeline.utils import to_float
        assert to_float("$1,234.56") == 1234.56
        assert to_float(42) == 42.0
        assert to_float("  100.5  ") == 100.5

    def test_to_float_empty(self):
        from pipeline.utils import to_float
        assert to_float(None) == 0.0
        assert to_float("") == 0.0

    def test_to_float_nan(self):
        import pandas as pd
        from pipeline.utils import to_float
        assert to_float(pd.NA) == 0.0
        assert to_float(float("nan")) == 0.0

    def test_to_float_invalid(self):
        from pipeline.utils import to_float
        assert to_float("not-a-number") == 0.0

    def test_strip_json_fences_plain(self):
        from pipeline.utils import strip_json_fences
        assert strip_json_fences('{"key": "value"}') == '{"key": "value"}'

    def test_strip_json_fences_with_json_fence(self):
        from pipeline.utils import strip_json_fences
        raw = '```json\n{"key": "value"}\n```'
        assert strip_json_fences(raw) == '{"key": "value"}'

    def test_strip_json_fences_with_plain_fence(self):
        from pipeline.utils import strip_json_fences
        raw = '```\n[1, 2, 3]\n```'
        assert strip_json_fences(raw) == '[1, 2, 3]'

    def test_get_claude_client_singleton(self):
        import pipeline.utils as utils_mod
        old = utils_mod._claude_client
        utils_mod._claude_client = None
        try:
            with patch("anthropic.Anthropic") as MockAnthropic:
                MockAnthropic.return_value = "mock-client"
                c1 = utils_mod.get_claude_client()
                c2 = utils_mod.get_claude_client()
                assert c1 == c2
                MockAnthropic.assert_called_once()
        finally:
            utils_mod._claude_client = old

    def test_call_claude_with_retry_success(self):
        from pipeline.utils import call_claude_with_retry
        mock_client = MagicMock()
        mock_client.messages.create.return_value = "response"
        result = call_claude_with_retry(mock_client, model="test", max_tokens=100, messages=[])
        assert result == "response"

    def test_call_claude_with_retry_rate_limit(self):
        from pipeline.utils import call_claude_with_retry
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            Exception("rate limit exceeded"),
            "response",
        ]
        with patch("time.sleep"):
            result = call_claude_with_retry(mock_client, max_retries=2, model="test", max_tokens=100, messages=[])
        assert result == "response"

    def test_call_claude_with_retry_non_retriable(self):
        from pipeline.utils import call_claude_with_retry
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ValueError("bad input")
        with pytest.raises(ValueError, match="bad input"):
            call_claude_with_retry(mock_client, max_retries=2, model="test", max_tokens=100, messages=[])

    def test_get_async_claude_client_singleton(self):
        import pipeline.utils as utils_mod
        old = utils_mod._async_claude_client
        utils_mod._async_claude_client = None
        try:
            with patch("anthropic.AsyncAnthropic") as MockAsync:
                MockAsync.return_value = "async-mock"
                c1 = utils_mod.get_async_claude_client()
                c2 = utils_mod.get_async_claude_client()
                assert c1 == c2
                MockAsync.assert_called_once()
        finally:
            utils_mod._async_claude_client = old

    @pytest.mark.asyncio
    async def test_call_claude_async_with_retry(self):
        from pipeline.utils import call_claude_async_with_retry
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value="async-response")
        result = await call_claude_async_with_retry(mock_client, model="test", max_tokens=100, messages=[])
        assert result == "async-response"

    @pytest.mark.asyncio
    async def test_call_claude_async_with_retry_rate_limit(self):
        from pipeline.utils import call_claude_async_with_retry
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[Exception("rate limit"), "ok"]
        )
        result = await call_claude_async_with_retry(mock_client, max_retries=2, model="test", max_tokens=100, messages=[])
        assert result == "ok"

    def test_create_engine_and_session(self):
        from pipeline.utils import create_engine_and_session
        engine, session_factory = create_engine_and_session()
        assert engine is not None
        assert session_factory is not None

    def test_default_database_url(self):
        from pipeline.utils import _default_database_url
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite+aiosqlite:///test.db"}):
            assert _default_database_url() == "sqlite+aiosqlite:///test.db"


# ═══════════════════════════════════════════════════════════════════════════
# 9. pipeline/ai/tax_analyzer.py
# ═══════════════════════════════════════════════════════════════════════════

class TestTaxAnalyzer:
    """Tests for pipeline.ai.tax_analyzer — 55% → 80%+."""

    def test_build_strategy_prompt(self):
        from pipeline.ai.tax_analyzer import _build_strategy_prompt
        snapshot = {
            "tax_year": 2025,
            "w2_wages": 200000,
            "total_business_expenses": 10000,
        }
        prompt = _build_strategy_prompt(snapshot, "- Filing: MFJ")
        assert "2025" in prompt
        assert "MFJ" in prompt
        assert "senior CPA" in prompt

    def test_build_strategy_prompt_no_context(self):
        from pipeline.ai.tax_analyzer import _build_strategy_prompt
        snapshot = {"tax_year": 2025}
        prompt = _build_strategy_prompt(snapshot)
        assert "No household profile configured" in prompt

    @pytest.mark.asyncio
    async def test_build_financial_snapshot(self, session):
        from pipeline.ai.tax_analyzer import _build_financial_snapshot

        # Seed minimal data
        profile = HouseholdProfile(
            name="Test", is_primary=True, spouse_a_income=200000
        )
        session.add(profile)

        entity = BusinessEntity(
            name="TestBiz", entity_type="sole_prop", tax_treatment="schedule_c", is_active=True
        )
        session.add(entity)
        await session.flush()

        # Mock get_tax_summary
        mock_summary = {
            "w2_total_wages": 200000,
            "w2_federal_withheld": 40000,
            "w2_state_allocations": [],
            "nec_total": 5000,
            "div_ordinary": 1000,
            "div_qualified": 500,
            "capital_gains_long": 2000,
            "capital_gains_short": 500,
            "interest_income": 300,
        }
        with patch("pipeline.ai.tax_analyzer.get_tax_summary", new_callable=AsyncMock, return_value=mock_summary):
            with patch("pipeline.ai.tax_analyzer.get_all_business_entities", new_callable=AsyncMock, return_value=[entity]):
                snapshot = await _build_financial_snapshot(session, 2025)

        assert snapshot["tax_year"] == 2025
        assert snapshot["w2_wages"] == 200000
        assert snapshot["board_income_nec"] == 5000

    @pytest.mark.asyncio
    async def test_build_tax_household_context(self, session):
        from pipeline.ai.tax_analyzer import _build_tax_household_context

        profile = HouseholdProfile(
            name="Test",
            is_primary=True,
            filing_status="mfj",
            spouse_a_income=200000,
            spouse_a_employer="TechCo",
            spouse_b_income=80000,
        )
        session.add(profile)

        entity = BusinessEntity(
            name="TestBiz", entity_type="sole_prop", tax_treatment="schedule_c",
            is_active=True, owner="Mike",
        )
        session.add(entity)
        await session.flush()

        context, sanitizer = await _build_tax_household_context(session)
        assert "MFJ" in context
        assert sanitizer is not None

    @pytest.mark.asyncio
    async def test_build_tax_household_context_with_benefits(self, session):
        from pipeline.ai.tax_analyzer import _build_tax_household_context

        profile = HouseholdProfile(
            name="Test", is_primary=True, filing_status="mfj",
            spouse_a_income=200000,
            tax_strategy_profile_json=json.dumps({"risk_tolerance": "aggressive"}),
        )
        session.add(profile)
        await session.flush()

        bp = BenefitPackage(
            household_id=profile.id,
            spouse="A",
            has_hsa=True,
            has_401k=True,
            annual_401k_contribution=23500,
        )
        session.add(bp)
        await session.flush()

        context, _ = await _build_tax_household_context(session)
        assert "HSA" in context
        assert "401(k)" in context


# ═══════════════════════════════════════════════════════════════════════════
# 8. pipeline/importers/amazon.py
# ═══════════════════════════════════════════════════════════════════════════

class TestAmazonImporter:
    """Tests for pipeline.importers.amazon — 48% → 80%+."""

    def test_parse_amazon_csv_basic(self):
        from pipeline.importers.amazon import parse_amazon_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,Original Quantity,Payment Method Type\n")
            # Same Shipment Item Subtotal means same shipment
            f.write("123-456,2025-01-15,Widget,$25.99,$13.57,1,Visa\n")
            f.write("123-456,2025-01-15,Gadget,$25.99,$13.56,2,Visa\n")
            path = f.name
        try:
            orders = parse_amazon_csv(path)
            assert len(orders) == 1  # Same shipment (same Order ID + same subtotal)
            assert orders[0]["parent_order_id"] == "123-456"
            assert orders[0]["total_charged"] == round(13.57 + 13.56, 2)
        finally:
            os.unlink(path)

    def test_parse_amazon_csv_multi_shipment(self):
        from pipeline.importers.amazon import parse_amazon_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,Original Quantity,Payment Method Type\n")
            f.write("ORD-001,2025-01-10,ItemA,$20.00,$21.00,1,Visa\n")
            f.write("ORD-001,2025-01-10,ItemB,$30.00,$31.50,1,Visa\n")
            path = f.name
        try:
            orders = parse_amazon_csv(path)
            assert len(orders) == 2
            assert any(o["order_id"].endswith("-S1") for o in orders)
            assert any(o["order_id"].endswith("-S2") for o in orders)
        finally:
            os.unlink(path)

    def test_parse_amazon_csv_legacy_format(self):
        from pipeline.importers.amazon import parse_amazon_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Order Date,Title,Item Total,Quantity\n")
            f.write("ORD-002,2025-02-20,BookTitle,$12.99,1\n")
            path = f.name
        try:
            orders = parse_amazon_csv(path)
            assert len(orders) == 1
            assert orders[0]["total_charged"] == 12.99
        finally:
            os.unlink(path)

    def test_parse_amazon_csv_invalid_format(self):
        from pipeline.importers.amazon import parse_amazon_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Col1,Col2,Col3\n")
            f.write("a,b,c\n")
            path = f.name
        try:
            with pytest.raises(ValueError, match="Unknown Amazon CSV format"):
                parse_amazon_csv(path)
        finally:
            os.unlink(path)

    def test_parse_digital_content_csv(self):
        from pipeline.importers.amazon import parse_digital_content_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Order Date,Product Name,Transaction Amount,Component Type\n")
            f.write("DIG-001,2025-03-01,Kindle Book,$9.99,Price Amount\n")
            f.write("DIG-001,2025-03-01,Kindle Book,$0.80,Tax\n")
            path = f.name
        try:
            orders = parse_digital_content_csv(path)
            assert len(orders) == 1
            assert orders[0]["total_charged"] == round(9.99 + 0.80, 2)
            assert orders[0]["is_digital"] is True
        finally:
            os.unlink(path)

    def test_parse_digital_content_csv_zero_total(self):
        from pipeline.importers.amazon import parse_digital_content_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Order Date,Product Name,Transaction Amount\n")
            f.write("DIG-FREE,2025-03-01,Free eBook,$0.00\n")
            path = f.name
        try:
            orders = parse_digital_content_csv(path)
            assert len(orders) == 0  # Zero-total orders skipped
        finally:
            os.unlink(path)

    def test_parse_digital_content_csv_missing_cols(self):
        from pipeline.importers.amazon import parse_digital_content_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Product Name\n")
            f.write("DIG-001,Book\n")
            path = f.name
        try:
            with pytest.raises(ValueError, match="missing columns"):
                parse_digital_content_csv(path)
        finally:
            os.unlink(path)

    def test_parse_refund_csv(self):
        from pipeline.importers.amazon import parse_refund_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Refund Amount,Refund Date,Reversal Reason\n")
            f.write("REF-001,$15.99,2025-02-15,Item defective\n")
            path = f.name
        try:
            refunds = parse_refund_csv(path)
            assert len(refunds) == 1
            assert refunds[0]["total_charged"] == -15.99
            assert refunds[0]["is_refund"] is True
            assert "REF-001-REFUND" in refunds[0]["order_id"]
        finally:
            os.unlink(path)

    def test_parse_refund_csv_multiple_for_same_order(self):
        from pipeline.importers.amazon import parse_refund_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Refund Amount,Refund Date,Reversal Reason\n")
            f.write("REF-002,$10.00,2025-02-10,\n")
            f.write("REF-002,$5.00,2025-02-12,\n")
            path = f.name
        try:
            refunds = parse_refund_csv(path)
            assert len(refunds) == 2
            ids = [r["order_id"] for r in refunds]
            assert "REF-002-REFUND" in ids
            assert "REF-002-REFUND-2" in ids
        finally:
            os.unlink(path)

    def test_parse_refund_csv_missing_cols(self):
        from pipeline.importers.amazon import parse_refund_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Order ID,Amount\n")
            f.write("R1,10\n")
            path = f.name
        try:
            with pytest.raises(ValueError, match="missing columns"):
                parse_refund_csv(path)
        finally:
            os.unlink(path)

    def test_enrich_raw_items_with_categories(self):
        from pipeline.importers.amazon import _enrich_raw_items_with_categories
        raw = json.dumps([
            {"title": "Widget", "quantity": 1, "price": 10.0},
            {"title": "Gadget", "quantity": 2, "price": 20.0},
        ])
        cats = [
            {"title": "Widget", "category": "Electronics", "segment": "personal"},
            {"title": "Gadget", "category": "Office Supplies", "segment": "business"},
        ]
        result = json.loads(_enrich_raw_items_with_categories(raw, cats))
        assert result[0]["category"] == "Electronics"
        assert result[1]["category"] == "Office Supplies"
        assert result[1]["segment"] == "business"

    @pytest.mark.asyncio
    async def test_build_amazon_household_context_no_session(self):
        from pipeline.importers.amazon import _build_amazon_household_context
        result = await _build_amazon_household_context(None)
        assert "No household profile" in result

    @pytest.mark.asyncio
    async def test_build_amazon_household_context_empty(self, session):
        from pipeline.importers.amazon import _build_amazon_household_context
        result = await _build_amazon_household_context(session)
        assert "Standard household" in result

    @pytest.mark.asyncio
    async def test_build_amazon_household_context_with_data(self, session):
        from pipeline.importers.amazon import _build_amazon_household_context

        profile = HouseholdProfile(
            name="Test",
            is_primary=True,
            filing_status="mfj",
            spouse_a_employer="TechCo",
            spouse_b_employer="MegaCorp",
        )
        session.add(profile)
        await session.flush()

        child = FamilyMember(
            household_id=profile.id,
            name="Junior",
            relationship="child",
        )
        session.add(child)

        biz = BusinessEntity(
            name="TestBiz", entity_type="sole_prop", is_active=True
        )
        session.add(biz)
        await session.flush()

        result = await _build_amazon_household_context(session)
        assert "MFJ" in result.upper() or "child" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 6. pipeline/ai/chat_tools.py — selected tool tests
# ═══════════════════════════════════════════════════════════════════════════

class TestChatTools:
    """Tests for pipeline.ai.chat_tools — 39% → 80%+."""

    @pytest.mark.asyncio
    async def test_list_manual_assets_empty(self, session):
        from pipeline.ai.chat_tools import _tool_list_manual_assets
        result = json.loads(await _tool_list_manual_assets(session, {}))
        assert result["count"] == 0
        assert result["total_assets"] == 0.0

    @pytest.mark.asyncio
    async def test_list_manual_assets_with_data(self, session):
        from pipeline.ai.chat_tools import _tool_list_manual_assets
        a1 = ManualAsset(name="House", asset_type="real_estate", current_value=500000, is_active=True)
        a2 = ManualAsset(name="Mortgage", asset_type="mortgage", current_value=300000, is_liability=True, is_active=True)
        session.add_all([a1, a2])
        await session.flush()

        result = json.loads(await _tool_list_manual_assets(session, {}))
        assert result["count"] == 2
        assert result["total_assets"] == 500000.0
        assert result["total_liabilities"] == 300000.0
        assert result["net"] == 200000.0

    @pytest.mark.asyncio
    async def test_list_manual_assets_type_filter(self, session):
        from pipeline.ai.chat_tools import _tool_list_manual_assets
        a1 = ManualAsset(name="House", asset_type="real_estate", current_value=500000, is_active=True)
        a2 = ManualAsset(name="Car", asset_type="vehicle", current_value=30000, is_active=True)
        session.add_all([a1, a2])
        await session.flush()

        result = json.loads(await _tool_list_manual_assets(session, {"asset_type": "vehicle"}))
        assert result["count"] == 1
        assert result["assets"][0]["name"] == "Car"

    @pytest.mark.asyncio
    async def test_update_asset_value_success(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value
        a = ManualAsset(name="House", asset_type="real_estate", current_value=500000, is_active=True)
        session.add(a)
        await session.flush()

        result = json.loads(await _tool_update_asset_value(session, {
            "asset_id": a.id, "new_value": 520000, "notes": "Zillow estimate"
        }))
        assert result["success"] is True
        assert result["old_value"] == 500000
        assert result["new_value"] == 520000

    @pytest.mark.asyncio
    async def test_update_asset_value_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value
        result = json.loads(await _tool_update_asset_value(session, {"asset_id": 999, "new_value": 100}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_asset_value_inactive(self, session):
        from pipeline.ai.chat_tools import _tool_update_asset_value
        a = ManualAsset(name="Old Car", asset_type="vehicle", current_value=5000, is_active=False)
        session.add(a)
        await session.flush()

        result = json.loads(await _tool_update_asset_value(session, {"asset_id": a.id, "new_value": 4000}))
        assert "error" in result
        assert "inactive" in result["error"]

    @pytest.mark.asyncio
    async def test_update_transaction_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction
        result = json.loads(await _tool_update_transaction(session, {"transaction_id": 999}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_transaction_no_changes(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction
        acct = Account(name="Test", institution="Bank", account_type="checking", is_active=True)
        session.add(acct)
        await session.flush()
        tx = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 1), description="Test",
            amount=-50.0, data_source="manual",
        )
        session.add(tx)
        await session.flush()

        result = json.loads(await _tool_update_transaction(session, {"transaction_id": tx.id}))
        assert "error" in result
        assert "No changes" in result["error"]

    @pytest.mark.asyncio
    async def test_update_transaction_exclude_and_notes(self, session):
        from pipeline.ai.chat_tools import _tool_update_transaction
        acct = Account(name="Test", institution="Bank", account_type="checking", is_active=True)
        session.add(acct)
        await session.flush()
        tx = Transaction(
            account_id=acct.id, date=datetime(2025, 1, 1), description="Dup",
            amount=-50.0, data_source="manual",
        )
        session.add(tx)
        await session.flush()

        result = json.loads(await _tool_update_transaction(session, {
            "transaction_id": tx.id,
            "is_excluded": True,
            "notes": "Duplicate charge",
            "is_manually_reviewed": True,
        }))
        assert result["success"] is True
        assert "excluded from reports" in result["changes"]
        assert "notes updated" in result["changes"]
        assert "marked as manually reviewed" in result["changes"]

    @pytest.mark.asyncio
    async def test_exclude_transactions_by_ids(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        acct = Account(name="Test", institution="Bank", account_type="checking", is_active=True)
        session.add(acct)
        await session.flush()

        txs = []
        for i in range(3):
            tx = Transaction(
                account_id=acct.id, date=datetime(2025, 1, i + 1),
                description=f"Tx{i}", amount=-10.0, data_source="manual",
            )
            session.add(tx)
            txs.append(tx)
        await session.flush()

        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
            "transaction_ids": [t.id for t in txs],
            "reason": "Duplicate charges",
        }))
        assert result["success"] is True
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_exclude_transactions_too_many(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        result = json.loads(await _tool_exclude_transactions(session, {
            "action": "exclude",
            "transaction_ids": list(range(51)),
        }))
        assert "error" in result
        assert "Maximum 50" in result["error"]

    @pytest.mark.asyncio
    async def test_exclude_transactions_no_criteria(self, session):
        from pipeline.ai.chat_tools import _tool_exclude_transactions
        result = json.loads(await _tool_exclude_transactions(session, {"action": "exclude"}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_save_user_context(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context
        result = json.loads(await _tool_save_user_context(session, {
            "category": "business",
            "key": "primary_biz",
            "value": "AutoRev is a car dealership SaaS company",
        }))
        assert result["success"] is True
        assert result["remembered"] is True

    @pytest.mark.asyncio
    async def test_save_user_context_invalid_category(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context
        result = json.loads(await _tool_save_user_context(session, {
            "category": "invalid_cat",
            "key": "test",
            "value": "test value",
        }))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_save_user_context_missing_fields(self, session):
        from pipeline.ai.chat_tools import _tool_save_user_context
        result = json.loads(await _tool_save_user_context(session, {
            "category": "business",
        }))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_stock_quote_error(self, session):
        from pipeline.ai.chat_tools import _tool_get_stock_quote
        with patch("pipeline.ai.chat_tools.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("API down"))
            result = json.loads(await _tool_get_stock_quote(session, {"ticker": "AAPL"}))
            assert "error" in result

    @pytest.mark.asyncio
    async def test_manage_budget_upsert_missing_fields(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        result = json.loads(await _tool_manage_budget(session, {
            "action": "upsert",
            "year": 2025,
            # Missing month, category, budget_amount
        }))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_manage_budget_unknown_action(self, session):
        from pipeline.ai.chat_tools import _tool_manage_budget
        result = json.loads(await _tool_manage_budget(session, {"action": "wipe"}))
        assert "error" in result
        assert "Unknown" in result["error"]

    @pytest.mark.asyncio
    async def test_manage_goal_delete_missing_id(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {"action": "delete"}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_manage_goal_upsert_new_missing_name(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {"action": "upsert"}))
        assert "error" in result
        assert "name" in result["error"]

    @pytest.mark.asyncio
    async def test_manage_goal_upsert_new_missing_target(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {"action": "upsert", "name": "My Goal"}))
        assert "error" in result
        assert "target_amount" in result["error"]

    @pytest.mark.asyncio
    async def test_manage_goal_unknown_action(self, session):
        from pipeline.ai.chat_tools import _tool_manage_goal
        result = json.loads(await _tool_manage_goal(session, {"action": "purge"}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_reminder_bad_date(self, session):
        from pipeline.ai.chat_tools import _tool_create_reminder
        result = json.loads(await _tool_create_reminder(session, {
            "title": "Pay taxes",
            "due_date": "not-a-date",
        }))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_business_entity_no_name(self, session):
        from pipeline.ai.chat_tools import _tool_create_business_entity
        result = json.loads(await _tool_create_business_entity(session, {}))
        assert "error" in result
        assert "name" in result["error"]

    @pytest.mark.asyncio
    async def test_update_business_entity_not_found(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        result = json.loads(await _tool_update_business_entity(session, {"entity_name": "Nonexistent Corp"}))
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_update_business_entity_no_changes(self, session):
        from pipeline.ai.chat_tools import _tool_update_business_entity
        entity = BusinessEntity(name="TestBiz", entity_type="sole_prop", is_active=True)
        session.add(entity)
        await session.flush()
        result = json.loads(await _tool_update_business_entity(session, {"entity_name": "TestBiz"}))
        assert "error" in result
        assert "No fields" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
# 7. pipeline/ai/chat.py — key coverage gaps
# ═══════════════════════════════════════════════════════════════════════════

class TestChat:
    """Tests for pipeline.ai.chat — 48% → 80%+."""

    def test_tool_labels_defined(self):
        from pipeline.ai.chat import TOOL_LABELS, TOOL_DONE_LABELS
        assert len(TOOL_LABELS) > 10
        assert len(TOOL_DONE_LABELS) > 10
        assert "search_transactions" in TOOL_LABELS
        assert "search_transactions" in TOOL_DONE_LABELS

    def test_system_prompt_base_content(self):
        from pipeline.ai.chat import _SYSTEM_PROMPT_BASE
        assert "Sir Henry" in _SYSTEM_PROMPT_BASE
        assert "financial advisor" in _SYSTEM_PROMPT_BASE
        assert "Credit Card Payment" in _SYSTEM_PROMPT_BASE

    def test_tools_list_structure(self):
        from pipeline.ai.chat import TOOLS
        assert len(TOOLS) > 10
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_invalidate_prompt_cache(self):
        from pipeline.ai.chat import invalidate_prompt_cache, _prompt_cache
        _prompt_cache["test_key"] = ("val", None, time.monotonic())
        invalidate_prompt_cache()
        assert len(_prompt_cache) == 0

    def test_max_tool_rounds(self):
        from pipeline.ai.chat import MAX_TOOL_ROUNDS
        assert MAX_TOOL_ROUNDS == 8


# ═══════════════════════════════════════════════════════════════════════════
# 14. pipeline/planning/proactive_insights.py
# ═══════════════════════════════════════════════════════════════════════════

class TestProactiveInsights:
    """Tests for pipeline.planning.proactive_insights — 75% → 80%+."""

    @pytest.mark.asyncio
    async def test_compute_proactive_insights_empty(self, session):
        from pipeline.planning.proactive_insights import compute_proactive_insights
        result = await compute_proactive_insights(session)
        assert isinstance(result, list)
        assert len(result) == 0  # No data → no insights

    @pytest.mark.asyncio
    async def test_uncategorized_transactions_below_threshold(self, session):
        from pipeline.planning.proactive_insights import _uncategorized_transactions
        # Add 5 uncategorized transactions (below threshold of 10)
        acct = Account(name="Test", institution="Bank", account_type="checking", is_active=True)
        session.add(acct)
        await session.flush()
        for i in range(5):
            tx = Transaction(
                account_id=acct.id, date=datetime(2025, 1, i + 1),
                description=f"Tx{i}", amount=-10.0, data_source="manual",
            )
            session.add(tx)
        await session.flush()
        result = await _uncategorized_transactions(session)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_uncategorized_transactions_above_threshold(self, session):
        from pipeline.planning.proactive_insights import _uncategorized_transactions
        acct = Account(name="Test", institution="Bank", account_type="checking", is_active=True)
        session.add(acct)
        await session.flush()
        for i in range(15):
            tx = Transaction(
                account_id=acct.id, date=datetime(2025, 1, (i % 28) + 1),
                description=f"Tx{i}", amount=-10.0, data_source="manual",
            )
            session.add(tx)
        await session.flush()
        result = await _uncategorized_transactions(session)
        assert len(result) == 1
        assert result[0]["type"] == "uncategorized"
        assert result[0]["value"] == 15

    @pytest.mark.asyncio
    async def test_quarterly_estimated_tax_no_business(self, session):
        from pipeline.planning.proactive_insights import _quarterly_estimated_tax
        result = await _quarterly_estimated_tax(session)
        assert result == []

    @pytest.mark.asyncio
    async def test_goal_milestones_at_50_pct(self, session):
        from pipeline.planning.proactive_insights import _goal_milestones
        goal = Goal(
            name="Emergency Fund", target_amount=10000, current_amount=5000,
            status="active",
        )
        session.add(goal)
        await session.flush()
        result = await _goal_milestones(session)
        assert len(result) == 1
        assert "50%" in result[0]["title"]

    @pytest.mark.asyncio
    async def test_goal_milestones_not_near_milestone(self, session):
        from pipeline.planning.proactive_insights import _goal_milestones
        goal = Goal(
            name="Fund", target_amount=10000, current_amount=4000,
            status="active",
        )
        session.add(goal)
        await session.flush()
        result = await _goal_milestones(session)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_missing_tax_docs_outside_season(self, session):
        from pipeline.planning.proactive_insights import _missing_tax_docs
        # If current month > April, should return empty
        today = date.today()
        if today.month > 4:
            result = await _missing_tax_docs(session)
            assert result == []

    @pytest.mark.asyncio
    async def test_insurance_renewals(self, session):
        from pipeline.planning.proactive_insights import _insurance_renewals
        profile = HouseholdProfile(name="Test", is_primary=True)
        session.add(profile)
        await session.flush()

        renewal_date = date.today() + timedelta(days=30)
        policy = InsurancePolicy(
            household_id=profile.id,
            policy_type="auto",
            provider="GEICO",
            annual_premium=1200,
            is_active=True,
            renewal_date=renewal_date,
        )
        session.add(policy)
        await session.flush()

        result = await _insurance_renewals(session)
        assert len(result) == 1
        assert result[0]["type"] == "insurance_renewal"

    @pytest.mark.asyncio
    async def test_insurance_renewals_too_far(self, session):
        from pipeline.planning.proactive_insights import _insurance_renewals
        profile = HouseholdProfile(name="Test", is_primary=True)
        session.add(profile)
        await session.flush()

        far_date = date.today() + timedelta(days=90)
        policy = InsurancePolicy(
            household_id=profile.id,
            policy_type="home",
            is_active=True,
            renewal_date=far_date,
        )
        session.add(policy)
        await session.flush()

        result = await _insurance_renewals(session)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_underwithholding_no_vest_income(self, session):
        from pipeline.planning.proactive_insights import _underwithholding_gap
        result = await _underwithholding_gap(session)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# 15. pipeline/planning/smart_defaults.py
# ═══════════════════════════════════════════════════════════════════════════

class TestSmartDefaults:
    """Tests for pipeline.planning.smart_defaults — 74% → 80%+."""

    @pytest.mark.asyncio
    async def test_compute_smart_defaults_empty(self, session):
        from pipeline.planning.smart_defaults import compute_smart_defaults
        result = await compute_smart_defaults(session)
        assert "household" in result
        assert "income" in result
        assert "retirement" in result
        assert "expenses" in result
        assert "debts" in result
        assert "assets" in result
        assert "net_worth" in result
        assert "recurring" in result
        assert "equity" in result
        assert "tax" in result
        assert "benefits" in result
        assert "goals" in result
        assert "businesses" in result
        assert "data_sources" in result

    @pytest.mark.asyncio
    async def test_household_defaults_empty(self, session):
        from pipeline.planning.smart_defaults import _household_defaults
        result = await _household_defaults(session)
        assert result == {}

    @pytest.mark.asyncio
    async def test_household_defaults_with_profile(self, session):
        from pipeline.planning.smart_defaults import _household_defaults
        profile = HouseholdProfile(
            name="Test",
            is_primary=True,
            filing_status="mfj",
            state="CA",
            spouse_a_name="Alice",
            spouse_a_income=200000,
            spouse_a_employer="TechCo",
            spouse_b_name="Bob",
            spouse_b_income=80000,
            combined_income=280000,
        )
        session.add(profile)
        await session.flush()

        result = await _household_defaults(session)
        assert result["filing_status"] == "mfj"
        assert result["combined_income"] == 280000
        assert result["spouse_a_income"] == 200000

    @pytest.mark.asyncio
    async def test_household_defaults_non_primary_fallback(self, session):
        from pipeline.planning.smart_defaults import _household_defaults
        profile = HouseholdProfile(name="Test", is_primary=False, filing_status="single")
        session.add(profile)
        await session.flush()

        result = await _household_defaults(session)
        assert result["filing_status"] == "single"

    @pytest.mark.asyncio
    async def test_age_defaults_no_member(self, session):
        from pipeline.planning.smart_defaults import _age_defaults
        result = await _age_defaults(session)
        assert result["current_age"] is None

    @pytest.mark.asyncio
    async def test_age_defaults_with_member(self, session):
        from pipeline.planning.smart_defaults import _age_defaults
        profile = HouseholdProfile(name="Test", is_primary=True)
        session.add(profile)
        await session.flush()

        member = FamilyMember(
            household_id=profile.id,
            name="Test User",
            relationship="self",
            date_of_birth=date(1990, 6, 15),
        )
        session.add(member)
        await session.flush()

        result = await _age_defaults(session)
        assert result["current_age"] is not None
        assert 30 <= result["current_age"] <= 40

    @pytest.mark.asyncio
    async def test_net_worth_defaults_empty(self, session):
        from pipeline.planning.smart_defaults import _net_worth_defaults
        result = await _net_worth_defaults(session)
        assert result["net_worth"] == 0
        assert result["as_of"] is None

    @pytest.mark.asyncio
    async def test_net_worth_defaults_with_snapshot(self, session):
        from pipeline.planning.smart_defaults import _net_worth_defaults
        snap = NetWorthSnapshot(
            snapshot_date=datetime.now(timezone.utc),
            year=2025, month=3,
            total_assets=1000000, total_liabilities=300000, net_worth=700000,
        )
        session.add(snap)
        await session.flush()

        result = await _net_worth_defaults(session)
        assert result["net_worth"] == 700000
        assert result["as_of"] == "2025-03"

    @pytest.mark.asyncio
    async def test_recurring_defaults_empty(self, session):
        from pipeline.planning.smart_defaults import _recurring_defaults
        result = await _recurring_defaults(session)
        assert result == []

    @pytest.mark.asyncio
    async def test_recurring_defaults_with_data(self, session):
        from pipeline.planning.smart_defaults import _recurring_defaults
        rec = RecurringTransaction(
            name="Netflix", amount=-15.99, frequency="monthly",
            category="Entertainment", status="active",
        )
        session.add(rec)
        await session.flush()

        result = await _recurring_defaults(session)
        assert len(result) == 1
        assert result[0]["name"] == "Netflix"
        assert result[0]["amount"] == 15.99  # abs

    @pytest.mark.asyncio
    async def test_equity_defaults_empty(self, session):
        from pipeline.planning.smart_defaults import _equity_defaults
        result = await _equity_defaults(session)
        assert result["total_value"] == 0

    @pytest.mark.asyncio
    async def test_equity_defaults_with_grants(self, session):
        from pipeline.planning.smart_defaults import _equity_defaults
        grant = EquityGrant(
            employer_name="TechCo",
            grant_type="RSU",
            grant_date=date(2024, 1, 1),
            total_shares=1000,
            vested_shares=500,
            unvested_shares=500,
            current_fmv=100.0,
            is_active=True,
        )
        session.add(grant)
        await session.flush()

        result = await _equity_defaults(session)
        assert result["vested_value"] == 50000.0
        assert result["unvested_value"] == 50000.0
        assert result["total_value"] == 100000.0

    @pytest.mark.asyncio
    async def test_tax_defaults_empty(self, session):
        from pipeline.planning.smart_defaults import _tax_defaults
        result = await _tax_defaults(session)
        assert result["total_withholding"] == 0
        assert result["tax_year"] is None

    @pytest.mark.asyncio
    async def test_benefits_defaults_empty(self, session):
        from pipeline.planning.smart_defaults import _benefits_defaults
        result = await _benefits_defaults(session)
        assert result["has_401k"] is False
        assert result["has_hsa"] is False

    @pytest.mark.asyncio
    async def test_benefits_defaults_with_data(self, session):
        from pipeline.planning.smart_defaults import _benefits_defaults
        profile = HouseholdProfile(name="Test", is_primary=True)
        session.add(profile)
        await session.flush()

        bp = BenefitPackage(
            household_id=profile.id,
            spouse="A",
            has_401k=True,
            has_hsa=True,
            has_espp=True,
            has_mega_backdoor=True,
            employer_match_pct=6.0,
            employer_match_limit_pct=3.0,
            health_premium_monthly=500,
        )
        session.add(bp)
        await session.flush()

        result = await _benefits_defaults(session)
        assert result["has_401k"] is True
        assert result["has_hsa"] is True
        assert result["has_espp"] is True
        assert result["match_pct"] == 6.0
        assert result["health_premium_monthly"] == 500

    @pytest.mark.asyncio
    async def test_goals_defaults(self, session):
        from pipeline.planning.smart_defaults import _goals_defaults
        goal = Goal(
            name="House Down Payment",
            target_amount=100000,
            current_amount=25000,
            monthly_contribution=2000,
            status="active",
        )
        session.add(goal)
        await session.flush()

        result = await _goals_defaults(session)
        assert len(result) == 1
        assert result[0]["progress_pct"] == 25.0

    @pytest.mark.asyncio
    async def test_business_defaults(self, session):
        from pipeline.planning.smart_defaults import _business_defaults
        biz = BusinessEntity(
            name="AutoRev",
            entity_type="sole_prop",
            tax_treatment="schedule_c",
            is_active=True,
        )
        session.add(biz)
        await session.flush()

        result = await _business_defaults(session)
        assert len(result) == 1
        assert result[0]["name"] == "AutoRev"

    @pytest.mark.asyncio
    async def test_data_source_flags(self, session):
        from pipeline.planning.smart_defaults import _data_source_flags
        result = await _data_source_flags(session)
        assert result["has_w2"] is False
        assert result["has_plaid"] is False
        assert result["has_household"] is False

    @pytest.mark.asyncio
    async def test_asset_defaults_with_types(self, session):
        from pipeline.planning.smart_defaults import _asset_defaults
        a1 = ManualAsset(name="House", asset_type="real_estate", current_value=500000, is_active=True)
        a2 = ManualAsset(name="Brokerage", asset_type="investment", current_value=100000, is_active=True)
        a3 = ManualAsset(name="Car", asset_type="vehicle", current_value=30000, is_active=True)
        a4 = ManualAsset(name="401k", asset_type="retirement", current_value=200000,
                         is_active=True, is_retirement_account=True)
        a5 = ManualAsset(name="Art", asset_type="collectible", current_value=5000, is_active=True)
        session.add_all([a1, a2, a3, a4, a5])
        await session.flush()

        result = await _asset_defaults(session)
        assert result["real_estate_total"] == 500000
        assert result["investment_total"] == 100000
        assert result["vehicle_total"] == 30000
        assert result["retirement_total"] == 200000
        assert result["other_total"] == 5000

    @pytest.mark.asyncio
    async def test_detect_household_updates_no_profile(self, session):
        from pipeline.planning.smart_defaults import detect_household_updates
        result = await detect_household_updates(session)
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_household_updates_no_w2(self, session):
        from pipeline.planning.smart_defaults import detect_household_updates
        profile = HouseholdProfile(
            name="Test", is_primary=True, spouse_a_employer="TechCo"
        )
        session.add(profile)
        await session.flush()
        result = await detect_household_updates(session)
        assert result == []
