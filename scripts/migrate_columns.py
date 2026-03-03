"""Add new columns to existing tables that were created before the schema update."""
import asyncio
from sqlalchemy import text
from pipeline.utils import create_engine_and_session


ALTER_STATEMENTS = [
    "ALTER TABLE accounts ADD COLUMN default_segment VARCHAR(20)",
    "ALTER TABLE accounts ADD COLUMN default_business_entity_id INTEGER REFERENCES business_entities(id)",
    "ALTER TABLE transactions ADD COLUMN business_entity_id INTEGER REFERENCES business_entities(id)",
    "ALTER TABLE transactions ADD COLUMN business_entity_override INTEGER REFERENCES business_entities(id)",
    "ALTER TABLE transactions ADD COLUMN effective_business_entity_id INTEGER REFERENCES business_entities(id)",
    "ALTER TABLE transactions ADD COLUMN reimbursement_status VARCHAR(20)",
    "ALTER TABLE transactions ADD COLUMN reimbursement_match_id INTEGER REFERENCES transactions(id)",
    "ALTER TABLE retirement_profiles ADD COLUMN current_annual_expenses FLOAT",
    "ALTER TABLE retirement_profiles ADD COLUMN debt_payoffs_json TEXT",
    "ALTER TABLE retirement_profiles ADD COLUMN earliest_retirement_age INTEGER",
]


async def migrate():
    engine, Session = create_engine_and_session()
    async with engine.begin() as conn:
        for stmt in ALTER_STATEMENTS:
            col_name = stmt.split("ADD COLUMN ")[1].split(" ")[0]
            try:
                await conn.execute(text(stmt))
                print(f"  ADDED: {col_name}")
            except Exception:
                print(f"  EXISTS: {col_name}")
    await engine.dispose()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
