"""
Apply the Claude-recommended vendor rules and account defaults to the database.
Deduplicates against existing rules by vendor_pattern + entity + date range.
"""
import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from pipeline.db import (
    create_vendor_rule,
    get_all_business_entities,
    get_all_vendor_rules,
    init_db,
    upsert_account,
)
from pipeline.db.schema import Account
from pipeline.utils import create_engine_and_session
from sqlalchemy import select, update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ENTITY_NAME_MAP = {
    "vivant": "Vivant",
    "accenture": "Accenture",
    "mike_aron_visuals": "Mike Aron Visuals",
    "autorev": "AutoRev",
    "provisional_consulting": "Provisional Consulting",
}

RULES_FILE = Path(r"c:\ServerData\SirHENRY\scripts\claude_rule_analysis.json")


def parse_date(s):
    if s is None:
        return None
    return date.fromisoformat(s)


async def main():
    with open(RULES_FILE) as f:
        analysis = json.load(f)

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            entities = await get_all_business_entities(session, include_inactive=True)
            entity_by_name = {e.name: e.id for e in entities}

            existing_rules = await get_all_vendor_rules(session, active_only=False)
            existing_set = set()
            for r in existing_rules:
                key = (r.vendor_pattern, r.business_entity_id,
                       str(r.effective_from), str(r.effective_to))
                existing_set.add(key)

            new_rules = analysis.get("new_vendor_rules", [])
            added = 0
            skipped = 0

            for rule_data in new_rules:
                raw_entity = rule_data["entity_name"]
                entity_name = ENTITY_NAME_MAP.get(raw_entity, raw_entity)
                entity_id = entity_by_name.get(entity_name)
                if not entity_id:
                    logger.warning(f"Entity not found: {entity_name} (raw: {raw_entity})")
                    skipped += 1
                    continue

                pattern = rule_data["vendor_pattern"]
                eff_from = parse_date(rule_data.get("effective_from"))
                eff_to = parse_date(rule_data.get("effective_to"))
                priority = rule_data.get("priority", 0)
                segment = rule_data.get("segment_override")

                key = (pattern, entity_id, str(eff_from), str(eff_to))
                if key in existing_set:
                    logger.info(f"  SKIP (exists): {pattern} -> {entity_name}")
                    skipped += 1
                    continue

                await create_vendor_rule(session, {
                    "vendor_pattern": pattern,
                    "business_entity_id": entity_id,
                    "segment_override": segment,
                    "effective_from": eff_from,
                    "effective_to": eff_to,
                    "priority": priority,
                })
                existing_set.add(key)
                added += 1
                logger.info(
                    f"  ADD: {pattern} -> {entity_name} ({segment}) "
                    f"[{eff_from or 'any'} to {eff_to or 'any'}]"
                )

            logger.info(f"\nRules: {added} added, {skipped} skipped")

            # Set account defaults for Corporate Platinum
            # Find the account by pattern match once imported
            acct_result = await session.execute(
                select(Account).where(Account.name.contains("Corporate"))
            )
            corp_acct = acct_result.scalar_one_or_none()
            if corp_acct:
                accenture_id = entity_by_name.get("Accenture")
                corp_acct.default_segment = "reimbursable"
                corp_acct.default_business_entity_id = accenture_id
                logger.info(
                    f"Set account defaults: {corp_acct.name} -> "
                    f"reimbursable / Accenture (id={accenture_id})"
                )
            else:
                logger.info(
                    "Corporate Platinum account not yet imported. "
                    "Defaults will be set when Monarch/CC import creates it."
                )

    # Print final summary
    async with Session() as session:
        all_rules = await get_all_vendor_rules(session, active_only=True)
        logger.info(f"\nTotal active vendor rules: {len(all_rules)}")
        for r in all_rules:
            entity = entity_by_name
            ename = next((k for k, v in entity_by_name.items() if v == r.business_entity_id), "?")
            logger.info(
                f"  {r.vendor_pattern:40s} -> {ename:25s} "
                f"seg={r.segment_override or 'none':12s} "
                f"from={r.effective_from or 'any':>10s}  to={r.effective_to or 'any':>10s}  "
                f"pri={r.priority}"
            )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
