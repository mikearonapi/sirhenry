"""
Scan all Monarch transactions for business-relevant vendors that might need rules.
Focuses on: equipment, tech, racing sim, monitors, servers, Apple, office gear.
"""
import pandas as pd
from pathlib import Path

mc = Path(r"c:\ServerData\SirHENRY\data\imports\Monarch\Monarch-Transactions.csv")
df = pd.read_csv(mc, dtype=str)
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
df["Date"] = pd.to_datetime(df["Date"])

keywords = [
    "trak racer", "fanatec", "samsung", "dell", "apple", "mac", "lg ",
    "b&h photo", "best buy", "newegg", "micro center", "adorama",
    "server", "synology", "unraid", "ubiquiti", "unifi",
    "monitor", "ultrawide", "racing", "sim ", "simulator",
    "home depot", "office", "desk", "chair", "steelcase",
    "costco", "amazon", "walmart",
    "shopify", "stripe", "squarespace", "wix",
    "godaddy", "namecheap", "cloudflare", "netlify",
    "aws", "google cloud", "azure", "digitalocean", "linode",
    "supadata", "wolfbox", "privacy bee",
    "rogue", "nuvio", "recovery", "ice barrel",
]

print("=" * 100)
print("POTENTIAL BUSINESS-RELATED TRANSACTIONS (by keyword)")
print("=" * 100)

for kw in keywords:
    matches = df[df["Merchant"].str.lower().str.contains(kw, na=False)]
    if len(matches) == 0:
        continue
    total = matches["Amount"].sum()
    print(f"\n  '{kw}' - {len(matches)} txns, ${total:,.2f}")
    for _, row in matches.sort_values("Date").iterrows():
        date_str = row["Date"].strftime("%Y-%m-%d")
        acct = str(row.get("Account", "")).strip()
        cat = str(row.get("Category", "")).strip()
        merchant = str(row["Merchant"]).strip()
        print(f"    {date_str}  {merchant:<40s} ${row['Amount']:>10,.2f}  cat={cat:<25s} acct={acct}")

# Also look for any Corporate Platinum card transactions that might be travel
print("\n" + "=" * 100)
print("CORPORATE AMEX TRANSACTIONS (should all be reimbursable)")
print("=" * 100)
corp = df[df["Account"].str.contains("Corporate Platinum", na=False)]
print(f"  Total Corp Amex txns: {len(corp)}")
cats = corp.groupby("Category")["Amount"].agg(["sum", "count"]).sort_values("sum")
for cat, row in cats.iterrows():
    print(f"    {cat:<30s}: {int(row['count']):>4d} txns, ${row['sum']:>10,.2f}")

# Look for Uber/Lyft that might be Accenture travel vs personal
print("\n" + "=" * 100)
print("UBER/LYFT TRANSACTIONS (check business vs personal)")
print("=" * 100)
uber = df[df["Merchant"].str.lower().str.contains("uber|lyft", na=False)]
for _, row in uber.sort_values("Date").iterrows():
    date_str = row["Date"].strftime("%Y-%m-%d")
    acct = str(row.get("Account", "")).strip()
    cat = str(row.get("Category", "")).strip()
    merchant = str(row["Merchant"]).strip()
    print(f"  {date_str}  {merchant:<30s} ${row['Amount']:>10,.2f}  cat={cat:<25s} acct={acct}")
