# Scripts

Utility scripts for data management, analysis, and one-time migrations.

> **WARNING:** Scripts marked "one-time migration" have already been run against the
> production database. Running them again is generally safe (most are idempotent) but
> unnecessary. When in doubt, run with `--dry-run` if supported, or inspect the code first.

## Script Index

| Script | Category | Description |
|--------|----------|-------------|
| `add_adobe_rules.py` | Maintenance | Adds missing Adobe vendor entity rules |
| `add_new_rules.py` | Maintenance | Adds new vendor rules (Trak Racer, Shopify, Cloudflare, etc.) |
| `amazon_reconciliation.py` | Maintenance | Reports Amazon vs CC gaps, rematches orders |
| `analyze_vendors.py` | Analysis | Analyzes vendors across data sources (reads Monarch CSV) |
| `apply_claude_rules.py` | Maintenance | Applies Claude-recommended vendor rules to the DB |
| `audit_db.py` | Analysis | Lists tables and schema info |
| `build_rules_with_claude.py` | Analysis | Uses Claude to recommend vendor rules from transaction data |
| `categorize_amazon_orders.py` | Maintenance | Runs Claude categorization for Amazon orders missing category |
| `check_plaid_status.py` | Analysis | Prints Plaid item status, cursors, and transaction counts |
| `cleanup_duplicates.py` | One-time migration | Removes CC transactions that overlap with Monarch |
| `compare_sources.py` | Analysis | Compares Monarch vs credit card CSV side-by-side |
| `csv_audit.py` | Analysis | Counts transaction rows in each credit card CSV |
| `data_audit.py` | Analysis | Runs a broad data audit (table counts, etc.) |
| `data_audit_2.py` | Analysis | Duplicates detail, CSV coverage, overlap analysis |
| `deep_analysis.py` | Analysis | Analyzes business transactions from June 2025 onward |
| `deep_dive_all_txns.py` | Analysis | Analyzes all Monarch transactions for anomalies |
| `do_resync.py` | Maintenance | Runs Plaid sync for all items |
| `find_duplicates.py` | Analysis | Finds duplicate transactions in the DB |
| `fix_accounts.py` | One-time migration | Updates account values (current_value, as_of_date) |
| `fix_and_audit_rsu.py` | One-time migration | Fixes Home Loan institution and audits equity_grants |
| `import_amazon_all.py` | Import | Imports all Amazon export files for configured accounts |
| `list_rules.py` | Analysis | Lists active vendor entity rules |
| `merge_plaid_accounts.py` | One-time migration | Merges duplicate Plaid shell accounts into originals |
| `migrate_columns.py` | One-time migration | Adds new columns to existing tables (ALTER TABLE) |
| `migrate_shipment_level.py` | One-time migration | Re-imports Amazon orders at shipment level |
| `plaid_tx_summary.py` | Analysis | Summarizes Plaid transactions by period |
| `populate_rsus.py` | One-time migration | Populates equity_grants and vesting_events |
| `reapply_rules.py` | Maintenance | Re-applies all entity rules to all transactions |
| `rename_entity.py` | One-time migration | Renames Provisional Consulting to Mike Aron AI Consulting |
| `replace_rules.py` | One-time migration | Replaces all vendor rules with a Claude-derived set |
| `reset_and_resync.py` | Maintenance | Deletes Plaid transactions, resets cursors, re-syncs |
| `reset_plaid_sync.py` | One-time migration | Deletes Plaid transactions and resets sync cursors |
| `scan_business_vendors.py` | Analysis | Scans Monarch for business-relevant vendors |
| `show_rules.py` | Analysis | Displays all vendor entity rules |
| `smart_rematch.py` | Maintenance | Rebuilds Amazon–CC matches using optimal assignment |
| `test_rules_matching.py` | Analysis | Tests that vendor rules match Monarch merchant names |

## Categories

- **Maintenance** — Safe to run anytime for ongoing operations
- **Analysis** — Read-only investigation and debugging tools
- **Import** — Imports external data sources into the database
- **One-time migration** — Already applied; re-running is safe but unnecessary
