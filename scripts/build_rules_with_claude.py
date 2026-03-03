"""
Analyze all transaction data and use Claude to recommend comprehensive
vendor entity rules and categorization improvements.
"""
import json
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

base = Path(r"c:\ServerData\SirHENRY\data\imports")

# --- Load Monarch ---
mc = base / "Monarch" / "Monarch-Transactions.csv"
df = pd.read_csv(mc, dtype=str)
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
df["Date"] = pd.to_datetime(df["Date"])

# --- Build merchant summary ---
merchant_data = []
for merchant, group in df.groupby("Merchant"):
    cats = group["Category"].value_counts().to_dict()
    accts = group["Account"].unique().tolist()
    dates = {
        "first": group["Date"].min().strftime("%Y-%m-%d"),
        "last": group["Date"].max().strftime("%Y-%m-%d"),
    }
    total = group["Amount"].sum()
    merchant_data.append({
        "merchant": merchant,
        "count": len(group),
        "total": round(total, 2),
        "categories": cats,
        "accounts": accts,
        "date_range": dates,
    })

# Sort by frequency
merchant_data.sort(key=lambda x: x["count"], reverse=True)

# Top 100 merchants + all business-tech/AI merchants
top_merchants = merchant_data[:100]
biz_merchants = [m for m in merchant_data if any(
    cat in str(m["categories"])
    for cat in ["Business Technology", "Gen AI", "Accenture", "Vivant"]
)]
# Combine and dedupe
seen = set()
combined = []
for m in top_merchants + biz_merchants:
    if m["merchant"] not in seen:
        combined.append(m)
        seen.add(m["merchant"])

# --- Account summary ---
account_summary = {}
for acct, group in df.groupby("Account"):
    account_summary[acct] = {
        "count": len(group),
        "total_debits": round(group[group["Amount"] < 0]["Amount"].sum(), 2),
        "total_credits": round(group[group["Amount"] > 0]["Amount"].sum(), 2),
        "categories": group["Category"].value_counts().head(5).to_dict(),
    }

prompt = f"""You are a senior CPA and financial data architect. I need you to analyze my household's 
transaction data and recommend a comprehensive set of vendor-entity mapping rules.

## Household Context
- **Mike**: W-2 employee at Accenture (management consulting, multi-state travel). Uses Corporate 
  Platinum Amex for work expenses (reimbursed). Started building SaaS projects with Cursor in June 2025.
  Launched AutoRev as a side business in Dec 2025. Previously ran Mike Aron Visuals (photography, defunct).
- **Christine**: Partner in Vivant Behavioral Healthcare (K-1 income). Receives regular payments from Vivant.
- **Accounts**: Budget (checking), Venture (Capital One credit card, primary spending), Corporate Platinum 
  (Accenture Amex), Mike/Christine Discretionary, various savings accounts.
- **Filing**: MFJ. Focus is 2025 tax year.

## Business Entities in System
1. **Accenture** (employer/W-2) — Mike's employer
2. **Mike Aron Visuals** (sole_prop/schedule_c) — defunct, ended May 2025
3. **Vivant** (partnership/K-1) — Christine's partnership
4. **Provisional Consulting** (sole_prop/section_195) — startup costs Jun-Nov 2025
5. **AutoRev** (sole_prop/schedule_c) — started Dec 2025

## Existing Vendor Rules (12)
- cursor, anthropic, openai, vercel, github → Provisional Consulting (Jun-Nov 2025) then AutoRev (Dec 2025+)
- upwork → Mike Aron Visuals (before 2026), AutoRev (2026+)

## Account Data
{json.dumps(account_summary, indent=2, default=str)}

## Merchant Data (top merchants + all business-relevant)
{json.dumps(combined, indent=2, default=str)}

## Tasks

### 1. VENDOR ENTITY RULES
Recommend additional vendor-entity rules beyond the existing 12. For each rule provide:
- `vendor_pattern`: regex-friendly pattern (lowercase)
- `entity_name`: which business entity
- `segment_override`: personal | business | investment | reimbursable
- `effective_from`: date or null
- `effective_to`: date or null  
- `priority`: 0-20 (higher = takes precedence)
- `reasoning`: why this rule exists

Consider:
- Corporate Platinum card should ALL be reimbursable/Accenture (account-level default handles this, but 
  are there any vendor-specific overrides needed?)
- Dev tools on Venture card: which are business vs personal? (e.g., is Google One personal or business?)
- Vivant payments to Christine
- Recurring subscriptions that could be partially business
- Travel merchants that appear on both Corp Amex and personal cards
- Time-based transitions (MAV → Provisional → AutoRev)

### 2. ACCOUNT-LEVEL DEFAULTS
Recommend `default_segment` and `default_business_entity` for each account:
- Corporate Platinum Card → reimbursable + Accenture
- Others?

### 3. CATEGORIZATION CONCERNS
Flag any merchants that are miscategorized or ambiguous. For example:
- Cursor transactions showing as "Gas" or "Restaurants & Bars" (misclassified)
- Merchants that could be split between personal and business

### 4. DEDUCTION OPPORTUNITIES
Flag any merchants/patterns that suggest missed tax deductions for 2025:
- Home office supplies?
- Professional development?
- Business meals?
- Phone/internet (partial business use)?

Return a JSON object with these keys:
{{
  "new_vendor_rules": [...],
  "account_defaults": {{...}},
  "categorization_issues": [...],
  "deduction_opportunities": [...]
}}

Return ONLY the JSON, no other text."""

print("Calling Claude API for vendor rule analysis...")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
    max_tokens=8192,
    messages=[{"role": "user", "content": prompt}],
)

raw = response.content[0].text.strip()
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
    raw = raw.strip()

# Save raw response
output_path = Path(r"c:\ServerData\SirHENRY\scripts\claude_rule_analysis.json")
with open(output_path, "w") as f:
    f.write(raw)

result = json.loads(raw)

print(f"\n{'='*70}")
print(f"NEW VENDOR RULES: {len(result.get('new_vendor_rules', []))}")
print(f"{'='*70}")
for rule in result.get("new_vendor_rules", []):
    print(f"  {rule['vendor_pattern']} -> {rule['entity_name']} "
          f"({rule.get('segment_override', 'N/A')}) "
          f"[{rule.get('effective_from', 'any')}-{rule.get('effective_to', 'any')}]")
    print(f"    Reason: {rule.get('reasoning', '')}")

print(f"\n{'='*70}")
print(f"ACCOUNT DEFAULTS")
print(f"{'='*70}")
for acct, defaults in result.get("account_defaults", {}).items():
    print(f"  {acct}: {defaults}")

print(f"\n{'='*70}")
print(f"CATEGORIZATION ISSUES: {len(result.get('categorization_issues', []))}")
print(f"{'='*70}")
for issue in result.get("categorization_issues", []):
    print(f"  - {issue}")

print(f"\n{'='*70}")
print(f"DEDUCTION OPPORTUNITIES: {len(result.get('deduction_opportunities', []))}")
print(f"{'='*70}")
for opp in result.get("deduction_opportunities", []):
    print(f"  - {opp}")

print(f"\nFull analysis saved to: {output_path}")
