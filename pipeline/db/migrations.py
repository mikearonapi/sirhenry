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


async def _016_chat_tables(session: AsyncSession) -> None:
    """Create chat_conversations and chat_messages tables for persistent history."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS chat_conversations (
            id           {d['pk']},
            title        VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
            page_context VARCHAR(50),
            created_at   {d['ts_now']},
            updated_at   {d['ts_now']}
        )
    """))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_chat_conv_context ON chat_conversations(page_context)"
    ))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_chat_conv_updated ON chat_conversations(updated_at)"
    ))
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id              {d['pk']},
            conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
            role            VARCHAR(20) NOT NULL,
            content         TEXT NOT NULL,
            actions_json    TEXT,
            created_at      {d['ts_now']}
        )
    """))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_chat_msg_conv ON chat_messages(conversation_id)"
    ))
    logger.info("Created chat_conversations and chat_messages tables.")


async def _017_business_entity_enrichment(session: AsyncSession) -> None:
    """Add description and expected_expenses to business_entities for AI categorization enrichment."""
    cols = [
        ("business_entities", "description", "TEXT"),
        ("business_entities", "expected_expenses", "TEXT"),
    ]
    for table, col, col_type in cols:
        try:
            await session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        except Exception:
            pass  # Column already exists
    logger.info("Added description, expected_expenses to business_entities.")


async def _018_category_rules_table(session: AsyncSession) -> None:
    """Create category_rules table for learned categorization patterns."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS category_rules (
            id {d['pk']},
            merchant_pattern VARCHAR(255) NOT NULL,
            category VARCHAR(100),
            tax_category VARCHAR(200),
            segment VARCHAR(20),
            business_entity_id INTEGER REFERENCES business_entities(id),
            source VARCHAR(20) NOT NULL DEFAULT 'user_override',
            match_count INTEGER NOT NULL DEFAULT 0,
            is_active {d['bool_false']},
            created_at {d['ts_now']},
            CONSTRAINT uq_category_rule_merchant UNIQUE (merchant_pattern)
        )
    """))
    # Fix: is_active should default to TRUE
    try:
        await session.execute(text(
            "UPDATE category_rules SET is_active = 1 WHERE is_active = 0"
        ))
    except Exception:
        pass
    logger.info("Created category_rules table.")


async def _019_payroll_connection_tables(session: AsyncSession) -> None:
    """Create payroll_connections and pay_stub_records tables."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS payroll_connections (
            id {d['pk']},
            plaid_user_token VARCHAR(200) NOT NULL,
            plaid_item_id VARCHAR(100),
            employer_name VARCHAR(255),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            income_source_type VARCHAR(20) NOT NULL DEFAULT 'payroll',
            last_synced_at {d['ts_null']},
            raw_data_json TEXT,
            created_at {d['ts_now']},
            updated_at {d['ts_now']}
        )
    """))
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS pay_stub_records (
            id {d['pk']},
            connection_id INTEGER NOT NULL REFERENCES payroll_connections(id) ON DELETE CASCADE,
            pay_date DATE NOT NULL,
            pay_period_start DATE,
            pay_period_end DATE,
            pay_frequency VARCHAR(20),
            gross_pay FLOAT,
            gross_pay_ytd FLOAT,
            net_pay FLOAT,
            net_pay_ytd FLOAT,
            deductions_json TEXT,
            employer_name VARCHAR(255),
            employer_ein VARCHAR(20),
            employer_address_json TEXT,
            work_state VARCHAR(2),
            created_at {d['ts_now']}
        )
    """))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_pay_stub_date ON pay_stub_records(connection_id, pay_date)"
    ))


async def _020_manual_asset_valuation_columns(session: AsyncSession) -> None:
    """Add valuation tracking columns to manual_assets."""
    for col, col_type in [
        ("vin", "VARCHAR(17)"),
        ("valuation_source", "VARCHAR(30)"),
        ("valuation_date", "DATETIME"),
        ("valuation_api_data_json", "TEXT"),
    ]:
        try:
            await session.execute(text(f"ALTER TABLE manual_assets ADD COLUMN {col} {col_type}"))
        except Exception:
            pass


async def _021_setup_completed_tracking(session: AsyncSession) -> None:
    """Add setup_completed_at to household_profiles."""
    try:
        await session.execute(text(
            "ALTER TABLE household_profiles ADD COLUMN setup_completed_at DATETIME"
        ))
    except Exception:
        pass


async def _022_payroll_user_id_column(session: AsyncSession) -> None:
    """Add plaid_user_id column and make plaid_user_token nullable (Plaid Dec 2025 change)."""
    try:
        await session.execute(text(
            "ALTER TABLE payroll_connections ADD COLUMN plaid_user_id VARCHAR(100)"
        ))
    except Exception:
        pass


async def _023_dedup_plaid_csv_duplicates(session: AsyncSession) -> None:
    """Mark Plaid transactions as excluded when a matching CSV transaction
    already exists (same account, date, amount).  This fixes double-counting
    caused by the same real-world transaction being imported via both CSV
    and Plaid with different hashes."""
    # Find Plaid transactions that duplicate a CSV transaction.
    # For each (account_id, date, amount) combo that has BOTH a csv and plaid
    # row, mark the plaid row as excluded.
    result = await session.execute(text("""
        UPDATE transactions
        SET is_excluded = 1,
            notes = COALESCE(notes, '') || ' [excluded: cross-source duplicate of CSV]'
        WHERE id IN (
            SELECT p.id
            FROM transactions p
            INNER JOIN transactions c
                ON c.account_id = p.account_id
                AND DATE(c.date) = DATE(p.date)
                AND c.amount = p.amount
                AND c.data_source != 'plaid'
                AND c.is_excluded = 0
            WHERE p.data_source = 'plaid'
              AND p.is_excluded = 0
        )
    """))
    count = result.rowcount
    logger.info(f"Cross-source dedup: excluded {count} Plaid duplicate transactions.")


async def _024_user_context_table(session: AsyncSession) -> None:
    """Create user_context table for persistent learned facts."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS user_context (
            id {d['pk']},
            category VARCHAR(50) NOT NULL,
            key VARCHAR(255) NOT NULL,
            value TEXT NOT NULL,
            source VARCHAR(20) NOT NULL DEFAULT 'chat',
            confidence FLOAT NOT NULL DEFAULT 1.0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at {d['ts_now']},
            updated_at {d['ts_now']},
            UNIQUE(category, key)
        )
    """))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_user_context_active ON user_context(is_active)"
    ))


async def _025_retirement_budget_overrides_table(session: AsyncSession) -> None:
    """Create retirement_budget_overrides table for per-category retirement adjustments."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS retirement_budget_overrides (
            id {d['pk']},
            profile_id INTEGER REFERENCES retirement_profiles(id),
            category VARCHAR(100) NOT NULL,
            multiplier FLOAT DEFAULT 1.0,
            fixed_amount FLOAT,
            reason VARCHAR(255),
            created_at {d['ts_now']},
            updated_at {d['ts_now']},
            UNIQUE(profile_id, category)
        )
    """))


async def _026_category_rule_date_fields(session: AsyncSession) -> None:
    """Add effective_from and effective_to date columns to category_rules."""
    for col in ("effective_from", "effective_to"):
        try:
            await session.execute(text(
                f"ALTER TABLE category_rules ADD COLUMN {col} DATE"
            ))
        except Exception:
            pass  # Column already exists


async def _027_transaction_parent_id(session: AsyncSession) -> None:
    """Add parent_transaction_id column for Amazon split transactions."""
    try:
        await session.execute(text(
            "ALTER TABLE transactions ADD COLUMN parent_transaction_id INTEGER REFERENCES transactions(id)"
        ))
    except Exception:
        pass  # Column already exists
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_transaction_parent ON transactions(parent_transaction_id)"
    ))


async def _028_flow_type_column_and_backfill(session: AsyncSession) -> None:
    """Add flow_type column and classify all existing transactions."""
    try:
        await session.execute(text(
            "ALTER TABLE transactions ADD COLUMN flow_type VARCHAR(20)"
        ))
    except Exception:
        pass  # Column already exists

    from pipeline.db.flow_classifier import classify_flow_type

    result = await session.execute(text(
        "SELECT id, amount, coalesce(effective_category, category), description "
        "FROM transactions WHERE flow_type IS NULL"
    ))
    rows = result.fetchall()
    batch: list[dict] = []
    for txn_id, amount, category, description in rows:
        ft = classify_flow_type(amount or 0, category, description)
        batch.append({"id": txn_id, "ft": ft})
        if len(batch) >= 500:
            await session.execute(
                text("UPDATE transactions SET flow_type = :ft WHERE id = :id"),
                batch,
            )
            batch = []
    if batch:
        await session.execute(
            text("UPDATE transactions SET flow_type = :ft WHERE id = :id"),
            batch,
        )


async def _029_app_settings_table(session: AsyncSession) -> None:
    """Create app_settings table for application-level configuration."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS app_settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT,
            updated_at {d['ts_now']}
        )
    """))


async def _030_life_scenario_composite_ids(session: AsyncSession) -> None:
    """Add composite_scenario_ids column to life_scenarios table."""
    try:
        await session.execute(text(
            "ALTER TABLE life_scenarios ADD COLUMN composite_scenario_ids TEXT"
        ))
    except Exception:
        pass  # Column already exists


async def _031_performance_indexes(session: AsyncSession) -> None:
    """Add performance indexes for common query patterns."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_transactions_account_id ON transactions(account_id)",
        "CREATE INDEX IF NOT EXISTS ix_transactions_date ON transactions(date)",
        "CREATE INDEX IF NOT EXISTS ix_transactions_period ON transactions(year, month)",
        "CREATE INDEX IF NOT EXISTS ix_tax_items_tax_year ON tax_items(tax_year)",
        "CREATE INDEX IF NOT EXISTS ix_plaid_accounts_item_id ON plaid_accounts(item_id)",
        "CREATE INDEX IF NOT EXISTS ix_category_rules_category ON category_rules(category)",
    ]
    for ddl in indexes:
        try:
            await session.execute(text(ddl))
        except Exception:
            pass  # Index already exists or table not yet created


async def _032_plaid_sync_phase_column(session: AsyncSession) -> None:
    """Add sync_phase column to plaid_items for granular sync progress tracking."""
    try:
        await session.execute(
            text("ALTER TABLE plaid_items ADD COLUMN sync_phase VARCHAR(30)")
        )
    except Exception:
        pass  # Column already exists


async def _033_additional_indexes(session: AsyncSession) -> None:
    """Add missing indexes for frequent query filters."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_transactions_excluded ON transactions(is_excluded)",
        "CREATE INDEX IF NOT EXISTS ix_transactions_effective_category ON transactions(effective_category)",
        "CREATE INDEX IF NOT EXISTS ix_transactions_period_ym ON transactions(period_year, period_month)",
        "CREATE INDEX IF NOT EXISTS ix_recurring_status ON recurring_transactions(status)",
        "CREATE INDEX IF NOT EXISTS ix_accounts_is_active ON accounts(is_active)",
        "CREATE INDEX IF NOT EXISTS ix_insurance_is_active ON insurance_policies(is_active)",
    ]
    for ddl in indexes:
        try:
            await session.execute(text(ddl))
        except Exception:
            pass


async def _034_preferred_name_column(session: AsyncSession) -> None:
    """Add spouse_a_preferred_name to household_profiles for chat personalization."""
    try:
        await session.execute(text(
            "ALTER TABLE household_profiles ADD COLUMN spouse_a_preferred_name VARCHAR(100)"
        ))
    except Exception:
        pass


async def _035_error_logs_table(session: AsyncSession) -> None:
    """Create error_logs table for user-submitted error reports."""
    d = _ddl(session)
    await session.execute(text(f"""
        CREATE TABLE IF NOT EXISTS error_logs (
            id {d['pk']},
            timestamp {d['ts_now']},
            error_type VARCHAR(50) NOT NULL,
            message VARCHAR(1000),
            stack_trace TEXT,
            source_url VARCHAR(500),
            user_agent VARCHAR(200),
            user_note VARCHAR(500),
            status VARCHAR(20) NOT NULL DEFAULT 'new',
            context_json TEXT
        )
    """))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_error_log_timestamp ON error_logs(timestamp)"
    ))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_error_log_status ON error_logs(status)"
    ))


async def _036_investment_holding_plaid_columns(session: AsyncSession) -> None:
    """Add data_source and plaid_security_id columns to investment_holdings for Plaid sync."""
    cols = [
        ("investment_holdings", "data_source", "VARCHAR(20) NOT NULL DEFAULT 'manual'"),
        ("investment_holdings", "plaid_security_id", "VARCHAR(100)"),
    ]
    for table, col, col_type in cols:
        try:
            await session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        except Exception:
            pass  # Column already exists


async def _037_plaid_item_env_column(session: AsyncSession) -> None:
    """Add plaid_env column to plaid_items to track sandbox vs production."""
    try:
        await session.execute(text(
            "ALTER TABLE plaid_items ADD COLUMN plaid_env VARCHAR(20) NOT NULL DEFAULT 'production'"
        ))
    except Exception:
        pass  # Column already exists


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
    ("016_chat_tables", _016_chat_tables),
    ("017_business_entity_enrichment", _017_business_entity_enrichment),
    ("018_category_rules_table", _018_category_rules_table),
    ("019_payroll_connection_tables", _019_payroll_connection_tables),
    ("020_manual_asset_valuation_columns", _020_manual_asset_valuation_columns),
    ("021_setup_completed_tracking", _021_setup_completed_tracking),
    ("022_payroll_user_id_column", _022_payroll_user_id_column),
    ("023_dedup_plaid_csv_duplicates", _023_dedup_plaid_csv_duplicates),
    ("024_user_context_table", _024_user_context_table),
    ("025_retirement_budget_overrides_table", _025_retirement_budget_overrides_table),
    ("026_category_rule_date_fields", _026_category_rule_date_fields),
    ("027_transaction_parent_id", _027_transaction_parent_id),
    ("028_flow_type_column_and_backfill", _028_flow_type_column_and_backfill),
    ("029_app_settings_table", _029_app_settings_table),
    ("030_life_scenario_composite_ids", _030_life_scenario_composite_ids),
    ("031_performance_indexes", _031_performance_indexes),
    ("032_plaid_sync_phase_column", _032_plaid_sync_phase_column),
    ("033_additional_indexes", _033_additional_indexes),
    ("034_preferred_name_column", _034_preferred_name_column),
    ("035_error_logs_table", _035_error_logs_table),
    ("036_investment_holding_plaid_columns", _036_investment_holding_plaid_columns),
    ("037_plaid_item_env_column", _037_plaid_item_env_column),
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
