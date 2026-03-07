"""Tests for pipeline/tax/checklist.py and pipeline/tax/quarterly.py."""
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from pipeline.db.schema import (
    Account,
    Document,
    HouseholdProfile,
    TaxItem,
    TaxStrategy,
    Transaction,
)
from pipeline.tax.checklist import compute_tax_checklist
from pipeline.tax.quarterly import compute_quarterly_estimate


# ---------------------------------------------------------------------------
# compute_tax_checklist
# ---------------------------------------------------------------------------

class TestChecklistEmpty:
    """Checklist on an empty database."""

    async def test_empty_db_returns_items(self, session):
        result = await compute_tax_checklist(session, 2024)
        assert result["tax_year"] == 2024
        assert isinstance(result["items"], list)
        assert len(result["items"]) > 0

    async def test_empty_db_all_incomplete_or_na(self, session):
        result = await compute_tax_checklist(session, 2024)
        for item in result["items"]:
            assert item["status"] in ("incomplete", "not_applicable")

    async def test_empty_db_completed_zero(self, session):
        result = await compute_tax_checklist(session, 2024)
        assert result["completed"] == 0
        assert result["progress_pct"] == 0

    async def test_item_shape(self, session):
        result = await compute_tax_checklist(session, 2024)
        for item in result["items"]:
            assert "id" in item
            assert "label" in item
            assert "description" in item
            assert "status" in item
            assert "detail" in item
            assert "category" in item

    async def test_categories_present(self, session):
        result = await compute_tax_checklist(session, 2024)
        categories = {item["category"] for item in result["items"]}
        assert "documents" in categories
        assert "preparation" in categories
        assert "payments" in categories
        assert "filing" in categories


class TestChecklistDocuments:
    """Document import checklist items."""

    @pytest_asyncio.fixture(autouse=True)
    async def _seed_w2(self, session):
        doc = Document(
            filename="w2_2024.pdf",
            original_path="/tmp/w2.pdf",
            file_type="pdf",
            document_type="w2",
            status="completed",
            file_hash="fakehash_w2_2024",
        )
        session.add(doc)
        await session.flush()
        self.doc_id = doc.id

        session.add(TaxItem(
            source_document_id=doc.id,
            tax_year=2024,
            form_type="w2",
            payer_name="Acme Corp",
            w2_wages=150000.0,
            w2_federal_tax_withheld=30000.0,
        ))
        await session.flush()

    async def test_w2_complete(self, session):
        result = await compute_tax_checklist(session, 2024)
        w2_item = next(i for i in result["items"] if i["id"] == "import_w2")
        assert w2_item["status"] == "complete"
        assert "1 document(s) imported" in w2_item["detail"]

    async def test_other_docs_still_incomplete(self, session):
        result = await compute_tax_checklist(session, 2024)
        nec_item = next(i for i in result["items"] if i["id"] == "import_1099_nec")
        assert nec_item["status"] == "incomplete"

    async def test_completed_count_reflects_docs(self, session):
        result = await compute_tax_checklist(session, 2024)
        assert result["completed"] >= 1

    async def test_wrong_year_no_match(self, session):
        result = await compute_tax_checklist(session, 2023)
        w2_item = next(i for i in result["items"] if i["id"] == "import_w2")
        assert w2_item["status"] == "incomplete"


class TestChecklistTransactions:
    """Transaction import and categorization checklist items."""

    @pytest_asyncio.fixture(autouse=True)
    async def _seed_transactions(self, session):
        acct = Account(name="Test Checking", institution="Test Bank", account_type="depository")
        session.add(acct)
        await session.flush()
        self.account_id = acct.id

        # 10 categorized transactions
        for i in range(10):
            session.add(Transaction(
                account_id=acct.id,
                date=datetime(2024, 6, 1 + i, tzinfo=timezone.utc),
                description=f"Purchase {i}",
                amount=-50.0,
                effective_category="Shopping",
                period_year=2024,
                period_month=6,
                is_excluded=False,
            ))
        await session.flush()

    async def test_transactions_imported(self, session):
        result = await compute_tax_checklist(session, 2024)
        txn_item = next(i for i in result["items"] if i["id"] == "import_transactions")
        assert txn_item["status"] == "complete"
        assert "10 transactions imported" in txn_item["detail"]

    async def test_all_categorized(self, session):
        result = await compute_tax_checklist(session, 2024)
        cat_item = next(i for i in result["items"] if i["id"] == "categorize_transactions")
        assert cat_item["status"] == "complete"
        assert "100.0%" in cat_item["detail"]

    async def test_partial_categorization(self, session):
        # Add 2 uncategorized out of 12 total → ~83% categorized
        for i in range(2):
            session.add(Transaction(
                account_id=self.account_id,
                date=datetime(2024, 7, 1 + i, tzinfo=timezone.utc),
                description=f"Unknown {i}",
                amount=-30.0,
                effective_category=None,
                period_year=2024,
                period_month=7,
                is_excluded=False,
            ))
        await session.flush()

        result = await compute_tax_checklist(session, 2024)
        cat_item = next(i for i in result["items"] if i["id"] == "categorize_transactions")
        assert cat_item["status"] == "partial"

    async def test_mostly_uncategorized(self, session):
        # Add 40 uncategorized → only 10/50 = 20% categorized
        for i in range(40):
            session.add(Transaction(
                account_id=self.account_id,
                date=datetime(2024, 8, 1, tzinfo=timezone.utc),
                description=f"Unknown {i}",
                amount=-10.0,
                effective_category=None,
                period_year=2024,
                period_month=8,
                is_excluded=False,
            ))
        await session.flush()

        result = await compute_tax_checklist(session, 2024)
        cat_item = next(i for i in result["items"] if i["id"] == "categorize_transactions")
        assert cat_item["status"] == "incomplete"


class TestChecklistBusiness:
    """Business expense review item."""

    async def test_no_business_txns_is_not_applicable(self, session):
        result = await compute_tax_checklist(session, 2024)
        biz_item = next(i for i in result["items"] if i["id"] == "review_business_expenses")
        assert biz_item["status"] == "not_applicable"

    async def test_not_applicable_excluded_from_total(self, session):
        result = await compute_tax_checklist(session, 2024)
        na_count = sum(1 for i in result["items"] if i["status"] == "not_applicable")
        total_items = len(result["items"])
        assert result["total"] == total_items - na_count


class TestChecklistPaymentsAndFiling:
    """Quarterly payment and filing deadline items."""

    async def test_four_quarterly_payments(self, session):
        result = await compute_tax_checklist(session, 2024)
        q_items = [i for i in result["items"] if i["category"] == "payments"]
        assert len(q_items) == 4

    async def test_quarterly_deadlines_correct(self, session):
        result = await compute_tax_checklist(session, 2024)
        q1 = next(i for i in result["items"] if i["id"] == "q1_estimated")
        assert "Apr 15, 2025" in q1["description"]
        q4 = next(i for i in result["items"] if i["id"] == "q4_estimated")
        assert "Jan 15, 2026" in q4["description"]

    async def test_filing_items_present(self, session):
        result = await compute_tax_checklist(session, 2024)
        filing_items = [i for i in result["items"] if i["category"] == "filing"]
        assert len(filing_items) == 2
        ids = {i["id"] for i in filing_items}
        assert "file_federal" in ids
        assert "file_state" in ids

    async def test_federal_filing_deadline(self, session):
        result = await compute_tax_checklist(session, 2024)
        federal = next(i for i in result["items"] if i["id"] == "file_federal")
        assert "Apr 15, 2025" in federal["description"]
        assert "Oct 15, 2025" in federal["description"]


class TestChecklistAIAnalysis:
    """AI tax strategy analysis item."""

    async def test_no_strategies_incomplete(self, session):
        result = await compute_tax_checklist(session, 2024)
        ai_item = next(i for i in result["items"] if i["id"] == "run_ai_analysis")
        assert ai_item["status"] == "incomplete"

    async def test_with_strategies_complete(self, session):
        session.add(TaxStrategy(
            tax_year=2024,
            priority=1,
            title="Max 401k",
            description="Maximize 401k contributions",
            strategy_type="retirement",
            estimated_savings_low=5000,
            estimated_savings_high=8000,
        ))
        await session.flush()

        result = await compute_tax_checklist(session, 2024)
        ai_item = next(i for i in result["items"] if i["id"] == "run_ai_analysis")
        assert ai_item["status"] == "complete"
        assert "1 strategies generated" in ai_item["detail"]


class TestChecklistProgressPct:
    """Progress percentage calculation."""

    async def test_progress_zero_when_empty(self, session):
        result = await compute_tax_checklist(session, 2024)
        assert result["progress_pct"] == 0

    async def test_progress_increases_with_docs(self, session):
        doc = Document(
            filename="w2.pdf", original_path="/tmp/w2.pdf",
            file_type="pdf", document_type="w2", status="completed",
            file_hash="fakehash_w2_progress",
        )
        session.add(doc)
        await session.flush()
        session.add(TaxItem(
            source_document_id=doc.id, tax_year=2024,
            form_type="w2", w2_wages=100000,
        ))
        await session.flush()

        result = await compute_tax_checklist(session, 2024)
        assert result["progress_pct"] > 0
        assert result["completed"] >= 1


# ---------------------------------------------------------------------------
# compute_quarterly_estimate
# ---------------------------------------------------------------------------

class TestQuarterlyEstimateEmpty:
    """Quarterly estimate on empty database."""

    async def test_empty_db_zero_income(self, session):
        result = await compute_quarterly_estimate(session, 2024)
        assert result["total_se_income"] == 0
        assert result["quarterly_amount"] == 0

    async def test_empty_db_response_shape(self, session):
        result = await compute_quarterly_estimate(session, 2024)
        assert result["tax_year"] == 2024
        assert "marginal_rate" in result
        assert "annual_estimated_tax" in result
        assert "due_dates" in result
        assert len(result["due_dates"]) == 4

    async def test_due_dates_correct(self, session):
        result = await compute_quarterly_estimate(session, 2024)
        dates = result["due_dates"]
        assert dates[0]["due_date"] == "2024-04-15"
        assert dates[1]["due_date"] == "2024-06-15"
        assert dates[2]["due_date"] == "2024-09-15"
        assert dates[3]["due_date"] == "2025-01-15"

    async def test_default_filing_status_single(self, session):
        """No household → defaults to single, marginal_rate=0.22."""
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.22


class TestQuarterlyWithIncome:
    """Quarterly estimate with NEC and K-1 income."""

    @pytest_asyncio.fixture(autouse=True)
    async def _seed_data(self, session):
        # Household
        hp = HouseholdProfile(
            filing_status="mfj",
            state="CA",
            spouse_a_income=200000,
            spouse_b_income=100000,
            combined_income=300000,
            is_primary=True,
        )
        session.add(hp)
        await session.flush()

        # NEC document
        doc = Document(
            filename="1099nec.pdf", original_path="/tmp/1099nec.pdf",
            file_type="pdf", document_type="1099_nec", status="completed",
            file_hash="fakehash_1099nec",
        )
        session.add(doc)
        await session.flush()
        self.doc_id = doc.id

        session.add(TaxItem(
            source_document_id=doc.id,
            tax_year=2024,
            form_type="1099-nec",
            payer_name="Consulting Client",
            nec_nonemployee_compensation=50000.0,
        ))
        await session.flush()

    async def test_nec_included(self, session):
        result = await compute_quarterly_estimate(session, 2024)
        assert result["total_se_income"] >= 50000

    async def test_quarterly_amount_positive(self, session):
        result = await compute_quarterly_estimate(session, 2024)
        assert result["quarterly_amount"] > 0

    async def test_annual_equals_four_quarterly(self, session):
        result = await compute_quarterly_estimate(session, 2024)
        expected = result["quarterly_amount"] * 4
        assert abs(result["annual_estimated_tax"] - expected) < 0.02

    async def test_marginal_rate_mfj_300k(self, session):
        """$300k combined MFJ → 24% bracket (190k < 300k < 340k)."""
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.24

    async def test_all_due_dates_have_amount(self, session):
        result = await compute_quarterly_estimate(session, 2024)
        for dd in result["due_dates"]:
            assert dd["amount"] == result["quarterly_amount"]
            assert "quarter" in dd
            assert "due_date" in dd

    async def test_k1_income_added(self, session):
        """Adding K-1 income increases total_se_income."""
        doc = Document(
            filename="k1.pdf", original_path="/tmp/k1.pdf",
            file_type="pdf", document_type="k1", status="completed",
            file_hash="fakehash_k1",
        )
        session.add(doc)
        await session.flush()

        session.add(TaxItem(
            source_document_id=doc.id,
            tax_year=2024,
            form_type="k-1",
            k1_ordinary_income=25000.0,
        ))
        await session.flush()

        result = await compute_quarterly_estimate(session, 2024)
        assert result["total_se_income"] >= 75000  # 50k NEC + 25k K-1


class TestQuarterlyMarginalRates:
    """Verify marginal rate logic for different income/filing combos."""

    @pytest_asyncio.fixture
    async def _make_household(self, session):
        async def _create(combined, filing_status="mfj"):
            hp = HouseholdProfile(
                filing_status=filing_status,
                state="CA",
                spouse_a_income=combined,
                spouse_b_income=0,
                combined_income=combined,
                is_primary=True,
            )
            session.add(hp)
            await session.flush()
        return _create

    async def test_mfj_low_income(self, session, _make_household):
        await _make_household(100000, "mfj")
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.22

    async def test_mfj_mid_income(self, session, _make_household):
        await _make_household(250000, "mfj")
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.24

    async def test_mfj_high_income(self, session, _make_household):
        await _make_household(400000, "mfj")
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.32

    async def test_single_low_income(self, session, _make_household):
        await _make_household(80000, "single")
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.22

    async def test_single_mid_income(self, session, _make_household):
        await _make_household(120000, "single")
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.24

    async def test_single_high_income(self, session, _make_household):
        await _make_household(200000, "single")
        result = await compute_quarterly_estimate(session, 2024)
        assert result["marginal_rate"] == 0.32
