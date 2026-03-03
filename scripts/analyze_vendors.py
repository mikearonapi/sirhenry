"""Quick analysis of vendors across all data sources."""
import pandas as pd
from pathlib import Path
from collections import defaultdict

base = Path(r"c:\ServerData\SirHENRY\data\imports")

# --- Load Monarch ---
mc = base / "Monarch" / "Monarch-Transactions.csv"
df = pd.read_csv(mc, dtype=str)
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
df["Date"] = pd.to_datetime(df["Date"])

# --- Business-relevant keywords ---
biz_keywords = [
    "cursor", "openai", "anthropic", "vercel", "github", "upwork", "adobe",
    "canva", "godaddy", "google cloud", "midjourney", "wix", "linkedin",
    "microsoft", "elevenlabs", "fliki", "creatify", "bloomberg", "supabase",
    "claude", "hp instant", "pdfsimpli", "google one", "figma", "notion",
    "slack", "zoom", "dropbox", "aws", "heroku", "netlify", "stripe",
    "squarespace", "mailchimp", "hubspot", "semrush", "ahrefs",
]

print("=" * 70)
print("BUSINESS-RELEVANT MERCHANTS ACROSS ALL ACCOUNTS")
print("=" * 70)
for kw in sorted(biz_keywords):
    matches = df[df["Merchant"].str.lower().str.contains(kw, na=False)]
    if len(matches) > 0:
        total = matches["Amount"].sum()
        accts = matches["Account"].unique()
        min_date = matches["Date"].min().strftime("%Y-%m")
        max_date = matches["Date"].max().strftime("%Y-%m")
        cats = matches["Category"].unique()
        print(f"\n  {kw}:")
        print(f"    {len(matches)} txns | ${total:,.2f} | {min_date} to {max_date}")
        print(f"    accounts: {', '.join(accts)}")
        print(f"    categories: {', '.join(cats)}")

# --- All unique merchants on Venture card with counts ---
print("\n" + "=" * 70)
print("ALL MERCHANTS ACROSS ALL ACCOUNTS (sorted by frequency)")
print("=" * 70)
all_merchants = df["Merchant"].value_counts()
for m, c in all_merchants.head(60).items():
    total = df[df["Merchant"] == m]["Amount"].sum()
    cats = df[df["Merchant"] == m]["Category"].unique()
    cat_str = ", ".join(cats[:3])
    print(f"  {m}: {c} txns | ${total:,.2f} | {cat_str}")

# --- Date range analysis for cursor/openai/anthropic ---
print("\n" + "=" * 70)
print("CURSOR/OPENAI/ANTHROPIC BY MONTH")
print("=" * 70)
for kw in ["cursor", "openai", "anthropic"]:
    matches = df[df["Merchant"].str.lower().str.contains(kw, na=False)].copy()
    if len(matches) > 0:
        matches["YM"] = matches["Date"].dt.to_period("M")
        monthly = matches.groupby("YM").agg(
            count=("Amount", "count"),
            total=("Amount", "sum"),
        )
        print(f"\n  {kw}:")
        for ym, row in monthly.iterrows():
            print(f"    {ym}: {row['count']} txns, ${row['total']:,.2f}")

# --- Tags analysis ---
print("\n" + "=" * 70)
print("TAGS ANALYSIS")
print("=" * 70)
tags_col = df["Tags"].dropna()
tag_counts = defaultdict(int)
for t in tags_col:
    for tag in str(t).split(","):
        tag = tag.strip()
        if tag and tag.lower() != "nan":
            tag_counts[tag] += 1
for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:20]:
    print(f"  {tag}: {count}")
