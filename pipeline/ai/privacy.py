"""
AI Data Privacy Layer — sanitizes PII before sending to Claude API.

Provides a bidirectional mapping between real PII (names, employers, entities)
and generic labels. Data sent to Claude uses labels; responses are desanitized
back to real values before returning to the user.

Usage:
    sanitizer = PIISanitizer()
    sanitizer.register_household(household, entities)
    safe_prompt = sanitizer.sanitize_text(prompt)
    # ... send safe_prompt to Claude ...
    user_response = sanitizer.desanitize_text(claude_response)
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class PIISanitizer:
    """Bidirectional mapping between real PII and generic labels."""

    def __init__(self):
        self._replacements: list[tuple[str, str]] = []  # (real_value, label) sorted longest-first
        self._reverse: list[tuple[str, str]] = []  # (label, real_value) sorted longest-first

    def register_household(self, household, entities=None) -> None:
        """Load all PII from a HouseholdProfile ORM object into mappings."""
        pairs: list[tuple[str, str]] = []

        if household:
            if household.spouse_a_name:
                pairs.append((household.spouse_a_name, "Primary Earner"))
            if household.spouse_b_name:
                pairs.append((household.spouse_b_name, "Secondary Earner"))
            if household.spouse_a_employer:
                pairs.append((household.spouse_a_employer, "Employer A"))
            if household.spouse_b_employer:
                pairs.append((household.spouse_b_employer, "Employer B"))

        if entities:
            for i, entity in enumerate(entities):
                name = entity.name if hasattr(entity, "name") else entity.get("name", "")
                if name:
                    label = f"Entity {chr(65 + i)}" if i < 26 else f"Entity {i + 1}"
                    pairs.append((name, label))

        # Sort by length descending so longer matches are replaced first
        # (e.g., "John Smith" before "John")
        pairs.sort(key=lambda p: len(p[0]), reverse=True)

        self._replacements = [(real, label) for real, label in pairs if real.strip()]
        self._reverse = [(label, real) for real, label in self._replacements]
        # Sort reverse by length descending too
        self._reverse.sort(key=lambda p: len(p[0]), reverse=True)

    def sanitize_text(self, text: str) -> str:
        """Replace all registered PII with generic labels."""
        for real_value, label in self._replacements:
            text = text.replace(real_value, label)
        return text

    def desanitize_text(self, text: str) -> str:
        """Reverse labels back to real values for user display."""
        for label, real_value in self._reverse:
            text = text.replace(label, real_value)
        return text

    def sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize string values in a dict."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.sanitize_text(value)
            elif isinstance(value, dict):
                result[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.sanitize_dict(item) if isinstance(item, dict)
                    else self.sanitize_text(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    @property
    def has_mappings(self) -> bool:
        return len(self._replacements) > 0


def build_sanitized_household_context(household, sanitizer: PIISanitizer) -> str:
    """Build a household context string with PII replaced by generic labels."""
    import json

    lines: list[str] = []
    if not household:
        return "- No household profile configured"

    filing = (household.filing_status or "unknown").upper()
    lines.append(f"- Filing status: {filing}")
    if household.state:
        lines.append(f"- State: {household.state}")

    if household.spouse_a_name:
        income_a = f"${household.spouse_a_income:,.0f} W-2" if household.spouse_a_income else "no W-2"
        emp_a = f" from {household.spouse_a_employer}" if household.spouse_a_employer else ""
        raw_line = f"- {household.spouse_a_name}: {income_a}{emp_a}"
        lines.append(sanitizer.sanitize_text(raw_line))
    if household.spouse_b_name:
        income_b = f"${household.spouse_b_income:,.0f} W-2" if household.spouse_b_income else "no W-2"
        emp_b = f" from {household.spouse_b_employer}" if household.spouse_b_employer else ""
        raw_line = f"- {household.spouse_b_name}: {income_b}{emp_b}"
        lines.append(sanitizer.sanitize_text(raw_line))

    if household.other_income_sources_json:
        try:
            sources = json.loads(household.other_income_sources_json)
            for src in sources:
                raw_line = f"  - Other income: {src.get('label', 'Unknown')} — ${src.get('amount', 0):,.0f} ({src.get('type', '')})"
                lines.append(sanitizer.sanitize_text(raw_line))
        except (json.JSONDecodeError, TypeError):
            pass

    if household.dependents_json:
        try:
            deps = json.loads(household.dependents_json)
            lines.append(f"- Dependents: {len(deps)}")
        except (json.JSONDecodeError, TypeError):
            pass

    return "\n".join(lines)


def sanitize_entity_list(
    entities,
    sanitizer: PIISanitizer,
    accounts_map: dict[int, list[str]] | None = None,
    rules_map: dict[int, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Return entity dicts with names replaced by labels.

    Optional enrichment maps add assigned account names and vendor patterns
    for richer AI categorization context. These fields are not PII.
    """
    result = []
    for e in entities:
        name = e.name if hasattr(e, "name") else e.get("name", "")
        entity_type = e.entity_type if hasattr(e, "entity_type") else e.get("entity_type", "")
        tax_treatment = e.tax_treatment if hasattr(e, "tax_treatment") else e.get("tax_treatment", "")
        owner = e.owner if hasattr(e, "owner") else e.get("owner", "")
        is_active = e.is_active if hasattr(e, "is_active") else e.get("is_active", True)
        is_provisional = e.is_provisional if hasattr(e, "is_provisional") else e.get("is_provisional", False)

        entry: dict[str, Any] = {
            "name": sanitizer.sanitize_text(name),
            "entity_type": entity_type,
            "tax_treatment": tax_treatment,
            "owner": sanitizer.sanitize_text(owner) if owner else owner,
            "is_active": is_active,
            "is_provisional": is_provisional,
        }

        # Enrichment fields — not PII, pass through as-is
        description = e.description if hasattr(e, "description") else e.get("description")
        expected_expenses = e.expected_expenses if hasattr(e, "expected_expenses") else e.get("expected_expenses")
        if description:
            entry["description"] = description
        if expected_expenses:
            entry["expected_expenses"] = expected_expenses

        eid = e.id if hasattr(e, "id") else e.get("id")
        if accounts_map and eid and eid in accounts_map:
            entry["assigned_accounts"] = accounts_map[eid]
        if rules_map and eid and eid in rules_map:
            entry["vendor_patterns"] = rules_map[eid]

        result.append(entry)
    return result


def log_ai_privacy_audit(action: str, data_categories: list[str], sanitized: bool) -> None:
    """Log what categories of data were sent to AI (not the values)."""
    status = "sanitized" if sanitized else "raw"
    logger.info(f"AI privacy audit: action={action} categories={data_categories} status={status}")
