"""
Remove duplicate transactions created by importing credit card CSVs
when Monarch already contains all the same data.

Strategy:
1. Check Monarch date range vs CC CSV date ranges
2. Remove CC transactions that fall within Monarch's date range per account
3. Keep any CC transactions that extend BEYOND Monarch's range (if any)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func, delete
from pipeline.db import init_db
from pipeline.db.schema import Transaction, Account, Document
from pipeline.utils import create_engine_and_session


async def main():
    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        # Identify source documents
        result = await session.execute(select(Document.id, Document.filename))
        docs = result.all()

        monarch_doc_ids = set()
        cc_doc_ids = set()
        for d in docs:
            if "Monarch" in d.filename:
                monarch_doc_ids.add(d.id)
            else:
                cc_doc_ids.add(d.id)

        print(f"Monarch docs: {monarch_doc_ids}")
        print(f"CC docs: {cc_doc_ids}")

        # Get Monarch date range
        result = await session.execute(
            select(
                func.min(Transaction.date),
                func.max(Transaction.date),
                func.count(Transaction.id),
            ).where(Transaction.source_document_id.in_(monarch_doc_ids))
        )
        m_min, m_max, m_count = result.one()
        print(f"\nMonarch: {m_count} txns, {m_min} to {m_max}")

        # Get CC date range
        result = await session.execute(
            select(
                func.min(Transaction.date),
                func.max(Transaction.date),
                func.count(Transaction.id),
            ).where(Transaction.source_document_id.in_(cc_doc_ids))
        )
        cc_min, cc_max, cc_count = result.one()
        print(f"CC CSVs: {cc_count} txns, {cc_min} to {cc_max}")

        # Check per-CC-doc what date ranges they cover
        print("\nCC doc breakdown:")
        for doc_id in sorted(cc_doc_ids):
            result = await session.execute(
                select(
                    Document.filename,
                    func.min(Transaction.date),
                    func.max(Transaction.date),
                    func.count(Transaction.id),
                )
                .join(Transaction, Transaction.source_document_id == Document.id)
                .where(Document.id == doc_id)
                .group_by(Document.filename)
            )
            row = result.one_or_none()
            if row:
                print(f"  {row[0]:<45s}: {row[2]} txns, {row[1]} to {row[2]}")

        # The Monarch data is comprehensive - it includes all linked accounts.
        # Since Monarch goes from {m_min} to {m_max}, and the CC CSVs overlap,
        # we should remove ALL CC CSV transactions.
        #
        # The CC transactions were all placed in a single "Capital One Venture"
        # account (even Corp Amex and Personal Amex), which is incorrect.
        # Monarch has them properly separated into their actual accounts.

        print(f"\n{'=' * 80}")
        print("CLEANUP PLAN")
        print(f"{'=' * 80}")
        print(f"Removing ALL {cc_count} credit card CSV transactions")
        print(f"  (they overlap with Monarch which has proper account separation)")
        print(f"Keeping ALL {m_count} Monarch transactions")
        print(f"Final count will be: {m_count}")

        # Also remove the CC-created account
        result = await session.execute(
            select(Account.id, Account.name)
            .where(Account.name == "Capital One Venture")
        )
        cc_account = result.one_or_none()

        confirm = input("\nProceed with cleanup? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            await engine.dispose()
            return

        # Delete CC transactions
        result = await session.execute(
            delete(Transaction).where(Transaction.source_document_id.in_(cc_doc_ids))
        )
        deleted_txns = result.rowcount
        print(f"Deleted {deleted_txns} CC transactions")

        # Delete CC documents
        result = await session.execute(
            delete(Document).where(Document.id.in_(cc_doc_ids))
        )
        deleted_docs = result.rowcount
        print(f"Deleted {deleted_docs} CC documents")

        # Delete the CC account if it exists and has no remaining txns
        if cc_account:
            remaining = await session.execute(
                select(func.count(Transaction.id))
                .where(Transaction.account_id == cc_account.id)
            )
            if remaining.scalar() == 0:
                await session.execute(
                    delete(Account).where(Account.id == cc_account.id)
                )
                print(f"Deleted orphan account: {cc_account.name} (id={cc_account.id})")

        await session.commit()

        # Verify
        total = (await session.execute(select(func.count(Transaction.id)))).scalar()
        accounts = (await session.execute(select(func.count(Account.id)))).scalar()
        docs_remaining = (await session.execute(select(func.count(Document.id)))).scalar()

        print(f"\n{'=' * 80}")
        print("POST-CLEANUP VERIFICATION")
        print(f"{'=' * 80}")
        print(f"Transactions: {total}")
        print(f"Accounts: {accounts}")
        print(f"Documents: {docs_remaining}")

        # Entity summary
        result = await session.execute(
            select(
                Transaction.effective_business_entity_id,
                func.count(Transaction.id),
                func.sum(Transaction.amount),
            )
            .where(Transaction.effective_business_entity_id.isnot(None))
            .group_by(Transaction.effective_business_entity_id)
        )
        from pipeline.db import get_all_business_entities
        entities = await get_all_business_entities(session, include_inactive=True)
        emap = {e.id: e.name for e in entities}
        print("\nEntity assignments:")
        for eid, cnt, total_amt in result.all():
            name = emap.get(eid, f"entity_{eid}")
            print(f"  {name:<30s}: {cnt:>5d} txns, ${total_amt:>12,.2f}")

        # Segment summary
        result = await session.execute(
            select(Transaction.effective_segment, func.count(Transaction.id))
            .group_by(Transaction.effective_segment)
        )
        print("\nSegment summary:")
        for seg, cnt in result.all():
            print(f"  {seg or 'null':<15s}: {cnt:>5d} txns")

    await engine.dispose()


asyncio.run(main())
