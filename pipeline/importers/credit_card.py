"""
Credit card CSV importer.
Reads a CSV from data/imports/credit-cards/, deduplicates by SHA-256 hash,
writes document + transactions to the DB, then archives the file.

Usage:
    python -m pipeline.importers.credit_card --file "data/imports/credit-cards/chase_jan.csv"
    python -m pipeline.importers.credit_card --dir "data/imports/credit-cards/"
"""
import argparse
import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import (
    apply_entity_rules,
    bulk_create_transactions,
    create_document,
    get_document_by_hash,
    upsert_account,
    update_document_status,
)
from pipeline.parsers.csv_parser import parse_credit_card_csv
from pipeline.utils import file_hash, create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed/credit-cards")


async def import_csv_file(
    session: AsyncSession,
    filepath: str,
    account_name: str = "Credit Card",
    account_subtype: str = "credit_card",
    institution: str = "",
    default_segment: str = "personal",
    account_id: int | None = None,
) -> dict:
    """
    Import a single CSV file. Returns a result summary dict.

    If account_id is provided, import directly into that existing account
    (skips account creation). Otherwise, upsert by name + subtype.
    """
    path = Path(filepath)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {filepath}"}

    fhash = file_hash(filepath)

    # Dedup check
    existing = await get_document_by_hash(session, fhash)
    if existing:
        logger.info(f"Skipping duplicate file (already imported as doc #{existing.id}): {path.name}")
        return {
            "status": "duplicate",
            "message": f"Already imported as document #{existing.id}",
            "document_id": existing.id,
            "transactions_imported": 0,
            "transactions_skipped": 0,
        }

    # Get or create account
    if account_id:
        from pipeline.db import get_account
        account = await get_account(session, account_id)
        if not account:
            return {"status": "error", "message": f"Account {account_id} not found"}
    else:
        account = await upsert_account(session, {
            "name": account_name,
            "account_type": "personal",
            "subtype": account_subtype,
            "institution": institution or "",
            "data_source": "csv",
        })

    # Create document record
    doc = await create_document(session, {
        "filename": path.name,
        "original_path": str(path.resolve()),
        "file_type": "csv",
        "document_type": "credit_card",
        "status": "processing",
        "file_hash": fhash,
        "file_size_bytes": path.stat().st_size,
        "account_id": account.id,
    })

    try:
        rows = parse_credit_card_csv(filepath, account.id, doc.id, default_segment)
    except ValueError as e:
        await update_document_status(session, doc.id, "failed", error_message=str(e))
        return {"status": "error", "message": str(e), "document_id": doc.id}

    # Bulk insert — returns count of actually inserted (non-duplicate) rows
    inserted = await bulk_create_transactions(session, rows)
    skipped = len(rows) - inserted

    # Apply entity assignment rules to newly imported transactions
    entity_updated = await apply_entity_rules(session, document_id=doc.id)
    logger.info(f"Entity rules applied to {entity_updated} transactions")

    # Compute archive path (actual copy deferred until after transaction commits)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"

    await update_document_status(session, doc.id, "completed", processed_path=str(dest))

    logger.info(
        f"Imported {inserted} transactions ({skipped} skipped) from {path.name}"
    )
    return {
        "status": "completed",
        "document_id": doc.id,
        "filename": path.name,
        "transactions_imported": inserted,
        "transactions_skipped": skipped,
        "message": f"Imported {inserted} transactions.",
        "_archive_src": str(filepath),
        "_archive_dest": str(dest),
    }


async def import_directory(
    session: AsyncSession,
    directory: str,
    **kwargs,
) -> list[dict]:
    results = []
    for csv_file in sorted(Path(directory).glob("*.csv")):
        result = await import_csv_file(session, str(csv_file), **kwargs)
        results.append(result)
    return results


async def _main():
    parser = argparse.ArgumentParser(description="Import credit card CSV statements")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a single CSV file")
    group.add_argument("--dir", help="Directory of CSV files to import")
    parser.add_argument("--account-name", default="Credit Card", help="Account name")
    parser.add_argument("--institution", default="", help="Bank/card institution name")
    parser.add_argument("--segment", default="personal",
                        choices=["personal", "business", "investment", "reimbursable"],
                        help="Default segment for transactions")
    args = parser.parse_args()

    engine, Session = create_engine_and_session()
    from pipeline.db import init_db
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            if args.file:
                all_results = [await import_csv_file(
                    session, args.file,
                    account_name=args.account_name,
                    institution=args.institution,
                    default_segment=args.segment,
                )]
            else:
                all_results = await import_directory(
                    session, args.dir,
                    account_name=args.account_name,
                    institution=args.institution,
                    default_segment=args.segment,
                )

        # Archive files after successful commit
        for r in all_results:
            src, dst = r.pop("_archive_src", None), r.pop("_archive_dest", None)
            if src and dst:
                shutil.copy2(src, dst)
            print(r)


if __name__ == "__main__":
    asyncio.run(_main())
