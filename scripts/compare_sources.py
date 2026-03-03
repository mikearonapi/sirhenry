"""
Compare Monarch CSV vs Credit Card CSV data richness.
Show actual field content side-by-side for the same transactions.
"""
import pandas as pd
from pathlib import Path

base = Path(r"c:\ServerData\SirHENRY\data\imports")

# Read Monarch
mc = base / "Monarch" / "Monarch-Transactions.csv"
mdf = pd.read_csv(mc, dtype=str)
print("=" * 100)
print("MONARCH CSV COLUMNS")
print("=" * 100)
for col in mdf.columns:
    non_null = mdf[col].notna().sum()
    sample = mdf[col].dropna().iloc[0] if non_null > 0 else "N/A"
    if len(str(sample)) > 80:
        sample = str(sample)[:80] + "..."
    print(f"  {col:<30s}  {non_null:>5d}/{len(mdf)} non-null  sample: {sample}")

# Read a Capital One CSV
print("\n" + "=" * 100)
print("CAPITAL ONE CSV COLUMNS (Family-Capital-One-2025.csv)")
print("=" * 100)
co = pd.read_csv(base / "credit-cards" / "Family-Capital-One-2025.csv", dtype=str)
for col in co.columns:
    non_null = co[col].notna().sum()
    sample = co[col].dropna().iloc[0] if non_null > 0 else "N/A"
    if len(str(sample)) > 80:
        sample = str(sample)[:80] + "..."
    print(f"  {col:<30s}  {non_null:>5d}/{len(co)} non-null  sample: {sample}")

# Read an Amex CSV
print("\n" + "=" * 100)
print("AMEX CSV COLUMNS (Personal-Amex-2025.csv)")
print("=" * 100)
ax = pd.read_csv(base / "credit-cards" / "Personal-Amex-2025.csv", dtype=str)
for col in ax.columns:
    non_null = ax[col].notna().sum()
    sample = ax[col].dropna().iloc[0] if non_null > 0 else "N/A"
    if len(str(sample)) > 80:
        sample = str(sample)[:80] + "..."
    print(f"  {col:<30s}  {non_null:>5d}/{len(ax)} non-null  sample: {sample}")

print("\n" + "=" * 100)
print("AMEX CSV COLUMNS (Accenture-Corp-Amex-2025.csv)")
print("=" * 100)
ax2 = pd.read_csv(base / "credit-cards" / "Accenture-Corp-Amex-2025.csv", dtype=str)
for col in ax2.columns:
    non_null = ax2[col].notna().sum()
    sample = ax2[col].dropna().iloc[0] if non_null > 0 else "N/A"
    if len(str(sample)) > 80:
        sample = str(sample)[:80] + "..."
    print(f"  {col:<30s}  {non_null:>5d}/{len(ax2)} non-null  sample: {sample}")

# Now compare the same transaction from both sources
print("\n" + "=" * 100)
print("SIDE-BY-SIDE COMPARISON: Same transactions from both sources")
print("=" * 100)

mdf["Date"] = pd.to_datetime(mdf["Date"])
mdf["Amount"] = pd.to_numeric(mdf["Amount"], errors="coerce")
co["Transaction Date"] = pd.to_datetime(co["Transaction Date"])
co["Debit"] = pd.to_numeric(co["Debit"], errors="coerce")
co["Credit"] = pd.to_numeric(co["Credit"], errors="coerce")

# Filter Monarch to Venture card only
venture = mdf[mdf["Account"].str.contains("Venture", na=False)].copy()

# Find matching transactions
matches = 0
for _, cc_row in co.head(30).iterrows():
    cc_date = cc_row["Transaction Date"]
    cc_amt = cc_row["Debit"] if pd.notna(cc_row["Debit"]) else cc_row.get("Credit", 0)
    if pd.isna(cc_amt):
        cc_amt = cc_row.get("Credit", 0)
        if pd.isna(cc_amt):
            continue

    # Find matching Monarch txn
    m_match = venture[
        (venture["Date"] == cc_date) &
        (venture["Amount"].abs() - abs(float(cc_amt))).abs() < 0.02
    ]
    if len(m_match) > 0:
        m_row = m_match.iloc[0]
        matches += 1
        if matches <= 10:
            print(f"\n  --- Match #{matches} ---")
            print(f"  CC  Date: {cc_date.strftime('%Y-%m-%d')}  Desc: {cc_row.get('Description', 'N/A')[:60]}")
            print(f"  CC  Amount: ${cc_amt}  Category: {cc_row.get('Category', 'N/A')}")
            print(f"  MON Date: {m_row['Date'].strftime('%Y-%m-%d')}  Desc: {m_row.get('Merchant', 'N/A')[:60]}")
            print(f"  MON Amount: ${m_row['Amount']}  Category: {m_row.get('Category', 'N/A')}")
            print(f"  MON Original: {str(m_row.get('Original Statement', 'N/A'))[:70]}")
            print(f"  MON Account: {m_row.get('Account', 'N/A')}")
            print(f"  MON Tags: {m_row.get('Tags', 'N/A')}")
            print(f"  MON Notes: {m_row.get('Notes', 'N/A')}")

print(f"\n  Total matches found in first 30 CC rows: {matches}")

# Check what Monarch has that CC doesn't
print("\n" + "=" * 100)
print("DATA RICHNESS COMPARISON")
print("=" * 100)
print("\n  MONARCH EXCLUSIVE FIELDS (not in CC CSVs):")
print("    - Merchant (cleaned merchant name)")
print("    - Category (Monarch Money AI categorization)")
print("    - Original Statement (raw bank description)")
print("    - Account (proper account name with last 4 digits)")
print("    - Tags (user-defined tags)")
print("    - Notes (user notes)")
print("    - Owner (account owner - Mike or Christine)")
print()
print("  CC CSV EXCLUSIVE FIELDS (not in Monarch):")
print("    - Capital One: Category (Capital One's own categorization)")
print("    - Amex: Extended Details, Appears On Your Statement As, Address, City/State, Zip, Country, Reference")
print()
print("  VERDICT:")
print("    Monarch is RICHER for Capital One (has cleaned merchant, categories, tags, notes, owner)")
print("    Amex CSVs have some extra fields (address, reference) but Monarch has better categorization")
print("    The CC 'Description' field = Monarch 'Original Statement' field (same raw bank text)")
