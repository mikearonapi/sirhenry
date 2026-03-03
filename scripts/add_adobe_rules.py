"""Add missing Adobe vendor entity rules."""
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.db import create_vendor_rule, get_all_business_entities, get_all_vendor_rules, init_db
from pipeline.utils import create_engine_and_session


async def main():
    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        entities = await get_all_business_entities(session, include_inactive=True)
        emap = {e.name: e.id for e in entities}

        ai_id = emap["Mike Aron AI Consulting"]
        autorev_id = emap["AutoRev"]

        new_rules = [
            {
                "vendor_pattern": "adobe",
                "business_entity_id": ai_id,
                "segment_override": "business",
                "effective_from": date(2025, 6, 1),
                "effective_to": date(2025, 11, 30),
                "priority": 10,
            },
            {
                "vendor_pattern": "adobe",
                "business_entity_id": autorev_id,
                "segment_override": "business",
                "effective_from": date(2025, 12, 1),
                "priority": 10,
            },
        ]

        for rule_data in new_rules:
            rule = await create_vendor_rule(session, rule_data)
            ename = "Mike Aron AI Consulting" if rule.business_entity_id == ai_id else "AutoRev"
            print(f"  Created: adobe -> {ename} "
                  f"(from={rule.effective_from}, to={rule.effective_to})")

        await session.commit()

        rules = await get_all_vendor_rules(session, active_only=True)
        print(f"\nTotal active rules: {len(rules)}")

    await engine.dispose()


asyncio.run(main())
