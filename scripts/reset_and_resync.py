import asyncio
from api.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        # Delete existing Plaid-sourced transactions
        r1 = await session.execute(text("DELETE FROM transactions WHERE notes LIKE 'Plaid:%'"))
        print(f"Deleted {r1.rowcount} Plaid transactions")

        # Reset all cursors so sync starts from scratch
        r2 = await session.execute(text("UPDATE plaid_items SET plaid_cursor = NULL, last_synced_at = NULL"))
        print(f"Reset cursors for {r2.rowcount} items")

        await session.commit()
        print("Done - ready for re-sync")

asyncio.run(main())
