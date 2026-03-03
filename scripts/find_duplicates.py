"""
Analyze duplicate transactions in the database.
Monarch CSV includes credit card txns from all linked accounts,
so importing credit card CSVs on top creates overlaps.
"""
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func, text
from pipeline.db import init_db
from pipeline.db.schema import Transaction, Account, Document
from pipeline.utils import create_engine_and_session


async def main():
    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        # Total counts
        total = (await session.execute(select(func.count(Transaction.id)))).scalar()
        print(f"Total transactions in DB: {total}")

        # Count by source document
        result = await session.execute(
            select(
                Document.filename,
                func.count(Transaction.id).label("cnt"),
            )
            .join(Transaction, Transaction.source_document_id == Document.id)
            .group_by(Document.filename)
        )
        print("\nTransactions by source file:")
        for row in result.all():
            print(f"  {row.filename:<50s}: {row.cnt:>6d}")

        # Count by account
        result = await session.execute(
            select(
                Account.name,
                func.count(Transaction.id).label("cnt"),
            )
            .join(Transaction, Transaction.account_id == Account.id)
            .group_by(Account.name)
        )
        print("\nTransactions by account:")
        for row in sorted(result.all(), key=lambda r: -r.cnt):
            print(f"  {row.name:<50s}: {row.cnt:>6d}")

        # Find potential duplicates: same date + same abs(amount) + similar account
        # across different source documents
        print("\n" + "=" * 80)
        print("DUPLICATE ANALYSIS: Same date + amount across different source docs")
        print("=" * 80)

        # Get all transactions with their source document info
        result = await session.execute(
            select(
                Transaction.id,
                Transaction.date,
                Transaction.amount,
                Transaction.description,
                Transaction.account_id,
                Transaction.source_document_id,
                Transaction.transaction_hash,
                Account.name.label("account_name"),
                Document.filename.label("source_file"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .join(Document, Transaction.source_document_id == Document.id)
            .order_by(Transaction.date, Transaction.amount)
        )
        all_txns = result.all()

        # Group by (date, amount) to find potential dupes
        by_key = defaultdict(list)
        for tx in all_txns:
            key = (tx.date.strftime("%Y-%m-%d"), round(tx.amount, 2))
            by_key[key].append(tx)

        dupe_groups = 0
        dupe_txns = 0
        dupe_ids_to_remove = []

        # Monarch doc IDs (prefer to keep these)
        monarch_docs = set()
        cc_docs = set()
        result2 = await session.execute(select(Document.id, Document.filename))
        for doc in result2.all():
            if "Monarch" in doc.filename:
                monarch_docs.add(doc.id)
            else:
                cc_docs.add(doc.id)

        print(f"\nMonarch doc IDs: {monarch_docs}")
        print(f"Credit card doc IDs: {cc_docs}")

        for key, txns in by_key.items():
            if len(txns) < 2:
                continue

            # Check if we have txns from both Monarch AND credit card sources
            sources = set(tx.source_document_id for tx in txns)
            has_monarch = sources & monarch_docs
            has_cc = sources & cc_docs

            if not (has_monarch and has_cc):
                continue

            # These are likely duplicates - same date + amount from both Monarch and CC
            monarch_txns = [tx for tx in txns if tx.source_document_id in monarch_docs]
            cc_txns = [tx for tx in txns if tx.source_document_id in cc_docs]

            # For each CC txn, try to match with a Monarch txn
            matched_monarch = set()
            for cc_tx in cc_txns:
                for m_tx in monarch_txns:
                    if m_tx.id in matched_monarch:
                        continue
                    # Same date, same amount - this is a dupe
                    # Keep the Monarch version (has better categorization from Monarch Money)
                    dupe_ids_to_remove.append(cc_tx.id)
                    matched_monarch.add(m_tx.id)
                    dupe_txns += 1
                    break

            if dupe_txns > dupe_groups * 0 and len(cc_txns) > 0:
                dupe_groups += 1

        print(f"\nDuplicate groups found: {dupe_groups}")
        print(f"Duplicate transactions (CC copies to remove): {len(dupe_ids_to_remove)}")
        print(f"Transactions after cleanup: {total - len(dupe_ids_to_remove)}")

        # Show some examples
        if dupe_ids_to_remove:
            print("\nSample duplicates (first 20):")
            sample_ids = dupe_ids_to_remove[:20]
            result = await session.execute(
                select(
                    Transaction.id,
                    Transaction.date,
                    Transaction.amount,
                    Transaction.description,
                    Account.name.label("acct"),
                    Document.filename.label("src"),
                )
                .join(Account, Transaction.account_id == Account.id)
                .join(Document, Transaction.source_document_id == Document.id)
                .where(Transaction.id.in_(sample_ids))
            )
            for tx in result.all():
                print(f"  id={tx.id:<6d} {str(tx.date)[:10]} ${tx.amount:>10,.2f}  "
                      f"{tx.description[:40]:<40s}  acct={tx.acct[:30]:<30s} src={tx.src}")

        # Save the IDs for removal
        if dupe_ids_to_remove:
            with open("scripts/duplicate_ids.txt", "w") as f:
                for did in dupe_ids_to_remove:
                    f.write(f"{did}\n")
            print(f"\nDuplicate IDs saved to scripts/duplicate_ids.txt")

        # Also check: are there CC accounts created that overlap with Monarch accounts?
        print("\n" + "=" * 80)
        print("ACCOUNT OVERLAP ANALYSIS")
        print("=" * 80)
        result = await session.execute(
            select(
                Account.id,
                Account.name,
                Account.institution,
                func.count(Transaction.id).label("cnt"),
            )
            .join(Transaction, Transaction.account_id == Account.id)
            .group_by(Account.id, Account.name, Account.institution)
            .order_by(Account.name)
        )
        for row in result.all():
            print(f"  id={row.id:<4d} {row.name:<50s} inst={row.institution or '':<20s} txns={row.cnt:>5d}")

    await engine.dispose()


asyncio.run(main())
