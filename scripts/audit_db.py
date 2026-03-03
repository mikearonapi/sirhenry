import sqlite3
import json
import os

DB_PATH = os.environ.get("DB_PATH", "/app/data/db/financials.db")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

cur = conn.cursor()

# List all tables
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("=== TABLES ===")
for t in tables:
    print(f"  {t['name']}")

# Find asset-related tables
for table_name in [t["name"] for t in tables]:
    if "asset" in table_name.lower() or "account" in table_name.lower() or "manual" in table_name.lower():
        print(f"\n=== {table_name} COLUMNS ===")
        cols = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
        for c in cols:
            print(f"  {c['name']} ({c['type']})")
        
        print(f"\n=== {table_name} DATA ===")
        rows = cur.execute(f"SELECT * FROM {table_name}").fetchall()
        for r in rows:
            d = dict(r)
            print("---")
            for k, v in d.items():
                if v is not None and v != "" and v != 0:
                    print(f"  {k}: {v}")

conn.close()
