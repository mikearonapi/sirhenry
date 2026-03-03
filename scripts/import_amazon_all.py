"""
Bulk Amazon data importer — imports all known Amazon export files for all
account holders in one shot.

File layout expected under data/imports/amazon/:
  <Name> Amazon Orders/
    Your Amazon Orders/
      Order History.csv           (retail orders)
      Digital Content Orders.csv  (Kindle, Prime Video, etc.)
    Your Returns & Refunds/
      Refund Details.csv          (refunds)

Accounts configured in ACCOUNTS below. Add or remove as needed.

Usage:
    python scripts/import_amazon_all.py
    python scripts/import_amazon_all.py --no-claude
    python scripts/import_amazon_all.py --skip-digital --skip-refunds
    python scripts/import_amazon_all.py --owner Mike   (single account only)

After importing, run reconciliation:
    python scripts/amazon_reconciliation.py --rematch
    python scripts/amazon_reconciliation.py --fix-cats --year 2024
    python scripts/amazon_reconciliation.py --fix-cats --year 2025
    python scripts/amazon_reconciliation.py --fix-cats --year 2026
"""
import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.db import init_db, init_extended_db
from pipeline.importers.amazon import import_amazon_csv
from pipeline.utils import create_engine_and_session

BASE_DIR = Path("data/imports/amazon")

# ---------------------------------------------------------------------------
# Account definitions — edit here if folder names change
# ---------------------------------------------------------------------------
ACCOUNTS: list[dict] = [
    {
        "owner": "Mike",
        "folder": BASE_DIR / "Mike Aron Amazon Orders",
        "retail": "Your Amazon Orders/Order History.csv",
        "digital": "Your Amazon Orders/Digital Content Orders.csv",
        "refund": "Your Returns & Refunds/Refund Details.csv",
    },
    {
        "owner": "Christine",
        "folder": BASE_DIR / "Christine Aron Amazon Orders",
        "retail": "Your Amazon Orders/Order History.csv",
        "digital": "Your Amazon Orders/Digital Content Orders.csv",
        "refund": "Your Returns & Refunds/Refund Details.csv",
    },
]


async def run(args) -> None:
    engine, Session = create_engine_and_session()
    await init_db(engine)
    await init_extended_db()

    summary: list[dict] = []

    for account in ACCOUNTS:
        if args.owner and account["owner"].lower() != args.owner.lower():
            continue

        owner = account["owner"]
        folder = account["folder"]

        if not folder.exists():
            print(f"[SKIP] {owner}: folder not found: {folder}")
            continue

        # --- Retail orders ---
        retail_path = folder / account["retail"]
        if retail_path.exists():
            print(f"\n[IMPORT] {owner} retail orders: {retail_path.name}")
            async with Session() as session:
                async with session.begin():
                    result = await import_amazon_csv(
                        session,
                        str(retail_path),
                        owner=owner,
                        file_type="retail",
                        run_categorize=not args.no_claude,
                    )
                src = result.pop("_archive_src", None)
                dst = result.pop("_archive_dest", None)
                if src and dst and result["status"] == "completed":
                    shutil.copy2(src, dst)
            print(f"  {result['message']}")
            summary.append({"owner": owner, "type": "retail", **result})
        else:
            print(f"[SKIP] {owner} retail: file not found: {retail_path}")

        # --- Digital content orders ---
        if not args.skip_digital:
            digital_path = folder / account["digital"]
            if digital_path.exists():
                print(f"\n[IMPORT] {owner} digital orders: {digital_path.name}")
                async with Session() as session:
                    async with session.begin():
                        result = await import_amazon_csv(
                            session,
                            str(digital_path),
                            owner=owner,
                            file_type="digital",
                            run_categorize=False,   # digital items rarely need Claude
                        )
                    src = result.pop("_archive_src", None)
                    dst = result.pop("_archive_dest", None)
                    if src and dst and result["status"] == "completed":
                        shutil.copy2(src, dst)
                print(f"  {result['message']}")
                summary.append({"owner": owner, "type": "digital", **result})
            else:
                print(f"[SKIP] {owner} digital: file not found: {digital_path}")

        # --- Refunds ---
        if not args.skip_refunds:
            refund_path = folder / account["refund"]
            if refund_path.exists():
                print(f"\n[IMPORT] {owner} refunds: {refund_path.name}")
                async with Session() as session:
                    async with session.begin():
                        result = await import_amazon_csv(
                            session,
                            str(refund_path),
                            owner=owner,
                            file_type="refund",
                            run_categorize=False,
                        )
                    src = result.pop("_archive_src", None)
                    dst = result.pop("_archive_dest", None)
                    if src and dst and result["status"] == "completed":
                        shutil.copy2(src, dst)
                print(f"  {result['message']}")
                summary.append({"owner": owner, "type": "refund", **result})
            else:
                print(f"[SKIP] {owner} refunds: file not found: {refund_path}")

    # Summary
    print(f"\n{'='*60}")
    print("  IMPORT SUMMARY")
    print(f"{'='*60}")
    total_imported = 0
    total_matched = 0
    for s in summary:
        imported = s.get("orders_imported", 0)
        matched = s.get("transactions_matched", 0)
        status = s.get("status", "?")
        total_imported += imported
        total_matched += matched
        print(f"  [{s['owner']:12}] {s['type']:8}  {status:10}  "
              f"{imported:4} imported  {matched:4} matched")
    print(f"{'─'*60}")
    print(f"  TOTAL: {total_imported} imported, {total_matched} matched to CC transactions")
    print(f"\nNext steps:")
    print(f"  python scripts/amazon_reconciliation.py --rematch")
    print(f"  python scripts/amazon_reconciliation.py --fix-cats --year 2024")
    print(f"  python scripts/amazon_reconciliation.py --fix-cats --year 2025")
    print(f"  python scripts/amazon_reconciliation.py --fix-cats --year 2026")
    print(f"  python scripts/amazon_reconciliation.py --year 2025")
    print(f"  python scripts/amazon_reconciliation.py --year 2026")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk Amazon data importer")
    parser.add_argument("--no-claude", action="store_true",
                        help="Skip Claude AI categorization for retail orders")
    parser.add_argument("--skip-digital", action="store_true",
                        help="Skip importing Digital Content Orders")
    parser.add_argument("--skip-refunds", action="store_true",
                        help="Skip importing Refund Details")
    parser.add_argument("--owner", default=None,
                        help='Import only one account, e.g. --owner Mike')
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
