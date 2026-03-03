"""Reset Plaid sync cursors and remove old Plaid transactions for re-import with enriched data."""
import sqlite3
import sys

DB_PATH = "/app/data/db/financials.db" if len(sys.argv) < 2 else sys.argv[1]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM transactions WHERE notes LIKE 'Plaid:%'")
plaid_count = c.fetchone()[0]
print(f"Plaid transactions to remove: {plaid_count}")

c.execute("DELETE FROM transactions WHERE notes LIKE 'Plaid:%'")
print(f"Deleted {c.rowcount} Plaid transactions")

c.execute("UPDATE plaid_items SET plaid_cursor = NULL, last_synced_at = NULL")
print(f"Reset cursors on {c.rowcount} Plaid items")

conn.commit()
conn.close()
print("Ready for fresh sync with enriched data.")
