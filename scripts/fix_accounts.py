import sqlite3
import json

DB_PATH = "/app/data/db/financials.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

fixes = [
    {
        "id": 6,
        "name": "Christine Sageworth Roth IRA",
        "updates": {
            "current_value": 77326.70,
            "as_of_date": "2025-12-31",
            "beneficiary": "Isabelle Aron (Primary), Michael Aron (Contingent)",
            "annual_return_pct": 20.59,
            "institution": "Sageworth",
        },
    },
    {
        "id": 7,
        "name": "Christine Sageworth Rollover IRA",
        "updates": {
            "current_value": 49126.78,
            "as_of_date": "2025-12-31",
            "beneficiary": "Isabelle Aron (Primary), Michael Aron (Contingent)",
            "annual_return_pct": 18.05,
            "institution": "Sageworth",
        },
    },
    {
        "id": 5,
        "name": "Sageworth",
        "updates": {
            "current_value": 343891.76,
            "as_of_date": "2025-12-31",
            "annual_return_pct": 15.49,
            "institution": "Sageworth",
            "description": "Michael and Christine Aron 2020 Joint Revocable Trust",
        },
    },
    {
        "id": 4,
        "name": "Home Loan",
        "updates": {
            "institution": "Freedom Mortgage",
        },
    },
]

for fix in fixes:
    asset_id = fix["id"]
    before = dict(cur.execute("SELECT * FROM manual_assets WHERE id = ?", (asset_id,)).fetchone())

    set_clauses = []
    params = []
    for col, val in fix["updates"].items():
        set_clauses.append(f"{col} = ?")
        params.append(val)

    set_clauses.append("updated_at = datetime('now')")
    params.append(asset_id)

    sql = f"UPDATE manual_assets SET {', '.join(set_clauses)} WHERE id = ?"
    cur.execute(sql, params)

    after = dict(cur.execute("SELECT * FROM manual_assets WHERE id = ?", (asset_id,)).fetchone())

    print(f"\n=== {fix['name']} (id={asset_id}) ===")
    for col in fix["updates"]:
        old_val = before.get(col)
        new_val = after.get(col)
        print(f"  {col}: {old_val} -> {new_val}")

conn.commit()

print("\n\n=== VERIFICATION: All investment accounts ===")
rows = cur.execute("SELECT * FROM manual_assets WHERE asset_type = 'investment' OR asset_type = 'loan'").fetchall()
for r in rows:
    d = dict(r)
    print(f"\n--- {d['name']} (id={d['id']}) ---")
    for k, v in d.items():
        if v is not None and v != "" and v != 0:
            print(f"  {k}: {v}")

conn.close()
print("\nDone. All fixes applied and verified.")
