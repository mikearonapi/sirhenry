"""
SirHENRY Vendor Rules Tool (consolidated)
============================================
Replaces: list_rules.py, show_rules.py, add_new_rules.py, add_adobe_rules.py,
          reapply_rules.py, replace_rules.py, apply_claude_rules.py,
          build_rules_with_claude.py, test_rules_matching.py

Usage:
    python scripts/rules.py list       # List all vendor entity rules
    python scripts/rules.py add        # Add new rules from a JSON file or inline
    python scripts/rules.py apply      # Re-apply all entity rules to transactions
    python scripts/rules.py build      # Use Claude to analyze data and recommend rules
    python scripts/rules.py test       # Test rule matching against Monarch CSV
    python scripts/rules.py replace    # Replace all rules from a Claude analysis JSON
"""
import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# Shared helpers
# ============================================================================
def _get_entity_maps(entities):
    """Return (id->name, name->id) dicts from a list of entity objects."""
    by_id = {e.id: e.name for e in entities}
    by_name = {e.name: e.id for e in entities}
    return by_id, by_name


def _parse_date(s):
    """Parse an ISO date string or return None."""
    if s is None:
        return None
    return date.fromisoformat(s)


# ============================================================================
# list — replaces list_rules.py + show_rules.py
# ============================================================================
async def cmd_list(args: argparse.Namespace) -> None:
    """Display all vendor entity rules, optionally grouped by entity."""
    from pipeline.db import get_all_vendor_rules, get_all_business_entities, init_db
    from pipeline.utils import create_engine_and_session

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as s:
        active_only = not getattr(args, "all", False)
        rules = await get_all_vendor_rules(s, active_only=active_only)
        entities = await get_all_business_entities(s, include_inactive=True)

    await engine.dispose()

    eid_to_name, _ = _get_entity_maps(entities)

    print(f"Total rules: {len(rules)} ({'active only' if active_only else 'all'})")
    print(f"Total entities: {len(entities)}")

    if getattr(args, "group", False):
        # Group by entity (show_rules.py style)
        by_entity: dict[str, list] = {}
        for r in rules:
            ename = eid_to_name.get(r.business_entity_id, "?")
            by_entity.setdefault(ename, []).append(r)

        for ename in sorted(by_entity.keys()):
            erules = by_entity[ename]
            print(f"\n--- {ename} ({len(erules)} rules) ---")
            for r in erules:
                seg = r.segment_override or "-"
                fr = str(r.effective_from) if r.effective_from else "any"
                to = str(r.effective_to) if r.effective_to else "any"
                print(f"  {r.vendor_pattern:<45s} seg={seg:<12s} "
                      f"{fr:>10s} - {to:>10s}  pri={r.priority}")
    else:
        # Flat list (list_rules.py style)
        print()
        for r in sorted(rules, key=lambda x: (x.business_entity_id, x.vendor_pattern)):
            ename = eid_to_name.get(r.business_entity_id, "?")
            efrom = str(r.effective_from) if r.effective_from else "any"
            eto = str(r.effective_to) if r.effective_to else "ongoing"
            seg = r.segment_override or ""
            print(f"  {r.vendor_pattern:<25s} -> {ename:<30s} seg={seg:<14s} "
                  f"from={efrom:<12s} to={eto:<12s} pri={r.priority}")


# ============================================================================
# add — replaces add_new_rules.py + add_adobe_rules.py
# ============================================================================
async def cmd_add(args: argparse.Namespace) -> None:
    """Add vendor entity rules from a JSON file or inline specification.

    JSON file format (array of rule objects):
    [
      {
        "vendor_pattern": "trak racer",
        "entity_name": "AutoRev",
        "segment": "business",
        "effective_from": "2026-01-01",
        "effective_to": null,
        "priority": 15
      }
    ]
    """
    from pipeline.db import (
        create_vendor_rule, get_all_business_entities,
        get_all_vendor_rules, init_db,
    )
    from pipeline.utils import create_engine_and_session

    engine, Session = create_engine_and_session()
    await init_db(engine)

    # Load rules from JSON file
    rules_file = Path(args.file)
    if not rules_file.exists():
        print(f"[ERROR] Rules file not found: {rules_file}")
        await engine.dispose()
        return

    with open(rules_file) as f:
        new_rules_data = json.load(f)

    if isinstance(new_rules_data, dict):
        # Support both {"rules": [...]} and bare list
        new_rules_data = new_rules_data.get("rules", new_rules_data.get("vendor_rules", [new_rules_data]))

    async with Session() as session:
        entities = await get_all_business_entities(session, include_inactive=True)
        _, name_to_id = _get_entity_maps(entities)

        added = 0
        for rule_data in new_rules_data:
            entity_name = rule_data.get("entity_name")
            entity_id = rule_data.get("business_entity_id") or name_to_id.get(entity_name)
            if not entity_id:
                print(f"  [WARN] Entity not found: {entity_name}")
                continue

            rule = await create_vendor_rule(session, {
                "vendor_pattern": rule_data["vendor_pattern"],
                "business_entity_id": entity_id,
                "segment_override": rule_data.get("segment") or rule_data.get("segment_override"),
                "effective_from": _parse_date(rule_data.get("effective_from")),
                "effective_to": _parse_date(rule_data.get("effective_to")),
                "priority": rule_data.get("priority", 10),
            })
            ename = entity_name or next(
                (k for k, v in name_to_id.items() if v == rule.business_entity_id), "?"
            )
            efrom = rule.effective_from or "any"
            eto = rule.effective_to or "ongoing"
            print(f"  + {rule.vendor_pattern:<30s} -> {ename:<30s} from={efrom} to={eto}")
            added += 1

        await session.commit()

        rules = await get_all_vendor_rules(session, active_only=True)
        print(f"\nAdded {added} new rules. Total active: {len(rules)}")

    await engine.dispose()


# ============================================================================
# apply — replaces reapply_rules.py + apply_claude_rules.py
# ============================================================================
async def cmd_apply(args: argparse.Namespace) -> None:
    """Re-apply all entity rules to all transactions in the DB.

    When --from-file is provided, first imports rules from a Claude analysis
    JSON file (deduplicating against existing rules), then applies all rules.
    """
    from sqlalchemy import select, func
    from pipeline.db import (
        apply_entity_rules, get_all_business_entities, get_all_vendor_rules,
        init_db, create_vendor_rule,
    )
    from pipeline.db.schema import Transaction, Account
    from pipeline.utils import create_engine_and_session

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        # If a file is provided, import rules first (apply_claude_rules.py logic)
        if getattr(args, "from_file", None):
            rules_path = Path(args.from_file)
            if not rules_path.exists():
                print(f"[ERROR] File not found: {rules_path}")
                await engine.dispose()
                return

            with open(rules_path) as f:
                analysis = json.load(f)

            entities = await get_all_business_entities(session, include_inactive=True)
            _, name_to_id = _get_entity_maps(entities)

            # Entity name mapping for common aliases
            ENTITY_ALIASES = {
                "vivant": "Vivant",
                "accenture": "Accenture",
                "mike_aron_visuals": "Mike Aron Visuals",
                "autorev": "AutoRev",
                "provisional_consulting": "Mike Aron AI Consulting",
            }

            existing_rules = await get_all_vendor_rules(session, active_only=False)
            existing_set = set()
            for r in existing_rules:
                key = (r.vendor_pattern, r.business_entity_id,
                       str(r.effective_from), str(r.effective_to))
                existing_set.add(key)

            new_rules = analysis.get("new_vendor_rules", analysis.get("vendor_rules", []))
            added = 0
            skipped = 0

            for rule_data in new_rules:
                raw_entity = rule_data.get("entity_name", "")
                entity_name = ENTITY_ALIASES.get(raw_entity, raw_entity)
                entity_id = name_to_id.get(entity_name)
                if not entity_id:
                    logger.warning(f"Entity not found: {entity_name} (raw: {raw_entity})")
                    skipped += 1
                    continue

                pattern = rule_data["vendor_pattern"]
                eff_from = _parse_date(rule_data.get("effective_from"))
                eff_to = _parse_date(rule_data.get("effective_to"))

                key = (pattern, entity_id, str(eff_from), str(eff_to))
                if key in existing_set:
                    logger.info(f"  SKIP (exists): {pattern} -> {entity_name}")
                    skipped += 1
                    continue

                await create_vendor_rule(session, {
                    "vendor_pattern": pattern,
                    "business_entity_id": entity_id,
                    "segment_override": rule_data.get("segment_override") or rule_data.get("segment"),
                    "effective_from": eff_from,
                    "effective_to": eff_to,
                    "priority": rule_data.get("priority", 0),
                })
                existing_set.add(key)
                added += 1
                logger.info(f"  ADD: {pattern} -> {entity_name} "
                            f"[{eff_from or 'any'} to {eff_to or 'any'}]")

            logger.info(f"Rules: {added} added, {skipped} skipped")

            # Set Corporate Platinum account defaults if applicable
            acct_result = await session.execute(
                select(Account).where(Account.name.contains("Corporate"))
            )
            corp_acct = acct_result.scalar_one_or_none()
            if corp_acct:
                accenture_id = name_to_id.get("Accenture")
                if accenture_id:
                    corp_acct.default_segment = "reimbursable"
                    corp_acct.default_business_entity_id = accenture_id
                    logger.info(f"Set account defaults: {corp_acct.name} -> reimbursable / Accenture")

        # Count before
        result = await session.execute(
            select(func.count(Transaction.id))
            .where(Transaction.effective_business_entity_id.isnot(None))
        )
        before = result.scalar()
        print(f"Transactions with entity BEFORE: {before}")

        # Apply rules
        updated = await apply_entity_rules(session)
        print(f"Rules applied, {updated} transactions updated")
        await session.commit()

        # Count after
        result = await session.execute(
            select(func.count(Transaction.id))
            .where(Transaction.effective_business_entity_id.isnot(None))
        )
        after = result.scalar()
        print(f"Transactions with entity AFTER: {after}")

        # Summary by entity
        entities = await get_all_business_entities(session, include_inactive=True)
        eid_to_name, _ = _get_entity_maps(entities)

        result = await session.execute(
            select(Transaction.effective_business_entity_id,
                   func.count(Transaction.id), func.sum(Transaction.amount))
            .where(Transaction.effective_business_entity_id.isnot(None))
            .group_by(Transaction.effective_business_entity_id)
        )
        print("\nEntity assignment summary:")
        for eid, cnt, total in result.all():
            name = eid_to_name.get(eid, f"entity_{eid}")
            print(f"  {name:<30s}: {cnt:>5d} txns, ${total:>12,.2f}")

        # Segment summary
        result = await session.execute(
            select(Transaction.effective_segment, func.count(Transaction.id))
            .group_by(Transaction.effective_segment)
        )
        print("\nSegment summary:")
        for seg, cnt in result.all():
            print(f"  {seg or 'null':<15s}: {cnt:>5d} txns")

    await engine.dispose()


# ============================================================================
# build — replaces build_rules_with_claude.py
# ============================================================================
async def cmd_build(args: argparse.Namespace) -> None:
    """Analyze transaction data with Claude to recommend vendor entity rules."""
    import pandas as pd
    from dotenv import load_dotenv

    load_dotenv()

    from pipeline.utils import get_claude_client, strip_json_fences, CLAUDE_MODEL

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

    # Build merchant summary
    merchant_data = []
    for merchant, group in df.groupby("Merchant"):
        cats = group["Category"].value_counts().to_dict()
        accts = group["Account"].unique().tolist()
        dates = {
            "first": group["Date"].min().strftime("%Y-%m-%d"),
            "last": group["Date"].max().strftime("%Y-%m-%d"),
        }
        total = group["Amount"].sum()
        merchant_data.append({
            "merchant": merchant, "count": len(group),
            "total": round(total, 2), "categories": cats,
            "accounts": accts, "date_range": dates,
        })

    merchant_data.sort(key=lambda x: x["count"], reverse=True)

    # Top 100 + business-relevant merchants
    top_merchants = merchant_data[:100]
    biz_merchants = [m for m in merchant_data if any(
        cat in str(m["categories"])
        for cat in ["Business Technology", "Gen AI", "Accenture", "Vivant"]
    )]
    seen = set()
    combined = []
    for m in top_merchants + biz_merchants:
        if m["merchant"] not in seen:
            combined.append(m)
            seen.add(m["merchant"])

    # Account summary
    account_summary = {}
    for acct, group in df.groupby("Account"):
        account_summary[acct] = {
            "count": len(group),
            "total_debits": round(group[group["Amount"] < 0]["Amount"].sum(), 2),
            "total_credits": round(group[group["Amount"] > 0]["Amount"].sum(), 2),
            "categories": group["Category"].value_counts().head(5).to_dict(),
        }

    prompt = f"""You are a senior CPA and financial data architect. Analyze this household's
transaction data and recommend comprehensive vendor-entity mapping rules.

## Account Data
{json.dumps(account_summary, indent=2, default=str)}

## Merchant Data (top merchants + all business-relevant)
{json.dumps(combined, indent=2, default=str)}

## Tasks
1. VENDOR ENTITY RULES: Recommend vendor-entity rules with vendor_pattern, entity_name,
   segment_override, effective_from, effective_to, priority, reasoning.
2. ACCOUNT-LEVEL DEFAULTS: Recommend default_segment and default_business_entity per account.
3. CATEGORIZATION CONCERNS: Flag miscategorized or ambiguous merchants.
4. DEDUCTION OPPORTUNITIES: Flag missed tax deduction patterns.

Return JSON with keys: new_vendor_rules, account_defaults, categorization_issues, deduction_opportunities.
Return ONLY JSON."""

    print("Calling Claude API for vendor rule analysis...")
    client = get_claude_client()
    response = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = strip_json_fences(response.content[0].text)
    output_path = args.output if hasattr(args, "output") and args.output else (
        PROJECT_ROOT / "scripts" / "claude_rule_analysis.json"
    )
    output_path = Path(output_path)
    with open(output_path, "w") as f:
        f.write(raw)

    result = json.loads(raw)

    print(f"\n{'=' * 70}")
    print(f"NEW VENDOR RULES: {len(result.get('new_vendor_rules', []))}")
    print(f"{'=' * 70}")
    for rule in result.get("new_vendor_rules", []):
        print(f"  {rule['vendor_pattern']} -> {rule['entity_name']} "
              f"({rule.get('segment_override', 'N/A')}) "
              f"[{rule.get('effective_from', 'any')}-{rule.get('effective_to', 'any')}]")
        print(f"    Reason: {rule.get('reasoning', '')}")

    print(f"\n{'=' * 70}")
    print("ACCOUNT DEFAULTS")
    print(f"{'=' * 70}")
    for acct, defaults in result.get("account_defaults", {}).items():
        print(f"  {acct}: {defaults}")

    print(f"\n{'=' * 70}")
    print(f"CATEGORIZATION ISSUES: {len(result.get('categorization_issues', []))}")
    print(f"{'=' * 70}")
    for issue in result.get("categorization_issues", []):
        print(f"  - {issue}")

    print(f"\n{'=' * 70}")
    print(f"DEDUCTION OPPORTUNITIES: {len(result.get('deduction_opportunities', []))}")
    print(f"{'=' * 70}")
    for opp in result.get("deduction_opportunities", []):
        print(f"  - {opp}")

    print(f"\nFull analysis saved to: {output_path}")


# ============================================================================
# test — replaces test_rules_matching.py
# ============================================================================
async def cmd_test(args: argparse.Namespace) -> None:
    """Test that vendor rules actually match real Monarch merchant names."""
    import pandas as pd
    from pipeline.db import get_all_vendor_rules, get_all_business_entities, init_db
    from pipeline.utils import create_engine_and_session

    engine, Session = create_engine_and_session()
    await init_db(engine)

    base = Path(os.environ.get(
        "IMPORT_DIR",
        str(PROJECT_ROOT / "data" / "imports"),
    ))
    mc = base / "Monarch" / "Monarch-Transactions.csv"
    if not mc.exists():
        print(f"[ERROR] Monarch CSV not found at {mc}")
        await engine.dispose()
        return

    df = pd.read_csv(mc, dtype=str)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

    async with Session() as session:
        rules = await get_all_vendor_rules(session, active_only=True)
        entities = await get_all_business_entities(session, include_inactive=True)
        eid_to_name, _ = _get_entity_maps(entities)

    print("RULE MATCHING TEST")
    print("=" * 80)
    total_matched = 0
    total_amount = 0.0

    for rule in sorted(rules, key=lambda r: r.vendor_pattern):
        pattern = rule.vendor_pattern.lower()
        entity_name = eid_to_name.get(rule.business_entity_id, "?")
        fr = rule.effective_from
        to = rule.effective_to

        matched = []
        for _, row in df.iterrows():
            merchant = str(row["Merchant"]).strip()
            tx_date = row["Date"].date()
            if fr and tx_date < fr:
                continue
            if to and tx_date > to:
                continue
            if re.search(pattern, merchant, re.IGNORECASE):
                matched.append({
                    "merchant": merchant, "date": str(tx_date),
                    "amount": row["Amount"], "account": row["Account"],
                })

        if matched:
            match_total = sum(m["amount"] for m in matched)
            total_matched += len(matched)
            total_amount += match_total
            print(f"\n  {rule.vendor_pattern} -> {entity_name}")
            print(f"    Dates: {fr or 'any'} to {to or 'any'}")
            print(f"    Matched: {len(matched)} txns, ${match_total:,.2f}")
            unique_merchants = set(m["merchant"] for m in matched)
            for um in sorted(unique_merchants):
                count = sum(1 for m in matched if m["merchant"] == um)
                print(f"      {um}: {count} txns")
        else:
            print(f"\n  {rule.vendor_pattern} -> {entity_name}")
            print(f"    Dates: {fr or 'any'} to {to or 'any'}")
            print(f"    NO MATCHES (rule may need adjustment)")

    print(f"\n{'=' * 80}")
    print(f"TOTAL: {total_matched} transactions matched, ${total_amount:,.2f}")

    await engine.dispose()


# ============================================================================
# replace — replaces replace_rules.py
# ============================================================================
async def cmd_replace(args: argparse.Namespace) -> None:
    """Replace all existing vendor rules with a clean set from a Claude analysis JSON.

    Deactivates all old rules, then inserts the new ones from the file.
    Also re-adds core income/reimbursement rules that the analysis may not include.
    """
    from sqlalchemy import text
    from pipeline.db import create_vendor_rule, get_all_business_entities, init_db
    from pipeline.utils import create_engine_and_session

    analysis_file = Path(args.file)
    if not analysis_file.exists():
        print(f"[ERROR] Analysis file not found: {analysis_file}")
        return

    with open(analysis_file) as f:
        analysis = json.load(f)

    engine, Session = create_engine_and_session()
    await init_db(engine)

    async with Session() as session:
        async with session.begin():
            # Deactivate ALL existing rules
            await session.execute(text("UPDATE vendor_entity_rules SET is_active=0"))
            logger.info("Deactivated all existing vendor rules.")

            entities = await get_all_business_entities(session, include_inactive=True)
            _, name_to_id = _get_entity_maps(entities)

            # Insert rules from analysis
            new_rules = analysis.get("vendor_rules", analysis.get("new_vendor_rules", []))
            added = 0
            for rule in new_rules:
                entity_name = rule.get("entity_name", "")
                entity_id = name_to_id.get(entity_name)
                if not entity_id:
                    logger.warning(f"Entity not found: {entity_name}")
                    continue

                await create_vendor_rule(session, {
                    "vendor_pattern": rule["vendor_pattern"],
                    "business_entity_id": entity_id,
                    "segment_override": rule.get("segment") or rule.get("segment_override"),
                    "effective_from": _parse_date(rule.get("effective_from")),
                    "effective_to": _parse_date(rule.get("effective_to")),
                    "priority": rule.get("priority", 10),
                })
                added += 1

            # Re-add core income/reimbursement rules
            extra_rules = [
                {"vendor_pattern": "vivant behaviora",
                 "business_entity_id": name_to_id.get("Vivant"),
                 "segment_override": None, "priority": 15},
                {"vendor_pattern": "accenture",
                 "business_entity_id": name_to_id.get("Accenture"),
                 "segment_override": None, "priority": 15},
                {"vendor_pattern": "upwork",
                 "business_entity_id": name_to_id.get("Mike Aron Visuals"),
                 "segment_override": "business",
                 "effective_to": date(2025, 12, 31), "priority": 15},
                {"vendor_pattern": "upwork",
                 "business_entity_id": name_to_id.get("AutoRev"),
                 "segment_override": "business",
                 "effective_from": date(2026, 1, 1), "priority": 15},
            ]
            for r in extra_rules:
                if r.get("business_entity_id"):
                    await create_vendor_rule(session, r)
                    added += 1

            logger.info(f"Inserted {added} new rules.")

    # Print final state
    async with Session() as session:
        r = await session.execute(text(
            "SELECT vr.id, vr.vendor_pattern, be.name, vr.segment_override, "
            "vr.effective_from, vr.effective_to, vr.priority "
            "FROM vendor_entity_rules vr "
            "JOIN business_entities be ON be.id = vr.business_entity_id "
            "WHERE vr.is_active=1 "
            "ORDER BY vr.vendor_pattern, vr.effective_from"
        ))
        rows = r.fetchall()
        logger.info(f"Final active rules: {len(rows)}")
        for row in rows:
            fr = str(row[4]) if row[4] else "any"
            to = str(row[5]) if row[5] else "any"
            seg = row[3] or "-"
            logger.info(f"  {row[1]:<40s} -> {row[2]:<25s} seg={seg:<12s} "
                        f"{fr:>10s} - {to:>10s}  pri={row[6]}")

    await engine.dispose()


# ============================================================================
# CLI entry point
# ============================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rules",
        description="SirHENRY vendor entity rules toolkit (consolidated)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = sub.add_parser("list", help="List all vendor entity rules")
    list_p.add_argument("--all", action="store_true",
                        help="Include inactive rules (default: active only)")
    list_p.add_argument("--group", "-g", action="store_true",
                        help="Group rules by entity")

    # add
    add_p = sub.add_parser("add", help="Add vendor entity rules from a JSON file")
    add_p.add_argument("file", help="Path to JSON file containing rules to add")

    # apply
    apply_p = sub.add_parser("apply", help="Re-apply all entity rules to transactions")
    apply_p.add_argument("--from-file", metavar="FILE",
                         help="Import rules from a Claude analysis JSON first, then apply")

    # build
    build_p = sub.add_parser("build", help="Use Claude to recommend vendor entity rules")
    build_p.add_argument("--output", "-o", metavar="FILE",
                         help="Output file for the analysis JSON "
                              "(default: scripts/claude_rule_analysis.json)")

    # test
    sub.add_parser("test", help="Test rule matching against Monarch CSV data")

    # replace
    replace_p = sub.add_parser("replace",
                               help="Replace ALL rules from a Claude analysis JSON")
    replace_p.add_argument("file", help="Path to Claude analysis JSON file")

    return parser


COMMANDS = {
    "list": cmd_list,
    "add": cmd_add,
    "apply": cmd_apply,
    "build": cmd_build,
    "test": cmd_test,
    "replace": cmd_replace,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMANDS[args.command]
    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
