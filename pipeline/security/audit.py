"""Audit logging utility — records sensitive operations with NO PII in detail fields."""
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db import AuditLog

logger = logging.getLogger(__name__)


async def log_audit(
    session: AsyncSession,
    action_type: str,
    data_category: Optional[str] = None,
    detail: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Write an audit log entry. Detail must NEVER contain PII — only counts and metadata."""
    entry = AuditLog(
        action_type=action_type,
        data_category=data_category,
        detail=detail,
        duration_ms=duration_ms,
    )
    session.add(entry)
    await session.flush()


@asynccontextmanager
async def audit_timer(
    session: AsyncSession,
    action_type: str,
    data_category: Optional[str] = None,
    detail: Optional[str] = None,
):
    """Context manager that times an operation and logs it with duration.

    Usage:
        async with audit_timer(session, "ai_chat", "conversation", "tools_used=3"):
            result = await run_chat(...)
    """
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            await log_audit(session, action_type, data_category, detail, elapsed_ms)
        except Exception as e:
            logger.warning(f"Audit log write failed (non-fatal): {e}")
