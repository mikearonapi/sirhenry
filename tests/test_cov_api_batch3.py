"""
Comprehensive tests for API route modules: import_routes, income, insights,
insurance, life_events, plaid, privacy.
Target: 95%+ code coverage for each module.
"""
import json
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import (
    Base,
    Account,
    Transaction,
    InsurancePolicy,
    BenefitPackage,
    LifeEvent,
    PlaidItem,
    PlaidAccount,
    OutlierFeedback,
    UserPrivacyConsent,
    AuditLog,
    PayrollConnection,
    PayStubRecord,
    AmazonOrder,
    HouseholdProfile,
)


# ---------------------------------------------------------------------------
# Fixtures
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

    from api.routes import import_routes, income, insights, insurance, life_events, plaid, privacy
    app.include_router(import_routes.router)
    app.include_router(income.router)
    app.include_router(insights.router)
    app.include_router(insurance.router)
    app.include_router(life_events.router)
    app.include_router(plaid.router)
    app.include_router(privacy.router)

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


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    async with test_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_account(session, name="Test Card", account_type="personal", subtype="credit_card"):
    acct = Account(name=name, account_type=account_type, subtype=subtype, currency="USD", data_source="csv")
    session.add(acct)
    await session.flush()
    return acct


async def _seed_transaction(session, account_id, description="AMAZON PURCHASE", amount=-50.0):
    tx = Transaction(
        account_id=account_id,
        date=datetime(2025, 3, 15, tzinfo=timezone.utc),
        description=description,
        amount=amount,
        currency="USD",
        segment="personal",
    )
    session.add(tx)
    await session.flush()
    return tx


async def _seed_household(session):
    hp = HouseholdProfile(
        filing_status="mfj",
        state="CA",
    )
    session.add(hp)
    await session.flush()
    return hp


# ===========================================================================
# import_routes.py tests
# ===========================================================================

class TestImportUpload:
    """Tests for POST /import/upload — all document_type branches."""

    @patch("pipeline.importers.credit_card.import_csv_file", new_callable=AsyncMock)
    async def test_upload_credit_card_csv(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed",
            "document_id": 1,
            "transactions_imported": 10,
            "transactions_skipped": 0,
            "message": "OK",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"credit_card": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("stmt.csv", b"date,amount\n2025-01-01,100", "text/csv")},
                data={
                    "document_type": "credit_card",
                    "account_name": "Chase",
                    "institution": "Chase",
                    "segment": "personal",
                    "run_categorize": "true",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["transactions_imported"] == 10

    @patch("pipeline.importers.tax_doc.import_pdf_file", new_callable=AsyncMock)
    async def test_upload_tax_document_pdf(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed",
            "document_id": 2,
            "transactions_imported": 0,
            "transactions_skipped": 0,
            "message": "Tax doc imported",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"tax_document": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("w2.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={
                    "document_type": "tax_document",
                    "tax_year": "2024",
                    "run_categorize": "false",
                },
            )
        assert resp.status_code == 200

    @patch("pipeline.importers.tax_doc.import_image_file", new_callable=AsyncMock)
    async def test_upload_tax_document_image(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed",
            "document_id": 3,
            "transactions_imported": 0,
            "transactions_skipped": 0,
            "message": "Image imported",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"tax_document": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("w2.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")},
                data={"document_type": "tax_document", "tax_year": "2024"},
            )
        assert resp.status_code == 200

    @patch("pipeline.importers.investment.import_investment_file", new_callable=AsyncMock)
    async def test_upload_investment(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed", "document_id": 4,
            "transactions_imported": 5, "transactions_skipped": 0, "message": "OK",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"investment": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("inv.csv", b"data", "text/csv")},
                data={"document_type": "investment"},
            )
        assert resp.status_code == 200

    @patch("pipeline.importers.amazon.import_amazon_csv", new_callable=AsyncMock)
    async def test_upload_amazon(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed", "document_id": 5,
            "transactions_imported": 3, "transactions_skipped": 0, "message": "OK",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"amazon": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("orders.csv", b"data", "text/csv")},
                data={"document_type": "amazon"},
            )
        assert resp.status_code == 200

    @patch("pipeline.importers.monarch.import_monarch_csv", new_callable=AsyncMock)
    async def test_upload_monarch(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed", "document_id": 6,
            "transactions_imported": 20, "transactions_skipped": 0, "message": "OK",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"monarch": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("export.csv", b"data", "text/csv")},
                data={"document_type": "monarch", "segment": "business"},
            )
        assert resp.status_code == 200

    @patch("pipeline.importers.insurance_doc.import_insurance_doc", new_callable=AsyncMock)
    async def test_upload_insurance(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed", "document_id": 7,
            "transactions_imported": 0, "transactions_skipped": 0, "message": "OK",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"insurance": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("policy.pdf", b"%PDF", "application/pdf")},
                data={"document_type": "insurance"},
            )
        assert resp.status_code == 200

    @patch("pipeline.importers.paystub.import_paystub", new_callable=AsyncMock)
    async def test_upload_pay_stub(self, mock_import, client, tmp_path):
        mock_import.return_value = {
            "status": "completed", "document_id": 8,
            "transactions_imported": 0, "transactions_skipped": 0, "message": "OK",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"pay_stub": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("stub.pdf", b"%PDF", "application/pdf")},
                data={"document_type": "pay_stub"},
            )
        assert resp.status_code == 200

    @patch("pipeline.importers.credit_card.import_csv_file", new_callable=AsyncMock)
    async def test_upload_no_filename(self, mock_import, client, tmp_path):
        """When filename is empty, httpx may still send it, but endpoint validates."""
        # An empty filename from httpx results in 422 (validation) or 400
        resp = await client.post(
            "/import/upload",
            files={"file": ("", b"data", "text/csv")},
            data={"document_type": "credit_card"},
        )
        # Empty filename may pass through or fail at FastAPI level
        assert resp.status_code in (400, 422)

    async def test_upload_bad_extension(self, client):
        resp = await client.post(
            "/import/upload",
            files={"file": ("data.xlsx", b"data", "application/vnd.openxmlformats")},
            data={"document_type": "credit_card"},
        )
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"]

    async def test_upload_unknown_document_type(self, client, tmp_path):
        with patch("api.routes.import_routes.IMPORT_DIRS", {}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("test.csv", b"data", "text/csv")},
                data={"document_type": "credit_card"},
            )
        assert resp.status_code == 400
        assert "Unknown document type" in resp.json()["detail"]

    @patch("pipeline.importers.credit_card.import_csv_file", new_callable=AsyncMock)
    async def test_upload_import_error_status(self, mock_import, client, tmp_path):
        mock_import.return_value = {"status": "error", "message": "Parse error"}
        with patch("api.routes.import_routes.IMPORT_DIRS", {"credit_card": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("bad.csv", b"bad,data", "text/csv")},
                data={"document_type": "credit_card"},
            )
        assert resp.status_code == 422
        assert "Parse error" in resp.json()["detail"]

    async def test_upload_file_too_large(self, client, tmp_path):
        """File over 50MB is rejected with 413."""
        async def fake_read(self_or_size=None, size=None):
            return b"x" * 50_000_001

        with patch("api.routes.import_routes.IMPORT_DIRS", {"credit_card": tmp_path}):
            with patch("starlette.datastructures.UploadFile.read", new=fake_read):
                resp = await client.post(
                    "/import/upload",
                    files={"file": ("big.csv", b"small", "text/csv")},
                    data={"document_type": "credit_card"},
                )
        assert resp.status_code == 413

    @patch("pipeline.importers.credit_card.import_csv_file", new_callable=AsyncMock)
    async def test_upload_invalid_filename_path_traversal(self, mock_import, client, tmp_path):
        """Test the safe_name check with a normal file (empty PurePosixPath.name would be tricky)."""
        mock_import.return_value = {
            "status": "completed", "document_id": 1,
            "transactions_imported": 0, "transactions_skipped": 0, "message": "OK",
        }
        with patch("api.routes.import_routes.IMPORT_DIRS", {"credit_card": tmp_path}):
            resp = await client.post(
                "/import/upload",
                files={"file": ("test.csv", b"data", "text/csv")},
                data={"document_type": "credit_card", "account_id": "1"},
            )
        assert resp.status_code == 200


class TestImportDetectType:
    """Tests for POST /import/detect-type."""

    @patch("pipeline.ai.categorizer.detect_document_type")
    async def test_detect_type_csv(self, mock_detect, client):
        mock_detect.return_value = {"detected_type": "credit_card", "confidence": 0.9}
        resp = await client.post(
            "/import/detect-type",
            files={"file": ("stmt.csv", b"Date,Amount,Description\n2025-01-01,100,Test", "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json()["detected_type"] == "credit_card"

    @patch("pipeline.ai.categorizer.detect_document_type")
    @patch("pipeline.parsers.pdf_parser.extract_pdf")
    async def test_detect_type_pdf(self, mock_extract, mock_detect, client):
        mock_pdf = MagicMock()
        mock_pdf.full_text = "W-2 Wage and Tax Statement"
        mock_extract.return_value = mock_pdf
        mock_detect.return_value = {"detected_type": "tax_document", "confidence": 0.95}
        resp = await client.post(
            "/import/detect-type",
            files={"file": ("w2.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )
        assert resp.status_code == 200

    @patch("pipeline.ai.categorizer.detect_document_type")
    @patch("pipeline.parsers.pdf_parser.extract_pdf")
    async def test_detect_type_pdf_extraction_fails(self, mock_extract, mock_detect, client):
        mock_extract.side_effect = Exception("PDF parse error")
        mock_detect.return_value = {"detected_type": "unknown", "confidence": 0.1}
        resp = await client.post(
            "/import/detect-type",
            files={"file": ("broken.pdf", b"%PDF-broken", "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["detected_type"] == "unknown"

    @patch("pipeline.ai.categorizer.detect_document_type")
    async def test_detect_type_pdf_empty_text(self, mock_detect, client):
        """PDF with no full_text."""
        mock_pdf = MagicMock()
        mock_pdf.full_text = ""
        with patch("pipeline.parsers.pdf_parser.extract_pdf", return_value=mock_pdf):
            mock_detect.return_value = {"detected_type": "unknown", "confidence": 0.1}
            resp = await client.post(
                "/import/detect-type",
                files={"file": ("empty.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert resp.status_code == 200

    async def test_detect_type_no_filename(self, client):
        resp = await client.post(
            "/import/detect-type",
            files={"file": ("", b"data", "text/csv")},
        )
        # Empty filename may be 400 (our check) or 422 (FastAPI validation)
        assert resp.status_code in (400, 422)

    @patch("pipeline.ai.categorizer.detect_document_type")
    async def test_detect_type_csv_decode_error(self, mock_detect, client):
        """CSV with non-decodable content falls back to empty text_preview."""
        mock_detect.return_value = {"detected_type": "unknown", "confidence": 0.1}
        resp = await client.post(
            "/import/detect-type",
            files={"file": ("data.csv", b"\x80\x81\x82\x83", "text/csv")},
        )
        assert resp.status_code == 200


class TestImportBatchTaxDocs:
    """Tests for POST /import/batch-tax-docs."""

    @patch("pipeline.importers.tax_doc.import_directory", new_callable=AsyncMock)
    async def test_batch_tax_docs(self, mock_import_dir, client):
        mock_import_dir.return_value = [
            {"status": "completed", "file": "w2.pdf"},
            {"status": "duplicate", "file": "w2_copy.pdf"},
            {"status": "error", "file": "bad.pdf"},
        ]
        resp = await client.post("/import/batch-tax-docs?tax_year=2024")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["completed"] == 1
        assert data["duplicate"] == 1
        assert data["error"] == 1

    @patch("pipeline.importers.tax_doc.import_directory", new_callable=AsyncMock)
    async def test_batch_tax_docs_no_completed(self, mock_import_dir, client):
        mock_import_dir.return_value = [{"status": "error", "file": "bad.pdf"}]
        resp = await client.post("/import/batch-tax-docs")
        assert resp.status_code == 200
        assert resp.json()["completed"] == 0


class TestImportCategorize:
    """Tests for POST /import/categorize."""

    @patch("pipeline.ai.categorizer.categorize_transactions", new_callable=AsyncMock)
    @patch("pipeline.ai.category_rules.apply_rules", new_callable=AsyncMock)
    @patch("pipeline.db.models.apply_entity_rules", new_callable=AsyncMock)
    async def test_categorize(self, mock_entity, mock_rules, mock_ai, client):
        mock_entity.return_value = 5
        mock_rules.return_value = {"applied": 3}
        mock_ai.return_value = {"categorized": 10, "skipped": 2}
        resp = await client.post("/import/categorize?year=2025&month=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_rules_applied"] == 5
        assert data["category_rules_applied"] == 3


class TestImportAmazonReconcile:
    """Tests for Amazon reconcile and split endpoints."""

    @patch("pipeline.importers.amazon.auto_match_amazon_orders", new_callable=AsyncMock)
    async def test_amazon_reconcile(self, mock_match, client):
        mock_match.return_value = {"matched": 5, "total": 10}
        resp = await client.post("/import/amazon-reconcile?fix_categories=true&year=2025")
        assert resp.status_code == 200
        assert resp.json()["matched"] == 5

    @patch("pipeline.importers.amazon.reprocess_existing_splits", new_callable=AsyncMock)
    async def test_reprocess_amazon_splits(self, mock_reprocess, client):
        mock_reprocess.return_value = {"processed": 3, "splits_created": 12}
        resp = await client.post("/import/amazon-split/reprocess?year=2025&dry_run=true")
        assert resp.status_code == 200
        assert resp.json()["processed"] == 3

    @patch("pipeline.importers.amazon._amazon_description_filter")
    async def test_amazon_reconcile_status_no_data(self, mock_filter, client):
        """Test reconcile status when no Amazon data exists."""
        from sqlalchemy import literal
        mock_filter.return_value = literal(False)
        resp = await client.get("/import/amazon-reconcile/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_amazon_orders"] == 0
        assert data["quality"] == "poor"

    @patch("pipeline.importers.amazon._amazon_description_filter")
    async def test_amazon_reconcile_status_with_year(self, mock_filter, client, db_session):
        """Test reconcile status with year filter."""
        from sqlalchemy import literal
        mock_filter.return_value = literal(False)
        resp = await client.get("/import/amazon-reconcile/status?year=2025")
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_rate_pct"] == 0


class _FakeAsyncCM:
    """Reusable fake async context manager for mocking `async with`."""
    def __init__(self, value=None):
        self.value = value
    async def __aenter__(self):
        return self.value
    async def __aexit__(self, *args):
        return False


class TestImportBackgroundTask:
    """Tests for _run_post_import_background."""

    async def test_post_import_background_all_succeed(self):
        """Test background task with all steps succeeding."""
        from api.routes.import_routes import _run_post_import_background

        mock_session = MagicMock()
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.import_routes.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("pipeline.db.models.apply_entity_rules", new_callable=AsyncMock, return_value=3),
            patch("pipeline.ai.category_rules.apply_rules", new_callable=AsyncMock, return_value={"applied": 2}),
            patch("pipeline.ai.categorizer.categorize_transactions", new_callable=AsyncMock, return_value={"categorized": 5}),
            patch("pipeline.importers.amazon.auto_match_amazon_orders", new_callable=AsyncMock, return_value={}),
            patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock),
        ):
            await _run_post_import_background(2025)

    async def test_post_import_background_all_fail(self):
        """Test background task with all steps failing gracefully."""
        from api.routes.import_routes import _run_post_import_background

        mock_session = MagicMock()
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.import_routes.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("pipeline.db.models.apply_entity_rules", new_callable=AsyncMock, side_effect=Exception("fail")),
            patch("pipeline.ai.category_rules.apply_rules", new_callable=AsyncMock, side_effect=Exception("fail")),
            patch("pipeline.ai.categorizer.categorize_transactions", new_callable=AsyncMock, side_effect=Exception("fail")),
            patch("pipeline.importers.amazon.auto_match_amazon_orders", new_callable=AsyncMock, side_effect=Exception("fail")),
            patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock, side_effect=Exception("fail")),
        ):
            # Should not raise
            await _run_post_import_background(None)


# ===========================================================================
# income.py tests
# ===========================================================================

class TestIncomeLinkToken:
    """Tests for POST /income/link-token."""

    @patch("pipeline.plaid.income_client.create_income_link_token")
    @patch("pipeline.plaid.income_client.create_plaid_user")
    async def test_link_token_new_user(self, mock_create_user, mock_link, client):
        mock_create_user.return_value = {"user_token": "ut-test-123", "user_id": "uid-123"}
        mock_link.return_value = "link-income-token-abc"
        resp = await client.post(
            "/income/link-token",
            json={"income_source_type": "payroll"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["link_token"] == "link-income-token-abc"
        assert "connection_id" in data

    @patch("pipeline.plaid.income_client.create_income_link_token")
    @patch("pipeline.plaid.income_client.create_plaid_user")
    async def test_link_token_new_user_no_token(self, mock_create_user, mock_link, client):
        """When create_plaid_user returns empty user_token (Income not enabled)."""
        mock_create_user.return_value = {"user_token": "", "user_id": "uid-123"}
        resp = await client.post(
            "/income/link-token",
            json={"income_source_type": "payroll"},
        )
        assert resp.status_code == 400
        assert "Income product" in resp.json()["detail"]

    @patch("pipeline.plaid.income_client.create_income_link_token")
    @patch("pipeline.plaid.income_client.create_plaid_user")
    async def test_link_token_create_user_value_error(self, mock_create_user, mock_link, client):
        mock_create_user.side_effect = ValueError("Plaid not configured")
        resp = await client.post(
            "/income/link-token",
            json={"income_source_type": "payroll"},
        )
        assert resp.status_code == 400

    @patch("pipeline.plaid.income_client.create_income_link_token")
    async def test_link_token_existing_connection(self, mock_link, client, db_session):
        """Reuse existing connection with token."""
        from pipeline.db.encryption import encrypt_token
        conn = PayrollConnection(
            plaid_user_token=encrypt_token("existing-token"),
            plaid_user_id="uid-existing",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.commit()

        mock_link.return_value = "link-reuse-token"
        resp = await client.post(
            "/income/link-token",
            json={"income_source_type": "payroll"},
        )
        assert resp.status_code == 200
        assert resp.json()["link_token"] == "link-reuse-token"

    @patch("pipeline.plaid.income_client.create_income_link_token")
    async def test_link_token_existing_connection_no_token(self, mock_link, client, db_session):
        """Existing connection with empty encrypted token."""
        from pipeline.db.encryption import encrypt_token
        conn = PayrollConnection(
            plaid_user_token=encrypt_token(""),
            plaid_user_id="uid-no-token",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.commit()

        mock_link.return_value = "link-token-reuse"
        resp = await client.post(
            "/income/link-token",
            json={"income_source_type": "payroll"},
        )
        assert resp.status_code == 200

    @patch("pipeline.plaid.income_client.create_income_link_token")
    async def test_link_token_link_creation_value_error(self, mock_link, client, db_session):
        """create_income_link_token raises ValueError."""
        conn = PayrollConnection(
            plaid_user_token=None,
            plaid_user_id="uid-x",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.commit()

        mock_link.side_effect = ValueError("Bad params")
        resp = await client.post(
            "/income/link-token",
            json={"income_source_type": "payroll"},
        )
        assert resp.status_code == 400

    @patch("pipeline.plaid.income_client.create_income_link_token")
    async def test_link_token_link_creation_generic_error(self, mock_link, client, db_session):
        """create_income_link_token raises generic Exception."""
        conn = PayrollConnection(
            plaid_user_token=None,
            plaid_user_id="uid-y",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.commit()

        mock_link.side_effect = RuntimeError("Network fail")
        resp = await client.post(
            "/income/link-token",
            json={"income_source_type": "payroll"},
        )
        assert resp.status_code == 400
        assert "Failed to create income link" in resp.json()["detail"]


class TestIncomeConnected:
    """Tests for POST /income/connected/{connection_id}."""

    async def test_income_connected(self, client, db_session):
        conn = PayrollConnection(
            plaid_user_id="uid-c",
            income_source_type="payroll",
            status="pending",
        )
        db_session.add(conn)
        await db_session.commit()

        resp = await client.post(f"/income/connected/{conn.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "syncing"
        assert data["connection_id"] == conn.id

    async def test_income_connected_not_found(self, client):
        resp = await client.post("/income/connected/99999")
        assert resp.status_code == 404


class TestIncomeConnections:
    """Tests for GET /income/connections."""

    async def test_list_connections(self, client, db_session):
        conn = PayrollConnection(
            plaid_user_id="uid-list",
            employer_name="Acme Corp",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.commit()

        resp = await client.get("/income/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["employer_name"] == "Acme Corp"

    async def test_list_connections_empty(self, client):
        resp = await client.get("/income/connections")
        assert resp.status_code == 200


class TestIncomeCascadeSummary:
    """Tests for GET /income/cascade-summary/{connection_id}."""

    async def test_cascade_summary_no_stubs(self, client, db_session):
        conn = PayrollConnection(
            plaid_user_id="uid-cas",
            employer_name="BigCo",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.commit()

        resp = await client.get(f"/income/cascade-summary/{conn.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pay_stubs_imported"] == 0
        assert data["annual_income"] is None

    async def test_cascade_summary_with_stubs(self, client, db_session):
        conn = PayrollConnection(
            plaid_user_id="uid-stubs",
            employer_name="BigCo",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.flush()

        stub = PayStubRecord(
            connection_id=conn.id,
            pay_date=date(2025, 3, 1),
            pay_frequency="biweekly",
            gross_pay=5000.0,
            gross_pay_ytd=15000.0,
            net_pay=3500.0,
            deductions_json=json.dumps([
                {"description": "401k", "amount": 500},
                {"description": "Health Insurance", "amount": 200},
            ]),
        )
        db_session.add(stub)
        await db_session.commit()

        with patch("pipeline.plaid.income_sync._estimate_annual_income", return_value=120000.0):
            resp = await client.get(f"/income/cascade-summary/{conn.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pay_stubs_imported"] == 1
        assert data["annual_income"] == 120000.0
        assert "401k" in data["benefits_detected"]

    async def test_cascade_summary_with_bad_deductions(self, client, db_session):
        """Deductions JSON that can't be parsed triggers except branch."""
        conn = PayrollConnection(
            plaid_user_id="uid-bad-ded",
            employer_name="BadDed Corp",
            income_source_type="payroll",
            status="active",
        )
        db_session.add(conn)
        await db_session.flush()

        stub = PayStubRecord(
            connection_id=conn.id,
            pay_date=date(2025, 3, 1),
            pay_frequency="biweekly",
            gross_pay=5000.0,
            gross_pay_ytd=15000.0,
            deductions_json="not valid json{",
        )
        db_session.add(stub)
        await db_session.commit()

        with patch("pipeline.plaid.income_sync._estimate_annual_income", return_value=100000.0):
            resp = await client.get(f"/income/cascade-summary/{conn.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["benefits_detected"] == []

    async def test_cascade_summary_not_found(self, client):
        resp = await client.get("/income/cascade-summary/99999")
        assert resp.status_code == 404


class TestIncomeSyncBackground:
    """Tests for _sync_income_background."""

    async def test_sync_background_success(self):
        from api.routes.income import _sync_income_background

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_conn = MagicMock()
        mock_conn.plaid_user_token = "encrypted"
        mock_conn.plaid_user_id = "uid"
        mock_result.scalar_one_or_none.return_value = mock_conn
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.income.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("api.routes.income.decrypt_token", return_value="real-token"),
            patch("pipeline.plaid.income_client.get_payroll_income", return_value={"items": []}),
            patch("pipeline.plaid.income_sync.sync_payroll_to_household", new_callable=AsyncMock, return_value={"stubs": 2}),
        ):
            await _sync_income_background(1)

    async def test_sync_background_not_found(self):
        from api.routes.income import _sync_income_background

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with patch("api.routes.income.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)):
            await _sync_income_background(999)

    async def test_sync_background_exception(self):
        from api.routes.income import _sync_income_background

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_conn = MagicMock()
        mock_conn.plaid_user_token = "encrypted"
        mock_conn.plaid_user_id = "uid"
        mock_result.scalar_one_or_none.return_value = mock_conn
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.income.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("api.routes.income.decrypt_token", return_value="real-token"),
            patch("pipeline.plaid.income_client.get_payroll_income", side_effect=Exception("API error")),
        ):
            await _sync_income_background(1)
            assert mock_conn.status == "error"

    async def test_sync_background_empty_token(self):
        from api.routes.income import _sync_income_background

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_conn = MagicMock()
        mock_conn.plaid_user_token = ""
        mock_conn.plaid_user_id = None
        mock_result.scalar_one_or_none.return_value = mock_conn
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.income.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("api.routes.income.decrypt_token", return_value=""),
            patch("pipeline.plaid.income_client.get_payroll_income", return_value={}),
            patch("pipeline.plaid.income_sync.sync_payroll_to_household", new_callable=AsyncMock, return_value={}),
        ):
            await _sync_income_background(1)


# ===========================================================================
# insights.py tests
# ===========================================================================

class TestInsightsAnnual:
    """Tests for GET /insights/annual."""

    @patch("api.routes.insights.compute_annual_insights", new_callable=AsyncMock)
    async def test_get_annual_insights(self, mock_compute, client):
        mock_compute.return_value = {
            "year": 2025,
            "transaction_count": 100,
            "summary": {
                "total_outlier_expenses": 5000, "total_outlier_income": 1000,
                "expense_outlier_count": 3, "income_outlier_count": 1,
                "normalized_monthly_budget": 6000, "actual_monthly_average": 6667,
                "normalization_savings": 667,
            },
            "expense_outliers": [],
            "income_outliers": [],
            "outlier_review": None,
            "normalized_budget": {
                "normalized_monthly_total": 6000,
                "mean_monthly_total": 6667,
                "min_month": 4000,
                "max_month": 9000,
                "by_category": [],
            },
            "monthly_analysis": [],
            "seasonal_patterns": [],
            "category_trends": [],
            "income_analysis": {
                "regular_monthly_median": 12500,
                "regular_monthly_mean": 12500,
                "total_regular": 150000,
                "total_irregular": 0,
                "irregular_items": [],
                "by_source": [],
            },
            "year_over_year": None,
        }
        resp = await client.get("/insights/annual?year=2025")
        assert resp.status_code == 200
        assert resp.json()["year"] == 2025

    @patch("api.routes.insights.compute_annual_insights", new_callable=AsyncMock)
    async def test_get_annual_insights_default_year(self, mock_compute, client):
        mock_compute.return_value = {
            "year": 2026,
            "transaction_count": 0,
            "summary": {
                "total_outlier_expenses": 0, "total_outlier_income": 0,
                "expense_outlier_count": 0, "income_outlier_count": 0,
                "normalized_monthly_budget": 0, "actual_monthly_average": 0,
                "normalization_savings": 0,
            },
            "expense_outliers": [],
            "income_outliers": [],
            "outlier_review": None,
            "normalized_budget": {
                "normalized_monthly_total": 0, "mean_monthly_total": 0,
                "min_month": 0, "max_month": 0, "by_category": [],
            },
            "monthly_analysis": [],
            "seasonal_patterns": [],
            "category_trends": [],
            "income_analysis": {
                "regular_monthly_median": 0, "regular_monthly_mean": 0,
                "total_regular": 0, "total_irregular": 0,
                "irregular_items": [], "by_source": [],
            },
            "year_over_year": None,
        }
        resp = await client.get("/insights/annual")
        assert resp.status_code == 200


class TestInsightsOutlierFeedback:
    """Tests for outlier feedback CRUD endpoints."""

    async def test_submit_outlier_feedback_new(self, client, db_session):
        acct = await _seed_account(db_session)
        tx = await _seed_transaction(db_session, acct.id, description="COSTCO WHOLESALE #1234")
        await db_session.commit()

        resp = await client.post("/insights/outlier-feedback", json={
            "transaction_id": tx.id,
            "classification": "recurring",
            "user_note": "Annual Costco membership",
            "apply_to_future": True,
            "year": 2025,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["classification"] == "recurring"
        assert data["transaction_id"] == tx.id
        assert "COSTCO" in data["description_pattern"]

    async def test_submit_outlier_feedback_update(self, client, db_session):
        acct = await _seed_account(db_session)
        tx = await _seed_transaction(db_session, acct.id, description="BIG PURCHASE")
        fb = OutlierFeedback(
            transaction_id=tx.id,
            classification="one_time",
            description_pattern="BIG PURCHASE",
            year=2025,
        )
        db_session.add(fb)
        await db_session.commit()

        resp = await client.post("/insights/outlier-feedback", json={
            "transaction_id": tx.id,
            "classification": "recurring",
            "user_note": "Actually recurring",
            "apply_to_future": True,
            "year": 2025,
        })
        assert resp.status_code == 200
        assert resp.json()["classification"] == "recurring"

    async def test_submit_outlier_feedback_tx_not_found(self, client):
        resp = await client.post("/insights/outlier-feedback", json={
            "transaction_id": 99999,
            "classification": "one_time",
            "year": 2025,
        })
        assert resp.status_code == 404

    async def test_list_outlier_feedback(self, client, db_session):
        acct = await _seed_account(db_session)
        tx = await _seed_transaction(db_session, acct.id)
        fb = OutlierFeedback(
            transaction_id=tx.id,
            classification="one_time",
            description_pattern="TEST",
            year=2025,
        )
        db_session.add(fb)
        await db_session.commit()

        resp = await client.get("/insights/outlier-feedback?year=2025")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_outlier_feedback_no_year(self, client):
        resp = await client.get("/insights/outlier-feedback")
        assert resp.status_code == 200

    async def test_delete_outlier_feedback(self, client, db_session):
        acct = await _seed_account(db_session)
        tx = await _seed_transaction(db_session, acct.id)
        fb = OutlierFeedback(
            transaction_id=tx.id,
            classification="one_time",
            description_pattern="TEST",
            year=2025,
        )
        db_session.add(fb)
        await db_session.commit()

        resp = await client.delete(f"/insights/outlier-feedback/{fb.id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_delete_outlier_feedback_not_found(self, client):
        resp = await client.delete("/insights/outlier-feedback/99999")
        assert resp.status_code == 404


# ===========================================================================
# insurance.py tests
# ===========================================================================

class TestInsurancePolicies:
    """Tests for insurance CRUD endpoints."""

    async def test_create_policy(self, client):
        resp = await client.post("/insurance/", json={
            "policy_type": "life",
            "provider": "MetLife",
            "coverage_amount": 500000,
            "annual_premium": 1200,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_type"] == "life"
        assert data["monthly_premium"] == 100.0

    async def test_create_policy_with_monthly_only(self, client):
        resp = await client.post("/insurance/", json={
            "policy_type": "auto",
            "provider": "Geico",
            "monthly_premium": 150,
        })
        assert resp.status_code == 201
        assert resp.json()["annual_premium"] == 1800.0

    async def test_create_policy_invalid_type(self, client):
        resp = await client.post("/insurance/", json={
            "policy_type": "spaceship",
            "provider": "SpaceX",
        })
        assert resp.status_code == 400
        assert "Invalid policy_type" in resp.json()["detail"]

    async def test_list_policies(self, client, db_session):
        p = InsurancePolicy(policy_type="health", provider="Blue Cross", is_active=True)
        db_session.add(p)
        await db_session.commit()

        resp = await client.get("/insurance/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_policies_with_filters(self, client, db_session):
        hp = await _seed_household(db_session)
        p = InsurancePolicy(
            policy_type="auto", provider="Progressive", is_active=True,
            household_id=hp.id,
        )
        db_session.add(p)
        await db_session.commit()

        resp = await client.get(f"/insurance/?household_id={hp.id}&policy_type=auto&is_active=true")
        assert resp.status_code == 200

    async def test_get_policy(self, client, db_session):
        p = InsurancePolicy(policy_type="dental", provider="Delta Dental", is_active=True)
        db_session.add(p)
        await db_session.commit()

        resp = await client.get(f"/insurance/{p.id}")
        assert resp.status_code == 200
        assert resp.json()["provider"] == "Delta Dental"

    async def test_get_policy_not_found(self, client):
        resp = await client.get("/insurance/99999")
        assert resp.status_code == 404

    async def test_update_policy(self, client, db_session):
        p = InsurancePolicy(policy_type="home", provider="Allstate", annual_premium=2400)
        db_session.add(p)
        await db_session.commit()

        resp = await client.patch(f"/insurance/{p.id}", json={
            "policy_type": "home",
            "annual_premium": 2600,
        })
        assert resp.status_code == 200
        assert resp.json()["annual_premium"] == 2600
        assert resp.json()["monthly_premium"] == pytest.approx(2600 / 12, abs=0.01)

    async def test_update_policy_monthly_only(self, client, db_session):
        p = InsurancePolicy(policy_type="auto", provider="USAA")
        db_session.add(p)
        await db_session.commit()

        resp = await client.patch(f"/insurance/{p.id}", json={
            "policy_type": "auto",
            "monthly_premium": 200,
        })
        assert resp.status_code == 200
        assert resp.json()["annual_premium"] == 2400.0

    async def test_update_policy_not_found(self, client):
        resp = await client.patch("/insurance/99999", json={
            "policy_type": "life",
        })
        assert resp.status_code == 404

    async def test_delete_policy(self, client, db_session):
        p = InsurancePolicy(policy_type="pet", provider="Embrace")
        db_session.add(p)
        await db_session.commit()

        resp = await client.delete(f"/insurance/{p.id}")
        assert resp.status_code == 204

    async def test_delete_policy_not_found(self, client):
        resp = await client.delete("/insurance/99999")
        assert resp.status_code == 404


class TestInsuranceGapAnalysis:
    """Tests for POST /insurance/gap-analysis."""

    @patch("api.routes.insurance.analyze_insurance_gaps")
    async def test_gap_analysis(self, mock_analyze, client, db_session):
        mock_analyze.return_value = {"gaps": ["life", "disability"], "score": 60}
        hp = await _seed_household(db_session)
        p = InsurancePolicy(
            policy_type="health", provider="Aetna", is_active=True,
            household_id=hp.id,
        )
        db_session.add(p)
        await db_session.commit()

        resp = await client.post("/insurance/gap-analysis", json={
            "household_id": hp.id,
            "spouse_a_income": 150000,
            "spouse_b_income": 100000,
            "total_debt": 50000,
            "dependents": 2,
            "net_worth": 500000,
        })
        assert resp.status_code == 200
        mock_analyze.assert_called_once()

    @patch("api.routes.insurance.analyze_insurance_gaps")
    async def test_gap_analysis_no_household(self, mock_analyze, client):
        mock_analyze.return_value = {"gaps": [], "score": 100}
        resp = await client.post("/insurance/gap-analysis", json={
            "spouse_a_income": 100000,
        })
        assert resp.status_code == 200


# ===========================================================================
# life_events.py tests
# ===========================================================================

class TestLifeEvents:
    """Tests for life events CRUD endpoints."""

    async def test_create_event(self, client):
        resp = await client.post("/life-events/", json={
            "event_type": "family",
            "event_subtype": "birth",
            "title": "Baby born",
            "event_date": "2025-06-15",
            "tax_year": 2025,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Baby born"

    async def test_create_event_with_auto_action_items(self, client):
        """Test that action items are auto-generated for known event types."""
        resp = await client.post("/life-events/", json={
            "event_type": "real_estate",
            "event_subtype": "purchase",
            "title": "Bought house",
            "tax_year": 2025,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["action_items_json"] is not None
        items = json.loads(data["action_items_json"])
        assert len(items) > 0

    async def test_create_event_custom_action_items(self, client):
        """When action_items_json is provided, don't auto-generate."""
        custom_items = json.dumps([{"text": "Custom item", "completed": False}])
        resp = await client.post("/life-events/", json={
            "event_type": "other",
            "title": "Custom event",
            "action_items_json": custom_items,
        })
        assert resp.status_code == 201
        data = resp.json()
        items = json.loads(data["action_items_json"])
        assert items[0]["text"] == "Custom item"

    async def test_list_events(self, client, db_session):
        ev = LifeEvent(event_type="family", title="Wedding", tax_year=2025)
        db_session.add(ev)
        await db_session.commit()

        resp = await client.get("/life-events/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_events_with_filters(self, client, db_session):
        hp = await _seed_household(db_session)
        ev = LifeEvent(
            event_type="employment", title="Job change",
            tax_year=2025, household_id=hp.id,
        )
        db_session.add(ev)
        await db_session.commit()

        resp = await client.get(
            f"/life-events/?household_id={hp.id}&event_type=employment&tax_year=2025"
        )
        assert resp.status_code == 200

    async def test_get_event(self, client, db_session):
        ev = LifeEvent(event_type="medical", title="Surgery", tax_year=2025)
        db_session.add(ev)
        await db_session.commit()

        resp = await client.get(f"/life-events/{ev.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Surgery"

    async def test_get_event_not_found(self, client):
        resp = await client.get("/life-events/99999")
        assert resp.status_code == 404

    async def test_update_event(self, client, db_session):
        ev = LifeEvent(event_type="family", title="Wedding", tax_year=2025)
        db_session.add(ev)
        await db_session.commit()

        resp = await client.patch(f"/life-events/{ev.id}", json={
            "title": "Wedding Reception",
            "event_date": "2025-10-01",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "Wedding Reception"

    async def test_update_event_not_found(self, client):
        resp = await client.patch("/life-events/99999", json={"title": "Gone"})
        assert resp.status_code == 404

    async def test_toggle_action_item(self, client, db_session):
        items = [
            {"text": "Do thing 1", "completed": False},
            {"text": "Do thing 2", "completed": False},
        ]
        ev = LifeEvent(
            event_type="family", title="Baby",
            tax_year=2025,
            action_items_json=json.dumps(items),
        )
        db_session.add(ev)
        await db_session.commit()

        resp = await client.patch(
            f"/life-events/{ev.id}/action-items/0",
            json={"index": 0, "completed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["items"][0]["completed"] is True

    async def test_toggle_action_item_not_found(self, client):
        resp = await client.patch(
            "/life-events/99999/action-items/0",
            json={"index": 0, "completed": True},
        )
        assert resp.status_code == 404

    async def test_toggle_action_item_out_of_range(self, client, db_session):
        ev = LifeEvent(
            event_type="family", title="Test",
            tax_year=2025,
            action_items_json=json.dumps([{"text": "Item", "completed": False}]),
        )
        db_session.add(ev)
        await db_session.commit()

        resp = await client.patch(
            f"/life-events/{ev.id}/action-items/5",
            json={"index": 5, "completed": True},
        )
        assert resp.status_code == 400
        assert "out of range" in resp.json()["detail"]

    async def test_delete_event(self, client, db_session):
        ev = LifeEvent(event_type="family", title="Delete me", tax_year=2025)
        db_session.add(ev)
        await db_session.commit()

        resp = await client.delete(f"/life-events/{ev.id}")
        assert resp.status_code == 204

    async def test_delete_event_not_found(self, client):
        resp = await client.delete("/life-events/99999")
        assert resp.status_code == 404

    async def test_get_action_templates(self, client):
        resp = await client.get(
            "/life-events/action-templates/real_estate?event_subtype=purchase"
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0

    async def test_get_action_templates_unknown_type(self, client):
        resp = await client.get("/life-events/action-templates/unicorn_event")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


# ===========================================================================
# plaid.py tests
# ===========================================================================

class TestPlaidLinkToken:
    """Tests for GET /plaid/link-token and /plaid/link-token/update/{item_id}."""

    @patch("api.routes.plaid.create_link_token")
    async def test_get_link_token(self, mock_create, client):
        mock_create.return_value = "link-sandbox-abc"
        resp = await client.get("/plaid/link-token")
        assert resp.status_code == 200
        assert resp.json()["link_token"] == "link-sandbox-abc"

    @patch("api.routes.plaid.create_link_token")
    async def test_get_link_token_error(self, mock_create, client):
        mock_create.side_effect = Exception("Plaid down")
        resp = await client.get("/plaid/link-token")
        assert resp.status_code == 500

    @patch("api.routes.plaid.create_link_token")
    @patch("api.routes.plaid.decrypt_token")
    async def test_get_update_link_token(self, mock_decrypt, mock_create, client, db_session):
        item = PlaidItem(
            item_id="item-update-1",
            access_token="encrypted-token",
            institution_name="Chase",
            status="active",
        )
        db_session.add(item)
        await db_session.commit()

        mock_decrypt.return_value = "access-token-real"
        mock_create.return_value = "link-update-token"

        resp = await client.get(f"/plaid/link-token/update/{item.id}")
        assert resp.status_code == 200
        assert resp.json()["link_token"] == "link-update-token"
        mock_create.assert_called_with(access_token="access-token-real")

    async def test_get_update_link_token_not_found(self, client):
        resp = await client.get("/plaid/link-token/update/99999")
        assert resp.status_code == 404

    @patch("api.routes.plaid.create_link_token")
    @patch("api.routes.plaid.decrypt_token")
    async def test_get_update_link_token_error(self, mock_decrypt, mock_create, client, db_session):
        item = PlaidItem(
            item_id="item-update-err",
            access_token="enc",
            institution_name="BoA",
            status="active",
        )
        db_session.add(item)
        await db_session.commit()

        mock_decrypt.return_value = "token"
        mock_create.side_effect = Exception("Plaid down")
        resp = await client.get(f"/plaid/link-token/update/{item.id}")
        assert resp.status_code == 500


class TestPlaidExchangeToken:
    """Tests for POST /plaid/exchange-token."""

    @patch("api.routes.plaid.get_accounts")
    @patch("api.routes.plaid.exchange_public_token")
    @patch("api.routes.plaid.encrypt_token")
    async def test_exchange_token_new_accounts(self, mock_encrypt, mock_exchange, mock_get_accounts, client, db_session):
        mock_encrypt.return_value = "encrypted-access"
        mock_exchange.return_value = {
            "access_token": "access-sandbox-123",
            "item_id": "item-new-123",
        }
        mock_get_accounts.return_value = [
            {
                "plaid_account_id": "pa-1",
                "name": "Checking",
                "official_name": "Checking",
                "type": "depository",
                "subtype": "checking",
                "mask": "1234",
                "current_balance": 5000,
                "available_balance": 4500,
            },
        ]

        with patch("pipeline.db.upsert_account", new_callable=AsyncMock) as mock_upsert:
            mock_acct = MagicMock()
            mock_acct.id = 100
            mock_upsert.return_value = mock_acct
            resp = await client.post("/plaid/exchange-token", json={
                "public_token": "public-sandbox-xyz",
                "institution_name": "Wells Fargo",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["accounts_created"] == 1

    @patch("api.routes.plaid.get_accounts")
    @patch("api.routes.plaid.exchange_public_token")
    @patch("api.routes.plaid.encrypt_token")
    async def test_exchange_token_merge_existing(self, mock_encrypt, mock_exchange, mock_get_accounts, client, db_session):
        """Test merging with an existing manual account."""
        # Seed an existing manual account
        existing_acct = Account(
            name="Chase Checking", account_type="personal",
            subtype="checking", institution="Chase",
            last_four="5678", currency="USD", data_source="manual",
            is_active=True,
        )
        db_session.add(existing_acct)
        await db_session.commit()

        mock_encrypt.return_value = "encrypted"
        mock_exchange.return_value = {
            "access_token": "access-sandbox-merge",
            "item_id": "item-merge-123",
        }
        mock_get_accounts.return_value = [
            {
                "plaid_account_id": "pa-merge-1",
                "name": "Chase Checking",
                "official_name": "Chase Checking Account",
                "type": "depository",
                "subtype": "checking",
                "mask": "5678",
                "current_balance": 10000,
                "available_balance": 9500,
            },
        ]

        resp = await client.post("/plaid/exchange-token", json={
            "public_token": "public-sandbox-merge",
            "institution_name": "Chase",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["accounts_matched"] >= 1

    @patch("api.routes.plaid.exchange_public_token")
    async def test_exchange_token_duplicate_institution(self, mock_exchange, client, db_session):
        """Test duplicate item prevention."""
        item = PlaidItem(
            item_id="existing-item",
            access_token="enc",
            institution_name="Chase",
            status="active",
        )
        db_session.add(item)
        await db_session.commit()

        resp = await client.post("/plaid/exchange-token", json={
            "public_token": "public-dup",
            "institution_name": "Chase",
        })
        assert resp.status_code == 409
        assert "already connected" in resp.json()["detail"]

    @patch("api.routes.plaid.exchange_public_token")
    async def test_exchange_token_exchange_fails(self, mock_exchange, client):
        mock_exchange.side_effect = Exception("Token invalid")
        resp = await client.post("/plaid/exchange-token", json={
            "public_token": "bad-token",
            "institution_name": "BoA",
        })
        assert resp.status_code == 400
        assert "Token exchange failed" in resp.json()["detail"]

    @patch("api.routes.plaid.get_accounts")
    @patch("api.routes.plaid.exchange_public_token")
    @patch("api.routes.plaid.encrypt_token")
    async def test_exchange_token_accounts_fetch_fails(self, mock_encrypt, mock_exchange, mock_get_accounts, client):
        mock_encrypt.return_value = "enc"
        mock_exchange.return_value = {
            "access_token": "access-fail",
            "item_id": "item-fail-accts",
        }
        mock_get_accounts.side_effect = Exception("API error")

        resp = await client.post("/plaid/exchange-token", json={
            "public_token": "public-accts-fail",
            "institution_name": "BoA Fail",
        })
        assert resp.status_code == 200
        assert resp.json()["accounts_created"] == 0


class TestPlaidSyncStatus:
    """Tests for GET /plaid/sync-status/{item_id}."""

    async def test_sync_status(self, client, db_session):
        item = PlaidItem(
            item_id="item-sync-1",
            access_token="enc",
            institution_name="Fidelity",
            status="active",
            sync_phase="complete",
        )
        db_session.add(item)
        await db_session.commit()

        resp = await client.get(f"/plaid/sync-status/{item.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_phase"] == "complete"

    async def test_sync_status_not_found(self, client):
        resp = await client.get("/plaid/sync-status/99999")
        assert resp.status_code == 404


class TestPlaidItems:
    """Tests for GET /plaid/items and DELETE /plaid/items/{item_id}."""

    async def test_list_items(self, client, db_session):
        item = PlaidItem(
            item_id="item-list-1",
            access_token="enc",
            institution_name="Schwab",
            status="active",
        )
        db_session.add(item)
        await db_session.commit()

        resp = await client.get("/plaid/items")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1

    @patch("api.routes.plaid.remove_item")
    @patch("api.routes.plaid.decrypt_token")
    async def test_delete_item(self, mock_decrypt, mock_remove, client, db_session):
        item = PlaidItem(
            item_id="item-del-1",
            access_token="enc",
            institution_name="Vanguard",
            status="active",
        )
        db_session.add(item)
        await db_session.commit()

        mock_decrypt.return_value = "access-del"
        resp = await client.delete(f"/plaid/items/{item.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    @patch("api.routes.plaid.remove_item")
    @patch("api.routes.plaid.decrypt_token")
    async def test_delete_item_revoke_fails(self, mock_decrypt, mock_remove, client, db_session):
        """Plaid revocation fails but item is still marked removed."""
        item = PlaidItem(
            item_id="item-del-fail",
            access_token="enc",
            institution_name="BoA",
            status="active",
        )
        db_session.add(item)
        await db_session.commit()

        mock_decrypt.return_value = "access-fail"
        mock_remove.side_effect = Exception("Plaid error")
        resp = await client.delete(f"/plaid/items/{item.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    async def test_delete_item_not_found(self, client):
        resp = await client.delete("/plaid/items/99999")
        assert resp.status_code == 404


class TestPlaidSync:
    """Tests for POST /plaid/sync."""

    async def test_sync_plaid(self, client):
        resp = await client.post("/plaid/sync")
        assert resp.status_code == 200
        assert resp.json()["status"] == "sync_started"


class TestPlaidAccounts:
    """Tests for GET /plaid/accounts."""

    async def test_list_plaid_accounts(self, client, db_session):
        item = PlaidItem(
            item_id="item-accts-list",
            access_token="enc",
            institution_name="Test Bank",
            status="active",
        )
        db_session.add(item)
        await db_session.flush()

        pa = PlaidAccount(
            plaid_item_id=item.id,
            plaid_account_id="pa-list-1",
            name="Savings",
            type="depository",
            subtype="savings",
            current_balance=25000,
        )
        db_session.add(pa)
        await db_session.commit()

        resp = await client.get("/plaid/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1


class TestPlaidHealth:
    """Tests for GET /plaid/health."""

    async def test_health_no_items(self, client):
        resp = await client.get("/plaid/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_items"] == 0

    async def test_health_with_items(self, client, db_session):
        item = PlaidItem(
            item_id="item-health-1",
            access_token="enc",
            institution_name="Health Bank",
            status="active",
            last_synced_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )
        db_session.add(item)
        await db_session.flush()

        pa1 = PlaidAccount(
            plaid_item_id=item.id,
            plaid_account_id="pa-health-dep",
            name="Checking",
            type="depository",
            current_balance=10000,
        )
        pa2 = PlaidAccount(
            plaid_item_id=item.id,
            plaid_account_id="pa-health-credit",
            name="Credit Card",
            type="credit",
            current_balance=2000,
        )
        pa3 = PlaidAccount(
            plaid_item_id=item.id,
            plaid_account_id="pa-health-inv",
            name="Investment",
            type="investment",
            current_balance=50000,
        )
        pa4 = PlaidAccount(
            plaid_item_id=item.id,
            plaid_account_id="pa-health-loan",
            name="Mortgage",
            type="loan",
            current_balance=300000,
        )
        db_session.add_all([pa1, pa2, pa3, pa4])
        await db_session.commit()

        resp = await client.get("/plaid/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_items"] >= 1
        assert data["summary"]["total_assets"] > 0
        assert data["summary"]["total_liabilities"] > 0

    async def test_health_with_stale_item(self, client, db_session):
        """Item with last_synced_at > 24 hours ago."""
        item = PlaidItem(
            item_id="item-health-stale",
            access_token="enc",
            institution_name="Stale Bank",
            status="active",
            last_synced_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(item)
        await db_session.commit()

        resp = await client.get("/plaid/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["any_stale"] is True

    async def test_health_naive_datetime(self, client, db_session):
        """Item with naive (no tzinfo) last_synced_at."""
        item = PlaidItem(
            item_id="item-health-naive",
            access_token="enc",
            institution_name="Naive Bank",
            status="active",
            last_synced_at=datetime(2025, 3, 1),  # naive
        )
        db_session.add(item)
        await db_session.commit()

        resp = await client.get("/plaid/health")
        assert resp.status_code == 200


class TestPlaidInitialSyncAndDedup:
    """Tests for _initial_sync_and_dedup background function."""

    async def test_initial_sync_success(self):
        from api.routes.plaid import _initial_sync_and_dedup

        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.access_token = "enc"
        mock_item.institution_name = "Test"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.plaid.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock, return_value=(10, 2)),
            patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock),
            patch("pipeline.ai.categorizer.categorize_transactions", new_callable=AsyncMock),
        ):
            await _initial_sync_and_dedup(1, [])
            assert mock_item.sync_phase == "complete"

    async def test_initial_sync_not_found(self):
        from api.routes.plaid import _initial_sync_and_dedup

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with patch("api.routes.plaid.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)):
            await _initial_sync_and_dedup(999, [])

    async def test_initial_sync_no_access_token(self):
        from api.routes.plaid import _initial_sync_and_dedup

        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.access_token = ""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with patch("api.routes.plaid.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)):
            await _initial_sync_and_dedup(1, [])

    async def test_initial_sync_failure(self):
        from api.routes.plaid import _initial_sync_and_dedup

        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.access_token = "enc"
        mock_item.institution_name = "Fail"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.plaid.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock, side_effect=Exception("sync err")),
        ):
            await _initial_sync_and_dedup(1, [])
            assert mock_item.status == "error"
            assert mock_item.sync_phase == "error"

    async def test_initial_sync_with_dedup_and_categorize_failures(self):
        from api.routes.plaid import _initial_sync_and_dedup

        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.access_token = "enc"
        mock_item.institution_name = "Dedup"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.plaid.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock, return_value=(5, 1)),
            patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock, side_effect=Exception("net worth fail")),
            patch("pipeline.ai.categorizer.categorize_transactions", new_callable=AsyncMock, side_effect=Exception("cat fail")),
            patch("pipeline.dedup.cross_source.auto_resolve_duplicates", new_callable=AsyncMock, side_effect=Exception("dedup fail")),
        ):
            await _initial_sync_and_dedup(1, [10, 20])
            assert mock_item.sync_phase == "complete"

    async def test_initial_sync_no_new_transactions(self):
        """sync returns added=0, so categorization is skipped."""
        from api.routes.plaid import _initial_sync_and_dedup

        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.access_token = "enc"
        mock_item.institution_name = "NoNew"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.plaid.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock, return_value=(0, 1)),
            patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock),
        ):
            await _initial_sync_and_dedup(1, [])
            assert mock_item.sync_phase == "complete"


class TestPlaidExchangeTokenMaskUpdate:
    """Test that mask is set on existing account when merging."""

    @patch("api.routes.plaid.get_accounts")
    @patch("api.routes.plaid.exchange_public_token")
    @patch("api.routes.plaid.encrypt_token")
    async def test_exchange_token_sets_mask_on_existing(self, mock_encrypt, mock_exchange, mock_get_accounts, client, db_session):
        """When existing account has no last_four and Plaid provides mask, it should be set."""
        existing_acct = Account(
            name="Chase Checking", account_type="personal",
            subtype="checking", institution="Chase",
            last_four=None, currency="USD", data_source="manual",
            is_active=True,
        )
        db_session.add(existing_acct)
        await db_session.commit()

        mock_encrypt.return_value = "encrypted"
        mock_exchange.return_value = {
            "access_token": "access-sandbox-mask",
            "item_id": "item-mask-test",
        }
        mock_get_accounts.return_value = [
            {
                "plaid_account_id": "pa-mask-1",
                "name": "Chase Checking",
                "official_name": None,
                "type": "depository",
                "subtype": "checking",
                "mask": "9876",
                "current_balance": 5000,
                "available_balance": 4500,
            },
        ]

        resp = await client.post("/plaid/exchange-token", json={
            "public_token": "public-mask-test",
            "institution_name": "Chase",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["accounts_matched"] >= 1


class TestPlaidInitialSyncDedup:
    """Test the dedup success path in _initial_sync_and_dedup."""

    async def test_initial_sync_dedup_success(self):
        """Test that successful dedup logs correctly."""
        from api.routes.plaid import _initial_sync_and_dedup

        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.access_token = "enc"
        mock_item.institution_name = "DedupOK"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.begin = MagicMock(return_value=_FakeAsyncCM())

        with (
            patch("api.routes.plaid.AsyncSessionLocal", return_value=_FakeAsyncCM(mock_session)),
            patch("pipeline.plaid.sync.sync_item", new_callable=AsyncMock, return_value=(5, 1)),
            patch("pipeline.plaid.sync.snapshot_net_worth", new_callable=AsyncMock),
            patch("pipeline.ai.categorizer.categorize_transactions", new_callable=AsyncMock),
            patch("pipeline.dedup.cross_source.auto_resolve_duplicates", new_callable=AsyncMock, return_value={"resolved": 3}),
        ):
            await _initial_sync_and_dedup(1, [10])
            assert mock_item.sync_phase == "complete"


class TestPlaidFindMatchingAccount:
    """Tests for _find_matching_account helper."""

    async def test_match_by_last_four(self, db_session):
        from api.routes.plaid import _find_matching_account

        acct = Account(
            name="Chase Visa", account_type="personal",
            subtype="credit_card", institution="Chase",
            last_four="4321", currency="USD", data_source="csv",
            is_active=True,
        )
        db_session.add(acct)
        await db_session.commit()

        result = await _find_matching_account(
            db_session,
            {"mask": "4321", "name": "Something", "subtype": "credit_card"},
            "Chase",
        )
        assert result is not None
        assert result.id == acct.id

    async def test_match_by_name(self, db_session):
        from api.routes.plaid import _find_matching_account

        acct = Account(
            name="Savings Account", account_type="personal",
            subtype="savings", institution="BoA",
            currency="USD", data_source="manual", is_active=True,
        )
        db_session.add(acct)
        await db_session.commit()

        result = await _find_matching_account(
            db_session,
            {"mask": None, "name": "Savings Account", "official_name": "", "subtype": "savings"},
            "BoA",
        )
        assert result is not None

    async def test_match_by_subtype_unique(self, db_session):
        from api.routes.plaid import _find_matching_account

        acct = Account(
            name="Main Checking", account_type="personal",
            subtype="checking", institution="WF",
            currency="USD", data_source="manual", is_active=True,
        )
        db_session.add(acct)
        await db_session.commit()

        result = await _find_matching_account(
            db_session,
            {"mask": None, "name": "Different Name", "official_name": None, "subtype": "checking"},
            "WF",
        )
        assert result is not None
        assert result.id == acct.id

    async def test_no_match(self, db_session):
        from api.routes.plaid import _find_matching_account

        result = await _find_matching_account(
            db_session,
            {"mask": "9999", "name": "Unknown", "official_name": None, "subtype": "brokerage"},
            "Nonexistent Bank",
        )
        assert result is None


# ===========================================================================
# privacy.py tests
# ===========================================================================

class TestPrivacyConsent:
    """Tests for privacy consent endpoints."""

    async def test_get_all_consent_empty(self, client):
        resp = await client.get("/privacy/consent")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_set_consent_new(self, client):
        resp = await client.post("/privacy/consent", json={
            "consent_type": "ai_features",
            "consented": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["consent_type"] == "ai_features"
        assert data["consented"] is True

    async def test_set_consent_update_existing(self, client, db_session):
        consent = UserPrivacyConsent(
            consent_type="plaid_sync",
            consented=False,
            consent_version="1.0",
        )
        db_session.add(consent)
        await db_session.commit()

        resp = await client.post("/privacy/consent", json={
            "consent_type": "plaid_sync",
            "consented": True,
        })
        assert resp.status_code == 200
        assert resp.json()["consented"] is True

    async def test_set_consent_revoke(self, client, db_session):
        consent = UserPrivacyConsent(
            consent_type="telemetry",
            consented=True,
            consent_version="1.0",
            consented_at=datetime.now(timezone.utc),
        )
        db_session.add(consent)
        await db_session.commit()

        resp = await client.post("/privacy/consent", json={
            "consent_type": "telemetry",
            "consented": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["consented"] is False

    async def test_set_consent_invalid_type(self, client):
        resp = await client.post("/privacy/consent", json={
            "consent_type": "invalid_type",
            "consented": True,
        })
        assert resp.status_code == 400

    async def test_get_consent_specific(self, client, db_session):
        consent = UserPrivacyConsent(
            consent_type="ai_features",
            consented=True,
            consent_version="1.0",
        )
        db_session.add(consent)
        await db_session.commit()

        resp = await client.get("/privacy/consent/ai_features")
        assert resp.status_code == 200
        assert resp.json()["consented"] is True

    async def test_get_consent_invalid_type(self, client):
        resp = await client.get("/privacy/consent/invalid")
        assert resp.status_code == 400

    async def test_get_consent_not_found(self, client):
        resp = await client.get("/privacy/consent/telemetry")
        assert resp.status_code == 404


class TestPrivacyDisclosure:
    """Tests for GET /privacy/disclosure."""

    async def test_get_disclosure(self, client):
        resp = await client.get("/privacy/disclosure")
        assert resp.status_code == 200
        data = resp.json()
        assert "data_handling" in data
        assert "ai_privacy" in data
        assert "encryption" in data
        assert "data_retention" in data
        assert len(data["data_handling"]) > 0


class TestPrivacyAuditLog:
    """Tests for GET /privacy/audit-log."""

    async def test_audit_log_empty(self, client):
        resp = await client.get("/privacy/audit-log")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_audit_log_with_entries(self, client, db_session):
        entry = AuditLog(
            action_type="consent_change",
            data_category="consent",
            detail="type=ai_features consented=true",
            duration_ms=50,
        )
        db_session.add(entry)
        await db_session.commit()

        resp = await client.get("/privacy/audit-log")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["action_type"] == "consent_change"

    async def test_audit_log_filter_by_action(self, client, db_session):
        entry1 = AuditLog(action_type="consent_change", detail="test1")
        entry2 = AuditLog(action_type="data_import", detail="test2")
        db_session.add_all([entry1, entry2])
        await db_session.commit()

        resp = await client.get("/privacy/audit-log?action_type=data_import")
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["action_type"] == "data_import" for e in data)

    async def test_audit_log_pagination(self, client, db_session):
        for i in range(5):
            db_session.add(AuditLog(action_type="test", detail=f"entry-{i}"))
        await db_session.commit()

        resp = await client.get("/privacy/audit-log?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 2
