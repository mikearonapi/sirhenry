"""Comprehensive data audit of the financials database."""
import asyncio
from api.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        print("=" * 70)
        print("1. TABLE ROW COUNTS")
        print("=" * 70)
        tables = await session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
        for (tbl,) in tables.fetchall():
            cnt = await session.execute(text(f"SELECT COUNT(*) FROM [{tbl}]"))
            print(f"  {tbl:40s} {cnt.scalar():>8,}")

        print("\n" + "=" * 70)
        print("2. TRANSACTIONS BY SOURCE (notes prefix)")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                CASE
                    WHEN notes LIKE 'Plaid:%' THEN 'Plaid'
                    WHEN notes LIKE 'Amazon:%' THEN 'Amazon'
                    WHEN notes LIKE '%CSV%' OR notes LIKE '%import%' THEN 'CSV Import'
                    WHEN notes IS NULL OR notes = '' THEN '(no notes)'
                    ELSE 'Other: ' || SUBSTR(notes, 1, 30)
                END as source,
                COUNT(*) as cnt,
                MIN(date) as earliest,
                MAX(date) as latest
            FROM transactions
            GROUP BY 1
            ORDER BY cnt DESC
        """))
        print(f"  {'Source':40s} {'Count':>8s} {'Earliest':>12s} {'Latest':>12s}")
        print("  " + "-" * 74)
        for row in r.fetchall():
            print(f"  {str(row[0]):40s} {row[1]:>8,} {str(row[2]):>12s} {str(row[3]):>12s}")

        print("\n" + "=" * 70)
        print("3. TRANSACTIONS BY YEAR/MONTH")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT period_year, period_month, COUNT(*)
            FROM transactions
            GROUP BY period_year, period_month
            ORDER BY period_year, period_month
        """))
        print(f"  {'Year':>6s} {'Month':>6s} {'Count':>8s}")
        print("  " + "-" * 24)
        for row in r.fetchall():
            print(f"  {row[0] or 'NULL':>6} {row[1] or 'NULL':>6} {row[2]:>8,}")

        print("\n" + "=" * 70)
        print("4. ACCOUNTS SUMMARY")
        print("=" * 70)
        cols_r = await session.execute(text("PRAGMA table_info(accounts)"))
        acct_cols = [c[1] for c in cols_r.fetchall()]
        print(f"  (accounts columns: {', '.join(acct_cols)})")
        r = await session.execute(text("""
            SELECT
                a.id, a.name, a.institution, a.account_type,
                (SELECT COUNT(*) FROM transactions t WHERE t.account_id = a.id) as tx_count,
                pa.plaid_account_id
            FROM accounts a
            LEFT JOIN plaid_accounts pa ON pa.account_id = a.id
            ORDER BY tx_count DESC
        """))
        print(f"  {'ID':>4s} {'Name':30s} {'Institution':20s} {'Type':12s} {'Txns':>6s} {'Plaid?':>8s}")
        print("  " + "-" * 84)
        for row in r.fetchall():
            plaid = "Yes" if row[5] else "No"
            print(f"  {row[0]:>4d} {str(row[1] or ''):30s} {str(row[2] or ''):20s} {str(row[3] or ''):12s} {row[4]:>6,} {plaid:>8s}")

        print("\n" + "=" * 70)
        print("5. DATA QUALITY CHECKS")
        print("=" * 70)

        # 5a. Transactions with NULL date
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE date IS NULL"))
        print(f"  Transactions with NULL date:          {r.scalar():>8,}")

        # 5b. Transactions with NULL amount
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE amount IS NULL"))
        print(f"  Transactions with NULL amount:        {r.scalar():>8,}")

        # 5c. Transactions with NULL account_id
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE account_id IS NULL"))
        print(f"  Transactions with NULL account_id:    {r.scalar():>8,}")

        # 5d. Transactions with NULL description
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE description IS NULL OR description = ''"))
        print(f"  Transactions with empty description:  {r.scalar():>8,}")

        # 5e. Orphaned transactions (account_id not in accounts)
        r = await session.execute(text("""
            SELECT COUNT(*) FROM transactions t
            WHERE t.account_id NOT IN (SELECT id FROM accounts)
        """))
        print(f"  Orphaned txns (bad account_id):       {r.scalar():>8,}")

        # 5f. Exact duplicate transactions (same hash)
        r = await session.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT transaction_hash, COUNT(*) as c
                FROM transactions
                WHERE transaction_hash IS NOT NULL AND transaction_hash != ''
                GROUP BY transaction_hash
                HAVING c > 1
            )
        """))
        print(f"  Duplicate transaction hashes:         {r.scalar():>8,}")

        # 5g. Likely duplicates (same account, date, amount, description)
        r = await session.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT account_id, date, amount, description, COUNT(*) as c
                FROM transactions
                GROUP BY account_id, date, amount, description
                HAVING c > 1
            )
        """))
        print(f"  Likely dupes (acct+date+amt+desc):    {r.scalar():>8,}")

        # 5h. Transactions with future dates
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE date > date('now', '+1 day')"))
        print(f"  Transactions with future dates:       {r.scalar():>8,}")

        # 5i. Transactions with very old dates (before 2020)
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE date < '2020-01-01'"))
        print(f"  Transactions before 2020:             {r.scalar():>8,}")

        # 5j. Zero-amount transactions
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE amount = 0"))
        print(f"  Zero-amount transactions:             {r.scalar():>8,}")

        # 5k. Transactions with NULL period_year or period_month
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE period_year IS NULL OR period_month IS NULL"))
        print(f"  NULL period_year/month:               {r.scalar():>8,}")

        # 5l. Excluded transactions
        r = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE is_excluded = 1"))
        print(f"  Excluded transactions (is_excluded):  {r.scalar():>8,}")

        print("\n" + "=" * 70)
        print("6. PLAID vs CSV OVERLAP (same account, same date, similar amount)")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT COUNT(*) FROM transactions p
            INNER JOIN transactions c
                ON p.account_id = c.account_id
                AND p.date = c.date
                AND ABS(p.amount - c.amount) < 0.01
                AND p.id != c.id
            WHERE p.notes LIKE 'Plaid:%'
            AND (c.notes NOT LIKE 'Plaid:%' OR c.notes IS NULL)
        """))
        print(f"  Plaid txns with a CSV match (potential overlaps): {r.scalar():>6,}")

        # Show a few examples
        r = await session.execute(text("""
            SELECT
                p.id as plaid_id, p.date, p.amount, p.description as plaid_desc,
                c.id as csv_id, c.description as csv_desc, c.notes as csv_notes
            FROM transactions p
            INNER JOIN transactions c
                ON p.account_id = c.account_id
                AND p.date = c.date
                AND ABS(p.amount - c.amount) < 0.01
                AND p.id != c.id
            WHERE p.notes LIKE 'Plaid:%'
            AND (c.notes NOT LIKE 'Plaid:%' OR c.notes IS NULL)
            LIMIT 10
        """))
        rows = r.fetchall()
        if rows:
            print(f"\n  Sample overlaps:")
            print(f"  {'PlaidID':>7s} {'Date':>12s} {'Amount':>10s} {'Plaid Desc':30s} {'CsvID':>6s} {'CSV Desc':30s}")
            print("  " + "-" * 100)
            for row in rows:
                print(f"  {row[0]:>7d} {str(row[1]):>12s} {row[2]:>10.2f} {str(row[3])[:30]:30s} {row[4]:>6d} {str(row[5])[:30]:30s}")

        print("\n" + "=" * 70)
        print("7. CATEGORY COVERAGE")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                CASE WHEN category IS NOT NULL AND category != '' THEN 'Categorized' ELSE 'Uncategorized' END as status,
                COUNT(*) as cnt
            FROM transactions
            GROUP BY 1
        """))
        for row in r.fetchall():
            print(f"  {row[0]:30s} {row[1]:>8,}")

asyncio.run(main())
