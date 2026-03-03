"""
Replace all existing vendor rules with the clean set from Claude's deep analysis.
Deactivates all old rules, then inserts the new ones.
"""
import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import text
from pipeline.db import create_vendor_rule, get_all_business_entities, init_db
from pipeline.utils import create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ANALYSIS_FILE = Path(r"c:\ServerData\SirHENRY\scripts\claude_deep_analysis.json")

ENTITY_NAME_TO_DB = {
    "Mike Aron Visuals": "Mike Aron Visuals",
    "Mike Aron AI Consulting": "Mike Aron AI Consulting",
    "AutoRev": "AutoRev",
    "Accenture": "Accenture",
    "Vivant": "Vivant",
}


def parse_date(s):
    if s is None:
        return None
    return date.fromisoformat(s)


async def main():
    with open(ANALYSIS_FILE) as f:
        analysis = json.load(f)

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            # Deactivate ALL existing rules
            await session.execute(text(
                "UPDATE vendor_entity_rules SET is_active=0"
            ))
            logger.info("Deactivated all existing vendor rules.")

            entities = await get_all_business_entities(session, include_inactive=True)
            entity_by_name = {e.name: e.id for e in entities}

            # Insert Claude's clean rules
            new_rules = analysis.get("vendor_rules", [])
            added = 0
            for rule in new_rules:
                entity_name = rule["entity_name"]
                entity_id = entity_by_name.get(entity_name)
                if not entity_id:
                    logger.warning(f"Entity not found: {entity_name}")
                    continue

                await create_vendor_rule(session, {
                    "vendor_pattern": rule["vendor_pattern"],
                    "business_entity_id": entity_id,
                    "segment_override": rule.get("segment"),
                    "effective_from": parse_date(rule.get("effective_from")),
                    "effective_to": parse_date(rule.get("effective_to")),
                    "priority": rule.get("priority", 10),
                })
                added += 1

            # Also add the core income/reimbursement rules that Claude's
            # analysis focused on expenses didn't include
            extra_rules = [
                {
                    "vendor_pattern": "vivant behaviora",
                    "business_entity_id": entity_by_name["Vivant"],
                    "segment_override": None,
                    "priority": 15,
                },
                {
                    "vendor_pattern": "accenture",
                    "business_entity_id": entity_by_name["Accenture"],
                    "segment_override": None,
                    "priority": 15,
                },
                {
                    "vendor_pattern": "upwork",
                    "business_entity_id": entity_by_name["Mike Aron Visuals"],
                    "segment_override": "business",
                    "effective_to": date(2025, 12, 31),
                    "priority": 15,
                },
                {
                    "vendor_pattern": "upwork",
                    "business_entity_id": entity_by_name["AutoRev"],
                    "segment_override": "business",
                    "effective_from": date(2026, 1, 1),
                    "priority": 15,
                },
            ]
            for r in extra_rules:
                await create_vendor_rule(session, r)
                added += 1

            logger.info(f"Inserted {added} new rules.")

    # Print final state
    async with Session() as session:
        r = await session.execute(text(
            "SELECT vr.id, vr.vendor_pattern, be.name, vr.segment_override, "
            "vr.effective_from, vr.effective_to, vr.priority "
            "FROM vendor_entity_rules vr "
            "JOIN business_entities be ON be.id = vr.business_entity_id "
            "WHERE vr.is_active=1 "
            "ORDER BY vr.vendor_pattern, vr.effective_from"
        ))
        rows = r.fetchall()
        logger.info(f"\nFinal active rules: {len(rows)}")
        for row in rows:
            fr = str(row[4]) if row[4] else "any"
            to = str(row[5]) if row[5] else "any"
            seg = row[3] or "-"
            logger.info(f"  {row[1]:<40s} -> {row[2]:<25s} seg={seg:<12s} {fr:>10s} - {to:>10s}  pri={row[6]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
