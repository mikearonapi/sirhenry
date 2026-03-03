"""Rename Provisional Consulting -> Mike Aron AI Consulting."""
import asyncio
from sqlalchemy import text
from pipeline.utils import create_engine_and_session


async def rename():
    engine, Session = create_engine_and_session()
    async with Session() as s:
        async with s.begin():
            await s.execute(text(
                "UPDATE business_entities SET name='Mike Aron AI Consulting', "
                "notes='Startup costs (Section 195) for SaaS/AI consulting work. "
                "June 2025 onward, no revenue.' "
                "WHERE name='Provisional Consulting'"
            ))
            r = await s.execute(text(
                "SELECT id, name, entity_type, tax_treatment, is_provisional, "
                "is_active, active_from, active_to FROM business_entities ORDER BY id"
            ))
            for row in r.fetchall():
                print(f"  id={row[0]}  {row[1]:<30s}  type={row[2]:<12s}  "
                      f"tax={row[3]:<12s}  prov={row[4]}  active={row[5]}  "
                      f"from={row[6]}  to={row[7]}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(rename())
