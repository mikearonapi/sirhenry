"""
Comprehensive tests for ALL importer modules in pipeline/importers/.

Covers:
  1. amazon.py    -- Amazon retail, digital, refund CSV parsers + import flow
  2. credit_card.py -- Credit card CSV import (full async flow with DB)
  3. investment.py  -- Investment statement PDF/CSV import
  4. monarch.py     -- Monarch Money CSV import
  5. paystub.py     -- Pay stub parser + suggestions builder
  6. tax_doc.py     -- Tax document importer (year inference, dedup, form detection)
  7. insurance_doc.py -- Insurance document importer
"""
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from pipeline.db.schema import (
    Account,
    AmazonOrder,
    Base,
    Document,
    InsurancePolicy,
    TaxItem,
    Transaction,
)


# ---- helpers ----

def _write_csv(directory: str, filename: str, content: str) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w", newline="") as f:
        f.write(content)
    return path


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
#  1. AMAZON IMPORTER
# ---------------------------------------------------------------------------

class TestAmazonRetailParser:
    """Tests for parse_amazon_csv (retail order history)."""

    def test_single_order_parsed_correctly(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-1234567-8901234,2025-06-15,USB-C Cable,$12.99,$12.99,1,Visa\n"
        )
        path = _write_csv(str(tmp_path), "retail.csv", csv)
        orders = parse_amazon_csv(path)

        assert len(orders) == 1
        order = orders[0]
        assert order["order_id"] == "111-1234567-8901234"
        assert order["parent_order_id"] == "111-1234567-8901234"
        assert order["total_charged"] == 12.99
        assert order["is_digital"] is False
        assert order["is_refund"] is False
        assert "USB-C Cable" in order["items_description"]
        assert order["payment_method_last4"] == "Visa"
        assert order["order_date"].year == 2025
        assert order["order_date"].month == 6
        assert order["order_date"].day == 15

    def test_multi_item_single_shipment(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-0000001-0000001,2025-03-10,Widget A,$25.00,$25.00,1,Visa\n"
            "111-0000001-0000001,2025-03-10,Widget B,$25.00,$15.00,2,Visa\n"
        )
        path = _write_csv(str(tmp_path), "multi_item.csv", csv)
        orders = parse_amazon_csv(path)

        # Same order, same shipment subtotal -> single shipment
        assert len(orders) == 1
        assert orders[0]["total_charged"] == 40.00  # 25 + 15

    def test_multi_shipment_order_produces_synthetic_ids(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-0000002-0000002,2025-04-01,Book,$10.00,$10.00,1,Mastercard\n"
            "111-0000002-0000002,2025-04-01,Headphones,$50.00,$50.00,1,Mastercard\n"
        )
        path = _write_csv(str(tmp_path), "multi_ship.csv", csv)
        orders = parse_amazon_csv(path)

        # Different shipment subtotals -> two synthetic IDs
        assert len(orders) == 2
        ids = {o["order_id"] for o in orders}
        assert any("-S" in oid for oid in ids)
        # Both share the same parent order ID
        parents = {o["parent_order_id"] for o in orders}
        assert parents == {"111-0000002-0000002"}

    def test_skips_rows_with_blank_order_id(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            ",2025-01-01,Ghost Item,$5.00,$5.00,1,Visa\n"
            "111-0000003-0000003,2025-01-01,Real Item,$8.00,$8.00,1,Visa\n"
        )
        path = _write_csv(str(tmp_path), "blank_id.csv", csv)
        orders = parse_amazon_csv(path)

        assert len(orders) == 1
        assert orders[0]["order_id"] == "111-0000003-0000003"

    def test_skips_rows_with_bad_dates(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-0000004-0000004,not-a-date,Bad Date,$5.00,$5.00,1,Visa\n"
            "111-0000005-0000005,2025-07-01,Good Order,$9.99,$9.99,1,Visa\n"
        )
        path = _write_csv(str(tmp_path), "bad_date.csv", csv)
        orders = parse_amazon_csv(path)

        assert len(orders) == 1
        assert orders[0]["total_charged"] == 9.99

    def test_missing_order_id_column_raises(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = "Bad Column,Order Date,Title\nfoo,2025-01-01,Item\n"
        path = _write_csv(str(tmp_path), "no_order_id.csv", csv)

        with pytest.raises(ValueError, match="Unknown Amazon CSV format"):
            parse_amazon_csv(path)

    def test_legacy_format_with_item_total(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = (
            "Order ID,Order Date,Product Name,Item Total,Quantity\n"
            "111-LEGACY-0001,2025-02-14,Valentine Roses,$29.99,1\n"
        )
        path = _write_csv(str(tmp_path), "legacy.csv", csv)
        orders = parse_amazon_csv(path)

        assert len(orders) == 1
        assert orders[0]["total_charged"] == 29.99
        assert "Valentine Roses" in orders[0]["items_description"]

    def test_quantity_greater_than_one(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-QTY-0001,2025-08-01,AA Batteries,$7.99,$15.98,2,Visa\n"
        )
        path = _write_csv(str(tmp_path), "qty.csv", csv)
        orders = parse_amazon_csv(path)

        assert len(orders) == 1
        raw_items = json.loads(orders[0]["raw_items"])
        assert raw_items[0]["quantity"] == 2
        assert "(x2)" in orders[0]["items_description"]

    def test_more_than_five_items_truncated(self, tmp_path):
        from pipeline.importers.amazon import parse_amazon_csv

        rows = []
        for i in range(7):
            rows.append(
                f"111-MANY-0001,2025-05-01,Item {i},$5.00,$5.00,1,Visa"
            )
        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            + "\n".join(rows)
        )
        path = _write_csv(str(tmp_path), "many.csv", csv)
        orders = parse_amazon_csv(path)

        assert len(orders) == 1
        assert "+ 2 more items" in orders[0]["items_description"]


class TestAmazonDigitalParser:
    """Tests for parse_digital_content_csv."""

    def test_digital_order_parsed(self, tmp_path):
        from pipeline.importers.amazon import parse_digital_content_csv

        csv = (
            "Order ID,Order Date,Product Name,Transaction Amount,"
            "Component Type,Quantity Ordered\n"
            "D01-1234-5678,2025-01-10,Kindle Book,9.99,Price Amount,1\n"
            "D01-1234-5678,2025-01-10,Kindle Book,0.80,Tax,1\n"
        )
        path = _write_csv(str(tmp_path), "digital.csv", csv)
        orders = parse_digital_content_csv(path)

        assert len(orders) == 1
        order = orders[0]
        assert order["order_id"] == "D01-1234-5678"
        assert order["total_charged"] == 10.79  # 9.99 + 0.80
        assert order["is_digital"] is True
        assert order["is_refund"] is False
        assert "Kindle Book" in order["items_description"]

    def test_zero_total_orders_excluded(self, tmp_path):
        from pipeline.importers.amazon import parse_digital_content_csv

        csv = (
            "Order ID,Order Date,Product Name,Transaction Amount,"
            "Component Type,Quantity Ordered\n"
            "D01-FREE-0001,2025-02-01,Free Ebook,0.00,Price Amount,1\n"
        )
        path = _write_csv(str(tmp_path), "free.csv", csv)
        orders = parse_digital_content_csv(path)
        assert len(orders) == 0

    def test_missing_columns_raises(self, tmp_path):
        from pipeline.importers.amazon import parse_digital_content_csv

        csv = "Order ID,Bad Column\nD01-X,foo\n"
        path = _write_csv(str(tmp_path), "bad_digital.csv", csv)

        with pytest.raises(ValueError, match="missing columns"):
            parse_digital_content_csv(path)

    def test_multiple_digital_orders(self, tmp_path):
        from pipeline.importers.amazon import parse_digital_content_csv

        csv = (
            "Order ID,Order Date,Product Name,Transaction Amount,"
            "Component Type,Quantity Ordered\n"
            "D01-AAA,2025-03-01,App Purchase,4.99,Price Amount,1\n"
            "D01-BBB,2025-03-02,Music Album,12.99,Price Amount,1\n"
            "D01-BBB,2025-03-02,Music Album,1.04,Tax,1\n"
        )
        path = _write_csv(str(tmp_path), "multi_digital.csv", csv)
        orders = parse_digital_content_csv(path)

        assert len(orders) == 2
        by_id = {o["order_id"]: o for o in orders}
        assert by_id["D01-AAA"]["total_charged"] == 4.99
        assert by_id["D01-BBB"]["total_charged"] == 14.03


class TestAmazonRefundParser:
    """Tests for parse_refund_csv."""

    def test_refund_parsed_with_negative_amount(self, tmp_path):
        from pipeline.importers.amazon import parse_refund_csv

        csv = (
            "Order ID,Refund Amount,Refund Date,Reversal Reason\n"
            "111-REF-0001,25.99,2025-04-15,Customer Return\n"
        )
        path = _write_csv(str(tmp_path), "refund.csv", csv)
        refunds = parse_refund_csv(path)

        assert len(refunds) == 1
        r = refunds[0]
        assert r["total_charged"] == -25.99  # always negative
        assert r["is_refund"] is True
        assert r["parent_order_id"] == "111-REF-0001"
        assert "111-REF-0001-REFUND" == r["order_id"]
        assert "Customer Return" in r["items_description"]

    def test_multiple_refunds_for_same_order(self, tmp_path):
        from pipeline.importers.amazon import parse_refund_csv

        csv = (
            "Order ID,Refund Amount,Refund Date,Reversal Reason\n"
            "111-MULTI-0001,10.00,2025-05-01,Defective\n"
            "111-MULTI-0001,5.00,2025-05-05,Wrong Item\n"
        )
        path = _write_csv(str(tmp_path), "multi_refund.csv", csv)
        refunds = parse_refund_csv(path)

        assert len(refunds) == 2
        ids = {r["order_id"] for r in refunds}
        # First refund: no suffix, second: -REFUND-2
        assert "111-MULTI-0001-REFUND" in ids
        assert "111-MULTI-0001-REFUND-2" in ids

    def test_zero_refund_skipped(self, tmp_path):
        from pipeline.importers.amazon import parse_refund_csv

        csv = (
            "Order ID,Refund Amount,Refund Date,Reversal Reason\n"
            "111-ZERO-0001,0.00,2025-06-01,\n"
        )
        path = _write_csv(str(tmp_path), "zero_refund.csv", csv)
        refunds = parse_refund_csv(path)
        assert len(refunds) == 0

    def test_missing_refund_columns_raises(self, tmp_path):
        from pipeline.importers.amazon import parse_refund_csv

        csv = "Order ID,Bad Column\n111-X,foo\n"
        path = _write_csv(str(tmp_path), "bad_refund.csv", csv)

        with pytest.raises(ValueError, match="missing columns"):
            parse_refund_csv(path)

    def test_fallback_to_creation_date(self, tmp_path):
        from pipeline.importers.amazon import parse_refund_csv

        csv = (
            "Order ID,Refund Amount,Refund Date,Creation Date,Reversal Reason\n"
            "111-FALLBACK-01,15.00,not-a-date,2025-07-01,Damaged\n"
        )
        path = _write_csv(str(tmp_path), "fallback_date.csv", csv)
        refunds = parse_refund_csv(path)

        assert len(refunds) == 1
        assert refunds[0]["order_date"].month == 7


class TestAmazonEnrichRawItems:
    """Tests for _enrich_raw_items_with_categories."""

    def test_merges_categories_by_title(self):
        from pipeline.importers.amazon import _enrich_raw_items_with_categories

        raw_items = json.dumps([
            {"title": "USB Cable", "quantity": 1, "price": 12.99},
            {"title": "Book", "quantity": 1, "price": 9.99},
        ])
        item_categories = [
            {"title": "USB Cable", "category": "Electronics", "segment": "personal"},
            {"title": "Book", "category": "Books & Media", "segment": "personal"},
        ]
        result = json.loads(_enrich_raw_items_with_categories(raw_items, item_categories))

        assert len(result) == 2
        assert result[0]["category"] == "Electronics"
        assert result[1]["category"] == "Books & Media"

    def test_handles_empty_raw_items(self):
        from pipeline.importers.amazon import _enrich_raw_items_with_categories

        result = json.loads(_enrich_raw_items_with_categories("", []))
        assert result == []

    def test_unmatched_items_keep_no_category(self):
        from pipeline.importers.amazon import _enrich_raw_items_with_categories

        raw_items = json.dumps([
            {"title": "Mystery Item", "quantity": 1, "price": 5.00},
        ])
        result = json.loads(_enrich_raw_items_with_categories(raw_items, []))
        assert "category" not in result[0]


class TestAmazonImportFlow:
    """Tests for import_amazon_csv (full async import into DB)."""

    @pytest.mark.asyncio
    async def test_import_file_not_found(self, session):
        from pipeline.importers.amazon import import_amazon_csv

        result = await import_amazon_csv(session, "/nonexistent/file.csv")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_import_retail_orders_no_ai(self, session, tmp_path):
        from pipeline.importers.amazon import import_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-IMPORT-0001,2025-09-01,Laptop Stand,$45.99,$45.99,1,Visa\n"
            "111-IMPORT-0002,2025-09-02,Mouse Pad,$12.50,$12.50,1,Visa\n"
        )
        path = _write_csv(str(tmp_path), "import_retail.csv", csv)

        result = await import_amazon_csv(
            session, path, owner="Mike", file_type="retail", run_categorize=False
        )

        assert result["status"] == "completed"
        assert result["orders_imported"] == 2
        assert result["document_id"] is not None

    @pytest.mark.asyncio
    async def test_duplicate_file_detected(self, session, tmp_path):
        from pipeline.importers.amazon import import_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-DUPE-0001,2025-10-01,Item,$10.00,$10.00,1,Visa\n"
        )
        path = _write_csv(str(tmp_path), "dupe.csv", csv)

        # First import
        r1 = await import_amazon_csv(session, path, run_categorize=False)
        assert r1["status"] == "completed"

        # Second import of same file
        r2 = await import_amazon_csv(session, path, run_categorize=False)
        assert r2["status"] == "duplicate"

    @pytest.mark.asyncio
    async def test_import_digital_orders(self, session, tmp_path):
        from pipeline.importers.amazon import import_amazon_csv

        csv = (
            "Order ID,Order Date,Product Name,Transaction Amount,"
            "Component Type,Quantity Ordered\n"
            "D01-IMP-001,2025-11-01,Audiobook,14.95,Price Amount,1\n"
        )
        path = _write_csv(str(tmp_path), "digital_import.csv", csv)

        result = await import_amazon_csv(
            session, path, file_type="digital", run_categorize=False
        )
        assert result["status"] == "completed"
        assert result["orders_imported"] == 1

    @pytest.mark.asyncio
    async def test_import_refund_orders(self, session, tmp_path):
        from pipeline.importers.amazon import import_amazon_csv

        csv = (
            "Order ID,Refund Amount,Refund Date,Reversal Reason\n"
            "111-IMP-REF-001,19.99,2025-12-01,Changed Mind\n"
        )
        path = _write_csv(str(tmp_path), "refund_import.csv", csv)

        result = await import_amazon_csv(
            session, path, file_type="refund", run_categorize=False
        )
        assert result["status"] == "completed"
        assert result["orders_imported"] == 1

    @pytest.mark.asyncio
    async def test_import_with_category_map(self, session, tmp_path):
        from pipeline.importers.amazon import import_amazon_csv

        csv = (
            "Order ID,Order Date,Title,Shipment Item Subtotal,Total Amount,"
            "Original Quantity,Payment Method Type\n"
            "111-CATMAP-001,2025-09-15,Office Chair,$299.99,$299.99,1,Visa\n"
        )
        path = _write_csv(str(tmp_path), "catmap.csv", csv)

        category_map = {
            "111-CATMAP-001": {
                "category": "Office Supplies",
                "segment": "business",
                "is_business": True,
                "is_gift": False,
            }
        }
        result = await import_amazon_csv(
            session, path, run_categorize=False, category_map=category_map
        )
        assert result["status"] == "completed"
        assert result["orders_imported"] == 1


# ---------------------------------------------------------------------------
#  2. CREDIT CARD IMPORTER
# ---------------------------------------------------------------------------

class TestCreditCardImporter:
    """Tests for credit_card.import_csv_file (full DB flow)."""

    @pytest.mark.asyncio
    async def test_import_chase_csv(self, session, tmp_path):
        from pipeline.importers.credit_card import import_csv_file

        csv = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "01/05/2025,01/06/2025,AMAZON MARKETPLACE,Shopping,Sale,-89.99,\n"
            "01/10/2025,01/11/2025,WHOLE FOODS MARKET,Groceries,Sale,-62.14,\n"
            "01/15/2025,01/16/2025,PAYMENT RECEIVED,,Payment,2500.00,\n"
        )
        path = _write_csv(str(tmp_path), "chase_stmt.csv", csv)

        result = await import_csv_file(
            session, path,
            account_name="Chase Sapphire",
            institution="Chase",
        )

        assert result["status"] == "completed"
        assert result["transactions_imported"] == 3
        assert result["transactions_skipped"] == 0
        assert result["document_id"] is not None

    @pytest.mark.asyncio
    async def test_import_file_not_found(self, session):
        from pipeline.importers.credit_card import import_csv_file

        result = await import_csv_file(session, "/nonexistent/cc.csv")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_duplicate_file_skipped(self, session, tmp_path):
        from pipeline.importers.credit_card import import_csv_file

        csv = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "02/01/2025,02/02/2025,STARBUCKS,Food,Sale,-5.50,\n"
        )
        path = _write_csv(str(tmp_path), "dupe_cc.csv", csv)

        r1 = await import_csv_file(session, path)
        assert r1["status"] == "completed"

        r2 = await import_csv_file(session, path)
        assert r2["status"] == "duplicate"
        assert r2["transactions_imported"] == 0

    @pytest.mark.asyncio
    async def test_import_with_business_segment(self, session, tmp_path):
        from pipeline.importers.credit_card import import_csv_file

        csv = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "03/01/2025,03/02/2025,OFFICE DEPOT,Office,Sale,-149.99,\n"
        )
        path = _write_csv(str(tmp_path), "biz_cc.csv", csv)

        result = await import_csv_file(
            session, path, default_segment="business"
        )
        assert result["status"] == "completed"
        assert result["transactions_imported"] == 1

    @pytest.mark.asyncio
    async def test_import_with_existing_account_id(self, session, tmp_path):
        from pipeline.importers.credit_card import import_csv_file

        # First create an account manually
        acct = Account(
            name="Existing Card",
            account_type="personal",
            subtype="credit_card",
            institution="Chase",
        )
        session.add(acct)
        await session.flush()

        csv = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "04/01/2025,04/02/2025,TARGET,Shopping,Sale,-35.00,\n"
        )
        path = _write_csv(str(tmp_path), "existing_acct.csv", csv)

        result = await import_csv_file(session, path, account_id=acct.id)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_import_with_invalid_account_id(self, session, tmp_path):
        from pipeline.importers.credit_card import import_csv_file

        csv = (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "05/01/2025,05/02/2025,UBER,Transport,Sale,-22.00,\n"
        )
        path = _write_csv(str(tmp_path), "bad_acct.csv", csv)

        result = await import_csv_file(session, path, account_id=99999)
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_import_unknown_format(self, session, tmp_path):
        from pipeline.importers.credit_card import import_csv_file

        csv = "Foo,Bar,Baz\n1,2,3\n"
        path = _write_csv(str(tmp_path), "bad_format.csv", csv)

        result = await import_csv_file(session, path)
        assert result["status"] == "error"
        assert "Unknown CSV format" in result["message"]

    @pytest.mark.asyncio
    async def test_import_directory(self, session, tmp_path):
        from pipeline.importers.credit_card import import_directory

        for i in range(3):
            csv = (
                "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
                f"06/{i+1:02d}/2025,06/{i+2:02d}/2025,Purchase {i},Shopping,Sale,-{10+i}.00,\n"
            )
            _write_csv(str(tmp_path), f"stmt_{i}.csv", csv)

        results = await import_directory(session, str(tmp_path))
        assert len(results) == 3
        assert all(r["status"] == "completed" for r in results)

    @pytest.mark.asyncio
    async def test_capital_one_debit_credit_format(self, session, tmp_path):
        from pipeline.importers.credit_card import import_csv_file

        csv = (
            "Transaction Date,Posted Date,Card No.,Description,Category,Debit,Credit\n"
            "2025-01-05,2025-01-06,1234,GROCERY STORE,Groceries,75.50,\n"
            "2025-01-10,2025-01-11,1234,REFUND,Return,,25.00\n"
        )
        path = _write_csv(str(tmp_path), "cap1.csv", csv)

        result = await import_csv_file(session, path, account_name="Capital One")
        assert result["status"] == "completed"
        assert result["transactions_imported"] == 2


# ---------------------------------------------------------------------------
#  3. INVESTMENT IMPORTER
# ---------------------------------------------------------------------------

class TestInvestmentImporter:
    """Tests for investment.py functions."""

    def test_detect_brokerage_fidelity(self):
        from pipeline.importers.investment import _detect_brokerage

        assert _detect_brokerage("Account at Fidelity Investments") == "Fidelity"

    def test_detect_brokerage_schwab(self):
        from pipeline.importers.investment import _detect_brokerage

        assert _detect_brokerage("Charles Schwab Statement") == "Schwab"

    def test_detect_brokerage_vanguard(self):
        from pipeline.importers.investment import _detect_brokerage

        assert _detect_brokerage("Vanguard Group Brokerage") == "Vanguard"

    def test_detect_brokerage_etrade(self):
        from pipeline.importers.investment import _detect_brokerage

        assert _detect_brokerage("E*TRADE Securities") == "E*Trade"
        assert _detect_brokerage("eTrade account") == "E*Trade"

    def test_detect_brokerage_td_ameritrade(self):
        from pipeline.importers.investment import _detect_brokerage

        assert _detect_brokerage("TD Ameritrade Account") == "TD Ameritrade"

    def test_detect_brokerage_merrill(self):
        from pipeline.importers.investment import _detect_brokerage

        assert _detect_brokerage("Merrill Lynch Wealth Management") == "Merrill Lynch"

    def test_detect_brokerage_unknown(self):
        from pipeline.importers.investment import _detect_brokerage

        assert _detect_brokerage("Some Random Broker XYZ") == "Unknown Brokerage"

    def test_extract_1099b_entries(self):
        from pipeline.importers.investment import _extract_1099b_entries

        text = (
            "APPLE INC                    15,000.00  12,000.00    3,000.00  long\n"
            "TESLA INC                    8,500.00   10,200.00   -1,700.00  short\n"
        )
        entries = _extract_1099b_entries(text)

        assert len(entries) == 2
        assert entries[0]["description"] == "APPLE INC"
        assert entries[0]["proceeds"] == 15000.00
        assert entries[0]["cost_basis"] == 12000.00
        assert entries[0]["gain_loss"] == 3000.00
        assert entries[0]["term"] == "long"

        assert entries[1]["description"] == "TESLA INC"
        assert entries[1]["gain_loss"] == -1700.00
        assert entries[1]["term"] == "short"

    def test_extract_1099b_no_matches(self):
        from pipeline.importers.investment import _extract_1099b_entries

        entries = _extract_1099b_entries("No relevant data here.")
        assert entries == []

    def test_extract_dividend_income(self):
        from pipeline.importers.investment import _extract_dividend_income

        text = "Total Dividends: $3,456.78\nOther info here"
        assert _extract_dividend_income(text) == 3456.78

    def test_extract_dividend_total_ordinary(self):
        from pipeline.importers.investment import _extract_dividend_income

        text = "Total Ordinary Dividends $1,234.56"
        assert _extract_dividend_income(text) == 1234.56

    def test_extract_dividend_none(self):
        from pipeline.importers.investment import _extract_dividend_income

        assert _extract_dividend_income("No dividend info") == 0.0

    @pytest.mark.asyncio
    async def test_import_file_not_found(self, session):
        from pipeline.importers.investment import import_investment_file

        result = await import_investment_file(session, "/no/such/file.pdf")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_import_unsupported_file_type(self, session, tmp_path):
        from pipeline.importers.investment import import_investment_file

        path = str(tmp_path / "data.xlsx")
        with open(path, "w") as f:
            f.write("dummy")

        result = await import_investment_file(session, path)
        assert result["status"] == "error"
        assert "Unsupported file type" in result["message"]

    @pytest.mark.asyncio
    async def test_import_investment_csv(self, session, tmp_path):
        from pipeline.importers.investment import import_investment_file

        csv = (
            "Date,Action,Symbol,Quantity,Price,Amount\n"
            "2025-06-01,Buy,AAPL,10,150.00,1500.00\n"
            "2025-06-15,Dividend,VTI,0,0,125.50\n"
            "2025-07-01,Sell,TSLA,5,250.00,-1250.00\n"
        )
        path = _write_csv(str(tmp_path), "schwab.csv", csv)

        result = await import_investment_file(
            session, path, account_name="Schwab Brokerage"
        )
        assert result["status"] == "completed"
        assert result["items_created"] == 3

    @pytest.mark.asyncio
    async def test_import_duplicate_csv(self, session, tmp_path):
        from pipeline.importers.investment import import_investment_file

        csv = (
            "Date,Action,Symbol,Quantity,Price,Amount\n"
            "2025-08-01,Buy,MSFT,5,400.00,2000.00\n"
        )
        path = _write_csv(str(tmp_path), "dup_inv.csv", csv)

        r1 = await import_investment_file(session, path)
        assert r1["status"] == "completed"

        r2 = await import_investment_file(session, path)
        assert r2["status"] == "duplicate"

    @pytest.mark.asyncio
    async def test_import_pdf_with_1099b_and_dividends(self, session, tmp_path):
        """Test PDF import with mocked extract_pdf returning 1099-B and dividend data."""
        from pipeline.importers.investment import import_investment_file
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage

        pdf_text = (
            "Fidelity Investments\n"
            "Annual Tax Statement 2025\n"
            "APPLE INC                    15,000.00  12,000.00    3,000.00  long\n"
            "Total Ordinary Dividends $2,500.00\n"
        )
        mock_doc = PDFDocument(
            filepath="fake.pdf",
            pages=[PDFPage(page_num=1, text=pdf_text, tables=[])],
        )

        pdf_path = str(tmp_path / "fidelity_2025.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 fake content for hashing")

        with patch("pipeline.importers.investment.extract_pdf", return_value=mock_doc):
            result = await import_investment_file(session, pdf_path, tax_year=2025)

        assert result["status"] == "completed"
        assert result["brokerage"] == "Fidelity"
        assert result["items_created"] >= 2  # 1099-B entry + dividend transaction


# ---------------------------------------------------------------------------
#  4. MONARCH IMPORTER
# ---------------------------------------------------------------------------

class TestMonarchImporter:
    """Tests for monarch.import_monarch_csv (full DB flow)."""

    @pytest.mark.asyncio
    async def test_import_monarch_csv(self, session, tmp_path):
        from pipeline.importers.monarch import import_monarch_csv

        csv = (
            "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
            "2025-01-15,Whole Foods,Groceries,Chase Sapphire ****4321,WHOLE FOODS MKT #123,,-87.32,\n"
            "2025-01-20,Costco,Shopping,Chase Sapphire ****4321,COSTCO WHOLESALE,Bulk buy,-120.50,\n"
            "2025-01-25,Amazon,Shopping,Amex Gold ****9876,AMZN MKTP US,,-45.99,\n"
        )
        path = _write_csv(str(tmp_path), "monarch_export.csv", csv)

        result = await import_monarch_csv(session, path)

        assert result["status"] == "completed"
        assert result["transactions_imported"] == 3
        assert "2 accounts" in result["message"]

    @pytest.mark.asyncio
    async def test_import_file_not_found(self, session):
        from pipeline.importers.monarch import import_monarch_csv

        result = await import_monarch_csv(session, "/nonexistent/monarch.csv")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_import_duplicate_file(self, session, tmp_path):
        from pipeline.importers.monarch import import_monarch_csv

        csv = (
            "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
            "2025-02-01,Starbucks,Coffee,Chase ****1111,STARBUCKS,,-5.50,\n"
        )
        path = _write_csv(str(tmp_path), "monarch_dup.csv", csv)

        r1 = await import_monarch_csv(session, path)
        assert r1["status"] == "completed"

        r2 = await import_monarch_csv(session, path)
        assert r2["status"] == "duplicate"

    @pytest.mark.asyncio
    async def test_empty_transactions_file(self, session, tmp_path):
        from pipeline.importers.monarch import import_monarch_csv

        csv = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        path = _write_csv(str(tmp_path), "empty_monarch.csv", csv)

        result = await import_monarch_csv(session, path)
        assert result["status"] == "completed"
        assert result["transactions_imported"] == 0

    @pytest.mark.asyncio
    async def test_business_tag_sets_segment(self, session, tmp_path):
        from pipeline.importers.monarch import import_monarch_csv

        csv = (
            "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
            "2025-03-01,Office Depot,Office,Chase ****2222,OFFICE DEPOT,,- 149.99,business\n"
        )
        path = _write_csv(str(tmp_path), "biz_monarch.csv", csv)

        result = await import_monarch_csv(session, path)
        assert result["status"] == "completed"
        assert result["transactions_imported"] == 1

    @pytest.mark.asyncio
    async def test_categories_preserved_from_monarch(self, session, tmp_path):
        from pipeline.importers.monarch import import_monarch_csv

        csv = (
            "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
            "2025-04-01,Shell Gas,Gas & Fuel,Citi ****3333,SHELL OIL,,-42.50,\n"
        )
        path = _write_csv(str(tmp_path), "cat_monarch.csv", csv)

        result = await import_monarch_csv(session, path)
        assert result["status"] == "completed"


class TestMonarchSegmentGuessing:
    """Test _guess_segment helper."""

    def test_business_tag(self):
        from pipeline.importers.monarch import _guess_segment
        from pipeline.parsers.csv_parser import MonarchTransaction

        tx = MonarchTransaction(
            date=datetime(2025, 1, 1),
            merchant="Office Depot",
            category="",
            account_name="",
            original_statement="",
            notes="",
            amount=-50.0,
            tags=["Business"],
        )
        assert _guess_segment(tx) == "business"

    def test_work_tag(self):
        from pipeline.importers.monarch import _guess_segment
        from pipeline.parsers.csv_parser import MonarchTransaction

        tx = MonarchTransaction(
            date=datetime(2025, 1, 1),
            merchant="LinkedIn",
            category="",
            account_name="",
            original_statement="",
            notes="",
            amount=-30.0,
            tags=["Work"],
        )
        assert _guess_segment(tx) == "business"

    def test_investment_tag(self):
        from pipeline.importers.monarch import _guess_segment
        from pipeline.parsers.csv_parser import MonarchTransaction

        tx = MonarchTransaction(
            date=datetime(2025, 1, 1),
            merchant="Fidelity",
            category="",
            account_name="",
            original_statement="",
            notes="",
            amount=-500.0,
            tags=["investing"],
        )
        assert _guess_segment(tx) == "investment"

    def test_personal_default(self):
        from pipeline.importers.monarch import _guess_segment
        from pipeline.parsers.csv_parser import MonarchTransaction

        tx = MonarchTransaction(
            date=datetime(2025, 1, 1),
            merchant="Target",
            category="",
            account_name="",
            original_statement="",
            notes="",
            amount=-25.0,
            tags=[],
        )
        assert _guess_segment(tx) == "personal"


# ---------------------------------------------------------------------------
#  5. PAYSTUB IMPORTER
# ---------------------------------------------------------------------------

class TestPaystubBuildSuggestions:
    """Tests for _build_suggestions in paystub.py."""

    def test_salary_from_annual(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {
            "employer_name": "Acme Corp",
            "annual_salary": 195000.00,
            "state": "CA",
        }
        suggestions = _build_suggestions(data)

        assert suggestions["household"]["employer"] == "Acme Corp"
        assert suggestions["household"]["income"] == 195000.00
        assert suggestions["household"]["work_state"] == "CA"

    def test_salary_extrapolated_from_ytd(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {
            "employer_name": "TechCo",
            "annual_salary": None,
            "gross_pay": None,
            "ytd_gross": 50000.00,
            "pay_date": "2025-03-15",
        }
        suggestions = _build_suggestions(data)

        # 50000 / 3 months * 12 = 200000
        assert suggestions["household"]["income"] == 200000.00

    def test_salary_extrapolated_from_gross_pay(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {
            "employer_name": "StartupCo",
            "annual_salary": None,
            "gross_pay": 7500.00,
            "ytd_gross": None,
        }
        suggestions = _build_suggestions(data)

        # 7500 * 26 (biweekly assumption) = 195000
        assert suggestions["household"]["income"] == 195000.00

    def test_401k_suggestions(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {
            "retirement_401k": 750.00,
            "retirement_401k_ytd": 3000.00,
            "employer_401k_match": 375.00,
        }
        suggestions = _build_suggestions(data)

        benefits = suggestions["benefits"]
        assert benefits["has_401k"] is True
        assert benefits["annual_401k_contribution"] == 19500.00  # 750 * 26
        assert benefits["employer_match_pct"] == 50.0  # 375/750 * 100

    def test_hsa_suggestions(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {
            "hsa_contribution": 150.00,
            "hsa_employer_contribution": 50.00,
        }
        suggestions = _build_suggestions(data)

        benefits = suggestions["benefits"]
        assert benefits["has_hsa"] is True
        assert benefits["hsa_employer_contribution"] == 1300.00  # 50 * 26

    def test_health_premium_monthly_conversion(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {
            "health_premium": 250.00,
            "dental_premium": 25.00,
            "vision_premium": 10.00,
        }
        suggestions = _build_suggestions(data)

        benefits = suggestions["benefits"]
        # 250 * 26 / 12 = 541.67
        assert abs(benefits["health_premium_monthly"] - 541.67) < 0.01
        # (25 + 10) * 26 / 12 = 75.83
        assert abs(benefits["dental_vision_monthly"] - 75.83) < 0.01

    def test_espp_detection(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {"espp_contribution": 500.00}
        suggestions = _build_suggestions(data)
        assert suggestions["benefits"]["has_espp"] is True

    def test_roth_401k_detection(self):
        from pipeline.importers.paystub import _build_suggestions

        data = {"retirement_roth_401k": 500.00}
        suggestions = _build_suggestions(data)
        assert suggestions["benefits"]["has_roth_401k"] is True

    def test_empty_data_returns_empty_suggestions(self):
        from pipeline.importers.paystub import _build_suggestions

        suggestions = _build_suggestions({})
        assert suggestions["household"] == {}
        assert suggestions["benefits"] == {}


class TestPaystubImportFlow:
    """Tests for import_paystub (async)."""

    @pytest.mark.asyncio
    async def test_file_not_found(self, session):
        from pipeline.importers.paystub import import_paystub

        result = await import_paystub(session, "/no/such/paystub.pdf")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_image_paystub_with_mocked_claude(self, session, tmp_path):
        from pipeline.importers.paystub import import_paystub

        # Create a fake image file
        img_path = str(tmp_path / "paystub.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # JPEG header

        mock_extracted = {
            "employer_name": "BigTech Inc",
            "annual_salary": 195000.00,
            "gross_pay": 7500.00,
            "net_pay": 5200.00,
            "federal_withholding": 1200.00,
            "state": "CA",
            "retirement_401k": 750.00,
            "employer_401k_match": 375.00,
            "hsa_contribution": 150.00,
            "health_premium": 250.00,
        }

        with patch(
            "pipeline.importers.paystub._extract_with_claude",
            new_callable=AsyncMock,
            return_value=mock_extracted,
        ):
            result = await import_paystub(session, img_path)

        assert result["status"] == "completed"
        assert result["extracted"]["employer_name"] == "BigTech Inc"
        assert result["extracted"]["annual_salary"] == 195000.00
        assert result["suggestions"]["household"]["income"] == 195000.00

    @pytest.mark.asyncio
    async def test_claude_extraction_failure(self, session, tmp_path):
        from pipeline.importers.paystub import import_paystub

        img_path = str(tmp_path / "bad_paystub.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 100)

        with patch(
            "pipeline.importers.paystub._extract_with_claude",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            result = await import_paystub(session, img_path)

        assert result["status"] == "error"
        assert "AI extraction failed" in result["message"]

    @pytest.mark.asyncio
    async def test_claude_returns_none(self, session, tmp_path):
        from pipeline.importers.paystub import import_paystub

        img_path = str(tmp_path / "unclear_paystub.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 100)

        with patch(
            "pipeline.importers.paystub._extract_with_claude",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await import_paystub(session, img_path)

        assert result["status"] == "error"
        assert "Could not extract" in result["message"]


# ---------------------------------------------------------------------------
#  6. TAX DOCUMENT IMPORTER
# ---------------------------------------------------------------------------

class TestTaxDocYearInference:
    """Tests for _infer_tax_year."""

    def test_year_from_filename(self):
        from pipeline.importers.tax_doc import _infer_tax_year

        assert _infer_tax_year("w2_2024.pdf", "") == 2024
        assert _infer_tax_year("1099-DIV_2025_fidelity.pdf", "") == 2025

    def test_year_from_document_text(self):
        from pipeline.importers.tax_doc import _infer_tax_year

        text = "This form is for calendar year 2024"
        assert _infer_tax_year("document.pdf", text) == 2024

    def test_year_from_text_w2_pattern(self):
        from pipeline.importers.tax_doc import _infer_tax_year

        text = "2025 W-2 Wage and Tax Statement"
        assert _infer_tax_year("generic.pdf", text) == 2025

    def test_year_from_text_tax_year_pattern(self):
        from pipeline.importers.tax_doc import _infer_tax_year

        text = "Tax Year 2023 Important Information"
        assert _infer_tax_year("doc.pdf", text) == 2023

    def test_default_to_previous_year(self):
        from pipeline.importers.tax_doc import _infer_tax_year

        now_year = datetime.now(timezone.utc).year
        assert _infer_tax_year("nodates.pdf", "no year info here") == now_year - 1

    def test_filename_takes_priority_over_text(self):
        from pipeline.importers.tax_doc import _infer_tax_year

        # Filename has 2025, text says 2024 -- filename wins
        assert _infer_tax_year("w2_2025.pdf", "calendar year 2024") == 2025


class TestTaxDocImportFlow:
    """Tests for import_pdf_file and import_image_file."""

    @pytest.mark.asyncio
    async def test_pdf_not_found(self, session):
        from pipeline.importers.tax_doc import import_pdf_file

        result = await import_pdf_file(session, "/nonexistent/w2.pdf")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_pdf_duplicate_detected(self, session, tmp_path):
        from pipeline.importers.tax_doc import import_pdf_file
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage

        pdf_path = str(tmp_path / "w2_2025.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 W-2 content")

        mock_doc = PDFDocument(
            filepath=pdf_path,
            pages=[PDFPage(page_num=1, text="W-2 Wage and Tax Statement 2025", tables=[])],
        )

        with patch("pipeline.importers.tax_doc.extract_pdf", return_value=mock_doc), \
             patch("pipeline.security.file_cleanup.clear_document_raw_text", new_callable=AsyncMock), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            r1 = await import_pdf_file(session, pdf_path, claude_fallback=False)

        assert r1["status"] == "completed"

        # Copy the file so it has the same hash but different path
        r2_path = str(tmp_path / "w2_2025_copy.pdf")
        with open(pdf_path, "rb") as src, open(r2_path, "wb") as dst:
            dst.write(src.read())

        with patch("pipeline.importers.tax_doc.extract_pdf", return_value=mock_doc):
            r2 = await import_pdf_file(session, r2_path)

        assert r2["status"] == "duplicate"

    @pytest.mark.asyncio
    async def test_pdf_import_no_claude(self, session, tmp_path):
        """Import a PDF without Claude fallback -- just creates document record."""
        from pipeline.importers.tax_doc import import_pdf_file
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage

        pdf_path = str(tmp_path / "1099div_2025.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 1099-DIV content")

        mock_doc = PDFDocument(
            filepath=pdf_path,
            pages=[PDFPage(page_num=1, text="1099-DIV Dividends 2025", tables=[])],
        )

        with patch("pipeline.importers.tax_doc.extract_pdf", return_value=mock_doc), \
             patch("pipeline.security.file_cleanup.clear_document_raw_text", new_callable=AsyncMock), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            result = await import_pdf_file(session, pdf_path, claude_fallback=False)

        assert result["status"] == "completed"
        assert result["document_id"] is not None
        assert result["form_type"] == "other"  # no Claude = no form detection
        assert result["tax_year"] == 2025

    @pytest.mark.asyncio
    async def test_pdf_import_with_claude_w2(self, session, tmp_path):
        """Full PDF import with mocked Claude extracting W-2 fields."""
        from pipeline.importers.tax_doc import import_pdf_file
        from pipeline.parsers.pdf_parser import PDFDocument, PDFPage

        pdf_path = str(tmp_path / "w2_acme_2025.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 mock W-2 content for hashing")

        w2_text = "W-2 Wage and Tax Statement\nEmployer: Acme Corp\nWages: $195,000\n2025"
        mock_doc = PDFDocument(
            filepath=pdf_path,
            pages=[PDFPage(page_num=1, text=w2_text, tables=[])],
        )

        claude_response = {
            "_form_type": "w2",
            "payer_name": "Acme Corp",
            "payer_ein": "12-3456789",
            "w2_wages": 195000.00,
            "w2_federal_tax_withheld": 35000.00,
            "w2_ss_wages": 168600.00,
            "w2_ss_tax_withheld": 10453.20,
            "w2_medicare_wages": 195000.00,
            "w2_medicare_tax_withheld": 2827.50,
            "w2_state": "CA",
            "w2_state_wages": 195000.00,
            "w2_state_income_tax": 15600.00,
        }

        with patch("pipeline.importers.tax_doc.extract_pdf", return_value=mock_doc), \
             patch("pipeline.importers.tax_doc.is_text_sparse", return_value=False), \
             patch("pipeline.ai.categorizer.extract_tax_fields_with_claude", new_callable=AsyncMock, return_value=claude_response), \
             patch("pipeline.security.file_cleanup.clear_document_raw_text", new_callable=AsyncMock), \
             patch("pipeline.security.audit.log_audit", new_callable=AsyncMock):
            result = await import_pdf_file(session, pdf_path, tax_year=2025, claude_fallback=True)

        assert result["status"] == "completed"
        assert result["form_type"] == "w2"
        assert result["tax_year"] == 2025
        assert result["fields_extracted"] >= 8

    @pytest.mark.asyncio
    async def test_image_not_found(self, session):
        from pipeline.importers.tax_doc import import_image_file

        result = await import_image_file(session, "/no/w2_photo.jpg")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_image_import_with_claude(self, session, tmp_path):
        from pipeline.importers.tax_doc import import_image_file

        img_path = str(tmp_path / "w2_photo_2024.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)

        claude_response = {
            "_form_type": "w2",
            "payer_name": "TechCorp",
            "w2_wages": 185000.00,
            "w2_federal_tax_withheld": 32000.00,
        }

        with patch(
            "pipeline.ai.categorizer.extract_tax_fields_with_claude",
            new_callable=AsyncMock,
            return_value=claude_response,
        ):
            result = await import_image_file(session, img_path, tax_year=2024)

        assert result["status"] == "completed"
        assert result["form_type"] == "w2"
        assert result["tax_year"] == 2024

    @pytest.mark.asyncio
    async def test_image_vision_extraction_failure(self, session, tmp_path):
        from pipeline.importers.tax_doc import import_image_file

        img_path = str(tmp_path / "bad_w2.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 200)

        with patch(
            "pipeline.ai.categorizer.extract_tax_fields_with_claude",
            new_callable=AsyncMock,
            side_effect=Exception("Vision API failed"),
        ):
            result = await import_image_file(session, img_path)

        assert result["status"] == "error"
        assert "Vision extraction failed" in result["message"]


class TestTaxDocTaxItemColumns:
    """Test that _TAXITEM_COLUMNS covers known form types."""

    def test_w2_columns_present(self):
        from pipeline.importers.tax_doc import _TAXITEM_COLUMNS

        w2_fields = [
            "w2_wages", "w2_federal_tax_withheld", "w2_ss_wages",
            "w2_ss_tax_withheld", "w2_medicare_wages", "w2_medicare_tax_withheld",
            "w2_state", "w2_state_wages", "w2_state_income_tax",
        ]
        for f in w2_fields:
            assert f in _TAXITEM_COLUMNS

    def test_1099_nec_columns_present(self):
        from pipeline.importers.tax_doc import _TAXITEM_COLUMNS

        assert "nec_nonemployee_compensation" in _TAXITEM_COLUMNS
        assert "nec_federal_tax_withheld" in _TAXITEM_COLUMNS

    def test_1099_div_columns_present(self):
        from pipeline.importers.tax_doc import _TAXITEM_COLUMNS

        assert "div_total_ordinary" in _TAXITEM_COLUMNS
        assert "div_qualified" in _TAXITEM_COLUMNS

    def test_k1_columns_present(self):
        from pipeline.importers.tax_doc import _TAXITEM_COLUMNS

        k1_fields = [
            "k1_ordinary_income", "k1_rental_income", "k1_guaranteed_payments",
            "k1_interest_income", "k1_dividends", "k1_qualified_dividends",
        ]
        for f in k1_fields:
            assert f in _TAXITEM_COLUMNS

    def test_1098_columns_present(self):
        from pipeline.importers.tax_doc import _TAXITEM_COLUMNS

        assert "m_mortgage_interest" in _TAXITEM_COLUMNS
        assert "m_points_paid" in _TAXITEM_COLUMNS
        assert "m_property_tax" in _TAXITEM_COLUMNS


# ---------------------------------------------------------------------------
#  7. INSURANCE DOCUMENT IMPORTER
# ---------------------------------------------------------------------------

class TestInsuranceDocToFloat:
    """Tests for _to_float helper in insurance_doc.py."""

    def test_float_value(self):
        from pipeline.importers.insurance_doc import _to_float

        assert _to_float(500000.00) == 500000.00

    def test_string_value(self):
        from pipeline.importers.insurance_doc import _to_float

        assert _to_float("1500.50") == 1500.50

    def test_none_returns_none(self):
        from pipeline.importers.insurance_doc import _to_float

        assert _to_float(None) is None

    def test_invalid_string_returns_none(self):
        from pipeline.importers.insurance_doc import _to_float

        assert _to_float("not-a-number") is None

    def test_int_value(self):
        from pipeline.importers.insurance_doc import _to_float

        assert _to_float(1000) == 1000.0


class TestInsuranceDocImportFlow:
    """Tests for import_insurance_doc."""

    @pytest.mark.asyncio
    async def test_file_not_found(self, session):
        from pipeline.importers.insurance_doc import import_insurance_doc

        result = await import_insurance_doc(session, "/nonexistent/policy.pdf")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_image_insurance_doc(self, session, tmp_path):
        from pipeline.importers.insurance_doc import import_insurance_doc

        img_path = str(tmp_path / "auto_insurance.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_extracted = {
            "provider": "State Farm",
            "policy_number": "POL-12345",
            "policy_type": "auto",
            "coverage_amount": 300000.00,
            "deductible": 500.00,
            "annual_premium": 1800.00,
            "monthly_premium": 150.00,
            "renewal_date": "2026-06-15",
            "named_insured": "John Smith",
            "vehicle_info": "2022 Toyota Camry",
            "employer_provided": False,
        }

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            return_value=mock_extracted,
        ):
            result = await import_insurance_doc(session, img_path, household_id=1)

        assert result["status"] == "completed"
        assert result["policy_id"] is not None
        assert result["document_id"] is not None
        assert result["extracted_fields"]["provider"] == "State Farm"
        assert result["extracted_fields"]["policy_type"] == "auto"

    @pytest.mark.asyncio
    async def test_claude_extraction_failure(self, session, tmp_path):
        from pipeline.importers.insurance_doc import import_insurance_doc

        img_path = str(tmp_path / "bad_doc.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 100)

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            result = await import_insurance_doc(session, img_path)

        assert result["status"] == "error"
        assert "AI extraction failed" in result["message"]

    @pytest.mark.asyncio
    async def test_claude_returns_none(self, session, tmp_path):
        from pipeline.importers.insurance_doc import import_insurance_doc

        img_path = str(tmp_path / "unclear_doc.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 100)

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await import_insurance_doc(session, img_path)

        assert result["status"] == "error"
        assert "Could not extract" in result["message"]

    @pytest.mark.asyncio
    async def test_home_insurance_with_address(self, session, tmp_path):
        from pipeline.importers.insurance_doc import import_insurance_doc

        img_path = str(tmp_path / "home_policy.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_extracted = {
            "provider": "Allstate",
            "policy_number": "HOME-99999",
            "policy_type": "home",
            "coverage_amount": 750000.00,
            "deductible": 2500.00,
            "annual_premium": 3600.00,
            "monthly_premium": 300.00,
            "renewal_date": "2026-12-01",
            "property_address": "456 Oak Ave, San Francisco, CA 94102",
            "employer_provided": False,
        }

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            return_value=mock_extracted,
        ):
            result = await import_insurance_doc(session, img_path)

        assert result["status"] == "completed"
        assert "home" in result["message"]

    @pytest.mark.asyncio
    async def test_duplicate_policy_updates_existing(self, session, tmp_path):
        """If policy_number already exists, update rather than create new."""
        from pipeline.importers.insurance_doc import import_insurance_doc

        # First import
        img1 = str(tmp_path / "policy_v1.jpg")
        with open(img1, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        extracted_v1 = {
            "provider": "GEICO",
            "policy_number": "GEICO-55555",
            "policy_type": "auto",
            "coverage_amount": 250000.00,
            "deductible": 500.00,
            "annual_premium": 1200.00,
            "monthly_premium": 100.00,
            "employer_provided": False,
        }

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            return_value=extracted_v1,
        ):
            r1 = await import_insurance_doc(session, img1)

        assert r1["status"] == "completed"
        original_policy_id = r1["policy_id"]

        # Second import with same policy number but updated premium
        img2 = str(tmp_path / "policy_v2.jpg")
        with open(img2, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x01" * 100)  # different content

        extracted_v2 = {
            "provider": "GEICO",
            "policy_number": "GEICO-55555",  # same policy number
            "policy_type": "auto",
            "coverage_amount": 300000.00,  # increased
            "deductible": 500.00,
            "annual_premium": 1400.00,  # increased
            "monthly_premium": 116.67,
            "employer_provided": False,
        }

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            return_value=extracted_v2,
        ):
            r2 = await import_insurance_doc(session, img2)

        assert r2["status"] == "updated"
        assert r2["policy_id"] == original_policy_id

    @pytest.mark.asyncio
    async def test_insurance_with_invalid_renewal_date(self, session, tmp_path):
        from pipeline.importers.insurance_doc import import_insurance_doc

        img_path = str(tmp_path / "bad_date_policy.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_extracted = {
            "provider": "Progressive",
            "policy_number": "PROG-77777",
            "policy_type": "auto",
            "coverage_amount": 200000.00,
            "deductible": 1000.00,
            "annual_premium": 900.00,
            "renewal_date": "not-a-valid-date",
            "employer_provided": False,
        }

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            return_value=mock_extracted,
        ):
            result = await import_insurance_doc(session, img_path)

        # Should still succeed -- bad date is just ignored
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_life_insurance_employer_provided(self, session, tmp_path):
        from pipeline.importers.insurance_doc import import_insurance_doc

        img_path = str(tmp_path / "life_insurance.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 100)

        mock_extracted = {
            "provider": "MetLife",
            "policy_number": "LIFE-11111",
            "policy_type": "life",
            "coverage_amount": 500000.00,
            "annual_premium": 0.00,  # employer-paid
            "employer_provided": True,
        }

        with patch(
            "pipeline.importers.insurance_doc._extract_with_claude",
            new_callable=AsyncMock,
            return_value=mock_extracted,
        ):
            result = await import_insurance_doc(session, img_path)

        assert result["status"] == "completed"
        assert result["extracted_fields"]["employer_provided"] is True


# ---------------------------------------------------------------------------
#  CROSS-CUTTING: Amazon transaction matching
# ---------------------------------------------------------------------------

class TestAmazonDescriptionFilter:
    """Tests for the Amazon description matching patterns."""

    def test_amazon_patterns(self):
        from pipeline.importers.amazon import AMAZON_DESCRIPTION_PATTERNS

        assert len(AMAZON_DESCRIPTION_PATTERNS) > 0
        patterns = [p.strip("%") for p in AMAZON_DESCRIPTION_PATTERNS]
        assert "amazon" in patterns
        assert "amzn" in patterns


# ---------------------------------------------------------------------------
#  CROSS-CUTTING: Monarch helpers
# ---------------------------------------------------------------------------

class TestMonarchParseAccountParts:
    """Test _parse_account_parts."""

    def test_simple_name(self):
        from pipeline.importers.monarch import _parse_account_parts

        inst, name = _parse_account_parts("Chase Sapphire ****4321")
        assert name == "Chase Sapphire ****4321"

    def test_whitespace_stripped(self):
        from pipeline.importers.monarch import _parse_account_parts

        inst, name = _parse_account_parts("  Amex Gold  ")
        assert name == "Amex Gold"
