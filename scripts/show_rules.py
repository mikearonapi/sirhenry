"""Display all vendor entity rules in the database."""
import asyncio
from pipeline.utils import create_engine_and_session
from pipeline.db import get_all_vendor_rules, get_all_business_entities, init_db


async def show():
    engine, Session = create_engine_and_session()
    await init_db(engine)
    async with Session() as s:
        rules = await get_all_vendor_rules(s)
        entities = await get_all_business_entities(s, include_inactive=True)
        emap = {e.id: e.name for e in entities}

        print(f"Total vendor rules: {len(rules)}")
        print(f"Total entities: {len(entities)}")
        print()

        by_entity = {}
        for r in rules:
            ename = emap.get(r.business_entity_id, "?")
            by_entity.setdefault(ename, []).append(r)

        for ename in sorted(by_entity.keys()):
            erules = by_entity[ename]
            print(f"--- {ename} ({len(erules)} rules) ---")
            for r in erules:
                seg = r.segment_override or "-"
                fr = str(r.effective_from) if r.effective_from else "any"
                to = str(r.effective_to) if r.effective_to else "any"
                print(f"  {r.vendor_pattern:<45s} seg={seg:<12s} {fr:>10s} - {to:>10s}  pri={r.priority}")
            print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(show())
