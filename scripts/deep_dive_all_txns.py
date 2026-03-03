"""
Deep dive analysis across ALL 5,810 Monarch transactions.
Identifies anomalies, miscategorizations, and entity assignment gaps.
Uses Claude to flag issues.
"""
import json
import os
import re
import pandas as pd
from pathlib import Path
from collections import defaultdict
from datetime import date
from dotenv import load_dotenv
import anthropic

load_dotenv()

base = Path(r"c:\ServerData\SirHENRY\data\imports")
mc = base / "Monarch" / "Monarch-Transactions.csv"
df = pd.read_csv(mc, dtype=str)
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
df["Date"] = pd.to_datetime(df["Date"])

# Load the active vendor rules from the DB
import asyncio
import sys
sys.path.insert(0, str(Path(r"c:\ServerData\SirHENRY")))
from pipeline.db import get_all_vendor_rules, get_all_business_entities, init_db
from pipeline.utils import create_engine_and_session


async def load_rules():
    engine, Session = create_engine_and_session()
    await init_db(engine)
    async with Session() as s:
        rules = await get_all_vendor_rules(s, active_only=True)
        entities = await get_all_business_entities(s, include_inactive=True)
    await engine.dispose()
    return rules, entities


rules, entities = asyncio.run(load_rules())
emap = {e.id: e.name for e in entities}


def match_entity(merchant, tx_date):
    """Simulate entity rule matching."""
    for rule in sorted(rules, key=lambda r: -r.priority):
        if rule.effective_from and tx_date < rule.effective_from:
            continue
        if rule.effective_to and tx_date > rule.effective_to:
            continue
        if re.search(rule.vendor_pattern, merchant, re.IGNORECASE):
            return emap.get(rule.business_entity_id, "?"), rule.segment_override
    return None, None


# Tag every transaction with entity
results = []
for _, row in df.iterrows():
    merchant = str(row["Merchant"]).strip()
    tx_date = row["Date"].date()
    amount = row["Amount"]
    category = str(row["Category"]).strip()
    account = str(row["Account"]).strip()
    entity, seg_override = match_entity(merchant, tx_date)

    is_corp = "Corporate Platinum" in account
    if is_corp:
        entity = "Accenture"
        seg_override = "reimbursable"

    results.append({
        "merchant": merchant,
        "date": str(tx_date),
        "amount": round(amount, 2),
        "category": category,
        "account": account,
        "matched_entity": entity,
        "segment_override": seg_override,
    })

results_df = pd.DataFrame(results)

# -----------------------------------------------------------------------
# ANALYSIS 1: Unmatched business-looking expenses
# -----------------------------------------------------------------------
print("=" * 80)
print("UNMATCHED EXPENSES (no entity rule, not Corp Amex, amount < -$10)")
print("=" * 80)

unmatched = results_df[
    (results_df["matched_entity"].isna()) &
    (results_df["amount"] < -10)
].copy()

# Group by category then merchant
cat_groups = unmatched.groupby("category")
suspicious_cats = [
    "Business Technology", "Gen AI", "Uncategorized", "Transfer",
]
for cat in suspicious_cats:
    if cat in cat_groups.groups:
        group = cat_groups.get_group(cat)
        print(f"\n  Category: {cat} ({len(group)} unmatched txns)")
        for m, mg in group.groupby("merchant"):
            total = mg["amount"].sum()
            print(f"    {m}: {len(mg)} txns, ${total:,.2f}")

# -----------------------------------------------------------------------
# ANALYSIS 2: Transactions with mismatched categories
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("ENTITY-ASSIGNED BUT STRANGE CATEGORY")
print("=" * 80)

matched = results_df[results_df["matched_entity"].notna()].copy()
for _, row in matched.iterrows():
    entity = row["matched_entity"]
    cat = row["category"]
    amount = row["amount"]
    if entity in ["Accenture", "Vivant"] and amount > 0:
        continue  # income is fine
    # Flag business expenses with personal categories
    if entity not in ["Accenture", "Vivant"] and row["segment_override"] == "business":
        personal_cats = [
            "Transfer", "Gas", "Restaurants & Bars", "Groceries", "Shopping",
            "Fast Food", "Coffee Shops",
        ]
        if cat in personal_cats:
            print(f"  {row['date']} {row['merchant']:<35s} ${row['amount']:>10,.2f}  "
                  f"cat={cat:<25s} entity={entity}")

# -----------------------------------------------------------------------
# ANALYSIS 3: Large unmatched transactions
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("LARGE UNMATCHED TRANSACTIONS (>$500 or <-$500)")
print("=" * 80)

large_unmatched = results_df[
    (results_df["matched_entity"].isna()) &
    ((results_df["amount"] > 500) | (results_df["amount"] < -500))
].copy()
large_unmatched = large_unmatched.sort_values("amount")

for _, row in large_unmatched.iterrows():
    print(f"  {row['date']} {row['merchant']:<35s} ${row['amount']:>10,.2f}  "
          f"cat={row['category']:<25s} acct={row['account']}")

# -----------------------------------------------------------------------
# ANALYSIS 4: Summary stats
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
total = len(results_df)
matched_count = results_df["matched_entity"].notna().sum()
unmatched_count = results_df["matched_entity"].isna().sum()
print(f"  Total transactions: {total}")
print(f"  Matched to entity: {matched_count} ({matched_count/total*100:.1f}%)")
print(f"  Unmatched (personal): {unmatched_count} ({unmatched_count/total*100:.1f}%)")

print("\n  By entity:")
for entity, group in results_df.groupby("matched_entity"):
    if pd.isna(entity):
        continue
    total_amt = group["amount"].sum()
    print(f"    {entity:<30s}: {len(group):>5d} txns, ${total_amt:>12,.2f}")

print(f"\n  Unmatched (personal) total: {unmatched_count} txns, "
      f"${results_df[results_df['matched_entity'].isna()]['amount'].sum():,.2f}")

# -----------------------------------------------------------------------
# ANALYSIS 5: Send edge cases to Claude
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("SENDING EDGE CASES TO CLAUDE FOR REVIEW...")
print("=" * 80)

# Collect all the questionable items
edge_cases = []

# Business-category but unmatched
for cat in ["Business Technology", "Gen AI"]:
    if cat in cat_groups.groups:
        group = cat_groups.get_group(cat)
        for _, row in group.iterrows():
            edge_cases.append({
                "merchant": row["merchant"],
                "date": row["date"],
                "amount": row["amount"],
                "category": row["category"],
                "account": row["account"],
                "issue": f"Categorized as '{cat}' but no entity rule matched",
            })

# Wrong-looking categories on matched transactions
for _, row in matched.iterrows():
    entity = row["matched_entity"]
    cat = row["category"]
    if entity not in ["Accenture", "Vivant"] and row["segment_override"] == "business":
        if cat in ["Transfer", "Gas", "Restaurants & Bars"]:
            edge_cases.append({
                "merchant": row["merchant"],
                "date": row["date"],
                "amount": row["amount"],
                "category": row["category"],
                "entity": entity,
                "issue": f"Matched to {entity} but category is '{cat}' which looks wrong",
            })

prompt = f"""You are a CPA reviewing transaction categorizations for accuracy. 
Here are edge cases that need human review.

## Business Entities
1. Accenture — W-2 employer (Corp Amex = reimbursable)
2. Mike Aron Visuals — defunct photography business (pre-June 2025)
3. Vivant — Christine's K-1 partnership
4. Mike Aron AI Consulting — Section 195 startup costs (June-Nov 2025)
5. AutoRev — new Schedule C business (Dec 2025+)

## Edge Cases to Review
{json.dumps(edge_cases, indent=2)}

For each edge case, provide:
1. Is this correctly categorized or does it need fixing?
2. If it needs an entity, which one?
3. What should the correct category be?
4. Any new vendor rules we should add?

Return JSON:
{{
  "reviews": [
    {{
      "merchant": "...",
      "date": "...", 
      "verdict": "correct|needs_fix|needs_rule|personal",
      "correct_category": "...",
      "correct_entity": "entity name or null",
      "reasoning": "..."
    }}
  ],
  "new_rules_needed": [
    {{
      "vendor_pattern": "...",
      "entity_name": "...",
      "segment": "...",
      "effective_from": "...",
      "effective_to": "...",
      "reasoning": "..."
    }}
  ]
}}

Return ONLY JSON."""

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
    max_tokens=8192,
    messages=[{"role": "user", "content": prompt}],
)

raw = response.content[0].text.strip()
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
    raw = raw.strip()

output = Path(r"c:\ServerData\SirHENRY\scripts\claude_edge_case_review.json")
with open(output, "w") as f:
    f.write(raw)

review = json.loads(raw)

verdicts = defaultdict(int)
for r in review.get("reviews", []):
    verdicts[r["verdict"]] += 1
    if r["verdict"] != "correct":
        print(f"  {r['merchant']} ({r['date']}): {r['verdict']}")
        print(f"    {r['reasoning']}")
        if r.get("correct_entity"):
            print(f"    -> entity: {r['correct_entity']}")
        if r.get("correct_category"):
            print(f"    -> category: {r['correct_category']}")

print(f"\nVerdicts: {dict(verdicts)}")

new_rules = review.get("new_rules_needed", [])
if new_rules:
    print(f"\nNew rules recommended: {len(new_rules)}")
    for nr in new_rules:
        print(f"  {nr['vendor_pattern']} -> {nr['entity_name']} ({nr.get('reasoning', '')})")

print(f"\nFull review saved to: {output}")
