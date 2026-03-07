"""Error report submission and admin listing routes."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/errors", tags=["errors"])


class ErrorReportIn(BaseModel):
    error_type: str = Field(..., max_length=50)
    message: Optional[str] = Field(None, max_length=2000)
    stack_trace: Optional[str] = Field(None, max_length=10000)
    source_url: Optional[str] = Field(None, max_length=500)
    user_note: Optional[str] = Field(None, max_length=500)
    context: Optional[dict] = None


class ErrorReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: str
    error_type: str
    message: Optional[str] = None
    stack_trace: Optional[str] = None
    source_url: Optional[str] = None
    user_agent: Optional[str] = None
    user_note: Optional[str] = None
    status: str
    context_json: Optional[str] = None


class StatusUpdateIn(BaseModel):
    status: str = Field(..., max_length=20)


@router.post("/report", status_code=201)
async def submit_error(
    body: ErrorReportIn,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Submit an error report from the frontend. PII is scrubbed before storage."""
    from pipeline.security.error_reporting import submit_error_report

    raw_ua = req.headers.get("user-agent", "")
    ua_short = raw_ua[:200] if raw_ua else None

    entry = await submit_error_report(
        session,
        error_type=body.error_type,
        message=body.message,
        stack_trace=body.stack_trace,
        source_url=body.source_url,
        user_agent=ua_short,
        user_note=body.user_note,
        context=body.context,
    )
    return {"id": entry.id, "status": "submitted"}


@router.get("/reports")
async def list_errors(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """List error reports for admin view."""
    from pipeline.security.error_reporting import get_error_reports

    entries, total = await get_error_reports(
        session, status=status, limit=limit, offset=offset,
    )
    return {
        "items": [
            ErrorReportOut(
                id=e.id,
                timestamp=e.timestamp.isoformat() if e.timestamp else "",
                error_type=e.error_type,
                message=e.message,
                stack_trace=e.stack_trace,
                source_url=e.source_url,
                user_agent=e.user_agent,
                user_note=e.user_note,
                status=e.status,
                context_json=e.context_json,
            )
            for e in entries
        ],
        "total": total,
    }


@router.patch("/reports/{error_id}")
async def update_status(
    error_id: int,
    body: StatusUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    """Update error report status (new -> acknowledged -> resolved)."""
    from pipeline.security.error_reporting import update_error_status

    entry = await update_error_status(session, error_id, body.status)
    if not entry:
        raise HTTPException(status_code=404, detail="Error report not found")
    return {"id": entry.id, "status": entry.status}
