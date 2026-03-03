"""
SirHENRY Deduplication Tool (consolidated)
============================================
Replaces: find_duplicates.py, cleanup_duplicates.py, compare_sources.py

Usage:
    python scripts/dedup.py find       # Analyze duplicate transactions in the DB
    python scripts/dedup.py clean      # Remove duplicate CC CSV transactions (interactive)
    python scripts/dedup.py compare    # Side-by-side comparison of Monarch vs CC CSV data
"""
import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# find — replaces find_duplicates.py
# ============================================================================
async def cmd_find(args: argparse.Namespace) -> None:
    """Analyze duplicate transactions in the database.

    Monarch CSV includes credit card txns from all linked accounts, so
    importing credit card CSVs on top creates overlaps. This command
    identifies those overlaps and writes removable IDs to a file.
    """
    from sqlalchemy import select, func
    from pipeline.db import init_db
    from pipeline.db.schema import Transaction, Account, Document
    from pipeline.utils import create_engine_and_session

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        total = (await session.execute(select(func.count(Transaction.id)))).scalar()
        print(f"Total transactions in DB: {total}")

        # Count by source document
        result = await session.execute(
            select(Document.filename, func.count(Transaction.id).label("cnt"))
            .join(Transaction, Transaction.source_document_id == Document.id)
            .group_by(Document.filename)
        )
        print("\nTransactions by source file:")
        for row in result.all():
            print(f"  {row.filename:<50s}: {row.cnt:>6d}")

        # Count by account
        result = await session.execute(
            select(Account.name, func.count(Transaction.id).label("cnt"))
            .join(Transaction, Transaction.account_id == Account.id)
            .group_by(Account.name)
        )
        print("\nTransactions by account:")
        for row in sorted(result.all(), key=lambda r: -r.cnt):
            print(f"  {row.name:<50s}: {row.cnt:>6d}")

        # Find potential duplicates across source documents
        print("\n" + "=" * 80)
        print("DUPLICATE ANALYSIS: Same date + amount across different source docs")
        print("=" * 80)

        result = await session.execute(
            select(
                Transaction.id, Transaction.date, Transaction.amount,
                Transaction.description, Transaction.account_id,
                Transaction.source_document_id, Transaction.transaction_hash,
                Account.name.label("account_name"),
                Document.filename.label("source_file"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .join(Document, Transaction.source_document_id == Document.id)
            .order_by(Transaction.date, Transaction.amount)
        )
        all_txns = result.all()

        by_key = defaultdict(list)
        for tx in all_txns:
            key = (tx.date.strftime("%Y-%m-%d"), round(tx.amount, 2))
            by_key[key].append(tx)

        # Identify Monarch vs CC doc IDs
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

        dupe_groups = 0
        dupe_ids_to_remove = []

        for key, txns in by_key.items():
            if len(txns) < 2:
                continue
            sources = set(tx.source_document_id for tx in txns)
            if not (sources & monarch_docs and sources & cc_docs):
                continue

            monarch_txns = [tx for tx in txns if tx.source_document_id in monarch_docs]
            cc_txns = [tx for tx in txns if tx.source_document_id in cc_docs]
            matched_monarch = set()

            for cc_tx in cc_txns:
                for m_tx in monarch_txns:
                    if m_tx.id not in matched_monarch:
                        dupe_ids_to_remove.append(cc_tx.id)
                        matched_monarch.add(m_tx.id)
                        break

            if cc_txns:
                dupe_groups += 1

        print(f"\nDuplicate groups found: {dupe_groups}")
        print(f"Duplicate transactions (CC copies to remove): {len(dupe_ids_to_remove)}")
        print(f"Transactions after cleanup: {total - len(dupe_ids_to_remove)}")

        if dupe_ids_to_remove:
            print("\nSample duplicates (first 20):")
            sample_ids = dupe_ids_to_remove[:20]
            result = await session.execute(
                select(
                    Transaction.id, Transaction.date, Transaction.amount,
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

            outfile = PROJECT_ROOT / "scripts" / "duplicate_ids.txt"
            with open(outfile, "w") as f:
                for did in dupe_ids_to_remove:
                    f.write(f"{did}\n")
            print(f"\nDuplicate IDs saved to {outfile}")

        # Account overlap analysis
        print("\n" + "=" * 80)
        print("ACCOUNT OVERLAP ANALYSIS")
        print("=" * 80)
        result = await session.execute(
            select(
                Account.id, Account.name, Account.institution,
                func.count(Transaction.id).label("cnt"),
            )
            .join(Transaction, Transaction.account_id == Account.id)
            .group_by(Account.id, Account.name, Account.institution)
            .order_by(Account.name)
        )
        for row in result.all():
            print(f"  id={row.id:<4d} {row.name:<50s} "
                  f"inst={row.institution or '':<20s} txns={row.cnt:>5d}")

    await engine.dispose()


# ============================================================================
# clean — replaces cleanup_duplicates.py
# ============================================================================
async def cmd_clean(args: argparse.Namespace) -> None:
    """Remove duplicate CC CSV transactions, keeping Monarch data.

    Strategy: Monarch has comprehensive, properly-separated account data.
    CC CSVs overlap and often merge everything into a single account.
    This command removes all CC CSV transactions that overlap with Monarch.
    """
    from sqlalchemy import select, func, delete
    from pipeline.db import init_db, get_all_business_entities
    from pipeline.db.schema import Transaction, Account, Document
    from pipeline.utils import create_engine_and_session

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
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

        # Monarch date range
        result = await session.execute(
            select(func.min(Transaction.date), func.max(Transaction.date),
                   func.count(Transaction.id))
            .where(Transaction.source_document_id.in_(monarch_doc_ids))
        )
        m_min, m_max, m_count = result.one()
        print(f"\nMonarch: {m_count} txns, {m_min} to {m_max}")

        # CC date range
        result = await session.execute(
            select(func.min(Transaction.date), func.max(Transaction.date),
                   func.count(Transaction.id))
            .where(Transaction.source_document_id.in_(cc_doc_ids))
        )
        cc_min, cc_max, cc_count = result.one()
        print(f"CC CSVs: {cc_count} txns, {cc_min} to {cc_max}")

        # Per-CC-doc breakdown
        print("\nCC doc breakdown:")
        for doc_id in sorted(cc_doc_ids):
            result = await session.execute(
                select(Document.filename, func.min(Transaction.date),
                       func.max(Transaction.date), func.count(Transaction.id))
                .join(Transaction, Transaction.source_document_id == Document.id)
                .where(Document.id == doc_id)
                .group_by(Document.filename)
            )
            row = result.one_or_none()
            if row:
                print(f"  {row[0]:<45s}: {row[3]} txns, {row[1]} to {row[2]}")

        print(f"\n{'=' * 80}")
        print("CLEANUP PLAN")
        print(f"{'=' * 80}")
        print(f"Removing ALL {cc_count} credit card CSV transactions")
        print(f"  (they overlap with Monarch which has proper account separation)")
        print(f"Keeping ALL {m_count} Monarch transactions")
        print(f"Final count will be: {m_count}")

        # Check for CC-created account
        result = await session.execute(
            select(Account.id, Account.name).where(Account.name == "Capital One Venture")
        )
        cc_account = result.one_or_none()

        if args.yes:
            confirm = "yes"
        else:
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

        # Delete orphan CC account
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
        entities = await get_all_business_entities(session, include_inactive=True)
        emap = {e.id: e.name for e in entities}
        result = await session.execute(
            select(Transaction.effective_business_entity_id,
                   func.count(Transaction.id), func.sum(Transaction.amount))
            .where(Transaction.effective_business_entity_id.isnot(None))
            .group_by(Transaction.effective_business_entity_id)
        )
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


# ============================================================================
# compare — replaces compare_sources.py
# ============================================================================
async def cmd_compare(args: argparse.Namespace) -> None:
    """Compare Monarch CSV vs Credit Card CSV data richness side-by-side."""
    import pandas as pd

    base = Path(os.environ.get(
        "IMPORT_DIR",
        str(PROJECT_ROOT / "data" / "imports"),
    ))

    def _print_columns(label: str, filepath: Path) -> pd.DataFrame:
        print("=" * 100)
        print(label)
        print("=" * 100)
        try:
            df = pd.read_csv(filepath, dtype=str)
        except FileNotFoundError:
            print(f"  NOT FOUND: {filepath}")
            return pd.DataFrame()
        for col in df.columns:
            non_null = df[col].notna().sum()
            sample = df[col].dropna().iloc[0] if non_null > 0 else "N/A"
            if len(str(sample)) > 80:
                sample = str(sample)[:80] + "..."
            print(f"  {col:<30s}  {non_null:>5d}/{len(df)} non-null  sample: {sample}")
        return df

    mdf = _print_columns("MONARCH CSV COLUMNS", base / "Monarch" / "Monarch-Transactions.csv")
    print()
    co = _print_columns("CAPITAL ONE CSV COLUMNS (Family-Capital-One-2025.csv)",
                        base / "credit-cards" / "Family-Capital-One-2025.csv")
    print()
    ax = _print_columns("AMEX CSV COLUMNS (Personal-Amex-2025.csv)",
                        base / "credit-cards" / "Personal-Amex-2025.csv")
    print()
    _print_columns("AMEX CSV COLUMNS (Accenture-Corp-Amex-2025.csv)",
                   base / "credit-cards" / "Accenture-Corp-Amex-2025.csv")

    # Side-by-side comparison if both Monarch and Capital One exist
    if not mdf.empty and not co.empty:
        print("\n" + "=" * 100)
        print("SIDE-BY-SIDE COMPARISON: Same transactions from both sources")
        print("=" * 100)

        mdf["Date"] = pd.to_datetime(mdf["Date"])
        mdf["Amount"] = pd.to_numeric(mdf["Amount"], errors="coerce")
        co["Transaction Date"] = pd.to_datetime(co["Transaction Date"])
        co["Debit"] = pd.to_numeric(co["Debit"], errors="coerce")
        co["Credit"] = pd.to_numeric(co["Credit"], errors="coerce")

        venture = mdf[mdf["Account"].str.contains("Venture", na=False)].copy()
        matches = 0
        for _, cc_row in co.head(30).iterrows():
            cc_date = cc_row["Transaction Date"]
            cc_amt = cc_row["Debit"] if pd.notna(cc_row["Debit"]) else cc_row.get("Credit", 0)
            if pd.isna(cc_amt):
                cc_amt = cc_row.get("Credit", 0)
                if pd.isna(cc_amt):
                    continue
            m_match = venture[
                (venture["Date"] == cc_date) &
                (venture["Amount"].abs() - abs(float(cc_amt))).abs() < 0.02
            ]
            if len(m_match) > 0:
                m_row = m_match.iloc[0]
                matches += 1
                if matches <= 10:
                    print(f"\n  --- Match #{matches} ---")
                    print(f"  CC  Date: {cc_date.strftime('%Y-%m-%d')}  "
                          f"Desc: {cc_row.get('Description', 'N/A')[:60]}")
                    print(f"  CC  Amount: ${cc_amt}  Category: {cc_row.get('Category', 'N/A')}")
                    print(f"  MON Date: {m_row['Date'].strftime('%Y-%m-%d')}  "
                          f"Desc: {m_row.get('Merchant', 'N/A')[:60]}")
                    print(f"  MON Amount: ${m_row['Amount']}  "
                          f"Category: {m_row.get('Category', 'N/A')}")
                    print(f"  MON Original: {str(m_row.get('Original Statement', 'N/A'))[:70]}")
                    print(f"  MON Account: {m_row.get('Account', 'N/A')}")
                    print(f"  MON Tags: {m_row.get('Tags', 'N/A')}")
                    print(f"  MON Notes: {m_row.get('Notes', 'N/A')}")

        print(f"\n  Total matches found in first 30 CC rows: {matches}")

    print("\n" + "=" * 100)
    print("DATA RICHNESS COMPARISON")
    print("=" * 100)
    print("\n  MONARCH EXCLUSIVE FIELDS (not in CC CSVs):")
    print("    - Merchant (cleaned merchant name)")
    print("    - Category (Monarch Money AI categorization)")
    print("    - Original Statement (raw bank description)")
    print("    - Account (proper account name with last 4 digits)")
    print("    - Tags (user-defined tags)")
    print("    - Notes (user notes)")
    print("    - Owner (account owner)")
    print()
    print("  CC CSV EXCLUSIVE FIELDS (not in Monarch):")
    print("    - Capital One: Category (Capital One's own categorization)")
    print("    - Amex: Extended Details, Appears On Your Statement As, "
          "Address, City/State, Zip, Country, Reference")
    print()
    print("  VERDICT:")
    print("    Monarch is RICHER for Capital One (cleaned merchant, categories, tags, notes, owner)")
    print("    Amex CSVs have some extra fields (address, reference) "
          "but Monarch has better categorization")
    print("    The CC 'Description' field = Monarch 'Original Statement' field (same raw bank text)")


# ============================================================================
# CLI entry point
# ============================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dedup",
        description="SirHENRY deduplication toolkit (consolidated)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("find", help="Analyze duplicate transactions in the DB")

    clean_p = sub.add_parser("clean", help="Remove duplicate CC CSV transactions")
    clean_p.add_argument("--yes", "-y", action="store_true",
                         help="Skip confirmation prompt")

    sub.add_parser("compare", help="Side-by-side Monarch vs CC CSV comparison")

    return parser


COMMANDS = {
    "find": cmd_find,
    "clean": cmd_clean,
    "compare": cmd_compare,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMANDS[args.command]
    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
