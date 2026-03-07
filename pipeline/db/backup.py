"""
Automatic database backup for SirHENRY.

Creates timestamped copies of the user's financials.db before risky operations
(startup, demo mode switch) and prunes old backups to save disk space.
"""
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Keep the last N backups per database
MAX_BACKUPS = 5


def _db_path_from_url(database_url: str) -> str | None:
    """Extract the filesystem path from a SQLite database URL."""
    prefix = "sqlite+aiosqlite:///"
    if database_url.startswith(prefix):
        return os.path.abspath(database_url[len(prefix):])
    return None


def _backup_dir(db_path: str) -> Path:
    """Backup directory sits alongside the database file."""
    return Path(db_path).parent / "backups"


def backup_database(database_url: str, reason: str = "startup") -> str | None:
    """
    Create a timestamped backup of the database file.

    Args:
        database_url: SQLite URL (e.g. sqlite+aiosqlite:///path/to/financials.db)
        reason: Short label for the backup (e.g. "startup", "pre-demo-switch")

    Returns:
        Path to the backup file, or None if backup was skipped.
    """
    db_path = _db_path_from_url(database_url)
    if not db_path or not os.path.exists(db_path):
        return None

    # Skip backup if database is tiny (empty / just schema)
    size = os.path.getsize(db_path)
    if size < 100_000:  # < 100KB = no meaningful user data
        logger.debug("Skipping backup — database too small (%d bytes)", size)
        return None

    backup_dir = _backup_dir(db_path)
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_name = Path(db_path).stem  # "financials"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{db_name}_{reason}_{timestamp}.db"
    backup_path = backup_dir / backup_name

    try:
        # Checkpoint WAL to flush all pending writes to the main database file
        # before copying. Without this, the backup may be inconsistent.
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception as e:
            logger.debug("WAL checkpoint skipped: %s", e)

        shutil.copy2(db_path, backup_path)
        logger.info("Database backed up: %s (%d KB)", backup_name, size // 1024)
        _prune_old_backups(backup_dir, db_name)
        return str(backup_path)
    except OSError as e:
        logger.warning("Backup failed: %s", e)
        return None


def _prune_old_backups(backup_dir: Path, db_name: str) -> None:
    """Keep only the most recent MAX_BACKUPS files for a given database."""
    backups = sorted(
        [f for f in backup_dir.glob(f"{db_name}_*.db")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[MAX_BACKUPS:]:
        try:
            old_backup.unlink()
            logger.debug("Pruned old backup: %s", old_backup.name)
        except OSError:
            pass


def list_backups(database_url: str) -> list[dict]:
    """List available backups for a database, newest first."""
    db_path = _db_path_from_url(database_url)
    if not db_path:
        return []

    backup_dir = _backup_dir(db_path)
    if not backup_dir.exists():
        return []

    db_name = Path(db_path).stem
    backups = sorted(
        [f for f in backup_dir.glob(f"{db_name}_*.db")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "filename": b.name,
            "path": str(b),
            "size_kb": b.stat().st_size // 1024,
            "created": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
        }
        for b in backups
    ]


def restore_backup(database_url: str, backup_path: str) -> bool:
    """
    Restore a database from a backup file.

    Creates a backup of the current state first (labeled "pre-restore"),
    then copies the backup file over the current database.
    """
    db_path = _db_path_from_url(database_url)
    if not db_path:
        return False

    if not os.path.exists(backup_path):
        logger.error("Backup file not found: %s", backup_path)
        return False

    # Safety: back up current state before overwriting
    backup_database(database_url, reason="pre-restore")

    try:
        shutil.copy2(backup_path, db_path)
        logger.info("Database restored from: %s", backup_path)
        return True
    except OSError as e:
        logger.error("Restore failed: %s", e)
        return False
