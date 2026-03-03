"""
Amazon Order History CSV importer.

How to get your Amazon order history:
1. Go to: https://www.amazon.com/cpc/amazon-gdpr/privacy-center
2. Request a copy of your data -- download the ZIP
3. Unzip into data/imports/amazon/<Name> Amazon Orders/
4. Drop the ZIP or extracted folders there

Supported file types (pass --type to select):
  retail   -- Your Amazon Orders/Order History.csv  (default)
  digital  -- Your Amazon Orders/Digital Content Orders.csv
  refund   -- Your Returns & Refunds/Refund Details.csv

Matching strategy:
  Retail orders are parsed at the SHIPMENT level (not order level) because
  Amazon charges the credit card per-shipment. Multi-shipment orders produce
  multiple amazon_orders rows with synthetic IDs: "{order_id}-S{n}".
  parent_order_id always stores the original Amazon Order ID.

  Matching uses date +/-5 days and amount +/-$5.00 against CC transactions
  whose description matches known Amazon patterns.

Usage:
    python -m pipeline.importers.amazon --file "..." --owner Mike
    python -m pipeline.importers.amazon --file "..." --owner Christine --type digital
    python -m pipeline.importers.amazon --file "..." --owner Mike --type refund
"""
import argparse
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import (
    AmazonOrder, Transaction,
    create_document, get_document_by_hash, update_document_status,
)
from pipeline.utils import file_hash, to_float, create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed/amazon")

MATCH_TOLERANCE_DAYS = 5
MATCH_TOLERANCE_AMOUNT = 5.0

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_amazon_csv(filepath: str) -> list[dict]:
    """
    Parse Amazon retail Order History CSV at SHIPMENT granularity.

    Amazon charges the CC per-shipment, not per-order. Items sharing the same
    (Order ID, Shipment Item Subtotal) belong to the same shipment and produce
    one CC charge equal to SUM(Total Amount) for those rows.

    Single-shipment orders keep the original order_id.
    Multi-shipment orders get synthetic IDs: "{order_id}-S1", "-S2", etc.
    parent_order_id always stores the raw Amazon Order ID.

    Handles both:
      - Current "Your Account" export (Shipment Item Subtotal / Total Amount)
      - Legacy privacy export (Item Total / Total Charged)
    """
    df = pd.read_csv(filepath, dtype=str, skip_blank_lines=True)
    df.columns = [c.strip() for c in df.columns]

    if "Order ID" not in df.columns:
        raise ValueError(f"Unknown Amazon CSV format. Columns: {list(df.columns)}")

    order_id_col = "Order ID"
    date_col = "Order Date"
    item_col = "Title" if "Title" in df.columns else "Product Name"

    has_shipment_info = "Shipment Item Subtotal" in df.columns

    if has_shipment_info:
        price_col = "Shipment Item Subtotal"
        line_total_col = "Total Amount"
        qty_col = "Original Quantity"
        payment_col = "Payment Method Type"
    elif "Item Total" in df.columns:
        price_col = "Item Total"
        line_total_col = "Item Total"
        qty_col = "Quantity"
        payment_col = None
    else:
        raise ValueError(f"Unknown Amazon CSV format. Columns: {list(df.columns)}")

    # First pass: collect rows grouped by (order_id, shipment_subtotal)
    # shipment_subtotal acts as the shipment grouping key
    shipments: dict[tuple[str, str], dict] = {}
    order_dates: dict[str, datetime] = {}
    order_payments: dict[str, str | None] = {}

    for _, row in df.iterrows():
        oid = str(row.get(order_id_col, "")).strip()
        if not oid or oid == "nan":
            continue

        try:
            order_date = pd.to_datetime(str(row[date_col]).strip()).to_pydatetime()
        except Exception:
            continue

        item_title = str(row.get(item_col, "")).strip()
        shipment_subtotal = str(row.get(price_col, "0")).strip()
        line_total = to_float(row.get(line_total_col, "0"))
        qty = 1
        if qty_col:
            raw_qty = row.get(qty_col)
            if raw_qty and str(raw_qty) not in ("", "nan", "Not Applicable"):
                try:
                    qty = int(float(str(raw_qty)))
                except (ValueError, TypeError):
                    qty = 1

        # Shipment grouping key
        if has_shipment_info:
            key = (oid, shipment_subtotal)
        else:
            key = (oid, "ALL")

        if key not in shipments:
            shipments[key] = {
                "items": [],
                "total_charged": 0.0,
            }
        shipments[key]["total_charged"] += line_total
        shipments[key]["items"].append({
            "title": item_title,
            "quantity": qty,
            "price": to_float(shipment_subtotal),
        })

        if oid not in order_dates:
            order_dates[oid] = order_date
        if oid not in order_payments and payment_col:
            pm = str(row.get(payment_col, "")).strip()
            if pm and pm not in ("nan", "Not Available", "Not Applicable"):
                order_payments[oid] = pm

    # Second pass: group shipments by order_id to decide naming
    from collections import defaultdict
    order_shipments: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for (oid, subtotal_key), shipment in shipments.items():
        order_shipments[oid].append((subtotal_key, shipment))

    result = []
    for oid, ship_list in order_shipments.items():
        is_multi = len(ship_list) > 1 and has_shipment_info

        for idx, (subtotal_key, shipment) in enumerate(ship_list, start=1):
            if is_multi:
                record_id = f"{oid}-S{idx}"
            else:
                record_id = oid

            total = round(shipment["total_charged"], 2)
            items = shipment["items"]

            items_desc = " | ".join(
                f"{i['title']} (x{i['quantity']})" if i["quantity"] > 1 else i["title"]
                for i in items[:5]
            )
            if len(items) > 5:
                items_desc += f" + {len(items) - 5} more items"

            result.append({
                "order_id": record_id,
                "parent_order_id": oid,
                "order_date": order_dates[oid],
                "items_description": items_desc,
                "total_charged": total,
                "payment_method_last4": order_payments.get(oid),
                "raw_items": json.dumps(items[:20]),
                "is_digital": False,
                "is_refund": False,
            })

    return result


def parse_digital_content_csv(filepath: str) -> list[dict]:
    """
    Parse Amazon Digital Content Orders CSV.

    One row per price component (Component Type = "Price Amount" or "Tax").
    Sum Transaction Amount per Order ID to get the total charged.
    """
    df = pd.read_csv(filepath, dtype=str, skip_blank_lines=True)
    df.columns = [c.strip() for c in df.columns]

    required = {"Order ID", "Order Date", "Product Name", "Transaction Amount"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Digital Content Orders CSV missing columns: {missing}")

    orders: dict[str, dict] = {}

    for _, row in df.iterrows():
        order_id = str(row.get("Order ID", "")).strip()
        if not order_id or order_id in ("nan", "Not Applicable"):
            continue

        try:
            order_date = pd.to_datetime(str(row["Order Date"]).strip()).to_pydatetime()
        except Exception:
            continue

        txn_amount = to_float(row.get("Transaction Amount", "0"))
        product_name = str(row.get("Product Name", "")).strip()
        qty = 1
        raw_qty = row.get("Quantity Ordered") or row.get("Original Quantity")
        if raw_qty and str(raw_qty) not in ("", "nan", "Not Applicable"):
            try:
                qty = int(float(str(raw_qty)))
            except (ValueError, TypeError):
                qty = 1

        if order_id not in orders:
            orders[order_id] = {
                "order_id": order_id,
                "order_date": order_date,
                "total_charged": 0.0,
                "payment_method_last4": None,
                "items": [],
                "_titles_seen": set(),
            }

        orders[order_id]["total_charged"] += txn_amount

        if product_name and product_name not in orders[order_id]["_titles_seen"]:
            orders[order_id]["_titles_seen"].add(product_name)
            orders[order_id]["items"].append({
                "title": product_name,
                "quantity": qty,
                "price": txn_amount,
            })

    result = []
    for order_id, order in orders.items():
        total = round(order["total_charged"], 2)
        if total == 0.0:
            continue

        items = order["items"]
        items_desc = " | ".join(
            f"{i['title']} (x{i['quantity']})" if i["quantity"] > 1 else i["title"]
            for i in items[:5]
        )
        if len(items) > 5:
            items_desc += f" + {len(items) - 5} more items"

        result.append({
            "order_id": order_id,
            "parent_order_id": order_id,
            "order_date": order["order_date"],
            "items_description": items_desc,
            "total_charged": total,
            "payment_method_last4": None,
            "raw_items": json.dumps(items[:20]),
            "is_digital": True,
            "is_refund": False,
        })

    return result


def parse_refund_csv(filepath: str) -> list[dict]:
    """
    Parse Amazon Refund Details CSV.

    Each row is one refund. Synthetic order_id: "<order_id>-REFUND-<n>".
    total_charged is negative (credit on card).
    """
    df = pd.read_csv(filepath, dtype=str, skip_blank_lines=True)
    df.columns = [c.strip() for c in df.columns]

    required = {"Order ID", "Refund Amount", "Refund Date"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Refund Details CSV missing columns: {missing}")

    refunds = []
    order_refund_counts: dict[str, int] = {}

    for _, row in df.iterrows():
        order_id = str(row.get("Order ID", "")).strip()
        if not order_id or order_id in ("nan", "Not Applicable"):
            continue

        refund_amount = to_float(row.get("Refund Amount", "0"))
        if refund_amount == 0.0:
            continue

        try:
            refund_date = pd.to_datetime(str(row["Refund Date"]).strip()).to_pydatetime()
        except Exception:
            try:
                refund_date = pd.to_datetime(str(row.get("Creation Date", "")).strip()).to_pydatetime()
            except Exception:
                continue

        order_refund_counts[order_id] = order_refund_counts.get(order_id, 0) + 1
        n = order_refund_counts[order_id]
        synthetic_id = f"{order_id}-REFUND-{n}" if n > 1 else f"{order_id}-REFUND"

        reason = str(row.get("Reversal Reason", "")).strip()
        if reason in ("nan", "Not Applicable", ""):
            reason = "Refund"

        refunds.append({
            "order_id": synthetic_id,
            "parent_order_id": order_id,
            "order_date": refund_date,
            "items_description": f"Refund for order {order_id}: {reason}",
            "total_charged": -abs(refund_amount),
            "payment_method_last4": None,
            "raw_items": json.dumps([{"title": f"Refund: {reason}", "quantity": 1, "price": -refund_amount}]),
            "is_digital": False,
            "is_refund": True,
        })

    return refunds


# ---------------------------------------------------------------------------
# AI Categorization
# ---------------------------------------------------------------------------

async def _categorize_amazon_orders_with_claude(orders: list[dict]) -> dict[str, dict]:
    """
    Use Claude to suggest categories for Amazon orders based on item descriptions.
    Returns {order_id: {category, segment, is_business, is_gift}}.
    """
    import anthropic
    from pipeline.ai.categories import AMAZON_CATEGORIES
    from pipeline.utils import CLAUDE_MODEL, strip_json_fences
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    order_list = [
        {"order_id": o["order_id"], "items": o["items_description"], "total": o["total_charged"]}
        for o in orders
    ]

    categories = AMAZON_CATEGORIES

    prompt = f"""You are categorizing Amazon orders for a family's financial tracking.

Household context:
- Primary earner works at Accenture (consulting) -- any tech, books, or office items may be business
- Wife sits on corporate boards -- any professional/business books or supplies may be deductible
- Family has children -- toys, baby items, school supplies are personal
- High Amazon usage includes household staples, electronics, clothing

For each order, determine:
1. category: pick the best from the list
2. segment: "personal" or "business"
3. is_business: true if likely a deductible business expense
4. is_gift: true if it appears to be a gift purchase

Category options: {json.dumps(categories)}

Return a JSON array with one object per order:
{{"order_id": "...", "category": "...", "segment": "personal|business", "is_business": bool, "is_gift": bool}}

Return ONLY the JSON array.

Orders:
{json.dumps(order_list, indent=2)}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = strip_json_fences(response.content[0].text)

    results_list: list[dict] = json.loads(raw)
    return {r["order_id"]: r for r in results_list}


# ---------------------------------------------------------------------------
# Transaction Matching
# ---------------------------------------------------------------------------

AMAZON_DESCRIPTION_PATTERNS = [
    "%amazon%", "%amzn%", "%amzn mktp%", "%amzn digital%",
    "%amazon.com%", "%amazon prime%", "%prime video%",
    "%whole foods%", "%amazon fresh%", "%amazon tip%",
]


def _amazon_description_filter():
    """Build an OR filter matching all known Amazon-related transaction descriptions."""
    from sqlalchemy import or_
    return or_(*(Transaction.description.ilike(p) for p in AMAZON_DESCRIPTION_PATTERNS))


async def _match_to_transactions(
    session: AsyncSession,
    order: dict,
    tolerance_days: int = MATCH_TOLERANCE_DAYS,
    amount_tolerance: float = MATCH_TOLERANCE_AMOUNT,
) -> int | None:
    """
    Try to match an Amazon shipment (or refund) to an existing CC transaction.

    Uses date +/-tolerance_days AND amount +/-amount_tolerance.
    Prefers unmatched transactions; skips already-claimed ones.
    Returns transaction.id or None.
    """
    start = order["order_date"] - timedelta(days=tolerance_days)
    end = order["order_date"] + timedelta(days=tolerance_days)

    if order.get("is_refund"):
        target_amount = abs(order["total_charged"])
    else:
        target_amount = -order["total_charged"]

    already_matched = select(AmazonOrder.matched_transaction_id).where(
        AmazonOrder.matched_transaction_id.isnot(None)
    ).scalar_subquery()

    result = await session.execute(
        select(Transaction).where(
            Transaction.date >= start,
            Transaction.date <= end,
            _amazon_description_filter(),
            Transaction.amount >= target_amount - amount_tolerance,
            Transaction.amount <= target_amount + amount_tolerance,
            Transaction.id.notin_(already_matched),
        ).order_by(
            func.abs(func.julianday(Transaction.date) - func.julianday(order["order_date"]))
        ).limit(1)
    )
    tx = result.scalar_one_or_none()
    return tx.id if tx else None


# ---------------------------------------------------------------------------
# Import entry point
# ---------------------------------------------------------------------------

async def import_amazon_csv(
    session: AsyncSession,
    filepath: str,
    owner: str | None = None,
    file_type: str = "retail",
    run_categorize: bool = True,
    category_map: dict[str, dict] | None = None,
) -> dict:
    """
    Import an Amazon data file into the amazon_orders table.

    Args:
        filepath: Path to the CSV file.
        owner: "Mike" or "Christine" -- tags orders with the account holder.
        file_type: "retail" | "digital" | "refund"
        run_categorize: Whether to call Claude for AI categorization.
        category_map: Pre-computed {parent_order_id: {category, segment, ...}}
                      used during migration to skip re-calling Claude.
    """
    path = Path(filepath)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {filepath}"}

    fhash = file_hash(filepath)
    existing = await get_document_by_hash(session, fhash)
    if existing:
        return {"status": "duplicate", "message": f"Already imported as document #{existing.id}"}

    doc_type_map = {
        "retail": "amazon_orders",
        "digital": "amazon_digital_orders",
        "refund": "amazon_refunds",
    }
    doc = await create_document(session, {
        "filename": path.name,
        "original_path": str(path.resolve()),
        "file_type": "csv",
        "document_type": doc_type_map.get(file_type, "amazon_orders"),
        "status": "processing",
        "file_hash": fhash,
        "file_size_bytes": path.stat().st_size,
    })

    try:
        if file_type == "digital":
            orders = parse_digital_content_csv(filepath)
        elif file_type == "refund":
            orders = parse_refund_csv(filepath)
        else:
            orders = parse_amazon_csv(filepath)
    except (ValueError, Exception) as e:
        await update_document_status(session, doc.id, "failed", error_message=str(e))
        return {"status": "error", "message": str(e)}

    logger.info(f"Parsed {len(orders)} Amazon records from {path.name} (type={file_type}, owner={owner})")

    # Resolve categories: use pre-computed map, call Claude, or leave blank
    categorizations: dict[str, dict] = {}
    if category_map:
        for order in orders:
            parent = order.get("parent_order_id", order["order_id"])
            if parent in category_map:
                categorizations[order["order_id"]] = category_map[parent]
    elif run_categorize and orders and file_type == "retail":
        batch_size = 30
        for i in range(0, len(orders), batch_size):
            batch = orders[i: i + batch_size]
            try:
                cats = await _categorize_amazon_orders_with_claude(batch)
                categorizations.update(cats)
            except Exception as e:
                logger.warning(f"Claude categorization batch {i // batch_size + 1} failed: {e}")

    inserted = 0
    matched = 0

    for order in orders:
        existing_order = await session.execute(
            select(AmazonOrder).where(AmazonOrder.order_id == order["order_id"])
        )
        if existing_order.scalar_one_or_none():
            continue

        cat_info = categorizations.get(order["order_id"], {})
        matched_tx_id = await _match_to_transactions(session, order)
        if matched_tx_id:
            matched += 1

        ao = AmazonOrder(
            order_id=order["order_id"],
            parent_order_id=order.get("parent_order_id", order["order_id"]),
            order_date=order["order_date"],
            items_description=order["items_description"],
            total_charged=order["total_charged"],
            suggested_category=cat_info.get("category"),
            effective_category=cat_info.get("category"),
            segment=cat_info.get("segment", "personal"),
            is_business=cat_info.get("is_business", False),
            is_gift=cat_info.get("is_gift", False),
            is_digital=order.get("is_digital", False),
            is_refund=order.get("is_refund", False),
            owner=owner,
            payment_method_last4=order.get("payment_method_last4"),
            matched_transaction_id=matched_tx_id,
            raw_items=order["raw_items"],
            source_document_id=doc.id,
        )
        session.add(ao)
        inserted += 1

    await session.flush()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"
    await update_document_status(session, doc.id, "completed", processed_path=str(dest))

    logger.info(f"Inserted {inserted} Amazon records, matched {matched} to credit card transactions.")
    return {
        "status": "completed",
        "document_id": doc.id,
        "orders_imported": inserted,
        "transactions_matched": matched,
        "message": f"Imported {inserted} {file_type} records, matched {matched} to card transactions.",
        "_archive_src": str(filepath),
        "_archive_dest": str(dest),
    }


# ---------------------------------------------------------------------------
# Auto-match (called after any CC import)
# ---------------------------------------------------------------------------

async def auto_match_amazon_orders(
    session: AsyncSession,
    propagate_categories: bool = True,
) -> dict:
    """
    Called after any transaction import (Monarch, CC, Plaid) to match unmatched
    Amazon orders against newly-available transactions and optionally push the
    item-level Amazon category onto the matched credit card transaction.

    Returns {"matched": int, "categories_propagated": int}.
    """
    unmatched = (await session.execute(
        select(AmazonOrder).where(AmazonOrder.matched_transaction_id.is_(None))
    )).scalars().all()

    if not unmatched:
        return {"matched": 0, "categories_propagated": 0}

    already_matched_subq = select(AmazonOrder.matched_transaction_id).where(
        AmazonOrder.matched_transaction_id.isnot(None)
    ).scalar_subquery()

    matched = 0
    propagated = 0

    for order in unmatched:
        start = order.order_date - timedelta(days=MATCH_TOLERANCE_DAYS)
        end = order.order_date + timedelta(days=MATCH_TOLERANCE_DAYS)

        if order.is_refund:
            target_amount = abs(order.total_charged)
        else:
            target_amount = -order.total_charged

        result = await session.execute(
            select(Transaction).where(
                Transaction.date >= start,
                Transaction.date <= end,
                _amazon_description_filter(),
                Transaction.amount >= target_amount - MATCH_TOLERANCE_AMOUNT,
                Transaction.amount <= target_amount + MATCH_TOLERANCE_AMOUNT,
                Transaction.id.notin_(already_matched_subq),
            ).order_by(
                func.abs(func.julianday(Transaction.date) - func.julianday(order.order_date))
            ).limit(1)
        )
        tx = result.scalar_one_or_none()
        if not tx:
            continue

        order.matched_transaction_id = tx.id
        matched += 1

        if propagate_categories and order.effective_category and not tx.is_manually_reviewed:
            tx.effective_category = order.effective_category
            tx.category = order.effective_category
            if order.segment:
                tx.effective_segment = order.segment
                tx.segment = order.segment
            propagated += 1

    if matched:
        await session.flush()

    logger.info(f"Amazon auto-match: {matched} matched, {propagated} categories propagated")
    return {"matched": matched, "categories_propagated": propagated}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def _main():
    parser = argparse.ArgumentParser(description="Import Amazon order history CSV")
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument(
        "--owner", default=None,
        help='Account holder name, e.g. "Mike" or "Christine"',
    )
    parser.add_argument(
        "--type", dest="file_type", default="retail",
        choices=["retail", "digital", "refund"],
        help="Type of Amazon CSV: retail (default), digital, or refund",
    )
    parser.add_argument("--no-claude", action="store_true", help="Skip AI categorization")
    args = parser.parse_args()

    engine, Session = create_engine_and_session()
    from pipeline.db import init_db, init_extended_db
    await init_db(engine)
    await init_extended_db()

    async with Session() as session:
        async with session.begin():
            result = await import_amazon_csv(
                session,
                args.file,
                owner=args.owner,
                file_type=args.file_type,
                run_categorize=not args.no_claude,
            )

        src, dst = result.pop("_archive_src", None), result.pop("_archive_dest", None)
        if src and dst:
            shutil.copy2(src, dst)

        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
