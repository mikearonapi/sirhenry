"""
Category Rules Engine — learns from user overrides and applies rules
to future (and optionally past) transactions.

When a user corrects a transaction's category, we normalize the merchant
name and create a rule. On future categorization, rules are applied
BEFORE sending to Claude, saving API calls and improving accuracy.
"""
import logging
import re
from datetime import datetime

from sqlalchemy import and_, cast, func, or_, select, update, Date
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.db.schema import BusinessEntity, CategoryRule, Transaction

logger = logging.getLogger(__name__)


def normalize_merchant(description: str) -> str:
    """Extract a stable merchant pattern from a transaction description.

    Strips transaction-specific suffixes like store numbers, dates,
    reference codes, and location identifiers.
    """
    if not description:
        return ""
    s = description.strip()
    # Remove common suffixes: store #, date patterns, reference numbers
    s = re.sub(r"\s*#\d+.*$", "", s)
    s = re.sub(r"\s+\d{2}/\d{2}.*$", "", s)
    s = re.sub(r"\s+\d{5,}.*$", "", s)  # long reference numbers
    s = re.sub(r"\s+(on|at|in)\s+\d.*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+[A-Z]{2}\s*$", "", s)  # state abbreviation at end
    s = re.sub(r"\s+\d{1,2}\.\d{2}$", "", s)  # trailing amount
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def _matches_merchant(pattern: str, merchant: str) -> bool:
    """Check if a rule pattern matches a normalized merchant name.

    Match strategy (checked in order):
    1. Exact match — "starbucks" == "starbucks"
    2. Prefix match — "starbucks" matches "starbucks coffee"
    3. Word-boundary match — "starbucks" matches "the starbucks store"

    Does NOT match if the pattern is merely a substring within a word,
    e.g. "at" does NOT match "national" or "starbucks".
    """
    if not pattern or not merchant:
        return False
    if pattern == merchant:
        return True
    if merchant.startswith(pattern + " "):
        return True
    # Word boundary: pattern preceded by space, followed by space or end
    if re.search(r"(?:^|\s)" + re.escape(pattern) + r"(?:\s|$)", merchant):
        return True
    return False


def _sql_merchant_like_filter(pattern: str):
    """Build a SQLAlchemy OR filter that matches a merchant pattern against
    LOWER(Transaction.description) using word-boundary-aware LIKE clauses.

    Mirrors the logic of _matches_merchant() but at the SQL level:
    - Pattern at start of description, followed by non-alpha or end
    - Pattern preceded by non-alpha character, followed by non-alpha or end

    Escape any LIKE wildcards in the pattern itself to avoid injection.
    SQLite LIKE is case-insensitive by default for ASCII, so we use
    func.lower() for safety with mixed-case data.
    """
    # Escape LIKE wildcards that might be in the pattern
    safe = pattern.replace("%", r"\%").replace("_", r"\_")
    desc_lower = func.lower(Transaction.description)
    return or_(
        # Pattern at start, followed by space or non-alpha char, or exact match
        desc_lower.like(safe + "%", escape="\\"),
        # Pattern after a space (word boundary)
        desc_lower.like("% " + safe + "%", escape="\\"),
    )


def _sort_rules_by_specificity(rules: list[CategoryRule]) -> list[CategoryRule]:
    """Sort rules so longer (more specific) patterns are checked first."""
    return sorted(rules, key=lambda r: len(r.merchant_pattern), reverse=True)


def _apply_rule_to_transaction(txn: Transaction, rule: CategoryRule) -> None:
    """Apply all fields from a rule to a transaction. Shared by apply_rules
    and apply_rule_retroactively to ensure consistent behavior."""
    if rule.category:
        txn.effective_category = rule.category
        txn.category = rule.category
    if rule.tax_category:
        txn.effective_tax_category = rule.tax_category
        txn.tax_category = rule.tax_category
    if rule.segment:
        txn.effective_segment = rule.segment
        txn.segment = rule.segment
    if rule.business_entity_id:
        txn.effective_business_entity_id = rule.business_entity_id
        txn.business_entity_id = rule.business_entity_id
    txn.ai_confidence = 0.95  # High confidence from user rule


def _txn_date(txn: Transaction):
    """Extract a date object from a transaction."""
    return txn.date.date() if hasattr(txn.date, "date") and callable(txn.date.date) else txn.date


def _rule_matches_date(rule: CategoryRule, txn_date) -> bool:
    """Check if a rule's date range allows this transaction date."""
    if rule.effective_from and txn_date < rule.effective_from:
        return False
    if rule.effective_to and txn_date > rule.effective_to:
        return False
    return True


async def learn_from_override(
    session: AsyncSession,
    transaction_id: int,
    new_category: str | None = None,
    new_tax_category: str | None = None,
    new_segment: str | None = None,
    new_business_entity_id: int | None = None,
) -> dict:
    """Create or update a category rule from a user override.

    Automatically applies the rule to all matching uncategorized transactions.
    Returns info about the rule and count of transactions auto-categorized.
    """
    # Get the transaction
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return {"rule_created": False, "error": "Transaction not found"}

    merchant = normalize_merchant(txn.description)
    if not merchant or len(merchant) < 3:
        return {"rule_created": False, "similar_count": 0, "merchant": ""}

    # Check for existing rule
    existing = await session.execute(
        select(CategoryRule).where(CategoryRule.merchant_pattern == merchant)
    )
    rule = existing.scalar_one_or_none()

    if rule:
        # Update existing rule
        if new_category:
            rule.category = new_category
        if new_tax_category:
            rule.tax_category = new_tax_category
        if new_segment:
            rule.segment = new_segment
        if new_business_entity_id is not None:
            rule.business_entity_id = new_business_entity_id
        rule.match_count = (rule.match_count or 0) + 1
        rule.is_active = True  # Re-activate if it was deactivated
    else:
        # Create new rule
        rule = CategoryRule(
            merchant_pattern=merchant,
            category=new_category,
            tax_category=new_tax_category,
            segment=new_segment,
            business_entity_id=new_business_entity_id,
            source="user_override",
            match_count=1,
        )
        session.add(rule)

    await session.flush()

    # Auto-apply rule to all matching uncategorized transactions
    apply_result = await apply_rule_retroactively(session, rule.id)
    applied_count = apply_result.get("applied", 0)

    return {
        "rule_created": True,
        "rule_id": rule.id,
        "merchant": merchant,
        "similar_count": applied_count,
        "applied_count": applied_count,
        "category": new_category,
    }


async def apply_rules(session: AsyncSession, transaction_ids: list[int] | None = None) -> dict:
    """Apply all active category rules to uncategorized transactions.

    Call this BEFORE Claude categorization to handle known merchants cheaply.
    Rules are sorted by pattern length (longest first) so more specific
    patterns take priority over shorter, broader ones.

    Uses SQL-level LIKE matching for each rule, issuing one UPDATE per rule
    instead of loading all transactions into Python.
    """
    # Load all active rules, sorted by specificity (longest pattern first)
    result = await session.execute(
        select(CategoryRule).where(CategoryRule.is_active.is_(True))
    )
    rules = _sort_rules_by_specificity(list(result.scalars()))
    if not rules:
        return {"applied": 0}

    applied = 0
    for rule in rules:
        if not rule.merchant_pattern:
            continue

        # Base filter: uncategorized, not manually reviewed, not excluded
        conditions = [
            Transaction.effective_category.is_(None),
            Transaction.is_manually_reviewed.is_(False),
            Transaction.is_excluded.is_(False),
        ]
        if transaction_ids:
            conditions.append(Transaction.id.in_(transaction_ids))

        # Merchant LIKE matching at SQL level
        conditions.append(_sql_merchant_like_filter(rule.merchant_pattern))

        # Date range filter
        if rule.effective_from:
            conditions.append(
                cast(Transaction.date, Date) >= rule.effective_from
            )
        if rule.effective_to:
            conditions.append(
                cast(Transaction.date, Date) <= rule.effective_to
            )

        # Build UPDATE values from the rule
        values: dict = {"ai_confidence": 0.95}
        if rule.category:
            values["effective_category"] = rule.category
            values["category"] = rule.category
        if rule.tax_category:
            values["effective_tax_category"] = rule.tax_category
            values["tax_category"] = rule.tax_category
        if rule.segment:
            values["effective_segment"] = rule.segment
            values["segment"] = rule.segment
        if rule.business_entity_id:
            values["effective_business_entity_id"] = rule.business_entity_id
            values["business_entity_id"] = rule.business_entity_id

        stmt = update(Transaction).where(and_(*conditions)).values(**values)
        result_update = await session.execute(stmt)
        matched = result_update.rowcount

        if matched > 0:
            rule.match_count = (rule.match_count or 0) + matched
            applied += matched

    return {"applied": applied, "rules_checked": len(rules)}


async def apply_rule_retroactively(session: AsyncSession, rule_id: int) -> dict:
    """Apply a specific rule to all matching past transactions.

    Uses a single SQL UPDATE with LIKE matching instead of loading all
    transactions into Python.
    """
    result = await session.execute(
        select(CategoryRule).where(CategoryRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return {"applied": 0, "error": "Rule not found"}

    if not rule.merchant_pattern:
        return {"applied": 0, "rule_id": rule_id, "merchant": ""}

    # Build SQL conditions
    conditions = [
        Transaction.is_excluded.is_(False),
        Transaction.is_manually_reviewed.is_(False),
        _sql_merchant_like_filter(rule.merchant_pattern),
    ]

    # Date range filter
    if rule.effective_from:
        conditions.append(
            cast(Transaction.date, Date) >= rule.effective_from
        )
    if rule.effective_to:
        conditions.append(
            cast(Transaction.date, Date) <= rule.effective_to
        )

    # Build UPDATE values from the rule
    values: dict = {"ai_confidence": 0.95}
    if rule.category:
        values["effective_category"] = rule.category
        values["category"] = rule.category
    if rule.tax_category:
        values["effective_tax_category"] = rule.tax_category
        values["tax_category"] = rule.tax_category
    if rule.segment:
        values["effective_segment"] = rule.segment
        values["segment"] = rule.segment
    if rule.business_entity_id:
        values["effective_business_entity_id"] = rule.business_entity_id
        values["business_entity_id"] = rule.business_entity_id

    stmt = update(Transaction).where(and_(*conditions)).values(**values)
    result_update = await session.execute(stmt)
    applied = result_update.rowcount

    rule.match_count = (rule.match_count or 0) + applied

    return {"applied": applied, "rule_id": rule_id, "merchant": rule.merchant_pattern}


async def update_rule(session: AsyncSession, rule_id: int, data: dict) -> dict:
    """Update a category rule's fields."""
    result = await session.execute(
        select(CategoryRule).where(CategoryRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return {"error": "Rule not found"}

    changes = []
    for field in ("category", "tax_category", "segment", "business_entity_id", "is_active", "effective_from", "effective_to"):
        if field in data:
            setattr(rule, field, data[field])
            changes.append(field)

    return {
        "success": True,
        "rule_id": rule.id,
        "changes": changes,
    }


async def deactivate_rule(session: AsyncSession, rule_id: int) -> dict:
    """Soft-delete a category rule."""
    result = await session.execute(
        select(CategoryRule).where(CategoryRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return {"error": "Rule not found"}

    rule.is_active = False
    return {"success": True, "rule_id": rule.id}


async def list_rules(session: AsyncSession) -> list[dict]:
    """List all category rules."""
    result = await session.execute(
        select(CategoryRule).order_by(CategoryRule.match_count.desc())
    )
    return [
        {
            "id": r.id,
            "merchant_pattern": r.merchant_pattern,
            "category": r.category,
            "tax_category": r.tax_category,
            "segment": r.segment,
            "business_entity_id": r.business_entity_id,
            "match_count": r.match_count,
            "is_active": r.is_active,
            "source": r.source,
            "effective_from": str(r.effective_from) if r.effective_from else None,
            "effective_to": str(r.effective_to) if r.effective_to else None,
        }
        for r in result.scalars()
    ]
