"""
Monarch Money CSV importer.
A single Monarch export can contain transactions across multiple accounts,
so this importer groups by the Account column and creates/links accounts.

Deduplication: uses Original Statement (the raw bank description) for hashing
so that the same transaction imported from both a card CSV and Monarch will
produce the same hash and be automatically deduplicated.

Usage:
    python -m pipeline.importers.monarch --file "data/imports/monarch/monarch_export.csv"
"""
import argparse
import asyncio
import logging
import shutil
from collections import defaultdict
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
from pipeline.parsers.csv_parser import (
    MonarchTransaction,
    monarch_tx_hash,
    parse_monarch_csv,
)
from pipeline.utils import file_hash, create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed/monarch")


def _guess_segment(tx: MonarchTransaction) -> str:
    """Infer segment from Monarch tags."""
    lower_tags = {t.lower() for t in tx.tags}
    if "business" in lower_tags or "work" in lower_tags:
        return "business"
    if "investment" in lower_tags or "investing" in lower_tags:
        return "investment"
    return "personal"


def _parse_account_parts(account_name: str) -> tuple[str, str]:
    """
    Monarch Account column often looks like 'Chase Sapphire ****4321'.
    Split into (institution_guess, display_name).
    """
    name = account_name.strip()
    return ("", name)


async def import_monarch_csv(
    session: AsyncSession,
    filepath: str,
    default_segment: str = "personal",
) -> dict:
    """
    Import a Monarch Money CSV export.  Returns a result summary dict.
    """
    path = Path(filepath)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {filepath}"}

    fhash = file_hash(filepath)

    existing = await get_document_by_hash(session, fhash)
    if existing:
        logger.info(f"Skipping duplicate Monarch file (doc #{existing.id}): {path.name}")
        return {
            "status": "duplicate",
            "message": f"Already imported as document #{existing.id}",
            "document_id": existing.id,
            "transactions_imported": 0,
            "transactions_skipped": 0,
        }

    doc = await create_document(session, {
        "filename": path.name,
        "original_path": str(path.resolve()),
        "file_type": "csv",
        "document_type": "monarch",
        "status": "processing",
        "file_hash": fhash,
        "file_size_bytes": path.stat().st_size,
    })

    try:
        monarch_txns = parse_monarch_csv(filepath)
    except ValueError as e:
        await update_document_status(session, doc.id, "failed", error_message=str(e))
        return {"status": "error", "message": str(e), "document_id": doc.id}

    if not monarch_txns:
        await update_document_status(session, doc.id, "completed")
        return {
            "status": "completed",
            "document_id": doc.id,
            "filename": path.name,
            "transactions_imported": 0,
            "transactions_skipped": 0,
            "message": "No transactions found in file.",
        }

    by_account: dict[str, list[MonarchTransaction]] = defaultdict(list)
    for tx in monarch_txns:
        key = tx.account_name or "Unknown Account"
        by_account[key].append(tx)

    account_cache: dict[str, int] = {}
    total_inserted = 0
    total_skipped = 0

    for acct_name, txns in by_account.items():
        if acct_name not in account_cache:
            _, display_name = _parse_account_parts(acct_name)
            account = await upsert_account(session, {
                "name": display_name,
                "account_type": "personal",
                "subtype": "credit_card",
                "institution": "",
            })
            account_cache[acct_name] = account.id

        acct_id = account_cache[acct_name]
        seen_hashes: dict[str, int] = {}
        rows: list[dict] = []

        for tx in txns:
            base_hash = monarch_tx_hash(tx, seq=0)
            seq = seen_hashes.get(base_hash, 0)
            tx_hash = monarch_tx_hash(tx, seq=seq)
            seen_hashes[base_hash] = seq + 1

            segment = _guess_segment(tx) or default_segment

            row: dict = {
                "account_id": acct_id,
                "source_document_id": doc.id,
                "date": tx.date,
                "description": tx.merchant,
                "amount": tx.amount,
                "currency": "USD",
                "segment": segment,
                "period_month": tx.date.month,
                "period_year": tx.date.year,
                "transaction_hash": tx_hash,
                "effective_segment": segment,
                "notes": tx.notes or None,
            }

            if tx.category:
                row["category"] = tx.category
                row["effective_category"] = tx.category

            rows.append(row)

        inserted = await bulk_create_transactions(session, rows)
        skipped = len(rows) - inserted
        total_inserted += inserted
        total_skipped += skipped
        logger.info(
            f"  Account '{acct_name}': {inserted} imported, {skipped} skipped (dupes)"
        )

    # Apply entity assignment rules to newly imported transactions
    entity_updated = await apply_entity_rules(session, document_id=doc.id)
    logger.info(f"Entity rules applied to {entity_updated} transactions")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"
    shutil.copy2(filepath, dest)

    await update_document_status(session, doc.id, "completed", processed_path=str(dest))

    logger.info(
        f"Monarch import done: {total_inserted} imported, {total_skipped} skipped from {path.name}"
    )
    return {
        "status": "completed",
        "document_id": doc.id,
        "filename": path.name,
        "transactions_imported": total_inserted,
        "transactions_skipped": total_skipped,
        "message": (
            f"Imported {total_inserted} transactions across "
            f"{len(by_account)} accounts. {total_skipped} duplicates skipped."
        ),
    }


async def _main():
    parser = argparse.ArgumentParser(description="Import Monarch Money CSV export")
    parser.add_argument("--file", required=True, help="Path to Monarch CSV file")
    parser.add_argument("--segment", default="personal",
                        choices=["personal", "business", "investment", "reimbursable"],
                        help="Default segment for transactions without tags")
    args = parser.parse_args()

    engine, Session = create_engine_and_session()
    from pipeline.db import init_db
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            result = await import_monarch_csv(session, args.file, default_segment=args.segment)
            print(result)


if __name__ == "__main__":
    asyncio.run(_main())
