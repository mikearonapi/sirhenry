"""Tests for the migration system."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from pipeline.db.migrations import run_migrations, MIGRATIONS


@pytest_asyncio.fixture
async def session():
    """Create an in-memory SQLite database for migration testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE household_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE benefit_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id INTEGER
            )
        """))
        await conn.execute(text("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                subtype TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_type TEXT,
                raw_text TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE tax_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_document_id INTEGER,
                form_type TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE plaid_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER
            )
        """))
        await conn.execute(text("""
            CREATE TABLE manual_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT
            )
        """))

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as sess:
        yield sess

    await engine.dispose()


@pytest.mark.asyncio
async def test_migrations_create_tracking_table(session):
    await run_migrations(session)
    result = await session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='_schema_migrations'")
    )
    assert result.scalar() == "_schema_migrations"


@pytest.mark.asyncio
async def test_all_migrations_recorded(session):
    await run_migrations(session)
    result = await session.execute(text("SELECT name FROM _schema_migrations ORDER BY name"))
    names = [row[0] for row in result]
    expected = [name for name, _ in MIGRATIONS]
    assert names == expected


@pytest.mark.asyncio
async def test_idempotent_rerun(session):
    count_1 = await run_migrations(session)
    count_2 = await run_migrations(session)
    assert count_1 == len(MIGRATIONS)
    assert count_2 == 0


@pytest.mark.asyncio
async def test_family_members_table_created(session):
    await run_migrations(session)
    result = await session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='family_members'")
    )
    assert result.scalar() == "family_members"


@pytest.mark.asyncio
async def test_plaid_enrichment_columns_added(session):
    await run_migrations(session)
    result = await session.execute(text("PRAGMA table_info(transactions)"))
    cols = {row[1] for row in result}
    assert "merchant_name" in cols
    assert "payment_channel" in cols
    assert "plaid_pfc_primary" in cols
