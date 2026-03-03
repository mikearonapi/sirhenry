"""
Seed business entities and vendor entity rules.

Usage:
    python -m pipeline.seed_entities
"""
import asyncio
import logging
from datetime import date

from pipeline.db import (
    create_vendor_rule,
    init_db,
    upsert_business_entity,
)
from pipeline.utils import create_engine_and_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ENTITIES = [
    {
        "name": "Accenture",
        "owner": "Mike",
        "entity_type": "employer",
        "tax_treatment": "w2",
        "is_active": True,
        "is_provisional": False,
        "notes": "W-2 employer, management consulting. Corporate Amex reimbursed.",
    },
    {
        "name": "Mike Aron Visuals",
        "owner": "Mike",
        "entity_type": "sole_prop",
        "tax_treatment": "schedule_c",
        "is_active": False,
        "is_provisional": False,
        "active_to": date(2025, 5, 31),
        "notes": "Defunct photography/visual business. No longer operating.",
    },
    {
        "name": "Vivant",
        "owner": "Christine",
        "entity_type": "partnership",
        "tax_treatment": "k1",
        "is_active": True,
        "is_provisional": False,
        "notes": "Christine's K-1 partnership income.",
    },
    {
        "name": "Mike Aron AI Consulting",
        "owner": "Mike",
        "entity_type": "sole_prop",
        "tax_treatment": "section_195",
        "is_active": True,
        "is_provisional": True,
        "active_from": date(2025, 6, 1),
        "active_to": date(2025, 11, 30),
        "notes": "Startup costs (Section 195) for SaaS/AI consulting work. June-Nov 2025, no revenue.",
    },
    {
        "name": "AutoRev",
        "owner": "Mike",
        "entity_type": "sole_prop",
        "tax_treatment": "schedule_c",
        "is_active": True,
        "is_provisional": False,
        "active_from": date(2025, 12, 1),
        "notes": "Side business for auto industry SaaS. Schedule C, no revenue yet.",
    },
]

VENDOR_RULES = [
    # AutoRev / Provisional dev tools
    {"vendor_pattern": "cursor", "entity_name": "Mike Aron AI Consulting", "segment_override": "business",
     "effective_from": date(2025, 6, 1), "effective_to": date(2025, 11, 30), "priority": 10},
    {"vendor_pattern": "cursor", "entity_name": "AutoRev", "segment_override": "business",
     "effective_from": date(2025, 12, 1), "priority": 10},
    {"vendor_pattern": "anthropic", "entity_name": "Mike Aron AI Consulting", "segment_override": "business",
     "effective_from": date(2025, 6, 1), "effective_to": date(2025, 11, 30), "priority": 10},
    {"vendor_pattern": "anthropic", "entity_name": "AutoRev", "segment_override": "business",
     "effective_from": date(2025, 12, 1), "priority": 10},
    {"vendor_pattern": "openai", "entity_name": "Mike Aron AI Consulting", "segment_override": "business",
     "effective_from": date(2025, 6, 1), "effective_to": date(2025, 11, 30), "priority": 10},
    {"vendor_pattern": "openai", "entity_name": "AutoRev", "segment_override": "business",
     "effective_from": date(2025, 12, 1), "priority": 10},
    {"vendor_pattern": "vercel", "entity_name": "Mike Aron AI Consulting", "segment_override": "business",
     "effective_from": date(2025, 6, 1), "effective_to": date(2025, 11, 30), "priority": 10},
    {"vendor_pattern": "vercel", "entity_name": "AutoRev", "segment_override": "business",
     "effective_from": date(2025, 12, 1), "priority": 10},
    {"vendor_pattern": "github", "entity_name": "Mike Aron AI Consulting", "segment_override": "business",
     "effective_from": date(2025, 6, 1), "effective_to": date(2025, 11, 30), "priority": 10},
    {"vendor_pattern": "github", "entity_name": "AutoRev", "segment_override": "business",
     "effective_from": date(2025, 12, 1), "priority": 10},

    # Upwork transitions
    {"vendor_pattern": "upwork", "entity_name": "Mike Aron Visuals", "segment_override": "business",
     "effective_to": date(2025, 12, 31), "priority": 10},
    {"vendor_pattern": "upwork", "entity_name": "AutoRev", "segment_override": "business",
     "effective_from": date(2026, 1, 1), "priority": 10},
]


async def seed():
    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            entity_id_map: dict[str, int] = {}
            for data in ENTITIES:
                entity = await upsert_business_entity(session, data)
                entity_id_map[entity.name] = entity.id
                logger.info(f"Entity: {entity.name} (id={entity.id})")

            for rule_data in VENDOR_RULES:
                entity_name = rule_data.pop("entity_name")
                entity_id = entity_id_map.get(entity_name)
                if not entity_id:
                    logger.warning(f"Entity not found for rule: {entity_name}")
                    continue
                rule_data["business_entity_id"] = entity_id
                rule = await create_vendor_rule(session, rule_data)
                logger.info(
                    f"Rule: '{rule.vendor_pattern}' -> {entity_name} "
                    f"({rule.effective_from or 'any'} to {rule.effective_to or 'any'})"
                )

    await engine.dispose()
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
