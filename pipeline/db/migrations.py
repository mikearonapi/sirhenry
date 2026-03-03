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
# Migration registry — add new migrations to the END of this list.
# ---------------------------------------------------------------------------
async def _001_family_members_table(session: AsyncSession) -> None:
    """Create family_members table if it doesn't exist."""
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            household_id INTEGER NOT NULL REFERENCES household_profiles(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            relationship VARCHAR(20) NOT NULL,
            date_of_birth DATE,
            ssn_last4 VARCHAR(4),
            is_earner BOOLEAN NOT NULL DEFAULT 0,
            income FLOAT DEFAULT 0.0,
            employer VARCHAR(255),
            work_state VARCHAR(2),
            employer_start_date DATE,
            grade_level VARCHAR(50),
            school_name VARCHAR(255),
            care_cost_annual FLOAT,
            college_start_year INTEGER,
            notes TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        ("transactions", "authorized_date", "DATETIME"),
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


# Ordered list of all migrations
MIGRATIONS: list[tuple[str, callable]] = [
    ("001_family_members_table", _001_family_members_table),
    ("002_household_columns", _002_household_columns),
    ("003_plaid_enrichment_columns", _003_plaid_enrichment_columns),
    ("004_account_subtype_default", _004_account_subtype_default),
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
            applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
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
