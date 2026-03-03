import sqlite3
import json

DB_PATH = "/app/data/db/financials.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ============================================================
# 1. Populate equity_grants with RSU grant history
# ============================================================

# FY22 Performance RSU - FULLY VESTED
# Grant: Jan 1, 2022 | ~45 total shares over 3 years
# Vesting: Jan 2023 (~14), Jan 2024 (14), Jan 2025 (15) = ~43 shares + dividend equivalents
# All tranches released; fully vested
fy22_vesting = json.dumps([
    {"date": "2023-01-01", "shares": 14, "status": "vested"},
    {"date": "2024-01-01", "shares": 14, "status": "vested"},
    {"date": "2025-01-01", "shares": 15, "status": "vested"},
])

cur.execute("""
    INSERT INTO equity_grants (
        employer_name, grant_type, grant_date, total_shares, vested_shares, unvested_shares,
        vesting_schedule_json, strike_price, current_fmv, ticker, is_active, notes,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
""", (
    "Accenture", "RSU", "2022-01-01", 43, 43, 0,
    fy22_vesting, 0.0, 269.62, "ACN", 0,
    "FY22 Performance RSU (Grant #USA9171058). Fully vested. Shares released to UBS broker.",
))
print("Inserted FY22 RSU grant (fully vested)")

# FY24 Performance RSU - 1 TRANCHE REMAINING
# Grant: Jan 1, 2024 | ~51 total shares over 3 years (17 per year)
# Vesting: Jan 2025 (17 vested), Jan 2026 (17 vested), Jan 2027 (17 unvested)
# Plus dividend equivalents at each vesting
fy24_vesting = json.dumps([
    {"date": "2025-01-01", "shares": 17, "status": "vested"},
    {"date": "2026-01-01", "shares": 17, "status": "vested"},
    {"date": "2027-01-01", "shares": 17, "status": "unvested"},
])

cur.execute("""
    INSERT INTO equity_grants (
        employer_name, grant_type, grant_date, total_shares, vested_shares, unvested_shares,
        vesting_schedule_json, strike_price, current_fmv, ticker, is_active, notes,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
""", (
    "Accenture", "RSU", "2024-01-01", 51, 34, 17,
    fy24_vesting, 0.0, 269.62, "ACN", 1,
    "FY24 Performance RSU (Grant #USA9221565). 2 of 3 tranches vested. "
    "Final tranche of ~17 shares vests Jan 1, 2027. "
    "Dividend equivalents also vest with each tranche.",
))
print("Inserted FY24 RSU grant (1 tranche unvested)")

# ============================================================
# 2. Populate vesting_events with historical releases
# ============================================================
fy22_grant_id = cur.execute(
    "SELECT id FROM equity_grants WHERE grant_date = '2022-01-01'"
).fetchone()["id"]

fy24_grant_id = cur.execute(
    "SELECT id FROM equity_grants WHERE grant_date = '2024-01-01'"
).fetchone()["id"]

vesting_events = [
    # FY22 vesting events
    (fy22_grant_id, "2024-01-01", 14, 351.17, 7, 0.50, None, True, 343.40, "2024-01-10", None, None, "vested"),
    (fy22_grant_id, "2025-01-01", 15, 352.76, 7, 0.45, None, True, 240.16, "2025-10-15", None, None, "vested"),
    # FY24 vesting events
    (fy24_grant_id, "2025-01-01", 17, 352.76, 7, 0.41, None, True, 240.16, "2025-10-15", None, None, "vested"),
    (fy24_grant_id, "2026-01-01", 17, 269.62, 9, 0.52, None, True, 281.53, "2026-01-09", None, None, "vested"),
    # FY24 unvested tranche
    (fy24_grant_id, "2027-01-01", 17, None, None, None, None, False, None, None, None, None, "scheduled"),
]

for ev in vesting_events:
    cur.execute("""
        INSERT INTO vesting_events (
            grant_id, vest_date, shares, price_at_vest, withheld_shares,
            federal_withholding_pct, state_withholding_pct, is_sold, sale_price,
            sale_date, net_proceeds, tax_impact_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ev)

print(f"Inserted {len(vesting_events)} vesting events")

# ============================================================
# 3. Add manual_asset entry for unvested RSU (Accounts page)
# ============================================================

# FY24 unvested: 17 shares at FMV ~$269.62 = $4,583.54
# Plus estimated dividend equivalents (~4 shares @ $270 = ~$1,080)
# Conservative estimate using only confirmed shares
unvested_value = 17 * 269.62  # $4,583.54

cur.execute("""
    INSERT INTO manual_assets (
        name, asset_type, is_liability, current_value, institution,
        description, is_active, notes, created_at, updated_at,
        owner, account_subtype, custodian, employer, tax_treatment,
        is_retirement_account, as_of_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'),
              ?, ?, ?, ?, ?, ?, ?)
""", (
    "Accenture RSU - Unvested",
    "investment",
    False,
    unvested_value,
    "UBS Financial Services",
    "FY24 Performance RSU (Grant #USA9221565) - 17 shares unvested, vesting Jan 1, 2027. "
    "Value based on FMV at last vesting ($269.62/share). "
    "Dividend equivalents will also vest with this tranche.",
    True,
    "Ticker: ACN. Grant total: 51 shares (17/yr x 3). Tranches 1-2 vested Jan 2025 & Jan 2026.",
    "Mike",
    "rsu",
    "UBS Financial Services",
    "Accenture",
    "taxable",
    False,
    "2026-01-01",
))
print(f"Inserted unvested RSU manual_asset (value=${unvested_value:,.2f})")

# Also add the ESPP current accumulation
# Active enrollment: 10% for Nov 2, 2025 - May 1, 2026
# ~$7,500 per 6-month period, ~4 months accumulated by Feb 2026 ≈ $5,000
espp_accumulated = 5000.0

cur.execute("""
    INSERT INTO manual_assets (
        name, asset_type, is_liability, current_value, institution,
        description, is_active, notes, created_at, updated_at,
        owner, account_subtype, custodian, employer, tax_treatment,
        is_retirement_account, as_of_date, contribution_rate_pct
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'),
              ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "Accenture ESPP",
    "investment",
    False,
    espp_accumulated,
    "UBS Financial Services",
    "Employee Stock Purchase Plan - 15% discount on ACN stock. "
    "Current period: Nov 2, 2025 - May 1, 2026. "
    "Shares purchased at end of period at discounted price.",
    True,
    "Ticker: ACN. 10% contribution rate. Historically ~$7,500/period with ~$1,324 discount. "
    "All previously purchased shares have been sold.",
    "Mike",
    "espp",
    "UBS Financial Services",
    "Accenture",
    "taxable",
    False,
    "2026-02-22",
    10.0,
))
print(f"Inserted ESPP manual_asset (accumulated ~${espp_accumulated:,.2f})")

conn.commit()

# ============================================================
# 4. Verification
# ============================================================
print("\n=== VERIFICATION: equity_grants ===")
rows = cur.execute("SELECT * FROM equity_grants").fetchall()
for r in rows:
    d = dict(r)
    print(f"\n--- {d['employer_name']} {d['grant_type']} ({d['grant_date']}) ---")
    for k, v in d.items():
        if v is not None and v != "" and v != 0:
            print(f"  {k}: {v}")

print("\n=== VERIFICATION: vesting_events ===")
rows = cur.execute("SELECT * FROM vesting_events").fetchall()
for r in rows:
    d = dict(r)
    print(f"\n--- Grant #{d['grant_id']} vest {d['vest_date']} ({d['status']}) ---")
    for k, v in d.items():
        if v is not None and v != "" and v != 0:
            print(f"  {k}: {v}")

print("\n=== VERIFICATION: new manual_assets ===")
rows = cur.execute(
    "SELECT * FROM manual_assets WHERE account_subtype IN ('rsu', 'espp')"
).fetchall()
for r in rows:
    d = dict(r)
    print(f"\n--- {d['name']} (id={d['id']}) ---")
    for k, v in d.items():
        if v is not None and v != "" and v != 0:
            print(f"  {k}: {v}")

conn.close()
print("\nDone.")
