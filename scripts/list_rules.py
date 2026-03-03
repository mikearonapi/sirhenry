"""List all active vendor entity rules."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.db import get_all_vendor_rules, get_all_business_entities, init_db
from pipeline.utils import create_engine_and_session


async def main():
    engine, Session = create_engine_and_session()
    await init_db(engine)
    async with Session() as s:
        rules = await get_all_vendor_rules(s, active_only=True)
        entities = await get_all_business_entities(s, include_inactive=True)
    await engine.dispose()

    emap = {e.id: e.name for e in entities}
    print(f"Total active rules: {len(rules)}\n")
    for r in sorted(rules, key=lambda x: (x.business_entity_id, x.vendor_pattern)):
        ename = emap.get(r.business_entity_id, "?")
        efrom = str(r.effective_from) if r.effective_from else "any"
        eto = str(r.effective_to) if r.effective_to else "ongoing"
        seg = r.segment_override or ""
        print(f"  {r.vendor_pattern:<25s} -> {ename:<30s} seg={seg:<14s} from={efrom:<12s} to={eto:<12s} pri={r.priority}")


asyncio.run(main())
