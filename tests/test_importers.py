"""Tests for CSV/file import parsing."""
import os
import pytest
import tempfile

from pipeline.parsers.csv_parser import (
    parse_credit_card_csv,
    _detect_issuer,
    _transaction_hash,
    is_monarch_csv,
    parse_monarch_csv,
    ISSUER_PROFILES,
)
from pipeline.utils import file_hash


def _write_csv(tmpdir: str, filename: str, content: str) -> str:
    """Write CSV content to a file and return the path."""
    path = os.path.join(tmpdir, filename)
    with open(path, "w", newline="") as f:
        f.write(content)
    return path


class TestIssuerDetection:
    """Test CSV column-based issuer detection."""

    def test_detect_chase(self):
        cols = {"Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"}
        assert _detect_issuer(cols) == "chase"

    def test_detect_amex(self):
        cols = {"Date", "Description", "Amount"}
        assert _detect_issuer(cols) == "amex"

    def test_detect_capital_one(self):
        cols = {"Transaction Date", "Posted Date", "Card No.", "Description", "Category", "Debit", "Credit"}
        assert _detect_issuer(cols) == "capital_one"

    def test_detect_citi(self):
        cols = {"Status", "Date", "Description", "Debit", "Credit"}
        assert _detect_issuer(cols) == "citi"

    def test_detect_bank_of_america(self):
        cols = {"Posted Date", "Reference Number", "Payee", "Address", "Amount"}
        assert _detect_issuer(cols) == "bank_of_america"

    def test_detect_discover(self):
        cols = {"Trans. Date", "Post Date", "Description", "Amount", "Category"}
        assert _detect_issuer(cols) == "discover"

    def test_unknown_columns_returns_none(self):
        cols = {"Foo", "Bar", "Baz"}
        assert _detect_issuer(cols) is None

    def test_amex_max_cols_constraint(self):
        # Amex profile has max_cols=4; if CSV has too many columns it should not match
        cols = {"Date", "Description", "Amount", "Extra1", "Extra2"}
        assert _detect_issuer(cols) != "amex"


class TestChaseCSVParsing:
    """Test Chase credit card CSV parsing end to end."""

    def test_parse_chase_csv(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "01/15/2025,01/16/2025,AMAZON MARKETPLACE,Shopping,Sale,-52.99,\n"
            "01/16/2025,01/17/2025,STARBUCKS,Food & Drink,Sale,-5.50,\n"
            "01/20/2025,01/21/2025,PAYMENT RECEIVED,,Payment,1500.00,\n"
        )
        path = _write_csv(str(tmp_path), "chase.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        assert len(rows) == 3
        # Chase: negative = debit (expense), positive = credit (payment)
        assert rows[0]["amount"] < 0  # Amazon purchase
        assert rows[2]["amount"] > 0  # Payment

    def test_chase_descriptions_preserved(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "02/01/2025,02/02/2025,WHOLE FOODS MARKET,Groceries,Sale,-87.32,\n"
        )
        path = _write_csv(str(tmp_path), "chase2.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        assert rows[0]["description"] == "WHOLE FOODS MARKET"

    def test_chase_period_tracking(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "03/15/2025,03/16/2025,Some Purchase,Shopping,Sale,-10.00,\n"
        )
        path = _write_csv(str(tmp_path), "chase3.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        assert rows[0]["period_month"] == 3
        assert rows[0]["period_year"] == 2025


class TestAmexCSVParsing:
    """Test American Express CSV parsing."""

    def test_parse_amex_csv(self, tmp_path):
        # Amex: positive = debit (expense), which gets flipped to negative
        content = (
            "Date,Description,Amount\n"
            "01/15/2025,UBER TRIP,25.00\n"
            "01/20/2025,COSTCO WHOLESALE,-150.00\n"
        )
        path = _write_csv(str(tmp_path), "amex.csv", content)
        rows = parse_credit_card_csv(path, account_id=2, document_id=2)
        assert len(rows) == 2
        # Amex amounts are flipped: positive becomes negative (expense)
        assert rows[0]["amount"] == -25.00
        assert rows[1]["amount"] == 150.00  # negative becomes positive (credit)


class TestTransactionDeduplication:
    """Test hash-based deduplication."""

    def test_same_transaction_same_hash(self):
        from datetime import datetime

        h1 = _transaction_hash(datetime(2025, 1, 15), "STARBUCKS", -5.50, seq=0)
        h2 = _transaction_hash(datetime(2025, 1, 15), "STARBUCKS", -5.50, seq=0)
        assert h1 == h2

    def test_different_dates_different_hash(self):
        from datetime import datetime

        h1 = _transaction_hash(datetime(2025, 1, 15), "STARBUCKS", -5.50)
        h2 = _transaction_hash(datetime(2025, 1, 16), "STARBUCKS", -5.50)
        assert h1 != h2

    def test_different_amounts_different_hash(self):
        from datetime import datetime

        h1 = _transaction_hash(datetime(2025, 1, 15), "STARBUCKS", -5.50)
        h2 = _transaction_hash(datetime(2025, 1, 15), "STARBUCKS", -6.00)
        assert h1 != h2

    def test_seq_disambiguates_identical_transactions(self):
        from datetime import datetime

        h1 = _transaction_hash(datetime(2025, 1, 15), "STARBUCKS", -5.50, seq=0)
        h2 = _transaction_hash(datetime(2025, 1, 15), "STARBUCKS", -5.50, seq=1)
        assert h1 != h2

    def test_duplicate_rows_get_unique_hashes(self, tmp_path):
        """Two identical transactions on the same day should get different hashes."""
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "01/15/2025,01/16/2025,STARBUCKS,Food,Sale,-5.50,\n"
            "01/15/2025,01/16/2025,STARBUCKS,Food,Sale,-5.50,\n"
        )
        path = _write_csv(str(tmp_path), "dupes.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        assert len(rows) == 2
        hashes = [r["transaction_hash"] for r in rows]
        assert hashes[0] != hashes[1]


class TestMalformedCSV:
    """Test handling of invalid or malformed CSV files."""

    def test_unknown_format_raises(self, tmp_path):
        content = "Foo,Bar,Baz\n1,2,3\n"
        path = _write_csv(str(tmp_path), "bad.csv", content)
        with pytest.raises(ValueError, match="Unknown CSV format"):
            parse_credit_card_csv(path, account_id=1, document_id=1)

    def test_empty_csv_raises(self, tmp_path):
        path = _write_csv(str(tmp_path), "empty.csv", "")
        with pytest.raises(ValueError):
            parse_credit_card_csv(path, account_id=1, document_id=1)

    def test_rows_with_bad_dates_skipped(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "01/15/2025,01/16/2025,Good Transaction,Shopping,Sale,-10.00,\n"
            "not-a-date,01/16/2025,Bad Date,Shopping,Sale,-20.00,\n"
            ",01/16/2025,Empty Date,Shopping,Sale,-30.00,\n"
        )
        path = _write_csv(str(tmp_path), "bad_dates.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        # Only the first row with a valid date should parse
        assert len(rows) == 1
        assert rows[0]["description"] == "Good Transaction"

    def test_rows_with_missing_description_skipped(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "01/15/2025,01/16/2025,,Shopping,Sale,-10.00,\n"
            "01/16/2025,01/17/2025,Valid Item,Shopping,Sale,-20.00,\n"
        )
        path = _write_csv(str(tmp_path), "no_desc.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        assert len(rows) == 1
        assert rows[0]["description"] == "Valid Item"


class TestDateParsing:
    """Test various date format edge cases."""

    def test_iso_date_format(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "2025-03-15,2025-03-16,ISO Date,Shopping,Sale,-10.00,\n"
        )
        path = _write_csv(str(tmp_path), "iso.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        assert len(rows) == 1
        assert rows[0]["period_month"] == 3

    def test_us_date_format(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "12/31/2025,01/01/2026,New Year,Shopping,Sale,-10.00,\n"
        )
        path = _write_csv(str(tmp_path), "us.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1)
        assert len(rows) == 1
        assert rows[0]["period_month"] == 12
        assert rows[0]["period_year"] == 2025


class TestFileHash:
    """Test file-level SHA-256 hashing."""

    def test_same_content_same_hash(self, tmp_path):
        content = "Transaction Date,Post Date,Description\n01/01/2025,01/02/2025,Test\n"
        path1 = _write_csv(str(tmp_path), "file1.csv", content)
        path2 = _write_csv(str(tmp_path), "file2.csv", content)
        assert file_hash(path1) == file_hash(path2)

    def test_different_content_different_hash(self, tmp_path):
        path1 = _write_csv(str(tmp_path), "a.csv", "content A")
        path2 = _write_csv(str(tmp_path), "b.csv", "content B")
        assert file_hash(path1) != file_hash(path2)

    def test_hash_is_64_char_hex(self, tmp_path):
        path = _write_csv(str(tmp_path), "test.csv", "some content")
        h = file_hash(path)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestDefaultSegment:
    """Test that default_segment is propagated to parsed transactions."""

    def test_personal_segment(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "01/15/2025,01/16/2025,Test,Shopping,Sale,-10.00,\n"
        )
        path = _write_csv(str(tmp_path), "seg.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1, default_segment="personal")
        assert rows[0]["segment"] == "personal"
        assert rows[0]["effective_segment"] == "personal"

    def test_business_segment(self, tmp_path):
        content = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "01/15/2025,01/16/2025,Test,Shopping,Sale,-10.00,\n"
        )
        path = _write_csv(str(tmp_path), "seg_biz.csv", content)
        rows = parse_credit_card_csv(path, account_id=1, document_id=1, default_segment="business")
        assert rows[0]["segment"] == "business"


class TestMonarchCSV:
    """Test Monarch Money CSV detection and parsing."""

    def test_detect_monarch_csv(self, tmp_path):
        content = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        path = _write_csv(str(tmp_path), "monarch.csv", content)
        assert is_monarch_csv(path) is True

    def test_non_monarch_csv(self, tmp_path):
        content = "Foo,Bar,Baz\n1,2,3\n"
        path = _write_csv(str(tmp_path), "not_monarch.csv", content)
        assert is_monarch_csv(path) is False

    def test_parse_monarch_transactions(self, tmp_path):
        content = (
            "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
            "2025-01-15,Whole Foods,Groceries,Chase Sapphire,WHOLE FOODS MKT,,-87.32,\n"
            "2025-01-20,Costco,Shopping,Chase Sapphire,COSTCO WHOLESALE,,-120.50,bulk\n"
        )
        path = _write_csv(str(tmp_path), "monarch.csv", content)
        txns = parse_monarch_csv(path)
        assert len(txns) == 2
        assert txns[0].merchant == "Whole Foods"
        assert txns[0].category == "Groceries"
