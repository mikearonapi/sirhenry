import sqlite3
import json

DB_PATH = "/app/data/db/financials.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# --- 1. Fix Home Loan institution back to CrossCountry Mortgage ---
cur.execute(
    "UPDATE manual_assets SET institution = 'CrossCountry Mortgage', updated_at = datetime('now') WHERE id = 4"
)
conn.commit()
row = dict(cur.execute("SELECT id, name, institution FROM manual_assets WHERE id = 4").fetchone())
print(f"=== Home Loan Fix ===")
print(f"  id={row['id']} name={row['name']} institution={row['institution']}")

# --- 2. Dump equity_grants table ---
print("\n=== equity_grants table ===")
cols = cur.execute("PRAGMA table_info(equity_grants)").fetchall()
print("Columns:", [c["name"] for c in cols])
rows = cur.execute("SELECT * FROM equity_grants").fetchall()
if not rows:
    print("  (empty - no rows)")
else:
    for r in rows:
        d = dict(r)
        print("---")
        for k, v in d.items():
            if v is not None and v != "" and v != 0:
                print(f"  {k}: {v}")

# --- 3. Dump vesting_events table ---
print("\n=== vesting_events table ===")
cols = cur.execute("PRAGMA table_info(vesting_events)").fetchall()
print("Columns:", [c["name"] for c in cols])
rows = cur.execute("SELECT * FROM vesting_events").fetchall()
if not rows:
    print("  (empty - no rows)")
else:
    for r in rows:
        d = dict(r)
        print("---")
        for k, v in d.items():
            if v is not None and v != "" and v != 0:
                print(f"  {k}: {v}")

# --- 4. Check if there's an ESPP account_subtype in manual_assets ---
print("\n=== Current investment manual_assets ===")
rows = cur.execute("SELECT id, name, asset_type, account_subtype, current_value FROM manual_assets WHERE asset_type = 'investment'").fetchall()
for r in rows:
    d = dict(r)
    print(f"  id={d['id']} name={d['name']} subtype={d['account_subtype']} value={d['current_value']}")

conn.close()
