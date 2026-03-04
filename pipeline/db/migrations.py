"""
Schema migrations — idempotent DDL operations that run on startup.

Each migration is a named function registered in MIGRATIONS (order matters).
A `_schema_migrations` table tracks which migrations have already run,
so they execute at most once per database.
"""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dialect helpers — support both SQLite and Postgres (Neon)
# ---------------------------------------------------------------------------
def _is_postgres(session: AsyncSession) -> bool:
    """Detect if the session is connected to a Postgres database."""
    url = str(session.bind.url) if session.bind else ""
    return "postgresql" in url


def _ddl(session: AsyncSession) -> dict[str, str]:
    """Return dialect-specific DDL fragments."""
    pg = _is_postgres(session)
    return {
        "pk": "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT",
        "bool_false": "BOOLEAN NOT NULL DEFAULT FALSE" if pg else "BOOLEAN NOT NULL DEFAULT 0",
        "bool_null": "BOOLEAN" if pg else "BOOLEAN",
        "ts_now": "TIMESTAMP NOT NULL DEFAULT NOW()" if pg else "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ts_null": "TIMESTAMP" if pg else "DATETIME",
    }


# ---------------------------------------------------------------------------
# Migration registry — add new migrations to the END of this list.
# ---------------------------------------------------------------------------
async def _001_family_members_table(session: AsyncSession) -> None:
    """Create family_members table if it doesn't exist."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS family_members (
            id {d['pk']},
            household_id INTEGER NOT NULL REFERENCES household_profiles(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            relationship VARCHAR(20) NOT NULL,
            date_of_birth DATE,
            ssn_last4 VARCHAR(4),
            is_earner {d['bool_false']},
            income FLOAT DEFAULT 0.0,
            employer VARCHAR(255),
            work_state VARCHAR(2),
            employer_start_date DATE,
            grade_level VARCHAR(50),
            school_name VARCHAR(255),
            care_cost_annual FLOAT,
            college_start_year INTEGER,
            notes TEXT,
            created_at {d['ts_now']},
            updated_at {d['ts_now']}
        )
    """))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_family_member_household ON family_members(household_id)"
    ))


async def _002_household_columns(session: AsyncSession) -> None:
    """Add extended columns to household_profiles and benefit_packages."""
    columns = [
        ("household_profiles", "spouse_a_work_state", "VARCHAR(2)"),
        ("household_profiles", "spouse_b_work_state", "VARCHAR(2)"),
        ("household_profiles", "spouse_a_start_date", "DATE"),
        ("household_profiles", "spouse_b_start_date", "DATE"),
        ("household_profiles", "estate_will_status", "VARCHAR(20)"),
        ("household_profiles", "estate_poa_status", "VARCHAR(20)"),
        ("household_profiles", "estate_hcd_status", "VARCHAR(20)"),
        ("household_profiles", "estate_trust_status", "VARCHAR(20)"),
        ("household_profiles", "beneficiaries_reviewed", "BOOLEAN"),
        ("household_profiles", "beneficiaries_reviewed_date", "DATE"),
        ("household_profiles", "other_income_annual", "FLOAT"),
        ("household_profiles", "other_income_sources_json", "TEXT"),
        ("benefit_packages", "annual_401k_contribution", "FLOAT"),
        ("benefit_packages", "health_plan_options_json", "TEXT"),
        ("benefit_packages", "life_insurance_coverage", "FLOAT"),
        ("benefit_packages", "life_insurance_cost_monthly", "FLOAT"),
        ("benefit_packages", "std_coverage_pct", "FLOAT"),
        ("benefit_packages", "std_waiting_days", "INTEGER"),
        ("benefit_packages", "ltd_coverage_pct", "FLOAT"),
        ("benefit_packages", "ltd_waiting_days", "INTEGER"),
        ("benefit_packages", "commuter_monthly_limit", "FLOAT"),
        ("benefit_packages", "tuition_reimbursement_annual", "FLOAT"),
        ("benefit_packages", "open_enrollment_start", "DATE"),
        ("benefit_packages", "open_enrollment_end", "DATE"),
    ]
    for table, col, col_type in columns:
        try:
            await session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        except Exception:
            pass  # Column already exists


async def _003_plaid_enrichment_columns(session: AsyncSession) -> None:
    """Add Plaid enrichment columns to transactions table."""
    columns = [
        ("transactions", "merchant_name", "VARCHAR(255)"),
        ("transactions", "authorized_date", "TIMESTAMP"),
        ("transactions", "payment_channel", "VARCHAR(20)"),
        ("transactions", "plaid_pfc_primary", "VARCHAR(100)"),
        ("transactions", "plaid_pfc_detailed", "VARCHAR(100)"),
        ("transactions", "plaid_pfc_confidence", "VARCHAR(20)"),
        ("transactions", "merchant_logo_url", "VARCHAR(500)"),
        ("transactions", "merchant_website", "VARCHAR(500)"),
        ("transactions", "plaid_location_json", "TEXT"),
        ("transactions", "plaid_counterparties_json", "TEXT"),
    ]
    for table, col, col_type in columns:
        try:
            await session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        except Exception:
            pass  # Column already exists


async def _004_account_subtype_default(session: AsyncSession) -> None:
    """Set subtype='checking' for accounts that have NULL subtype."""
    result = await session.execute(
        text("SELECT COUNT(*) FROM accounts WHERE subtype IS NULL")
    )
    count = result.scalar() or 0
    if count > 0:
        await session.execute(
            text("UPDATE accounts SET subtype = 'checking' WHERE subtype IS NULL")
        )
        logger.info(f"Set default subtype='checking' for {count} accounts.")


async def _005_data_source_columns(session: AsyncSession) -> None:
    """Add data_source column to accounts and transactions for provenance tracking."""
    cols = [
        ("accounts", "data_source", "VARCHAR(20) NOT NULL DEFAULT 'manual'"),
        ("transactions", "data_source", "VARCHAR(20) NOT NULL DEFAULT 'csv'"),
    ]
    for table, col, col_type in cols:
        try:
            await session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        except Exception:
            pass  # Column already exists

    # Backfill: accounts linked via PlaidAccount → data_source='plaid'
    try:
        await session.execute(text("""
            UPDATE accounts SET data_source = 'plaid'
            WHERE id IN (SELECT account_id FROM plaid_accounts WHERE account_id IS NOT NULL)
        """))
    except Exception:
        pass  # plaid_accounts table may not exist yet
    # Backfill: transactions with Plaid enrichment fields → data_source='plaid'
    try:
        await session.execute(text("""
            UPDATE transactions SET data_source = 'plaid'
            WHERE plaid_pfc_primary IS NOT NULL OR payment_channel IS NOT NULL
        """))
    except Exception:
        pass  # enrichment columns may not exist yet
    logger.info("Added data_source columns and backfilled existing data.")


async def _006_account_links_table(session: AsyncSession) -> None:
    """Create account_links table for tracking merged/linked accounts."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS account_links (
            id {d['pk']},
            primary_account_id INTEGER NOT NULL REFERENCES accounts(id),
            secondary_account_id INTEGER NOT NULL REFERENCES accounts(id),
            link_type VARCHAR(20) NOT NULL DEFAULT 'same_account',
            created_at {d['ts_now']},
            UNIQUE(primary_account_id, secondary_account_id)
        )
    """))
    logger.info("Created account_links table.")


async def _007_manual_asset_account_link(session: AsyncSession) -> None:
    """Add linked_account_id to manual_assets for bridging to Account table."""
    try:
        await session.execute(text(
            "ALTER TABLE manual_assets ADD COLUMN linked_account_id INTEGER REFERENCES accounts(id)"
        ))
    except Exception:
        pass  # Column already exists
    logger.info("Added linked_account_id to manual_assets.")


async def _008_k1_income_columns(session: AsyncSession):
    """Add K-1 income columns to tax_items table."""
    d = _ddl(session)
    cols = [
        ("k1_ordinary_income", "REAL"),
        ("k1_rental_income", "REAL"),
        ("k1_other_rental_income", "REAL"),
        ("k1_guaranteed_payments", "REAL"),
        ("k1_interest_income", "REAL"),
        ("k1_dividends", "REAL"),
        ("k1_qualified_dividends", "REAL"),
        ("k1_short_term_capital_gain", "REAL"),
        ("k1_long_term_capital_gain", "REAL"),
        ("k1_section_179", "REAL"),
        ("k1_distributions", "REAL"),
    ]
    for col_name, col_type in cols:
        try:
            await session.execute(text(
                f"ALTER TABLE tax_items ADD COLUMN {col_name} {col_type}"
            ))
        except Exception:
            pass  # Column already exists
    logger.info("Added K-1 income columns to tax_items.")


async def _009_additional_tax_form_columns(session: AsyncSession):
    """Add 1099-R, 1099-G, 1099-K, 1098 columns to tax_items table."""
    cols = [
        # 1099-R (retirement distributions)
        ("r_gross_distribution", "REAL"),
        ("r_taxable_amount", "REAL"),
        ("r_federal_tax_withheld", "REAL"),
        ("r_distribution_code", "VARCHAR(10)"),
        ("r_state_tax_withheld", "REAL"),
        ("r_state", "VARCHAR(2)"),
        # 1099-G (government payments)
        ("g_unemployment_compensation", "REAL"),
        ("g_state_tax_refund", "REAL"),
        ("g_federal_tax_withheld", "REAL"),
        ("g_state", "VARCHAR(2)"),
        # 1099-K (payment platforms)
        ("k_gross_amount", "REAL"),
        ("k_federal_tax_withheld", "REAL"),
        ("k_state", "VARCHAR(2)"),
        # 1098 (mortgage interest)
        ("m_mortgage_interest", "REAL"),
        ("m_points_paid", "REAL"),
        ("m_property_tax", "REAL"),
    ]
    for col_name, col_type in cols:
        try:
            await session.execute(text(
                f"ALTER TABLE tax_items ADD COLUMN {col_name} {col_type}"
            ))
        except Exception:
            pass  # Column already exists
    logger.info("Added 1099-R, 1099-G, 1099-K, 1098 columns to tax_items.")


async def _010_backfill_document_type(session: AsyncSession) -> None:
    """Backfill Document.document_type from TaxItem.form_type.
    The importer previously left document_type as 'processing' even after
    successful extraction. This migration sets it to the detected form type."""
    await session.execute(text("""
        UPDATE documents
        SET document_type = (
            SELECT ti.form_type FROM tax_items ti
            WHERE ti.source_document_id = documents.id
            LIMIT 1
        )
        WHERE document_type IN ('processing', 'other')
          AND EXISTS (
            SELECT 1 FROM tax_items ti
            WHERE ti.source_document_id = documents.id
          )
    """))
    logger.info("Backfilled document_type from tax_items form_type.")


async def _011_privacy_consent_table(session: AsyncSession) -> None:
    """Create user_privacy_consent table for tracking AI/Plaid/telemetry consent."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS user_privacy_consent (
            id {d['pk']},
            consent_type VARCHAR(50) NOT NULL,
            consented {d['bool_false']},
            consent_version VARCHAR(20) NOT NULL DEFAULT '1.0',
            consented_at {d['ts_null']},
            created_at {d['ts_now']},
            updated_at {d['ts_now']},
            UNIQUE(consent_type)
        )
    """))
    logger.info("Created user_privacy_consent table.")


async def _012_audit_log_table(session: AsyncSession) -> None:
    """Create audit_log table for tracking sensitive operations."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS audit_log (
            id {d['pk']},
            timestamp {d['ts_now']},
            action_type VARCHAR(50) NOT NULL,
            data_category VARCHAR(50),
            detail VARCHAR(500),
            duration_ms INTEGER
        )
    """))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_audit_timestamp ON audit_log(timestamp)"
    ))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_audit_action ON audit_log(action_type)"
    ))
    logger.info("Created audit_log table with indexes.")


# Ordered list of all migrations
async def _013_tax_strategy_enhanced_columns(session: AsyncSession) -> None:
    """Add confidence, category, complexity, and other enhanced fields to tax_strategies."""
    cols = [
        ("confidence", "FLOAT"),
        ("confidence_reasoning", "TEXT"),
        ("category", "VARCHAR(50)"),
        ("complexity", "VARCHAR(20)"),
        ("prerequisites_json", "TEXT"),
        ("who_its_for", "TEXT"),
        ("related_simulator", "VARCHAR(50)"),
    ]
    for col_name, col_type in cols:
        try:
            await session.execute(text(f"ALTER TABLE tax_strategies ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass  # Column already exists


async def _014_household_tax_strategy_profile(session: AsyncSession) -> None:
    """Add tax_strategy_profile_json column to household_profiles for interview answers."""
    try:
        await session.execute(text("ALTER TABLE household_profiles ADD COLUMN tax_strategy_profile_json TEXT"))
    except Exception:
        pass  # Column already exists


async def _015_target_allocations_table(session: AsyncSession) -> None:
    """Create target_allocations table for portfolio target allocation tracking."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS target_allocations (
            id {d['pk']},
            name VARCHAR(255) NOT NULL DEFAULT 'My Target Allocation',
            allocation_json TEXT NOT NULL DEFAULT '{{}}',
            is_active {"BOOLEAN NOT NULL DEFAULT TRUE" if _is_postgres(session) else "BOOLEAN NOT NULL DEFAULT 1"},
            created_at {d['ts_now']}
        )
    """))
    logger.info("Created target_allocations table.")


MIGRATIONS: list[tuple[str, callable]] = [
    ("001_family_members_table", _001_family_members_table),
    ("002_household_columns", _002_household_columns),
    ("003_plaid_enrichment_columns", _003_plaid_enrichment_columns),
    ("004_account_subtype_default", _004_account_subtype_default),
    ("005_data_source_columns", _005_data_source_columns),
    ("006_account_links_table", _006_account_links_table),
    ("007_manual_asset_account_link", _007_manual_asset_account_link),
    ("008_k1_income_columns", _008_k1_income_columns),
    ("009_additional_tax_form_columns", _009_additional_tax_form_columns),
    ("010_backfill_document_type", _010_backfill_document_type),
    ("011_privacy_consent_table", _011_privacy_consent_table),
    ("012_audit_log_table", _012_audit_log_table),
    ("013_tax_strategy_enhanced_columns", _013_tax_strategy_enhanced_columns),
    ("014_household_tax_strategy_profile", _014_household_tax_strategy_profile),
    ("015_target_allocations_table", _015_target_allocations_table),
]


# ---------------------------------------------------------------------------
# Runner — tracks applied migrations in a _schema_migrations table
# ---------------------------------------------------------------------------
async def run_migrations(session: AsyncSession) -> int:
    """
    Run all pending migrations. Returns the count of newly applied migrations.
    Safe to call on every startup — skips already-applied migrations.
    """
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            name VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await session.commit()

    result = await session.execute(text("SELECT name FROM _schema_migrations"))
    applied = {row[0] for row in result}

    count = 0
    for name, fn in MIGRATIONS:
        if name in applied:
            continue
        try:
            await fn(session)
            await session.execute(
                text("INSERT INTO _schema_migrations (name) VALUES (:name)"),
                {"name": name},
            )
            await session.commit()
            logger.info(f"Migration applied: {name}")
            count += 1
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration failed: {name} — {e}")
            raise

    if count == 0:
        logger.info("All migrations already applied.")
    else:
        logger.info(f"Applied {count} new migration(s).")
    return count
