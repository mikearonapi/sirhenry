"""
PII-safe logging filter.

Installs a regex-based redaction filter on the root logger that strips
sensitive patterns (SSNs, dollar amounts, EINs, emails) and dynamically-
loaded known names from all log messages.

Usage:
    from pipeline.security.logging import install_pii_filter, update_known_names
    install_pii_filter()  # call once at startup
    update_known_names(["Alice Smith", "Bob Smith"])  # after loading household
"""
import logging
import re
from typing import Sequence

logger = logging.getLogger(__name__)

# Singleton filter instance so we can update known names dynamically
_filter_instance: "PIIRedactionFilter | None" = None


class PIIRedactionFilter(logging.Filter):
    """Logging filter that redacts PII patterns from log messages."""

    # Static patterns — compiled once
    SSN_FULL = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    SSN_LAST4 = re.compile(r"\bssn[_\s]*(?:last[_\s]*4)?[:\s]*\d{4}\b", re.IGNORECASE)
    DOLLAR = re.compile(r"\$[\d,]+\.?\d*")
    EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
    EIN = re.compile(r"\b\d{2}-\d{7}\b")

    def __init__(self, known_names: Sequence[str] | None = None):
        super().__init__()
        self._known_names: list[str] = []
        if known_names:
            self.set_known_names(known_names)

    def set_known_names(self, names: Sequence[str]) -> None:
        """Update the list of known PII names to redact (e.g. household members)."""
        # Filter out short/empty names and deduplicate
        self._known_names = sorted(
            {n.strip() for n in names if n and len(n.strip()) > 2},
            key=len,
            reverse=True,  # longest first to avoid partial matches
        )

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact PII from the log record. Always returns True (never drops records)."""
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True

    def _redact(self, text: str) -> str:
        """Apply all redaction patterns to a string."""
        text = self.SSN_FULL.sub("[SSN]", text)
        text = self.SSN_LAST4.sub("[SSN_LAST4]", text)
        text = self.DOLLAR.sub("[$***]", text)
        text = self.EMAIL.sub("[EMAIL]", text)
        text = self.EIN.sub("[EIN]", text)
        for name in self._known_names:
            text = text.replace(name, "[NAME]")
        return text


def install_pii_filter(known_names: Sequence[str] | None = None) -> PIIRedactionFilter:
    """Install the PII redaction filter on the root logger. Safe to call multiple times."""
    global _filter_instance
    if _filter_instance is not None:
        return _filter_instance
    _filter_instance = PIIRedactionFilter(known_names)
    logging.getLogger().addFilter(_filter_instance)
    logger.info("PII redaction filter installed on root logger")
    return _filter_instance


def update_known_names(names: Sequence[str]) -> None:
    """Update the PII filter with household member names loaded from the database."""
    if _filter_instance is not None:
        _filter_instance.set_known_names(names)
        logger.info(f"PII filter updated with {len(names)} known names")


async def load_known_names_from_db(session) -> list[str]:
    """Query the database for all known person names (household + family members)."""
    from sqlalchemy import select
    from pipeline.db.schema import HouseholdProfile, FamilyMember

    names: list[str] = []

    # Household profile names
    result = await session.execute(select(HouseholdProfile))
    for h in result.scalars().all():
        if h.spouse_a_name:
            names.append(h.spouse_a_name)
        if h.spouse_b_name:
            names.append(h.spouse_b_name)
        if h.spouse_a_employer:
            names.append(h.spouse_a_employer)
        if h.spouse_b_employer:
            names.append(h.spouse_b_employer)

    # Family member names
    result = await session.execute(select(FamilyMember))
    for fm in result.scalars().all():
        if fm.name:
            names.append(fm.name)

    return names
