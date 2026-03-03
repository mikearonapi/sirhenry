"""
Add new vendor entity rules based on user context:
- Trak Racer, Fanatec -> AutoRev (2026+ racing simulator business equipment)
- Shopify -> AutoRev (2025-12+ e-commerce platform for business)
- Cloudflare, Netlify, DigitalOcean, Linode -> AI Consulting / AutoRev (hosting)
- Stripe -> AutoRev (payment processing)
- GitHub -> AI Consulting / AutoRev (already covered by Cursor rules but adding explicit)
"""
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
        visuals_id = emap["Mike Aron Visuals"]

        new_rules = [
            # Racing sim gear -> AutoRev (2026+)
            {"vendor_pattern": "trak racer", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2026, 1, 1), "priority": 15},
            {"vendor_pattern": "fanatec", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2026, 1, 1), "priority": 15},

            # Shopify -> AutoRev (Dec 2025+, e-commerce platform)
            {"vendor_pattern": "^Shopify$", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 15},

            # Stripe -> AutoRev (payment processing)
            {"vendor_pattern": "^Stripe$", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 15},

            # Hosting/infra: Jun-Nov 2025 -> AI Consulting, Dec+ -> AutoRev
            {"vendor_pattern": "cloudflare", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "cloudflare", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            {"vendor_pattern": "netlify", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "netlify", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            {"vendor_pattern": "digitalocean", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "digitalocean", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            {"vendor_pattern": "linode|akamai", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "linode|akamai", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            # Namecheap domains
            {"vendor_pattern": "namecheap", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "namecheap", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            # Supadata -> AI Consulting (data scraping/research tool)
            {"vendor_pattern": "supadata", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "supadata", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            # Gamma App -> AI Consulting (AI presentation tool)
            {"vendor_pattern": "gamma app", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "gamma app", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            # GitHub -> AI Consulting / AutoRev (code hosting)
            {"vendor_pattern": "github", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 16},
            {"vendor_pattern": "github", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 17},

            # AWS -> AI Consulting / AutoRev
            {"vendor_pattern": "amazon web services|aws", "business_entity_id": ai_id,
             "segment_override": "business", "effective_from": date(2025, 6, 1),
             "effective_to": date(2025, 11, 30), "priority": 20},
            {"vendor_pattern": "amazon web services|aws", "business_entity_id": autorev_id,
             "segment_override": "business", "effective_from": date(2025, 12, 1), "priority": 20},
        ]

        added = 0
        for rule_data in new_rules:
            rule = await create_vendor_rule(session, rule_data)
            ename = emap.get(rule.business_entity_id, {})
            for name, eid in emap.items():
                if eid == rule.business_entity_id:
                    ename = name
                    break
            efrom = rule.effective_from or "any"
            eto = rule.effective_to or "ongoing"
            print(f"  + {rule.vendor_pattern:<30s} -> {ename:<30s} from={efrom} to={eto}")
            added += 1

        await session.commit()

        rules = await get_all_vendor_rules(session, active_only=True)
        print(f"\nAdded {added} new rules. Total active: {len(rules)}")

    await engine.dispose()


asyncio.run(main())
