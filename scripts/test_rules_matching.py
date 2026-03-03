"""Test that the vendor rules actually match real Monarch merchant names."""
import re
import asyncio
import pandas as pd
from pathlib import Path
from datetime import date

from pipeline.db import get_all_vendor_rules, get_all_business_entities, init_db
from pipeline.utils import create_engine_and_session


async def test():
    engine, Session = create_engine_and_session()
    await init_db(engine)

    # Load actual merchants
    mc = Path(r"c:\ServerData\SirHENRY\data\imports\Monarch\Monarch-Transactions.csv")
    df = pd.read_csv(mc, dtype=str)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

    async with Session() as session:
        rules = await get_all_vendor_rules(session, active_only=True)
        entities = await get_all_business_entities(session, include_inactive=True)
        emap = {e.id: e.name for e in entities}

    # Test each rule against actual data
    print("RULE MATCHING TEST")
    print("=" * 80)
    total_matched = 0
    total_amount = 0.0

    for rule in sorted(rules, key=lambda r: r.vendor_pattern):
        pattern = rule.vendor_pattern.lower()
        entity_name = emap.get(rule.business_entity_id, "?")
        fr = rule.effective_from
        to = rule.effective_to

        matched = []
        for _, row in df.iterrows():
            merchant = str(row["Merchant"]).strip()
            tx_date = row["Date"].date()

            if fr and tx_date < fr:
                continue
            if to and tx_date > to:
                continue

            if re.search(pattern, merchant, re.IGNORECASE):
                matched.append({
                    "merchant": merchant,
                    "date": str(tx_date),
                    "amount": row["Amount"],
                    "account": row["Account"],
                })

        if matched:
            match_total = sum(m["amount"] for m in matched)
            total_matched += len(matched)
            total_amount += match_total
            print(f"\n  {rule.vendor_pattern} -> {entity_name}")
            print(f"    Dates: {fr or 'any'} to {to or 'any'}")
            print(f"    Matched: {len(matched)} txns, ${match_total:,.2f}")
            unique_merchants = set(m["merchant"] for m in matched)
            for um in sorted(unique_merchants):
                count = sum(1 for m in matched if m["merchant"] == um)
                print(f"      {um}: {count} txns")
        else:
            print(f"\n  {rule.vendor_pattern} -> {entity_name}")
            print(f"    Dates: {fr or 'any'} to {to or 'any'}")
            print(f"    NO MATCHES (rule may need adjustment)")

    print(f"\n{'='*80}")
    print(f"TOTAL: {total_matched} transactions matched, ${total_amount:,.2f}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test())
