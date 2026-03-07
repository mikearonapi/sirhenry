"""Error report ingestion — PII-scrubs and stores error logs."""
import json
import logging
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import ErrorLog
from pipeline.security.logging import scrub_pii

logger = logging.getLogger(__name__)

MAX_MESSAGE = 1000
MAX_STACK = 5000
MAX_NOTE = 500
MAX_URL = 500
MAX_UA = 200


def _truncate(text: Optional[str], limit: int) -> Optional[str]:
    if not text:
        return None
    return text[:limit]


async def submit_error_report(
    session: AsyncSession,
    *,
    error_type: str,
    message: Optional[str] = None,
    stack_trace: Optional[str] = None,
    source_url: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_note: Optional[str] = None,
    context: Optional[dict] = None,
) -> ErrorLog:
    """Scrub PII from all fields and persist an error report."""
    entry = ErrorLog(
        error_type=error_type,
        message=_truncate(scrub_pii(message) if message else None, MAX_MESSAGE),
        stack_trace=_truncate(scrub_pii(stack_trace) if stack_trace else None, MAX_STACK),
        source_url=_truncate(source_url, MAX_URL),
        user_agent=_truncate(user_agent, MAX_UA),
        user_note=_truncate(scrub_pii(user_note) if user_note else None, MAX_NOTE),
        context_json=json.dumps(context) if context else None,
    )
    session.add(entry)
    await session.flush()
    return entry


async def get_error_reports(
    session: AsyncSession,
    *,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ErrorLog], int]:
    """Retrieve error reports for admin view, newest first."""
    query = select(ErrorLog).order_by(desc(ErrorLog.timestamp))
    count_query = select(func.count()).select_from(ErrorLog)

    if status:
        query = query.where(ErrorLog.status == status)
        count_query = count_query.where(ErrorLog.status == status)

    total = await session.scalar(count_query) or 0
    result = await session.execute(query.offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def update_error_status(
    session: AsyncSession,
    error_id: int,
    status: str,
) -> Optional[ErrorLog]:
    """Update the status of an error report (new -> acknowledged -> resolved)."""
    result = await session.execute(
        select(ErrorLog).where(ErrorLog.id == error_id)
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry.status = status
        await session.flush()
    return entry
