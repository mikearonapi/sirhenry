"""Privacy consent, disclosure, and audit log endpoints."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.models.schemas import ConsentIn, ConsentOut, PrivacyDisclosure
from pipeline.db import UserPrivacyConsent, AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/privacy", tags=["privacy"])

VALID_CONSENT_TYPES = {"ai_features", "plaid_sync", "telemetry"}


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

@router.get("/consent", response_model=list[ConsentOut])
async def get_all_consent(session: AsyncSession = Depends(get_session)):
    """Return all consent statuses."""
    result = await session.execute(
        select(UserPrivacyConsent).order_by(UserPrivacyConsent.consent_type)
    )
    return result.scalars().all()


@router.get("/consent/{consent_type}", response_model=ConsentOut)
async def get_consent(
    consent_type: str,
    session: AsyncSession = Depends(get_session),
):
    """Return consent status for a specific type."""
    if consent_type not in VALID_CONSENT_TYPES:
        raise HTTPException(400, f"Invalid consent type. Must be one of: {VALID_CONSENT_TYPES}")
    result = await session.execute(
        select(UserPrivacyConsent).where(UserPrivacyConsent.consent_type == consent_type)
    )
    consent = result.scalar_one_or_none()
    if not consent:
        raise HTTPException(404, f"No consent record for '{consent_type}'")
    return consent


@router.post("/consent", response_model=ConsentOut)
async def set_consent(
    body: ConsentIn,
    session: AsyncSession = Depends(get_session),
):
    """Record or update user consent for a specific type."""
    if body.consent_type not in VALID_CONSENT_TYPES:
        raise HTTPException(400, f"Invalid consent type. Must be one of: {VALID_CONSENT_TYPES}")

    result = await session.execute(
        select(UserPrivacyConsent).where(UserPrivacyConsent.consent_type == body.consent_type)
    )
    consent = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if consent:
        consent.consented = body.consented
        consent.consented_at = now if body.consented else None
        consent.updated_at = now
    else:
        consent = UserPrivacyConsent(
            consent_type=body.consent_type,
            consented=body.consented,
            consented_at=now if body.consented else None,
        )
        session.add(consent)

    await session.flush()

    # Log consent change to audit log
    session.add(AuditLog(
        action_type="consent_change",
        data_category="consent",
        detail=f"type={body.consent_type} consented={body.consented}",
    ))

    logger.info(f"Consent updated: {body.consent_type}={body.consented}")
    return consent


# ---------------------------------------------------------------------------
# Disclosure
# ---------------------------------------------------------------------------

@router.get("/disclosure", response_model=PrivacyDisclosure)
async def get_disclosure():
    """Return the privacy disclosure explaining how user data is handled."""
    return PrivacyDisclosure(
        data_handling=[
            "Your financial data is stored only on your local machine.",
            "SirHENRY (the company) never has access to your financial data.",
            "Your database is encrypted at rest using keys stored locally.",
            "Uploaded documents (W-2s, 1099s) are securely deleted after processing.",
        ],
        ai_privacy=[
            "AI analysis anonymizes your names and employers before sending to Claude.",
            "Only financial amounts and categories are sent — never raw account numbers or SSNs.",
            "Anthropic (Claude's provider) does not train on API data by default.",
            "API request logs are retained for 7 days only, then permanently deleted.",
            "You can disable AI features at any time by revoking consent.",
        ],
        encryption=[
            "Sensitive fields (names, SSNs, employer info) are encrypted with AES-256 at rest.",
            "Plaid access tokens are encrypted with a separate Fernet key.",
            "Encryption keys are stored locally and never transmitted.",
        ],
        data_retention=[
            "Uploaded files are securely deleted within 7 days of processing.",
            "Document raw text is cleared from the database after data extraction.",
            "You can export or delete all your data at any time.",
        ],
    )


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

@router.get("/audit-log")
async def get_audit_log(
    action_type: str | None = Query(None, description="Filter by action type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Return paginated audit log entries. No PII is stored in audit entries."""
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if action_type:
        query = query.where(AuditLog.action_type == action_type)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": str(r.timestamp),
            "action_type": r.action_type,
            "data_category": r.data_category,
            "detail": r.detail,
            "duration_ms": r.duration_ms,
        }
        for r in rows
    ]
