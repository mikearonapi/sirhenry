"""
One-time migration: merge duplicate Plaid shell accounts into original CSV-imported accounts.

Plaid's exchange-token created new Account rows (IDs 15-26) instead of linking to
the existing CSV-imported accounts (IDs 1-12) that match by last-4 digits.

This script:
  1. Moves transactions from shell accounts to originals
  2. Re-points plaid_accounts foreign keys to originals
  3. Deletes the empty shell accounts
  4. Cleans up account names and corrects institution labels
"""
import sqlite3
import sys

DB_PATH = "/app/data/db/financials.db" if len(sys.argv) < 2 else sys.argv[1]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# shell_account_id -> original_account_id (matched by last-4 digits of account number)
MERGE_MAP = {
    15: 11,  # Mike Discretionary 0209
    16: 12,  # Emergency Savings 0403
    17: 10,  # Christine Discretionary 0432
    18: 6,   # Birthday Fund 4266
    19: 3,   # Vacation Fund 5577
    20: 9,   # Christmas Fund 7556
    21: 5,   # Home Upgrades 7569
    22: 4,   # Tax Funds 8175
    23: 1,   # Budget 9595
    24: 2,   # Izzy Wedding 4593
    25: 8,   # Izzy College 9369
    26: 7,   # Eli College 9641
}

NAME_FIXES = {
    1:  ("Budget", "Bank of America"),
    2:  ("Izzy Wedding", "Ally Bank"),
    3:  ("Vacation Fund", "Bank of America"),
    4:  ("Tax Funds", "Bank of America"),
    5:  ("Home Upgrades", "Bank of America"),
    6:  ("Birthday Fund", "Bank of America"),
    7:  ("Eli College", "Ally Bank"),
    8:  ("Izzy College", "Ally Bank"),
    9:  ("Christmas Fund", "Bank of America"),
    10: ("Christine Discretionary", "Bank of America"),
    11: ("Mike Discretionary", "Bank of America"),
    12: ("Emergency Savings", "Bank of America"),
}

# Pre-check: verify shell accounts exist
for shell_id in MERGE_MAP:
    c.execute("SELECT id FROM accounts WHERE id = ?", (shell_id,))
    if not c.fetchone():
        print(f"ERROR: Shell account {shell_id} not found. Aborting.")
        sys.exit(1)

# Step 1: Move transactions
total_moved = 0
for shell_id, original_id in MERGE_MAP.items():
    c.execute("SELECT COUNT(*) FROM transactions WHERE account_id = ?", (shell_id,))
    count = c.fetchone()[0]
    if count > 0:
        c.execute("UPDATE transactions SET account_id = ? WHERE account_id = ?",
                  (original_id, shell_id))
        total_moved += count
        print(f"  Moved {count} transactions: account {shell_id} -> {original_id}")
print(f"Step 1: Moved {total_moved} transactions total")

# Step 2: Re-point plaid_accounts to original accounts
repointed = 0
for shell_id, original_id in MERGE_MAP.items():
    c.execute("UPDATE plaid_accounts SET account_id = ? WHERE account_id = ?",
              (original_id, shell_id))
    repointed += c.rowcount
print(f"Step 2: Re-pointed {repointed} plaid_accounts to originals")

# Step 3: Delete shell accounts
shell_ids = list(MERGE_MAP.keys())
placeholders = ",".join("?" * len(shell_ids))
c.execute(f"DELETE FROM accounts WHERE id IN ({placeholders})", shell_ids)
print(f"Step 3: Deleted {c.rowcount} shell accounts")

# Step 4: Clean up names and institutions
for acct_id, (name, institution) in NAME_FIXES.items():
    c.execute("UPDATE accounts SET name = ?, institution = ? WHERE id = ?",
              (name, institution, acct_id))
print(f"Step 4: Cleaned {len(NAME_FIXES)} account names and institutions")

conn.commit()

# Verify final state
print()
print("=== Final Accounts ===")
c.execute("SELECT id, name, institution, subtype, balance FROM accounts ORDER BY id")
for r in c.fetchall():
    print(f"  #{r[0]:>2} {r[1]:<35} {r[2] or '':<20} {r[3] or '':<12} bal={r[4]}")

print()
print("=== Plaid Linkage ===")
c.execute("""
    SELECT pa.id, pa.account_id, pa.name, pa.mask, a.name as acct_name
    FROM plaid_accounts pa
    JOIN accounts a ON pa.account_id = a.id
    ORDER BY pa.id
""")
for r in c.fetchall():
    print(f"  PlaidAcct {r[0]:>2} -> Account {r[1]:>2} | {r[2]:<28} mask={r[3]} ({r[4]})")

conn.close()
print()
print("Migration complete.")
