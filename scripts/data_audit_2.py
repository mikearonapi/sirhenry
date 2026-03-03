"""Part 2: Deeper quality checks - duplicates detail, CSV coverage, overlap analysis."""
import asyncio
from api.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        print("=" * 70)
        print("A. LIKELY DUPLICATES (same acct+date+amt+desc) — TOP 30")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT account_id, date, amount, description, COUNT(*) as c,
                GROUP_CONCAT(id) as ids,
                GROUP_CONCAT(COALESCE(SUBSTR(notes, 1, 20), '(none)')) as note_sources
            FROM transactions
            GROUP BY account_id, date, amount, description
            HAVING c > 1
            ORDER BY c DESC, date DESC
            LIMIT 30
        """))
        print(f"  {'AcctID':>6s} {'Date':>12s} {'Amount':>10s} {'Desc':30s} {'Cnt':>4s} {'IDs':20s} {'Sources':30s}")
        print("  " + "-" * 116)
        for row in r.fetchall():
            print(f"  {row[0]:>6} {str(row[1])[:10]:>12s} {row[2]:>10.2f} {str(row[3])[:30]:30s} {row[4]:>4d} {str(row[5])[:20]:20s} {str(row[6])[:30]:30s}")

        print("\n" + "=" * 70)
        print("B. PLAID vs CSV OVERLAP BREAKDOWN BY ACCOUNT")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                a.name,
                COUNT(DISTINCT p.id) as plaid_txns,
                COUNT(DISTINCT CASE WHEN c.id IS NOT NULL THEN p.id END) as with_csv_match,
                COUNT(DISTINCT CASE WHEN c.id IS NULL THEN p.id END) as plaid_only
            FROM transactions p
            JOIN accounts a ON a.id = p.account_id
            LEFT JOIN transactions c
                ON p.account_id = c.account_id
                AND p.date = c.date
                AND ABS(p.amount - c.amount) < 0.01
                AND p.id != c.id
                AND (c.notes NOT LIKE 'Plaid:%' OR c.notes IS NULL)
            WHERE p.notes LIKE 'Plaid:%'
            GROUP BY a.name
            ORDER BY plaid_txns DESC
        """))
        print(f"  {'Account':30s} {'Plaid':>6s} {'Has CSV':>8s} {'New':>6s}")
        print("  " + "-" * 54)
        for row in r.fetchall():
            print(f"  {str(row[0])[:30]:30s} {row[1]:>6d} {row[2]:>8d} {row[3]:>6d}")

        print("\n" + "=" * 70)
        print("C. ZERO-AMOUNT TRANSACTIONS (sample)")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT t.id, t.date, t.description, t.notes, a.name
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE t.amount = 0
            ORDER BY t.date DESC
            LIMIT 15
        """))
        print(f"  {'ID':>6s} {'Date':>12s} {'Desc':35s} {'Notes':25s} {'Account':20s}")
        print("  " + "-" * 102)
        for row in r.fetchall():
            print(f"  {row[0]:>6d} {str(row[1])[:10]:>12s} {str(row[2])[:35]:35s} {str(row[3] or '')[:25]:25s} {str(row[4])[:20]:20s}")

        print("\n" + "=" * 70)
        print("D. TRANSACTION COUNT BY ACCOUNT (CSV vs Plaid)")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                a.name,
                a.institution,
                COUNT(*) as total,
                SUM(CASE WHEN t.notes LIKE 'Plaid:%' THEN 1 ELSE 0 END) as from_plaid,
                SUM(CASE WHEN t.notes NOT LIKE 'Plaid:%' OR t.notes IS NULL THEN 1 ELSE 0 END) as from_csv,
                MIN(t.date) as earliest,
                MAX(t.date) as latest
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            GROUP BY a.id
            ORDER BY total DESC
        """))
        print(f"  {'Account':25s} {'Inst':15s} {'Total':>6s} {'Plaid':>6s} {'CSV':>6s} {'Earliest':>12s} {'Latest':>12s}")
        print("  " + "-" * 86)
        for row in r.fetchall():
            print(f"  {str(row[0])[:25]:25s} {str(row[1])[:15]:15s} {row[2]:>6d} {row[3]:>6d} {row[4]:>6d} {str(row[5])[:10]:>12s} {str(row[6])[:10]:>12s}")

        print("\n" + "=" * 70)
        print("E. MONTHLY TRANSACTION VOLUME — DEC 2025 SPIKE ANALYSIS")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                a.name,
                COUNT(*) as cnt
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE t.period_year = 2025 AND t.period_month = 12
            GROUP BY a.name
            ORDER BY cnt DESC
        """))
        print(f"  Dec 2025 has 445 transactions. By account:")
        for row in r.fetchall():
            print(f"    {str(row[0])[:35]:35s} {row[1]:>6d}")

asyncio.run(main())
