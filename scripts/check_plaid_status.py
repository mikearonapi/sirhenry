import asyncio
from api.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT id, institution_name, plaid_cursor, last_synced_at FROM plaid_items"))
        for row in result.fetchall():
            print(row)
        print("---")
        result2 = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE notes LIKE 'Plaid:%'"))
        print("Plaid transactions:", result2.scalar())
        result3 = await session.execute(text("SELECT COUNT(*) FROM transactions"))
        print("Total transactions:", result3.scalar())

asyncio.run(main())
