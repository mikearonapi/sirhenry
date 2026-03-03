"""Count actual transaction rows in each credit card CSV."""
import csv
import os

files = [
    'data/imports/credit-cards/Family-Capital-One-2024.csv',
    'data/imports/credit-cards/Family-Capital-One-2025.csv',
    'data/imports/credit-cards/Family-Capital-One-2026YTD.csv',
    'data/imports/credit-cards/Accenture-Corp-Amex-2024.csv',
    'data/imports/credit-cards/Accenture-Corp-Amex-2025.csv',
    'data/imports/credit-cards/Accenture-Corp-Amex-2026YTD.csv',
    'data/imports/credit-cards/Personal-Amex-2024.csv',
    'data/imports/credit-cards/Personal-Amex-2025.csv',
    'data/imports/credit-cards/Personal-Amex-2026.csv',
    'data/imports/Monarch/Monarch-Transactions.csv',
]

for f in files:
    path = os.path.join('/app', f)
    try:
        with open(path) as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            date_key = 'Date' if 'Date' in rows[0] else 'Transaction Date'
            dates = [r.get(date_key, '') for r in rows]
            dates = [d for d in dates if d]
            name = os.path.basename(f)
            print(f"  {name:40s} {len(rows):>6d} txns  {min(dates):>12s} to {max(dates):>12s}")
    except Exception as e:
        print(f"  {os.path.basename(f):40s} ERROR: {e}")

# Check if Personal Amex is in Monarch
print("\nSearching Monarch for Personal Amex / -23005...")
with open('/app/data/imports/Monarch/Monarch-Transactions.csv') as fh:
    reader = csv.DictReader(fh)
    for row in reader:
        acct = row.get('Account', '')
        if '23005' in acct or 'personal' in acct.lower() or 'amex' in acct.lower():
            print(f"  Found: {acct}")
            break
    else:
        print("  NOT FOUND — Personal Amex is not in Monarch export")
