"""
One-time migration: re-import Amazon retail orders at SHIPMENT level.

Previously orders were grouped by Order ID (one row per order). Now they're
grouped by (Order ID, Shipment Item Subtotal) so each CC charge gets its own
row. This dramatically improves match rates for multi-shipment orders.

Strategy:
  1. Read existing amazon_orders to save Claude category assignments
     (keyed by parent_order_id / order_id -> {category, segment, ...})
  2. Delete existing retail order rows + their document records
  3. Re-import both Mike and Christine at shipment level, using saved categories
  4. Re-import digital + refund files (these are unaffected but need doc re-creation)
  5. Run rematch + fix-cats

Usage:
    python scripts/migrate_shipment_level.py
    python scripts/migrate_shipment_level.py --dry-run   (show plan without changes)
"""
import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select, text
from pipeline.db import init_db, init_extended_db, AmazonOrder, Document
from pipeline.importers.amazon import import_amazon_csv
from pipeline.utils import create_engine_and_session

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE = Path("data/imports/amazon")

FILES = [
    {"owner": "Mike",      "type": "retail",  "path": BASE / "Mike Aron Amazon Orders/Your Amazon Orders/Order History.csv"},
    {"owner": "Christine", "type": "retail",  "path": BASE / "Christine Aron Amazon Orders/Your Amazon Orders/Order History.csv"},
    {"owner": "Mike",      "type": "digital", "path": BASE / "Mike Aron Amazon Orders/Your Amazon Orders/Digital Content Orders.csv"},
    {"owner": "Christine", "type": "digital", "path": BASE / "Christine Aron Amazon Orders/Your Amazon Orders/Digital Content Orders.csv"},
    {"owner": "Mike",      "type": "refund",  "path": BASE / "Mike Aron Amazon Orders/Your Returns & Refunds/Refund Details.csv"},
    {"owner": "Christine", "type": "refund",  "path": BASE / "Christine Aron Amazon Orders/Your Returns & Refunds/Refund Details.csv"},
]


async def run(dry_run: bool = False):
    engine, Session = create_engine_and_session()
    await init_db(engine)
    await init_extended_db()

    # --- Step 1: Save existing categories ---
    logger.info("Step 1: Saving existing Claude categorizations...")
    category_map: dict[str, dict] = {}

    async with Session() as session:
        all_orders = (await session.execute(
            select(AmazonOrder).where(AmazonOrder.effective_category.isnot(None))
        )).scalars().all()

        for ao in all_orders:
            key = ao.parent_order_id or ao.order_id
            # Strip -S1, -S2, -REFUND suffixes to get the parent order ID
            for suffix in ("-REFUND", "-S"):
                if suffix in key:
                    key = key.split(suffix)[0]
                    break
            if ao.effective_category and ao.effective_category != "Unknown":
                category_map[key] = {
                    "category": ao.effective_category,
                    "segment": ao.segment,
                    "is_business": ao.is_business,
                    "is_gift": ao.is_gift,
                }

    logger.info(f"  Saved {len(category_map)} order categorizations")

    if dry_run:
        logger.info("[DRY RUN] Would delete all amazon_orders and document records, then re-import.")
        logger.info(f"  Category map has {len(category_map)} entries to reuse")
        for f in FILES:
            exists = f["path"].exists()
            logger.info(f"  {f['owner']:12} {f['type']:8} {'EXISTS' if exists else 'MISSING'}  {f['path'].name}")
        return

    # --- Step 2: Delete all existing amazon_orders + document records ---
    logger.info("Step 2: Deleting existing amazon_orders and document records...")

    async with Session() as session:
        async with session.begin():
            # Get document IDs linked to amazon orders
            doc_ids = (await session.execute(
                select(AmazonOrder.source_document_id).where(
                    AmazonOrder.source_document_id.isnot(None)
                ).distinct()
            )).scalars().all()

            deleted_orders = (await session.execute(
                delete(AmazonOrder)
            )).rowcount

            deleted_docs = 0
            for did in doc_ids:
                await session.execute(delete(Document).where(Document.id == did))
                deleted_docs += 1

    logger.info(f"  Deleted {deleted_orders} amazon_order rows, {deleted_docs} document records")

    # --- Step 3: Re-import all files at shipment level ---
    logger.info("Step 3: Re-importing at shipment level...")

    for f in FILES:
        if not f["path"].exists():
            logger.warning(f"  SKIP {f['owner']} {f['type']}: {f['path']} not found")
            continue

        use_cats = category_map if f["type"] == "retail" else None

        async with Session() as session:
            async with session.begin():
                result = await import_amazon_csv(
                    session,
                    str(f["path"]),
                    owner=f["owner"],
                    file_type=f["type"],
                    run_categorize=False,
                    category_map=use_cats,
                )

            src = result.pop("_archive_src", None)
            dst = result.pop("_archive_dest", None)
            if src and dst and result["status"] == "completed":
                shutil.copy2(src, dst)

        logger.info(f"  {f['owner']:12} {f['type']:8} -> {result.get('message', result.get('status'))}")

    # --- Step 4: Summary ---
    logger.info("\nMigration complete. Next steps:")
    logger.info("  python scripts/amazon_reconciliation.py --rematch")
    logger.info("  python scripts/amazon_reconciliation.py --fix-cats --year 2024")
    logger.info("  python scripts/amazon_reconciliation.py --fix-cats --year 2025")
    logger.info("  python scripts/amazon_reconciliation.py --fix-cats --year 2026")
    logger.info("  python scripts/amazon_reconciliation.py")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Migrate Amazon data to shipment-level matching")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
