"""
Deep analysis of all business-relevant transactions from June 2025 onward.
Groups expenses by vendor and month to identify the right entity cutover points.
Also looks at pre-June data for Mike Aron Visuals historical expenses.
"""
import json
import os
import pandas as pd
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
import anthropic

load_dotenv()

base = Path(r"c:\ServerData\SirHENRY\data\imports")
mc = base / "Monarch" / "Monarch-Transactions.csv"
df = pd.read_csv(mc, dtype=str)
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
df["Date"] = pd.to_datetime(df["Date"])

# -----------------------------------------------------------------------
# PART 1: All business-tech / Gen AI / Accenture vendors by month
# -----------------------------------------------------------------------
biz_cats = [
    "Business Technology", "Gen AI", "Accenture Expenses", "Accenture Paycheck",
    "Vivant Paycheck",
]
biz_df = df[df["Category"].isin(biz_cats)].copy()

# Also grab anything from Corporate Platinum card
corp_df = df[df["Account"].str.contains("Corporate Platinum", na=False)].copy()

# And any vendor that has a business-tech-ish name
tech_patterns = [
    "cursor", "openai", "anthropic", "vercel", "github", "upwork", "adobe",
    "canva", "godaddy", "midjourney", "wix", "linkedin", "microsoft",
    "elevenlabs", "fliki", "creatify", "bloomberg", "supabase", "claude",
    "hp instant", "google cloud", "google one", "verizon", "notion", "figma",
    "stripe", "aws", "heroku", "netlify", "squarespace",
]
pattern_str = "|".join(tech_patterns)
tech_df = df[df["Merchant"].str.lower().str.contains(pattern_str, na=False)].copy()

# Combine all
all_biz = pd.concat([biz_df, corp_df, tech_df]).drop_duplicates(subset=["Date", "Merchant", "Amount"])
all_biz = all_biz.sort_values(["Date", "Merchant"])

# -----------------------------------------------------------------------
# PART 2: Monthly breakdown by vendor for Jun 2025+
# -----------------------------------------------------------------------
print("=" * 80)
print("BUSINESS-RELEVANT EXPENSES: JUN 2025 ONWARD (by vendor, monthly)")
print("=" * 80)

jun_onward = all_biz[all_biz["Date"] >= "2025-06-01"].copy()
jun_onward["YM"] = jun_onward["Date"].dt.to_period("M").astype(str)

# Group by merchant and month
vendor_monthly = defaultdict(lambda: defaultdict(float))
vendor_counts = defaultdict(int)
vendor_accounts = defaultdict(set)

for _, row in jun_onward.iterrows():
    merchant = row["Merchant"]
    ym = row["YM"]
    amount = row["Amount"]
    vendor_monthly[merchant][ym] += amount
    vendor_counts[merchant] += 1
    vendor_accounts[merchant].add(row["Account"])

# Sort vendors by total spend
vendor_totals = {m: sum(months.values()) for m, months in vendor_monthly.items()}
sorted_vendors = sorted(vendor_totals.items(), key=lambda x: x[1])

for merchant, total in sorted_vendors:
    if abs(total) < 5:
        continue
    months = vendor_monthly[merchant]
    accts = ", ".join(vendor_accounts[merchant])
    count = vendor_counts[merchant]
    print(f"\n  {merchant} ({count} txns, total=${total:,.2f})")
    print(f"    accounts: {accts}")
    for ym in sorted(months.keys()):
        print(f"    {ym}: ${months[ym]:,.2f}")

# -----------------------------------------------------------------------
# PART 3: Pre-June 2025 data for Mike Aron Visuals historical
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("MIKE ARON VISUALS ERA: PRE-JUNE 2025 BUSINESS EXPENSES")
print("=" * 80)

pre_jun = all_biz[
    (all_biz["Date"] < "2025-06-01") &
    (all_biz["Account"] != "Corporate Platinum Card\u00ae (...1002)") &
    (all_biz["Amount"] < 0)
].copy()

if len(pre_jun) > 0:
    pre_vendors = pre_jun.groupby("Merchant").agg(
        count=("Amount", "count"),
        total=("Amount", "sum"),
        last_date=("Date", "max"),
    ).sort_values("total")

    for merchant, row in pre_vendors.iterrows():
        if abs(row["total"]) < 10:
            continue
        print(f"  {merchant}: {int(row['count'])} txns, ${row['total']:,.2f}, last={row['last_date'].strftime('%Y-%m-%d')}")

# -----------------------------------------------------------------------
# PART 4: Build a JSON summary for Claude to reason about entity assignments
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("SENDING TO CLAUDE FOR ENTITY ASSIGNMENT ANALYSIS...")
print("=" * 80)

# Build structured data for Claude
jun_summary = []
for merchant, total in sorted_vendors:
    if abs(total) < 5:
        continue
    months = vendor_monthly[merchant]
    jun_summary.append({
        "merchant": merchant,
        "count": vendor_counts[merchant],
        "total": round(total, 2),
        "accounts": list(vendor_accounts[merchant]),
        "monthly": {k: round(v, 2) for k, v in sorted(months.items())},
    })

pre_summary = []
if len(pre_jun) > 0:
    pre_vendors_df = pre_jun.groupby("Merchant").agg(
        count=("Amount", "count"),
        total=("Amount", "sum"),
        first_date=("Date", "min"),
        last_date=("Date", "max"),
    )
    for merchant, row in pre_vendors_df.iterrows():
        if abs(row["total"]) < 10:
            continue
        pre_summary.append({
            "merchant": merchant,
            "count": int(row["count"]),
            "total": round(row["total"], 2),
            "first": row["first_date"].strftime("%Y-%m-%d"),
            "last": row["last_date"].strftime("%Y-%m-%d"),
        })

prompt = f"""You are a CPA and tax strategist helping structure business entity assignments for 
a household's financial data. The goal is to CORRECTLY assign every business-relevant expense to 
the right entity for tax purposes.

## Entities

1. **Accenture** (id=1) — Mike's W-2 employer. Corporate Amex card is reimbursable.
2. **Mike Aron Visuals** (id=2) — Mike's defunct photography/visual business. Schedule C. 
   No longer operating. Had expenses through ~May 2025. HISTORICAL ONLY.
3. **Vivant** (id=3) — Christine's K-1 partnership. Income only, minimal direct expenses.
4. **Mike Aron AI Consulting** (id=4) — Mike's startup costs entity. Section 195 treatment. 
   Covers expenses from June 2025 through Nov 2025 when Mike was exploring SaaS/AI projects 
   with Cursor before AutoRev was formed. NO REVENUE. Costs only.
5. **AutoRev** (id=5) — Mike's side business. Schedule C. Started Dec 2025. 
   Auto industry SaaS. Some expenses from Dec 2025 onward.

## Key Decision Points

- June-Nov 2025: Mike was building SaaS projects, using Cursor heavily, paying for AI tools. 
  These are startup costs under "Mike Aron AI Consulting" (Section 195).
- Dec 2025: AutoRev officially started. From here, business tool expenses shift to AutoRev.
- The Corporate Platinum Amex is 100% Accenture reimbursable (handled by account defaults).
- Some tools like Adobe, Canva were used for Mike Aron Visuals before June 2025, 
  then could be personal, then business again for AutoRev.
- Verizon is household phone/internet — only partially business use.
- Some vendors are clearly personal (Amazon groceries, etc.) even though they show up 
  in the business technology category in Monarch.

## Business Expenses Jun 2025+ (by vendor, monthly)
{json.dumps(jun_summary, indent=2)}

## Pre-June 2025 Business Expenses (Mike Aron Visuals era)
{json.dumps(pre_summary, indent=2)}

## Your Task

For each vendor that has business-relevant expenses, provide a precise entity assignment rule.
Think carefully about:

1. **Which entity**: Is this Mike Aron Visuals (pre-June), AI Consulting (Jun-Nov), or AutoRev (Dec+)?
2. **Date boundaries**: Exactly when does each vendor transition between entities?
3. **Personal vs business**: Some tools might be personal use (e.g., Adobe for personal photo editing).
   Don't force everything to be business.
4. **The gap period**: Jun-Nov 2025 — tools used for SaaS exploration are Section 195 startup costs
   under Mike Aron AI Consulting. But tools like Adobe that Mike was already paying for personally 
   might just be personal during this period.
5. **Verizon**: Flag but don't auto-assign — needs manual % allocation.
6. **Corporate Amex merchants**: Skip these — account-level default handles them.

Return a JSON object:
{{
  "vendor_rules": [
    {{
      "vendor_pattern": "regex pattern",
      "entity_id": 1-5,
      "entity_name": "name for clarity",
      "segment": "business|personal|reimbursable",
      "effective_from": "YYYY-MM-DD or null",
      "effective_to": "YYYY-MM-DD or null",
      "priority": 0-20,
      "reasoning": "why"
    }}
  ],
  "manual_review_needed": [
    {{
      "merchant": "name",
      "issue": "why manual review needed",
      "suggestion": "what to do"
    }}
  ],
  "personal_vendors": [
    "merchant names that should stay personal even though they appear in biz categories"
  ]
}}

Be PRECISE. Don't create rules for vendors that are clearly personal. 
Only create rules where there's a real business purpose.
Return ONLY the JSON."""

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

output_path = Path(r"c:\ServerData\SirHENRY\scripts\claude_deep_analysis.json")
with open(output_path, "w") as f:
    f.write(raw)

result = json.loads(raw)

print(f"\nVENDOR RULES: {len(result.get('vendor_rules', []))}")
for r in result.get("vendor_rules", []):
    print(f"  {r['vendor_pattern']:<45s} -> {r['entity_name']:<25s} "
          f"seg={r['segment']:<12s} "
          f"from={r.get('effective_from') or 'any':>10s} "
          f"to={r.get('effective_to') or 'any':>10s}  "
          f"pri={r['priority']}")
    print(f"    {r['reasoning']}")

print(f"\nMANUAL REVIEW NEEDED: {len(result.get('manual_review_needed', []))}")
for item in result.get("manual_review_needed", []):
    print(f"  {item['merchant']}: {item['issue']}")
    print(f"    Suggestion: {item['suggestion']}")

print(f"\nPERSONAL VENDORS (skip): {result.get('personal_vendors', [])}")

print(f"\nFull analysis saved to: {output_path}")
