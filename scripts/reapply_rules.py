"""Re-apply all entity rules to all transactions in the DB."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.db import apply_entity_rules, get_all_business_entities, init_db
from pipeline.utils import create_engine_and_session
from sqlalchemy import select, func
from pipeline.db.schema import Transaction


async def main():
    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        # Count before
        result = await session.execute(
            select(func.count(Transaction.id)).where(Transaction.effective_business_entity_id.isnot(None))
        )
        before = result.scalar()
        print(f"Transactions with entity BEFORE: {before}")

        # Apply rules
        updated = await apply_entity_rules(session)
        print(f"Rules applied, {updated} transactions updated")

        await session.commit()

        # Count after
        result = await session.execute(
            select(func.count(Transaction.id)).where(Transaction.effective_business_entity_id.isnot(None))
        )
        after = result.scalar()
        print(f"Transactions with entity AFTER: {after}")

        # Summary by entity
        entities = await get_all_business_entities(session, include_inactive=True)
        emap = {e.id: e.name for e in entities}

        result = await session.execute(
            select(
                Transaction.effective_business_entity_id,
                func.count(Transaction.id),
                func.sum(Transaction.amount),
            )
            .where(Transaction.effective_business_entity_id.isnot(None))
            .group_by(Transaction.effective_business_entity_id)
        )
        rows = result.all()
        print("\nEntity assignment summary:")
        for eid, cnt, total in rows:
            name = emap.get(eid, f"entity_{eid}")
            print(f"  {name:<30s}: {cnt:>5d} txns, ${total:>12,.2f}")

        # Count by segment
        result = await session.execute(
            select(
                Transaction.effective_segment,
                func.count(Transaction.id),
            )
            .group_by(Transaction.effective_segment)
        )
        rows = result.all()
        print("\nSegment summary:")
        for seg, cnt in rows:
            print(f"  {seg or 'null':<15s}: {cnt:>5d} txns")

    await engine.dispose()


asyncio.run(main())
