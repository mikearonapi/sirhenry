"""
Secure file deletion and lifecycle management.

Provides utilities for:
- Overwriting file contents before unlinking (secure delete)
- Clearing raw_text from Document records after extraction
- Sweeping old import files past their retention period
"""
import logging
import os
import time
from pathlib import Path
from typing import Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def secure_delete_file(filepath: str) -> bool:
    """Overwrite file contents with zeros before unlinking.

    Returns True if file was successfully deleted, False otherwise.
    """
    try:
        path = Path(filepath)
        if not path.exists():
            return False

        size = path.stat().st_size
        with open(filepath, "wb") as f:
            f.write(b"\x00" * size)
            f.flush()
            os.fsync(f.fileno())
        path.unlink()
        logger.info(f"Securely deleted: {path.name}")
        return True
    except Exception as e:
        logger.warning(f"Secure delete failed for {Path(filepath).name}: {e}")
        # Fall back to normal delete
        try:
            Path(filepath).unlink(missing_ok=True)
            return True
        except Exception:
            return False


async def clear_document_raw_text(session: AsyncSession, document_id: int) -> None:
    """Clear the raw_text field from a Document after data extraction is complete.

    The raw_text stores full OCR content of tax documents (W-2s, 1099s)
    which contains highly sensitive data. After fields are extracted into
    TaxItem records, the raw text is no longer needed.
    """
    from pipeline.db.schema import Document
    await session.execute(
        update(Document).where(Document.id == document_id).values(raw_text=None)
    )
    logger.info(f"Cleared raw_text for document #{document_id}")


def cleanup_old_files(
    directory: str,
    max_age_days: int = 7,
    extensions: Optional[set[str]] = None,
) -> int:
    """Remove files older than max_age_days from a directory.

    Returns the count of deleted files. Uses secure deletion.
    """
    if extensions is None:
        extensions = {".csv", ".pdf", ".jpg", ".jpeg", ".png"}

    dir_path = Path(directory)
    if not dir_path.is_dir():
        return 0

    cutoff = time.time() - (max_age_days * 86400)
    deleted = 0

    for file_path in dir_path.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in extensions:
            continue
        try:
            if file_path.stat().st_mtime < cutoff:
                if secure_delete_file(str(file_path)):
                    deleted += 1
        except Exception as e:
            logger.warning(f"Cleanup error for {file_path.name}: {e}")

    if deleted:
        logger.info(f"Cleaned up {deleted} old files from {dir_path}")
    return deleted
