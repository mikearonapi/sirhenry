"""
SirHENRY Audit Tool (consolidated)
====================================
Replaces: data_audit.py, data_audit_2.py, deep_analysis.py,
          deep_dive_all_txns.py, csv_audit.py, audit_db.py, analyze_vendors.py

Usage:
    python scripts/audit.py data       # DB row counts, sources, quality checks, overlaps
    python scripts/audit.py deep       # Claude-powered deep analysis of business expenses
    python scripts/audit.py csv        # Count rows in each credit card / Monarch CSV
    python scripts/audit.py db         # Raw SQLite table & column inspection
    python scripts/audit.py vendors    # Business-relevant merchant analysis from Monarch CSV
"""
import argparse
import asyncio
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# Ensure project root is on sys.path for pipeline imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# data — replaces data_audit.py + data_audit_2.py
# ============================================================================
async def cmd_data(args: argparse.Namespace) -> None:
    """Comprehensive data audit of the financials database."""
    from api.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as session:
        # ---- Part 1 (from data_audit.py) ----

        print("=" * 70)
        print("1. TABLE ROW COUNTS")
        print("=" * 70)
        tables = await session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
        for (tbl,) in tables.fetchall():
            cnt = await session.execute(text(f"SELECT COUNT(*) FROM [{tbl}]"))
            print(f"  {tbl:40s} {cnt.scalar():>8,}")

        print("\n" + "=" * 70)
        print("2. TRANSACTIONS BY SOURCE (notes prefix)")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                CASE
                    WHEN notes LIKE 'Plaid:%' THEN 'Plaid'
                    WHEN notes LIKE 'Amazon:%' THEN 'Amazon'
                    WHEN notes LIKE '%CSV%' OR notes LIKE '%import%' THEN 'CSV Import'
                    WHEN notes IS NULL OR notes = '' THEN '(no notes)'
                    ELSE 'Other: ' || SUBSTR(notes, 1, 30)
                END as source,
                COUNT(*) as cnt,
                MIN(date) as earliest,
                MAX(date) as latest
            FROM transactions
            GROUP BY 1
            ORDER BY cnt DESC
        """))
        print(f"  {'Source':40s} {'Count':>8s} {'Earliest':>12s} {'Latest':>12s}")
        print("  " + "-" * 74)
        for row in r.fetchall():
            print(f"  {str(row[0]):40s} {row[1]:>8,} {str(row[2]):>12s} {str(row[3]):>12s}")

        print("\n" + "=" * 70)
        print("3. TRANSACTIONS BY YEAR/MONTH")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT period_year, period_month, COUNT(*)
            FROM transactions
            GROUP BY period_year, period_month
            ORDER BY period_year, period_month
        """))
        print(f"  {'Year':>6s} {'Month':>6s} {'Count':>8s}")
        print("  " + "-" * 24)
        for row in r.fetchall():
            print(f"  {row[0] or 'NULL':>6} {row[1] or 'NULL':>6} {row[2]:>8,}")

        print("\n" + "=" * 70)
        print("4. ACCOUNTS SUMMARY")
        print("=" * 70)
        cols_r = await session.execute(text("PRAGMA table_info(accounts)"))
        acct_cols = [c[1] for c in cols_r.fetchall()]
        print(f"  (accounts columns: {', '.join(acct_cols)})")
        r = await session.execute(text("""
            SELECT
                a.id, a.name, a.institution, a.account_type,
                (SELECT COUNT(*) FROM transactions t WHERE t.account_id = a.id) as tx_count,
                pa.plaid_account_id
            FROM accounts a
            LEFT JOIN plaid_accounts pa ON pa.account_id = a.id
            ORDER BY tx_count DESC
        """))
        print(f"  {'ID':>4s} {'Name':30s} {'Institution':20s} {'Type':12s} {'Txns':>6s} {'Plaid?':>8s}")
        print("  " + "-" * 84)
        for row in r.fetchall():
            plaid = "Yes" if row[5] else "No"
            print(f"  {row[0]:>4d} {str(row[1] or ''):30s} {str(row[2] or ''):20s} "
                  f"{str(row[3] or ''):12s} {row[4]:>6,} {plaid:>8s}")

        print("\n" + "=" * 70)
        print("5. DATA QUALITY CHECKS")
        print("=" * 70)

        checks = [
            ("Transactions with NULL date",         "SELECT COUNT(*) FROM transactions WHERE date IS NULL"),
            ("Transactions with NULL amount",       "SELECT COUNT(*) FROM transactions WHERE amount IS NULL"),
            ("Transactions with NULL account_id",   "SELECT COUNT(*) FROM transactions WHERE account_id IS NULL"),
            ("Transactions with empty description", "SELECT COUNT(*) FROM transactions WHERE description IS NULL OR description = ''"),
            ("Orphaned txns (bad account_id)",      "SELECT COUNT(*) FROM transactions t WHERE t.account_id NOT IN (SELECT id FROM accounts)"),
            ("Duplicate transaction hashes",        """SELECT COUNT(*) FROM (
                SELECT transaction_hash, COUNT(*) as c FROM transactions
                WHERE transaction_hash IS NOT NULL AND transaction_hash != ''
                GROUP BY transaction_hash HAVING c > 1)"""),
            ("Likely dupes (acct+date+amt+desc)",   """SELECT COUNT(*) FROM (
                SELECT account_id, date, amount, description, COUNT(*) as c
                FROM transactions GROUP BY account_id, date, amount, description HAVING c > 1)"""),
            ("Transactions with future dates",      "SELECT COUNT(*) FROM transactions WHERE date > date('now', '+1 day')"),
            ("Transactions before 2020",            "SELECT COUNT(*) FROM transactions WHERE date < '2020-01-01'"),
            ("Zero-amount transactions",            "SELECT COUNT(*) FROM transactions WHERE amount = 0"),
            ("NULL period_year/month",              "SELECT COUNT(*) FROM transactions WHERE period_year IS NULL OR period_month IS NULL"),
            ("Excluded transactions (is_excluded)", "SELECT COUNT(*) FROM transactions WHERE is_excluded = 1"),
        ]
        for label, sql in checks:
            r = await session.execute(text(sql))
            print(f"  {label + ':':42s} {r.scalar():>8,}")

        print("\n" + "=" * 70)
        print("6. PLAID vs CSV OVERLAP")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT COUNT(*) FROM transactions p
            INNER JOIN transactions c
                ON p.account_id = c.account_id
                AND p.date = c.date
                AND ABS(p.amount - c.amount) < 0.01
                AND p.id != c.id
            WHERE p.notes LIKE 'Plaid:%'
            AND (c.notes NOT LIKE 'Plaid:%' OR c.notes IS NULL)
        """))
        print(f"  Plaid txns with a CSV match (potential overlaps): {r.scalar():>6,}")

        r = await session.execute(text("""
            SELECT
                p.id as plaid_id, p.date, p.amount, p.description as plaid_desc,
                c.id as csv_id, c.description as csv_desc, c.notes as csv_notes
            FROM transactions p
            INNER JOIN transactions c
                ON p.account_id = c.account_id
                AND p.date = c.date
                AND ABS(p.amount - c.amount) < 0.01
                AND p.id != c.id
            WHERE p.notes LIKE 'Plaid:%'
            AND (c.notes NOT LIKE 'Plaid:%' OR c.notes IS NULL)
            LIMIT 10
        """))
        rows = r.fetchall()
        if rows:
            print(f"\n  Sample overlaps:")
            print(f"  {'PlaidID':>7s} {'Date':>12s} {'Amount':>10s} {'Plaid Desc':30s} {'CsvID':>6s} {'CSV Desc':30s}")
            print("  " + "-" * 100)
            for row in rows:
                print(f"  {row[0]:>7d} {str(row[1]):>12s} {row[2]:>10.2f} "
                      f"{str(row[3])[:30]:30s} {row[4]:>6d} {str(row[5])[:30]:30s}")

        print("\n" + "=" * 70)
        print("7. CATEGORY COVERAGE")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                CASE WHEN category IS NOT NULL AND category != '' THEN 'Categorized' ELSE 'Uncategorized' END as status,
                COUNT(*) as cnt
            FROM transactions
            GROUP BY 1
        """))
        for row in r.fetchall():
            print(f"  {row[0]:30s} {row[1]:>8,}")

        # ---- Part 2 (from data_audit_2.py) ----

        print("\n" + "=" * 70)
        print("A. LIKELY DUPLICATES (same acct+date+amt+desc) -- TOP 30")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT account_id, date, amount, description, COUNT(*) as c,
                GROUP_CONCAT(id) as ids,
                GROUP_CONCAT(COALESCE(SUBSTR(notes, 1, 20), '(none)')) as note_sources
            FROM transactions
            GROUP BY account_id, date, amount, description
            HAVING c > 1
            ORDER BY c DESC, date DESC
            LIMIT 30
        """))
        print(f"  {'AcctID':>6s} {'Date':>12s} {'Amount':>10s} {'Desc':30s} {'Cnt':>4s} {'IDs':20s} {'Sources':30s}")
        print("  " + "-" * 116)
        for row in r.fetchall():
            print(f"  {row[0]:>6} {str(row[1])[:10]:>12s} {row[2]:>10.2f} "
                  f"{str(row[3])[:30]:30s} {row[4]:>4d} {str(row[5])[:20]:20s} {str(row[6])[:30]:30s}")

        print("\n" + "=" * 70)
        print("B. PLAID vs CSV OVERLAP BREAKDOWN BY ACCOUNT")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                a.name,
                COUNT(DISTINCT p.id) as plaid_txns,
                COUNT(DISTINCT CASE WHEN c.id IS NOT NULL THEN p.id END) as with_csv_match,
                COUNT(DISTINCT CASE WHEN c.id IS NULL THEN p.id END) as plaid_only
            FROM transactions p
            JOIN accounts a ON a.id = p.account_id
            LEFT JOIN transactions c
                ON p.account_id = c.account_id
                AND p.date = c.date
                AND ABS(p.amount - c.amount) < 0.01
                AND p.id != c.id
                AND (c.notes NOT LIKE 'Plaid:%' OR c.notes IS NULL)
            WHERE p.notes LIKE 'Plaid:%'
            GROUP BY a.name
            ORDER BY plaid_txns DESC
        """))
        print(f"  {'Account':30s} {'Plaid':>6s} {'Has CSV':>8s} {'New':>6s}")
        print("  " + "-" * 54)
        for row in r.fetchall():
            print(f"  {str(row[0])[:30]:30s} {row[1]:>6d} {row[2]:>8d} {row[3]:>6d}")

        print("\n" + "=" * 70)
        print("C. ZERO-AMOUNT TRANSACTIONS (sample)")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT t.id, t.date, t.description, t.notes, a.name
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE t.amount = 0
            ORDER BY t.date DESC
            LIMIT 15
        """))
        print(f"  {'ID':>6s} {'Date':>12s} {'Desc':35s} {'Notes':25s} {'Account':20s}")
        print("  " + "-" * 102)
        for row in r.fetchall():
            print(f"  {row[0]:>6d} {str(row[1])[:10]:>12s} {str(row[2])[:35]:35s} "
                  f"{str(row[3] or '')[:25]:25s} {str(row[4])[:20]:20s}")

        print("\n" + "=" * 70)
        print("D. TRANSACTION COUNT BY ACCOUNT (CSV vs Plaid)")
        print("=" * 70)
        r = await session.execute(text("""
            SELECT
                a.name,
                a.institution,
                COUNT(*) as total,
                SUM(CASE WHEN t.notes LIKE 'Plaid:%' THEN 1 ELSE 0 END) as from_plaid,
                SUM(CASE WHEN t.notes NOT LIKE 'Plaid:%' OR t.notes IS NULL THEN 1 ELSE 0 END) as from_csv,
                MIN(t.date) as earliest,
                MAX(t.date) as latest
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            GROUP BY a.id
            ORDER BY total DESC
        """))
        print(f"  {'Account':25s} {'Inst':15s} {'Total':>6s} {'Plaid':>6s} "
              f"{'CSV':>6s} {'Earliest':>12s} {'Latest':>12s}")
        print("  " + "-" * 86)
        for row in r.fetchall():
            print(f"  {str(row[0])[:25]:25s} {str(row[1])[:15]:15s} {row[2]:>6d} "
                  f"{row[3]:>6d} {row[4]:>6d} {str(row[5])[:10]:>12s} {str(row[6])[:10]:>12s}")


# ============================================================================
# deep — replaces deep_analysis.py + deep_dive_all_txns.py
# ============================================================================
async def cmd_deep(args: argparse.Namespace) -> None:
    """Deep business-expense analysis using Monarch CSV and Claude AI."""
    import pandas as pd
    from dotenv import load_dotenv

    load_dotenv()

    from pipeline.db import get_all_vendor_rules, get_all_business_entities, init_db
    from pipeline.utils import (
        create_engine_and_session, get_claude_client,
        strip_json_fences, CLAUDE_MODEL,
    )

    base = Path(os.environ.get(
        "IMPORT_DIR",
        str(PROJECT_ROOT / "data" / "imports"),
    ))
    mc = base / "Monarch" / "Monarch-Transactions.csv"
    if not mc.exists():
        print(f"[ERROR] Monarch CSV not found at {mc}")
        return

    df = pd.read_csv(mc, dtype=str)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"])

    # --- Load entity rules from DB ---
    engine, Session = create_engine_and_session()
    await init_db(engine)
    async with Session() as s:
        rules = await get_all_vendor_rules(s, active_only=True)
        entities = await get_all_business_entities(s, include_inactive=True)
    await engine.dispose()
    emap = {e.id: e.name for e in entities}

    def match_entity(merchant, tx_date):
        for rule in sorted(rules, key=lambda r: -r.priority):
            if rule.effective_from and tx_date < rule.effective_from:
                continue
            if rule.effective_to and tx_date > rule.effective_to:
                continue
            if re.search(rule.vendor_pattern, merchant, re.IGNORECASE):
                return emap.get(rule.business_entity_id, "?"), rule.segment_override
        return None, None

    # --- Tag every transaction with entity ---
    results = []
    for _, row in df.iterrows():
        merchant = str(row["Merchant"]).strip()
        tx_date = row["Date"].date()
        amount = row["Amount"]
        category = str(row["Category"]).strip()
        account = str(row["Account"]).strip()
        entity, seg_override = match_entity(merchant, tx_date)
        if "Corporate Platinum" in account:
            entity = "Accenture"
            seg_override = "reimbursable"
        results.append({
            "merchant": merchant, "date": str(tx_date), "amount": round(amount, 2),
            "category": category, "account": account,
            "matched_entity": entity, "segment_override": seg_override,
        })

    results_df = pd.DataFrame(results)

    # --- Unmatched business-looking expenses ---
    print("=" * 80)
    print("UNMATCHED EXPENSES (no entity rule, not Corp Amex, amount < -$10)")
    print("=" * 80)
    unmatched = results_df[
        (results_df["matched_entity"].isna()) & (results_df["amount"] < -10)
    ].copy()
    cat_groups = unmatched.groupby("category")
    for cat in ["Business Technology", "Gen AI", "Uncategorized", "Transfer"]:
        if cat in cat_groups.groups:
            group = cat_groups.get_group(cat)
            print(f"\n  Category: {cat} ({len(group)} unmatched txns)")
            for m, mg in group.groupby("merchant"):
                total = mg["amount"].sum()
                print(f"    {m}: {len(mg)} txns, ${total:,.2f}")

    # --- Mismatched categories ---
    print("\n" + "=" * 80)
    print("ENTITY-ASSIGNED BUT STRANGE CATEGORY")
    print("=" * 80)
    matched = results_df[results_df["matched_entity"].notna()].copy()
    personal_cats = ["Transfer", "Gas", "Restaurants & Bars", "Groceries",
                     "Shopping", "Fast Food", "Coffee Shops"]
    for _, row in matched.iterrows():
        entity = row["matched_entity"]
        if entity in ["Accenture", "Vivant"] and row["amount"] > 0:
            continue
        if entity not in ["Accenture", "Vivant"] and row["segment_override"] == "business":
            if row["category"] in personal_cats:
                print(f"  {row['date']} {row['merchant']:<35s} ${row['amount']:>10,.2f}  "
                      f"cat={row['category']:<25s} entity={entity}")

    # --- Large unmatched ---
    print("\n" + "=" * 80)
    print("LARGE UNMATCHED TRANSACTIONS (>$500 or <-$500)")
    print("=" * 80)
    large = results_df[
        (results_df["matched_entity"].isna()) &
        ((results_df["amount"] > 500) | (results_df["amount"] < -500))
    ].sort_values("amount")
    for _, row in large.iterrows():
        print(f"  {row['date']} {row['merchant']:<35s} ${row['amount']:>10,.2f}  "
              f"cat={row['category']:<25s} acct={row['account']}")

    # --- Summary ---
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total = len(results_df)
    matched_count = results_df["matched_entity"].notna().sum()
    unmatched_count = results_df["matched_entity"].isna().sum()
    print(f"  Total transactions: {total}")
    print(f"  Matched to entity: {matched_count} ({matched_count/total*100:.1f}%)")
    print(f"  Unmatched (personal): {unmatched_count} ({unmatched_count/total*100:.1f}%)")
    print("\n  By entity:")
    for entity, group in results_df.groupby("matched_entity"):
        if pd.isna(entity):
            continue
        total_amt = group["amount"].sum()
        print(f"    {entity:<30s}: {len(group):>5d} txns, ${total_amt:>12,.2f}")

    # --- Send edge cases to Claude (if --claude flag) ---
    if getattr(args, "claude", False):
        print("\n" + "=" * 80)
        print("SENDING EDGE CASES TO CLAUDE FOR REVIEW...")
        print("=" * 80)

        edge_cases = []
        for cat in ["Business Technology", "Gen AI"]:
            if cat in cat_groups.groups:
                for _, row in cat_groups.get_group(cat).iterrows():
                    edge_cases.append({
                        "merchant": row["merchant"], "date": row["date"],
                        "amount": row["amount"], "category": row["category"],
                        "account": row["account"],
                        "issue": f"Categorized as '{cat}' but no entity rule matched",
                    })

        if edge_cases:
            client = get_claude_client()
            prompt = (
                "You are a CPA reviewing transaction categorizations for accuracy.\n"
                "Review these edge cases and return JSON with 'reviews' and 'new_rules_needed' keys.\n\n"
                f"{json.dumps(edge_cases, indent=2)}\n\nReturn ONLY JSON."
            )
            response = client.messages.create(
                model=CLAUDE_MODEL, max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = strip_json_fences(response.content[0].text)
            output = PROJECT_ROOT / "scripts" / "claude_edge_case_review.json"
            with open(output, "w") as f:
                f.write(raw)
            review = json.loads(raw)
            verdicts = defaultdict(int)
            for r in review.get("reviews", []):
                verdicts[r["verdict"]] += 1
                if r["verdict"] != "correct":
                    print(f"  {r['merchant']} ({r['date']}): {r['verdict']}")
                    print(f"    {r['reasoning']}")
            print(f"\nVerdicts: {dict(verdicts)}")
            print(f"Full review saved to: {output}")
        else:
            print("  No edge cases to review.")


# ============================================================================
# csv — replaces csv_audit.py
# ============================================================================
async def cmd_csv(args: argparse.Namespace) -> None:
    """Count actual transaction rows in each credit card and Monarch CSV."""
    import_dir = os.environ.get(
        "IMPORT_DIR",
        str(PROJECT_ROOT / "data" / "imports"),
    )
    base = Path(import_dir)

    files = [
        base / "credit-cards" / "Family-Capital-One-2024.csv",
        base / "credit-cards" / "Family-Capital-One-2025.csv",
        base / "credit-cards" / "Family-Capital-One-2026YTD.csv",
        base / "credit-cards" / "Accenture-Corp-Amex-2024.csv",
        base / "credit-cards" / "Accenture-Corp-Amex-2025.csv",
        base / "credit-cards" / "Accenture-Corp-Amex-2026YTD.csv",
        base / "credit-cards" / "Personal-Amex-2024.csv",
        base / "credit-cards" / "Personal-Amex-2025.csv",
        base / "credit-cards" / "Personal-Amex-2026.csv",
        base / "Monarch" / "Monarch-Transactions.csv",
    ]

    print("=" * 70)
    print("CSV ROW COUNTS")
    print("=" * 70)
    for filepath in files:
        name = filepath.name
        try:
            with open(filepath) as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                if not rows:
                    print(f"  {name:40s} 0 txns")
                    continue
                date_key = "Date" if "Date" in rows[0] else "Transaction Date"
                dates = [r.get(date_key, "") for r in rows if r.get(date_key)]
                date_range = f"{min(dates):>12s} to {max(dates):>12s}" if dates else "no dates"
                print(f"  {name:40s} {len(rows):>6d} txns  {date_range}")
        except FileNotFoundError:
            print(f"  {name:40s} NOT FOUND")
        except Exception as e:
            print(f"  {name:40s} ERROR: {e}")


# ============================================================================
# db — replaces audit_db.py
# ============================================================================
async def cmd_db(args: argparse.Namespace) -> None:
    """Raw SQLite table and column inspection."""
    import sqlite3

    db_path = os.environ.get("DB_PATH")
    if not db_path:
        # Try common locations
        for candidate in [
            PROJECT_ROOT / "data" / "db" / "financials.db",
            Path.home() / ".sirhenry" / "data" / "financials.db",
        ]:
            if candidate.exists():
                db_path = str(candidate)
                break
    if not db_path:
        print("[ERROR] Database not found. Set DB_PATH environment variable.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("=== TABLES ===")
    for t in tables:
        print(f"  {t['name']}")

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


# ============================================================================
# vendors — replaces analyze_vendors.py
# ============================================================================
async def cmd_vendors(args: argparse.Namespace) -> None:
    """Analyze business-relevant vendors from Monarch CSV."""
    import pandas as pd

    base = Path(os.environ.get(
        "IMPORT_DIR",
        str(PROJECT_ROOT / "data" / "imports"),
    ))
    mc = base / "Monarch" / "Monarch-Transactions.csv"
    if not mc.exists():
        print(f"[ERROR] Monarch CSV not found at {mc}")
        return

    df = pd.read_csv(mc, dtype=str)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"])

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

    print("\n" + "=" * 70)
    print("ALL MERCHANTS ACROSS ALL ACCOUNTS (sorted by frequency)")
    print("=" * 70)
    all_merchants = df["Merchant"].value_counts()
    for m, c in all_merchants.head(60).items():
        total = df[df["Merchant"] == m]["Amount"].sum()
        cats = df[df["Merchant"] == m]["Category"].unique()
        cat_str = ", ".join(cats[:3])
        print(f"  {m}: {c} txns | ${total:,.2f} | {cat_str}")

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

    print("\n" + "=" * 70)
    print("TAGS ANALYSIS")
    print("=" * 70)
    tags_col = df["Tags"].dropna()
    tag_counts: dict[str, int] = defaultdict(int)
    for t in tags_col:
        for tag in str(t).split(","):
            tag = tag.strip()
            if tag and tag.lower() != "nan":
                tag_counts[tag] += 1
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  {tag}: {count}")


# ============================================================================
# CLI entry point
# ============================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit",
        description="SirHENRY data audit toolkit (consolidated)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("data", help="DB row counts, sources, quality checks, overlaps")

    deep_p = sub.add_parser("deep", help="Deep business-expense analysis with entity matching")
    deep_p.add_argument("--claude", action="store_true",
                        help="Send edge cases to Claude for review")

    sub.add_parser("csv", help="Count rows in each credit card / Monarch CSV")
    sub.add_parser("db", help="Raw SQLite table and column inspection")
    sub.add_parser("vendors", help="Business-relevant merchant analysis from Monarch CSV")

    return parser


COMMANDS = {
    "data": cmd_data,
    "deep": cmd_deep,
    "csv": cmd_csv,
    "db": cmd_db,
    "vendors": cmd_vendors,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMANDS[args.command]
    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
