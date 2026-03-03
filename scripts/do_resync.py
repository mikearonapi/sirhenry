import asyncio, logging
logging.basicConfig(level=logging.INFO)
from api.database import AsyncSessionLocal
from pipeline.plaid.sync import sync_all_items

async def main():
    async with AsyncSessionLocal() as session:
        result = await sync_all_items(session, run_categorize=False)
        print(result)

asyncio.run(main())
