import asyncio
from api.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        r = await session.execute(text("""
            SELECT
                MIN(date) as earliest,
                MAX(date) as latest,
                COUNT(*) as total,
                period_year,
                period_month
            FROM transactions
            WHERE notes LIKE 'Plaid:%'
            GROUP BY period_year, period_month
            ORDER BY period_year, period_month
        """))
        rows = r.fetchall()
        print(f"{'Year':>6} {'Month':>6} {'Count':>6}")
        print("-" * 22)
        for row in rows:
            print(f"{row[3]:>6} {row[4]:>6} {row[2]:>6}")
        print("-" * 22)

        r2 = await session.execute(text("""
            SELECT MIN(date), MAX(date), COUNT(*)
            FROM transactions WHERE notes LIKE 'Plaid:%'
        """))
        earliest, latest, total = r2.fetchone()
        print(f"Range: {earliest} to {latest} ({total} transactions)")

asyncio.run(main())
